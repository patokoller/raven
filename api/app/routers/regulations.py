"""Raven — Regulatory Intelligence Router"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()


class AddDocumentRequest(BaseModel):
    url: str
    title: Optional[str] = None


@router.get("")
async def list_documents(
    status: Optional[str] = None,
    criticality: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all regulatory documents, newest first."""
    try:
        q = (
            supabase.table("regulatory_documents")
            .select("doc_id, source, regulator, doc_type, doc_ref, title, url, "
                    "published_date, status, criticality, affected_entity_types, "
                    "affected_counterparties, summary, created_at, applied_at")
            .eq("tenant_id", settings.DEFAULT_TENANT_ID)
            .order("created_at", desc=True)
        )
        if status:
            q = q.eq("status", status)
        if criticality:
            q = q.eq("criticality", criticality)
        return q.limit(50).execute().data or []
    except Exception as e:
        print(f"[regulations] list error: {e}")
        return []


@router.get("/stats")
async def get_stats(current_user: CurrentUser = Depends(get_current_user)):
    """Summary stats for the regulatory intelligence panel."""
    try:
        docs = (
            supabase.table("regulatory_documents")
            .select("status, criticality")
            .eq("tenant_id", settings.DEFAULT_TENANT_ID)
            .execute()
            .data
        ) or []
        return {
            "total":    len(docs),
            "new":      sum(1 for d in docs if d["status"] == "new"),
            "analysed": sum(1 for d in docs if d["status"] in ("analysed", "reviewed")),
            "applied":  sum(1 for d in docs if d["status"] == "applied"),
            "critical": sum(1 for d in docs if d["criticality"] == "CRITICAL"),
            "high":     sum(1 for d in docs if d["criticality"] == "HIGH"),
        }
    except Exception as e:
        print(f"[regulations] stats error: {e}")
        return {"total": 0, "new": 0, "analysed": 0, "applied": 0, "critical": 0, "high": 0}


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get full document detail including complete analysis."""
    doc = (
        supabase.table("regulatory_documents")
        .select("*")
        .eq("doc_id", doc_id)
        .single()
        .execute()
        .data
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/add")
async def add_document(
    body: AddDocumentRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Manually add a regulatory document URL for analysis."""
    from app.services.regulatory_monitor import add_manual_document
    result = add_manual_document(body.url, body.title)

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "AGENT",
        "event_type":     "regulatory.document_added",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "metadata":       {"url": body.url, "title": body.title},
    }).execute()

    return result


@router.post("/monitor/run")
async def run_monitor(current_user: CurrentUser = Depends(get_current_user)):
    """Manually trigger a regulatory monitoring run across all sources."""
    from app.services.regulatory_monitor import run_monitor
    from app.workers.tasks import run_in_thread
    run_in_thread(run_monitor)
    return {"status": "started", "message": "Monitoring run started — check back in 2-3 minutes"}


@router.post("/{doc_id}/reanalyse")
async def reanalyse(
    doc_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Re-run analysis on a document."""
    from app.services.regulatory_analysis import analyse_document
    from app.workers.tasks import run_in_thread
    run_in_thread(analyse_document, doc_id)
    return {"status": "started", "doc_id": doc_id}


@router.post("/{doc_id}/apply-weights")
async def apply_weights(
    doc_id: str,
    entity_type: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Apply the weight recommendations from this document's analysis."""
    from app.services.regulatory_analysis import apply_weight_recommendations
    result = apply_weight_recommendations(doc_id, entity_type)

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "CONFIG_CHANGE",
        "event_type":     "regulatory.weights_applied",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "metadata":       {"doc_id": doc_id, "result": result},
    }).execute()

    return result


@router.patch("/{doc_id}/status")
async def update_status(
    doc_id: str,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update document status (reviewed, dismissed, etc.)"""
    allowed = ("reviewed", "dismissed", "applied")
    new_status = body.get("status")
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {allowed}")

    supabase.table("regulatory_documents").update({
        "status":      new_status,
        "reviewed_by": current_user.user_id,
        "reviewed_at": datetime.utcnow().isoformat(),
        "analyst_notes": body.get("notes"),
        "updated_at":  datetime.utcnow().isoformat(),
    }).eq("doc_id", doc_id).execute()

    return {"status": "updated", "doc_id": doc_id, "new_status": new_status}
