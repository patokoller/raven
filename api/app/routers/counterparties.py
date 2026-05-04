"""
Raven — Counterparties Router
GET  /api/v1/counterparties           — list with scores
GET  /api/v1/counterparties/{id}      — entity detail
GET  /api/v1/counterparties/{id}/scores — score history
POST /api/v1/counterparties/{id}/override — manual override
POST /api/v1/counterparties/{id}/data     — manual data input
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


# ── Pydantic schemas ──────────────────────────────────────────

class CounterpartyListItem(BaseModel):
    counterparty_id: UUID
    slug: str
    display_name: str
    entity_type: str
    jurisdiction: Optional[str]
    regulator: Optional[str]
    current_risk_tier: Optional[str]
    composite_score: Optional[float]
    score_delta_7d: Optional[float]
    score_delta_30d: Optional[float]
    scored_at: Optional[datetime]
    is_active: bool


class ScoreOverrideRequest(BaseModel):
    dimension: str          # "regulatory", "financial", "operational", "liquidity", "onchain", "reputation"
    new_value: float
    rationale: str          # Required — logged to audit trail


class ManualDataInput(BaseModel):
    data_type: str          # "por_update", "news_event", "regulatory_change", "financial_update"
    data: dict
    notes: Optional[str]


# ── Endpoints ─────────────────────────────────────────────────

@router.get("", response_model=List[CounterpartyListItem])
async def list_counterparties(
    entity_type: Optional[str] = Query(None),
    risk_tier: Optional[str] = Query(None),
    is_active: bool = Query(True),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List all counterparties with their latest scores.
    Supports filtering by type and risk tier.
    """
    query = (
        supabase.table("counterparties")
        .select("""
            counterparty_id, slug, display_name, entity_type,
            jurisdiction, regulator, current_risk_tier, is_active,
            counterparty_scores!latest_score_id(
                composite_score, score_delta_7d, score_delta_30d, scored_at
            )
        """)
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", is_active)
    )

    if entity_type:
        query = query.eq("entity_type", entity_type)
    if risk_tier:
        query = query.eq("current_risk_tier", risk_tier)

    result = query.order("display_name").execute()

    # Flatten the join
    items = []
    for row in result.data:
        score = row.get("counterparty_scores") or {}
        items.append(CounterpartyListItem(
            counterparty_id=row["counterparty_id"],
            slug=row["slug"],
            display_name=row["display_name"],
            entity_type=row["entity_type"],
            jurisdiction=row.get("jurisdiction"),
            regulator=row.get("regulator"),
            current_risk_tier=row.get("current_risk_tier"),
            composite_score=score.get("composite_score") if score else None,
            score_delta_7d=score.get("score_delta_7d") if score else None,
            score_delta_30d=score.get("score_delta_30d") if score else None,
            scored_at=score.get("scored_at") if score else None,
            is_active=row["is_active"],
        ))

    return items


@router.get("/{counterparty_id}")
async def get_counterparty(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Full counterparty detail including score breakdown."""
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

    # Get latest score with full dimension breakdown
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
    """Score history for trend charts. Returns composite + 6 dimensions."""
    from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

    result = (
        supabase.table("counterparty_scores")
        .select("""
            score_id, scored_at, composite_score, risk_tier,
            regulatory_score, financial_score, operational_score,
            liquidity_score, onchain_score, reputation_score,
            score_delta_7d, score_delta_30d, is_overridden
        """)
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
    """
    Analyst override of a dimension score.
    Triggers score recalculation and logs to audit trail.
    FINMA requirement: all overrides documented with rationale.
    """
    valid_dimensions = ["regulatory", "financial", "operational", "liquidity", "onchain", "reputation"]
    if body.dimension not in valid_dimensions:
        raise HTTPException(status_code=400, detail=f"Invalid dimension. Must be one of: {valid_dimensions}")

    if not 0 <= body.new_value <= 100:
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100")

    # Get current score
    cp = (
        supabase.table("counterparties")
        .select("latest_score_id, display_name")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )

    if not cp.data or not cp.data.get("latest_score_id"):
        raise HTTPException(status_code=404, detail="No score exists for this counterparty")

    score_id = cp.data["latest_score_id"]
    current_score = (
        supabase.table("counterparty_scores")
        .select(f"{body.dimension}_score, composite_score")
        .eq("score_id", score_id)
        .single()
        .execute()
    )

    original_value = current_score.data.get(f"{body.dimension}_score", 0)

    # Log override
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

    # Update score record
    supabase.table("counterparty_scores").update({
        f"{body.dimension}_score": body.new_value,
        "is_overridden": True,
        "override_by": current_user.user_id,
        "override_rationale": body.rationale,
        "override_at": datetime.utcnow().isoformat(),
    }).eq("score_id", score_id).execute()

    # Write audit log
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
        "metadata": {
            "counterparty_id": str(counterparty_id),
            "counterparty_name": cp.data["display_name"],
            "rationale": body.rationale,
        }
    }).execute()

    # Trigger async score recalculation
    from app.workers.scoring import recalculate_score_task
    recalculate_score_task.delay(str(counterparty_id))

    return {
        "status": "override_applied",
        "counterparty_id": counterparty_id,
        "dimension": body.dimension,
        "original_value": original_value,
        "new_value": body.new_value,
        "recalculation_queued": True,
    }
