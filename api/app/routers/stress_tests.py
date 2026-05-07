"""Raven — Stress Tests Router"""
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()

@router.get("/scenarios")
async def list_scenarios(current_user: CurrentUser = Depends(get_current_user)):
    from app.workers.stress_engine import get_all_scenarios
    return get_all_scenarios()

@router.get("/results/{portfolio_id}")
async def get_results(portfolio_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return (
        supabase.table("stress_test_results")
        .select("*, stress_scenarios(display_name, description)")
        .eq("portfolio_id", portfolio_id)
        .order("run_at", desc=True)
        .execute()
        .data
    )
