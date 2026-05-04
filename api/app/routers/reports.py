"""
Raven — Reports Router
POST /api/v1/reports/generate        — trigger AI report generation
GET  /api/v1/reports                 — list reports (workflow queue)
GET  /api/v1/reports/{id}            — full report with sections
PATCH /api/v1/reports/{id}/sections  — inline edit sections
POST /api/v1/reports/{id}/approve    — Senior Analyst approval gate
POST /api/v1/reports/{id}/deliver    — mark as delivered
GET  /api/v1/reports/{id}/pdf        — download PDF
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.auth import get_current_user, require_senior_analyst, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()


class GenerateReportRequest(BaseModel):
    portfolio_id: str
    client_id: str
    report_period: str       # e.g. "Q2 2025", "Monthly – June 2025"
    title: Optional[str] = None
    assigned_reviewer: Optional[str] = None


class SectionEditRequest(BaseModel):
    section: str             # "executive_summary", "counterparty_analysis", etc.
    content: dict


class DeliveryRequest(BaseModel):
    channel: str             # "email", "secure_link", "portal"
    note: Optional[str] = None


@router.post("/generate")
async def generate_report(
    body: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Trigger the AI agent pipeline to generate a report draft."""
    import uuid

    report_id = str(uuid.uuid4())
    ref_num = supabase.table("reports").select("report_id").execute()
    report_ref = f"RPT-{datetime.utcnow().year}-{len(ref_num.data) + 1:03d}"

    title = body.title or f"Risk Report — {body.report_period}"

    # Create report record in DRAFT state
    supabase.table("reports").insert({
        "report_id": report_id,
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "client_id": body.client_id,
        "portfolio_id": body.portfolio_id,
        "report_ref": report_ref,
        "title": title,
        "report_period": body.report_period,
        "status": "DRAFT",
        "assigned_reviewer": body.assigned_reviewer,
        "generation_started_at": datetime.utcnow().isoformat(),
    }).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "AGENT",
        "event_type": "report.generation_started",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "reports",
        "resource_id": report_id,
        "metadata": {"report_ref": report_ref, "period": body.report_period},
    }).execute()

    # Queue the agent pipeline
    from app.workers.report_pipeline import generate_report_task
    generate_report_task.delay(report_id, body.portfolio_id, body.client_id)

    return {
        "status": "generation_started",
        "report_id": report_id,
        "report_ref": report_ref,
        "estimated_completion_minutes": 5,
    }


@router.get("")
async def list_reports(
    status: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Report workflow queue — all reports with status."""
    q = (
        supabase.table("reports")
        .select("""
            report_id, report_ref, title, report_period, status,
            created_at, generation_completed_at, approved_at, delivered_at,
            clients(display_name, client_ref),
            assigned_reviewer_user:users!reports_assigned_reviewer_fkey(full_name)
        """)
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
    )
    if status:
        q = q.eq("status", status.upper())
    return q.order("created_at", desc=True).execute().data


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Full report including all AI-generated sections."""
    report = (
        supabase.table("reports")
        .select("*")
        .eq("report_id", report_id)
        .single()
        .execute()
    )
    if not report.data:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.data


@router.patch("/{report_id}/sections")
async def edit_section(
    report_id: str,
    body: SectionEditRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Inline edit a report section. Changes tracked in audit log."""
    valid_sections = [
        "executive_summary", "portfolio_composition", "risk_scorecard",
        "counterparty_analysis", "stress_test_results", "recommendations"
    ]
    if body.section not in valid_sections:
        raise HTTPException(status_code=400, detail=f"Invalid section. Must be one of: {valid_sections}")

    # Get current content for audit diff
    report = supabase.table("reports").select(f"section_{body.section}, status").eq("report_id", report_id).single().execute()
    if not report.data:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.data["status"] not in ("DRAFT", "IN_REVIEW"):
        raise HTTPException(status_code=400, detail="Cannot edit — report is already approved or delivered")

    old_content = report.data.get(f"section_{body.section}")

    supabase.table("reports").update({
        f"section_{body.section}": body.content,
        "status": "IN_REVIEW",
    }).eq("report_id", report_id).execute()

    # Audit log every edit
    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "HUMAN_REVIEW",
        "event_type": "report.section_edited",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "reports",
        "resource_id": report_id,
        "before_state": {body.section: old_content},
        "after_state": {body.section: body.content},
    }).execute()

    return {"status": "updated", "section": body.section}


@router.post("/{report_id}/approve")
async def approve_report(
    report_id: str,
    current_user: CurrentUser = Depends(require_senior_analyst),
):
    """
    Senior Analyst approval gate. Locks editing.
    Only senior_analyst or admin roles can call this.
    """
    report = supabase.table("reports").select("status").eq("report_id", report_id).single().execute()
    if not report.data:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.data["status"] == "DELIVERED":
        raise HTTPException(status_code=400, detail="Report already delivered")
    if report.data["status"] == "APPROVED":
        raise HTTPException(status_code=400, detail="Report already approved")

    supabase.table("reports").update({
        "status": "APPROVED",
        "approved_by": current_user.user_id,
        "approved_at": datetime.utcnow().isoformat(),
    }).eq("report_id", report_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "HUMAN_REVIEW",
        "event_type": "report.approved",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "reports",
        "resource_id": report_id,
        "metadata": {"approver_role": current_user.role},
    }).execute()

    # Trigger PDF generation
    from app.workers.report_pipeline import render_pdf_task
    render_pdf_task.delay(report_id)

    return {"status": "approved", "pdf_generation": "queued"}


@router.post("/{report_id}/deliver")
async def mark_delivered(
    report_id: str,
    body: DeliveryRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    report = supabase.table("reports").select("status").eq("report_id", report_id).single().execute()
    if not report.data or report.data["status"] != "APPROVED":
        raise HTTPException(status_code=400, detail="Report must be APPROVED before delivery")

    supabase.table("reports").update({
        "status": "DELIVERED",
        "delivered_by": current_user.user_id,
        "delivered_at": datetime.utcnow().isoformat(),
        "delivery_channel": body.channel,
        "delivery_note": body.note,
    }).eq("report_id", report_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "DELIVERY",
        "event_type": "report.delivered",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "reports",
        "resource_id": report_id,
        "metadata": {"channel": body.channel, "note": body.note},
    }).execute()

    return {"status": "delivered", "channel": body.channel}
