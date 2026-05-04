"""Raven — Alerts Router"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()

class AlertAction(BaseModel):
    action: str       # "acknowledge", "escalate", "dismiss", "resolve"
    note: Optional[str] = None

@router.get("")
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    q = (
        supabase.table("alerts")
        .select("*, counterparties(display_name, entity_type, current_risk_tier)")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
    )
    if status:
        q = q.eq("status", status.upper())
    else:
        q = q.in_("status", ["OPEN", "ACKNOWLEDGED", "ESCALATED"])
    if severity:
        q = q.eq("severity", severity.upper())
    return q.order("triggered_at", desc=True).execute().data

@router.post("/{alert_id}/action")
async def alert_action(
    alert_id: str,
    body: AlertAction,
    current_user: CurrentUser = Depends(get_current_user),
):
    from datetime import datetime
    valid = {"acknowledge", "escalate", "dismiss", "resolve"}
    if body.action not in valid:
        raise HTTPException(status_code=400, detail=f"Action must be one of: {valid}")

    status_map = {"acknowledge": "ACKNOWLEDGED", "escalate": "ESCALATED", "dismiss": "DISMISSED", "resolve": "RESOLVED"}
    update = {"status": status_map[body.action], "updated_at": datetime.utcnow().isoformat()}
    if body.action == "acknowledge":
        update.update({"acknowledged_by": current_user.user_id, "acknowledged_at": datetime.utcnow().isoformat()})
    elif body.action in ("resolve", "dismiss"):
        update.update({"resolved_by": current_user.user_id, "resolved_at": datetime.utcnow().isoformat(), "resolution_note": body.note})

    supabase.table("alerts").update(update).eq("alert_id", alert_id).execute()
    return {"status": "updated", "new_status": status_map[body.action]}
