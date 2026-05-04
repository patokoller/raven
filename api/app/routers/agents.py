"""Raven — Agents Router"""
from fastapi import APIRouter, Depends, BackgroundTasks
from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings
from app.workers.tasks import run_in_thread
from app.workers.scoring import score_all_counterparties, score_single_counterparty

router = APIRouter()

@router.post("/score/run-all")
async def run_all_scores(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Trigger scoring for all active counterparties in the background."""
    background_tasks.add_task(score_all_counterparties)
    return {
        "status": "started",
        "message": "Scoring all 25 counterparties. Refresh the dashboard in ~60 seconds.",
    }

@router.post("/score/{counterparty_id}")
async def run_single_score(
    counterparty_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    background_tasks.add_task(score_single_counterparty, counterparty_id)
    return {"status": "started", "counterparty_id": counterparty_id}

@router.get("/runs")
async def list_agent_runs(current_user: CurrentUser = Depends(get_current_user)):
    logs = (
        supabase.table("audit_log")
        .select("log_id, event_ts, event_type, metadata")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("event_category", "AGENT")
        .order("event_ts", desc=True)
        .limit(50)
        .execute()
    )
    return logs.data
