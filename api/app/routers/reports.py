"""Raven — Reports Router"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.core.auth import get_current_user, require_senior_analyst, CurrentUser
from app.core.database import supabase
from app.core.config import settings
from app.workers.report_pipeline import generate_report
import uuid

router = APIRouter()


class GenerateRequest(BaseModel):
    portfolio_id: str
    client_id: str
    report_period: str
    title: Optional[str] = None


class SectionEdit(BaseModel):
    section: str
    content: dict


class DeliveryRequest(BaseModel):
    channel: str
    note: Optional[str] = None


@router.post("/generate")
async def generate_report_endpoint(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    report_id  = str(uuid.uuid4())
    count      = len(supabase.table("reports").select("report_id").execute().data)
    report_ref = f"RPT-{datetime.utcnow().year}-{count+1:03d}"
    title      = body.title or f"Risk Report — {body.report_period}"

    supabase.table("reports").insert({
        "report_id": report_id,
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "client_id": body.client_id,
        "portfolio_id": body.portfolio_id,
        "report_ref": report_ref,
        "title": title,
        "report_period": body.report_period,
        "status": "DRAFT",
        "generation_started_at": datetime.utcnow().isoformat(),
    }).execute()

    background_tasks.add_task(generate_report, report_id, body.portfolio_id, body.client_id)

    return {"status": "generation_started", "report_id": report_id, "report_ref": report_ref, "estimated_minutes": 3}


@router.get("")
async def list_reports(status: Optional[str] = None, current_user: CurrentUser = Depends(get_current_user)):
    q = supabase.table("reports").select("report_id,report_ref,title,report_period,status,created_at,generation_completed_at,approved_at,delivered_at,clients(display_name)").eq("tenant_id", settings.DEFAULT_TENANT_ID)
    if status:
        q = q.eq("status", status.upper())
    return q.order("created_at", desc=True).execute().data


@router.get("/{report_id}")
async def get_report(report_id: str, current_user: CurrentUser = Depends(get_current_user)):
    r = supabase.table("reports").select("*").eq("report_id", report_id).single().execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Report not found")
    return r.data


@router.patch("/{report_id}/sections")
async def edit_section(report_id: str, body: SectionEdit, current_user: CurrentUser = Depends(get_current_user)):
    valid = ["executive_summary","portfolio_composition","risk_scorecard","counterparty_analysis","stress_test_results","recommendations"]
    if body.section not in valid:
        raise HTTPException(status_code=400, detail=f"Section must be one of: {valid}")

    r = supabase.table("reports").select(f"section_{body.section},status").eq("report_id", report_id).single().execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Report not found")
    if r.data["status"] in ("APPROVED","DELIVERED"):
        raise HTTPException(status_code=400, detail="Cannot edit approved/delivered report")

    old = r.data.get(f"section_{body.section}")
    supabase.table("reports").update({f"section_{body.section}": body.content, "status": "IN_REVIEW"}).eq("report_id", report_id).execute()
    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID, "event_category": "HUMAN_REVIEW",
        "event_type": "report.section_edited", "actor_type": "USER",
        "actor_id": current_user.user_id, "resource_type": "reports", "resource_id": report_id,
        "before_state": {body.section: old}, "after_state": {body.section: body.content},
    }).execute()
    return {"status": "updated", "section": body.section}


@router.post("/{report_id}/approve")
async def approve_report(report_id: str, current_user: CurrentUser = Depends(require_senior_analyst)):
    r = supabase.table("reports").select("status").eq("report_id", report_id).single().execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Not found")
    if r.data["status"] in ("APPROVED","DELIVERED"):
        raise HTTPException(status_code=400, detail=f"Already {r.data['status'].lower()}")

    supabase.table("reports").update({"status": "APPROVED", "approved_by": current_user.user_id, "approved_at": datetime.utcnow().isoformat()}).eq("report_id", report_id).execute()
    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID, "event_category": "HUMAN_REVIEW",
        "event_type": "report.approved", "actor_type": "USER",
        "actor_id": current_user.user_id, "resource_type": "reports", "resource_id": report_id,
    }).execute()
    return {"status": "approved"}


@router.post("/{report_id}/deliver")
async def deliver_report(report_id: str, body: DeliveryRequest, current_user: CurrentUser = Depends(get_current_user)):
    r = supabase.table("reports").select("status").eq("report_id", report_id).single().execute()
    if not r.data or r.data["status"] != "APPROVED":
        raise HTTPException(status_code=400, detail="Report must be APPROVED first")
    supabase.table("reports").update({"status": "DELIVERED", "delivered_by": current_user.user_id, "delivered_at": datetime.utcnow().isoformat(), "delivery_channel": body.channel, "delivery_note": body.note}).eq("report_id", report_id).execute()
    return {"status": "delivered"}
