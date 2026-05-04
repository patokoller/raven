"""Raven — Agents Router (trigger scoring runs)"""
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()

@router.post("/score/run-all")
async def run_all_scores(current_user: CurrentUser = Depends(get_current_user)):
    """Trigger scoring for all active counterparties."""
    from app.workers.scoring import score_all_counterparties_task
    task = score_all_counterparties_task.delay()
    return {"status": "queued", "task_id": task.id, "message": "Scoring pipeline started for all counterparties"}

@router.post("/score/{counterparty_id}")
async def run_single_score(
    counterparty_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    from app.workers.scoring import recalculate_score_task
    task = recalculate_score_task.delay(counterparty_id)
    return {"status": "queued", "task_id": task.id, "counterparty_id": counterparty_id}

@router.get("/runs")
async def list_agent_runs(current_user: CurrentUser = Depends(get_current_user)):
    logs = (
        supabase.table("audit_log")
        .select("log_id, event_ts, event_type, actor_id, metadata")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("event_category", "AGENT")
        .order("event_ts", desc=True)
        .limit(50)
        .execute()
    )
    return logs.data
