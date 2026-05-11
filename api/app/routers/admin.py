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
    """Get current scoring weights including last update metadata."""
    try:
        row = (
            supabase.table("system_config")
            .select("value, updated_at, updated_by")
            .eq("key", "scoring_weights")
            .eq("tenant_id", settings.DEFAULT_TENANT_ID)
            .execute()
        )
        if row.data:
            r = row.data[0]
            # Check if last update came from regulatory intelligence
            source = "manual"
            if r.get("updated_at"):
                reg = (
                    supabase.table("regulatory_documents")
                    .select("doc_ref, title, applied_at")
                    .eq("tenant_id", settings.DEFAULT_TENANT_ID)
                    .eq("status", "applied")
                    .order("applied_at", desc=True)
                    .limit(1)
                    .execute()
                    .data
                )
                if reg and reg[0].get("applied_at"):
                    source = f"regulatory: {reg[0].get('doc_ref', reg[0].get('title',''))[:50]}"
            return {
                "weights":    r["value"],
                "updated_at": r.get("updated_at"),
                "source":     source,
            }
    except Exception:
        pass
    return {"weights": settings.SCORING_WEIGHTS, "updated_at": None, "source": "default"}


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



@router.patch("/counterparties/{counterparty_id}")
async def update_counterparty(
    counterparty_id: str,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update counterparty metadata (display_name, entity_type, jurisdiction, regulator)."""
    allowed = {"display_name","legal_name","entity_type","jurisdiction",
               "regulator","license_number","website","notes"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    existing = supabase.table("counterparties").select("counterparty_id,display_name")         .eq("counterparty_id", counterparty_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    supabase.table("counterparties").update(update)         .eq("counterparty_id", counterparty_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type":     "counterparty.updated",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "resource_type":  "counterparties",
        "resource_id":    counterparty_id,
        "metadata":       {"fields_updated": list(update.keys())},
    }).execute()

    return {"status": "updated", "counterparty_id": counterparty_id}


@router.delete("/counterparties/{counterparty_id}")
async def delete_counterparty(
    counterparty_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a counterparty (sets is_active=False)."""
    existing = supabase.table("counterparties")         .select("counterparty_id,display_name,slug")         .eq("counterparty_id", counterparty_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    cp = existing.data[0]

    # Soft delete — preserve data, just deactivate
    supabase.table("counterparties").update({"is_active": False})         .eq("counterparty_id", counterparty_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type":     "counterparty.deleted",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "resource_type":  "counterparties",
        "resource_id":    counterparty_id,
        "metadata":       {"slug": cp["slug"], "display_name": cp["display_name"]},
    }).execute()

    return {"status": "deleted", "counterparty_id": counterparty_id}

@router.post("/research/batch")
async def batch_research(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Trigger AI research for ALL counterparties that haven't been researched yet.
    Runs sequentially in background to avoid rate limits.
    Returns immediately — poll /api/v1/admin/research/status for progress.
    """
    cps = (
        supabase.table("counterparties")
        .select("counterparty_id, display_name, research_status")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    )

    # Queue all that aren't already running or complete
    to_research = [
        cp for cp in cps
        if cp.get("research_status") not in ("complete", "running")
    ]

    # If everything is done or errored, allow full retry of errors
    if not to_research:
        to_research = [cp for cp in cps if cp.get("research_status") == "error"]

    from app.agents.research_agent import run_research_agent
    from app.workers.tasks import run_in_thread

    def run_batch(counterparty_ids: list):
        """Run sequentially with delay to respect API rate limits."""
        import time
        for cp_id in counterparty_ids:
            try:
                run_research_agent(cp_id)
                time.sleep(15)  # 15s between each — respects 30k token/min limit
            except Exception as e:
                print(f"[batch_research] Error on {cp_id}: {e}")

    ids = [cp["counterparty_id"] for cp in to_research]
    run_in_thread(run_batch, ids)

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "AGENT",
        "event_type":     "counterparty.batch_research_started",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "metadata":       {"total": len(ids), "entity_names": [cp["display_name"] for cp in to_research]},
    }).execute()

    return {
        "status":   "started",
        "queued":   len(ids),
        "skipped":  len(cps) - len(ids),
        "message":  f"Researching {len(ids)} counterparties sequentially. Takes ~{len(ids)*2} minutes total (Haiku model, 15s between each).",
        "entities": [cp["display_name"] for cp in to_research],
    }


@router.get("/research/status")
async def batch_research_status(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get research completion status across all counterparties."""
    cps = (
        supabase.table("counterparties")
        .select("counterparty_id, display_name, entity_type, research_status, last_researched_at, current_risk_tier, enrichment_data")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    )

    summary = {
        "complete": [],
        "running":  [],
        "error":    [],
        "none":     [],
    }

    for cp in cps:
        status = cp.get("research_status") or "none"
        enrichment_count = len([v for v in (cp.get("enrichment_data") or {}).values() if v is not None])
        summary[status if status in summary else "none"].append({
            "name":             cp["display_name"],
            "entity_type":      cp["entity_type"],
            "risk_tier":        cp.get("current_risk_tier"),
            "enrichment_fields": enrichment_count,
            "last_researched":  cp.get("last_researched_at"),
        })

    return {
        "total":          len(cps),
        "complete":       len(summary["complete"]),
        "running":        len(summary["running"]),
        "error":          len(summary["error"]),
        "not_started":    len(summary["none"]),
        "pct_complete":   round(len(summary["complete"]) / len(cps) * 100) if cps else 0,
        "breakdown":      summary,
    }


@router.post("/research/apply-all")
async def batch_apply_research(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Apply ALL research findings to enrichment data for ALL counterparties
    that have completed research. Scores sequentially (not parallel) to
    avoid overwhelming Supabase connections.
    """
    from app.agents.research_agent import extract_enrichment_from_research
    from app.workers.scoring import score_all_counterparties
    from app.workers.tasks import run_in_thread

    cps = (
        supabase.table("counterparties")
        .select("counterparty_id, display_name, research_data, enrichment_data")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("research_status", "complete")
        .execute()
        .data
    )

    applied  = []
    skipped  = []
    errors   = []

    for cp in cps:
        if not cp.get("research_data"):
            skipped.append(cp["display_name"])
            continue
        try:
            new_enrichment = extract_enrichment_from_research(cp["research_data"])
            if not new_enrichment:
                skipped.append(cp["display_name"])
                continue

            existing = cp.get("enrichment_data") or {}
            merged   = {**existing, **new_enrichment}

            supabase.table("counterparties").update({
                "enrichment_data":  merged,
                "last_enriched_at": datetime.utcnow().isoformat(),
                "last_enriched_by": current_user.user_id,
            }).eq("counterparty_id", cp["counterparty_id"]).execute()

            applied.append(cp["display_name"])
            print(f"[apply_all] Applied {len(new_enrichment)} fields to {cp['display_name']}")

        except Exception as e:
            errors.append(cp["display_name"])
            print(f"[apply_all] Error on {cp['display_name']}: {e}")

    # Single sequential rescore of ALL counterparties (safer than 40 parallel threads)
    if applied:
        run_in_thread(score_all_counterparties)

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "HUMAN_REVIEW",
        "event_type":     "counterparty.batch_apply_research",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "metadata": {
            "applied_count": len(applied),
            "skipped_count": len(skipped),
            "error_count":   len(errors),
            "applied":       applied,
            "skipped":       skipped,
            "errors":        errors,
        },
    }).execute()

    return {
        "status":          "applied",
        "applied":         len(applied),
        "skipped":         len(skipped),
        "errors":          len(errors),
        "rescore_queued":  True,
        "message":         f"Applied to {len(applied)} counterparties — full rescore running in background (~60s)",
    }
