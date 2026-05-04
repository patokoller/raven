"""
Raven — Admin Router
Weight management and system configuration.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict
from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings
from datetime import datetime

router = APIRouter()


class WeightsUpdate(BaseModel):
    weights: Dict[str, float]
    rescore: bool = False


@router.get("/weights")
async def get_weights(current_user: CurrentUser = Depends(get_current_user)):
    """Get current scoring weights."""
    # Try to load from DB config table, fall back to settings
    try:
        row = (
            supabase.table("system_config")
            .select("value")
            .eq("key", "scoring_weights")
            .eq("tenant_id", settings.DEFAULT_TENANT_ID)
            .execute()
        )
        if row.data:
            return {"weights": row.data[0]["value"]}
    except Exception:
        pass
    return {"weights": settings.SCORING_WEIGHTS}


@router.post("/weights")
async def save_weights(
    body: WeightsUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Save scoring weights. Optionally trigger full rescore."""
    total = sum(body.weights.values())
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0 (got {total:.3f})")

    # Upsert into system_config (best-effort — table may not exist yet)
    try:
        supabase.table("system_config").upsert({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "key":       "scoring_weights",
            "value":     body.weights,
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": current_user.user_id,
        }, on_conflict="tenant_id,key").execute()
    except Exception as e:
        print(f"[admin] Could not persist weights to DB: {e}")

    # Update in-memory settings regardless
    settings.SCORING_WEIGHTS.update(body.weights)

    # Audit log
    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "CONFIG_CHANGE",
        "event_type":     "weights.updated",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "after_state":    body.weights,
        "metadata":       {"rescore_triggered": body.rescore},
    }).execute()

    if body.rescore:
        from app.workers.scoring import score_all_counterparties
        from app.workers.tasks import run_in_thread
        run_in_thread(score_all_counterparties)

    return {"status": "saved", "weights": body.weights, "rescore_queued": body.rescore}


@router.post("/counterparties")
async def add_counterparty(
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Add a new counterparty to the registry."""
    required = ["slug", "display_name", "entity_type"]
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Check slug uniqueness
    existing = (
        supabase.table("counterparties")
        .select("slug")
        .eq("slug", body["slug"])
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail=f"Slug '{body['slug']}' already exists")

    cp = supabase.table("counterparties").insert({
        "tenant_id":    settings.DEFAULT_TENANT_ID,
        "slug":         body["slug"],
        "display_name": body["display_name"],
        "legal_name":   body.get("legal_name"),
        "entity_type":  body["entity_type"],
        "jurisdiction": body.get("jurisdiction"),
        "regulator":    body.get("regulator"),
        "license_number": body.get("license_number"),
        "website":      body.get("website"),
        "notes":        body.get("notes"),
        "external_ids": body.get("external_ids", {}),
    }).execute()

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type":     "counterparty.created",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "resource_type":  "counterparties",
        "resource_id":    cp.data[0]["counterparty_id"],
        "metadata":       {"slug": body["slug"], "display_name": body["display_name"]},
    }).execute()

    return {"status": "created", "counterparty": cp.data[0]}
