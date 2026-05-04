"""
Raven — Counterparties Router
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.database import supabase
from app.core.config import settings
from app.core.auth import get_current_user, CurrentUser

router = APIRouter()


class ScoreOverrideRequest(BaseModel):
    dimension: str
    new_value: float
    rationale: str


@router.get("")
async def list_counterparties(
    entity_type: Optional[str] = Query(None),
    risk_tier: Optional[str] = Query(None),
    is_active: bool = Query(True),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all counterparties with their latest scores."""

    # Simple query — no complex joins that can fail
    q = (
        supabase.table("counterparties")
        .select("*")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", is_active)
    )
    if entity_type:
        q = q.eq("entity_type", entity_type)
    if risk_tier:
        q = q.eq("current_risk_tier", risk_tier)

    cps = q.order("display_name").execute().data

    # Fetch latest scores separately for counterparties that have them
    scored_ids = [cp["counterparty_id"] for cp in cps if cp.get("latest_score_id")]
    scores_by_cp = {}

    if scored_ids:
        score_ids = [cp["latest_score_id"] for cp in cps if cp.get("latest_score_id")]
        scores = (
            supabase.table("counterparty_scores")
            .select("score_id, counterparty_id, composite_score, score_delta_7d, score_delta_30d, scored_at")
            .in_("score_id", score_ids)
            .execute()
            .data
        )
        scores_by_cp = {s["score_id"]: s for s in scores}

    # Merge
    result = []
    for cp in cps:
        score = scores_by_cp.get(cp.get("latest_score_id"), {})
        result.append({
            "counterparty_id": cp["counterparty_id"],
            "slug": cp["slug"],
            "display_name": cp["display_name"],
            "entity_type": cp["entity_type"],
            "jurisdiction": cp.get("jurisdiction"),
            "regulator": cp.get("regulator"),
            "current_risk_tier": cp.get("current_risk_tier"),
            "is_active": cp["is_active"],
            "composite_score": score.get("composite_score"),
            "score_delta_7d": score.get("score_delta_7d"),
            "score_delta_30d": score.get("score_delta_30d"),
            "scored_at": score.get("scored_at"),
        })

    return result


@router.get("/{counterparty_id}")
async def get_counterparty(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    cp = (
        supabase.table("counterparties")
        .select("*")
        .eq("counterparty_id", str(counterparty_id))
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .single()
        .execute()
    )
    if not cp.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    if cp.data.get("latest_score_id"):
        score = (
            supabase.table("counterparty_scores")
            .select("*")
            .eq("score_id", cp.data["latest_score_id"])
            .single()
            .execute()
        )
        cp.data["latest_score"] = score.data

    return cp.data


@router.get("/{counterparty_id}/scores")
async def get_score_history(
    counterparty_id: UUID,
    days: int = Query(90, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
):
    from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = (
        supabase.table("counterparty_scores")
        .select("score_id, scored_at, composite_score, risk_tier, regulatory_score, financial_score, operational_score, liquidity_score, onchain_score, reputation_score, score_delta_7d, score_delta_30d, is_overridden")
        .eq("counterparty_id", str(counterparty_id))
        .gte("scored_at", from_date)
        .order("scored_at", desc=False)
        .execute()
    )
    return {"counterparty_id": counterparty_id, "scores": result.data, "days": days}


@router.post("/{counterparty_id}/override")
async def override_score(
    counterparty_id: UUID,
    body: ScoreOverrideRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    valid_dimensions = ["regulatory", "financial", "operational", "liquidity", "onchain", "reputation"]
    if body.dimension not in valid_dimensions:
        raise HTTPException(status_code=400, detail=f"Dimension must be one of: {valid_dimensions}")
    if not 0 <= body.new_value <= 100:
        raise HTTPException(status_code=400, detail="Score must be 0–100")

    cp = (
        supabase.table("counterparties")
        .select("latest_score_id, display_name")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data or not cp.data.get("latest_score_id"):
        raise HTTPException(status_code=404, detail="No score exists yet for this counterparty")

    score_id = cp.data["latest_score_id"]
    current_score = (
        supabase.table("counterparty_scores")
        .select(f"{body.dimension}_score")
        .eq("score_id", score_id)
        .single()
        .execute()
    )
    original_value = current_score.data.get(f"{body.dimension}_score", 0)

    supabase.table("score_overrides").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "score_id": score_id,
        "counterparty_id": str(counterparty_id),
        "user_id": current_user.user_id,
        "dimension": body.dimension,
        "original_value": original_value,
        "override_value": body.new_value,
        "rationale": body.rationale,
    }).execute()

    supabase.table("counterparty_scores").update({
        f"{body.dimension}_score": body.new_value,
        "is_overridden": True,
        "override_by": current_user.user_id,
        "override_rationale": body.rationale,
        "override_at": datetime.utcnow().isoformat(),
    }).eq("score_id", score_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "HUMAN_REVIEW",
        "event_type": "score.overridden",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "counterparty_scores",
        "resource_id": score_id,
        "before_state": {body.dimension: original_value},
        "after_state": {body.dimension: body.new_value},
        "metadata": {"counterparty_id": str(counterparty_id), "rationale": body.rationale},
    }).execute()

    from app.workers.scoring import score_single_counterparty
    from app.workers.tasks import run_in_thread
    run_in_thread(score_single_counterparty, str(counterparty_id))

    return {"status": "override_applied", "dimension": body.dimension, "new_value": body.new_value}
