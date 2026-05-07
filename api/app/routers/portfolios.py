"""
Raven — Portfolios Router
POST /api/v1/portfolios/upload
GET  /api/v1/portfolios
GET  /api/v1/portfolios/{id}/metrics
GET  /api/v1/portfolios/{id}/positions
POST /api/v1/portfolios/{id}/stress
"""

import io, uuid
from datetime import datetime, date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from pydantic import BaseModel

from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings
from app.workers.analytics import compute_portfolio_metrics

router = APIRouter()

STABLECOINS = {"USDT","USDC","DAI","BUSD","TUSD","FRAX","USDP","GUSD"}

def infer_asset_class(symbol: str) -> str:
    s = symbol.upper()
    if s in STABLECOINS: return "stablecoin"
    if len(s) <= 5 and s.isalpha(): return "crypto"
    return "crypto"

# Map any non-enum asset classes to valid enum values
ASSET_CLASS_MAP = {
    "defi_protocol": "crypto",
    "defi": "crypto",
    "token": "crypto",
}

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lower().strip().replace(" ","_") for c in df.columns]
    for aliases, canon in [
        (["ticker","symbol","coin","asset"], "asset_symbol"),
        (["qty","amount","units","holdings"], "quantity"),
        (["value","value_chf","nav_chf","mkt_val"], "market_value_chf"),
    ]:
        for a in aliases:
            if a in df.columns and canon not in df.columns:
                df = df.rename(columns={a: canon})
    return df


@router.get("")
async def list_portfolios(current_user: CurrentUser = Depends(get_current_user)):
    return (
        supabase.table("portfolios")
        .select("*, clients(display_name, client_ref)")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
        .data
    )


@router.post("/upload")
async def upload_portfolio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    client_id: str = Form(...),
    portfolio_name: str = Form(...),
    valuation_date: str = Form(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content)) if file.filename.endswith((".xlsx",".xls")) else pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    df = normalize_df(df)
    if "asset_symbol" not in df.columns:
        raise HTTPException(status_code=400, detail="Need column: symbol, ticker, coin, or asset")
    if "quantity" not in df.columns:
        raise HTTPException(status_code=400, detail="Need column: quantity, qty, amount, or units")

    df = df.dropna(subset=["asset_symbol","quantity"])
    df["asset_symbol"] = df["asset_symbol"].str.upper().str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df = df[df["quantity"] > 0]

    if df.empty:
        raise HTTPException(status_code=400, detail="No valid positions found")

    client = supabase.table("clients").select("client_ref").eq("client_id", client_id).single().execute().data
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    portfolio_id  = str(uuid.uuid4())
    portfolio_ref = f"PF-{client['client_ref']}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"

    supabase.table("portfolios").insert({
        "portfolio_id": portfolio_id,
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "client_id": client_id,
        "portfolio_ref": portfolio_ref,
        "display_name": portfolio_name,
        "valuation_date": valuation_date,
        "source_file_path": file.filename,
        "last_uploaded_at": datetime.utcnow().isoformat(),
        "last_uploaded_by": current_user.user_id,
    }).execute()

    cps   = supabase.table("counterparties").select("counterparty_id,slug,display_name").execute().data
    cp_map = {c["display_name"].lower(): c for c in cps}

    total_nav, positions = 0.0, []
    for _, row in df.iterrows():
        val = float(row.get("market_value_chf") or 0)
        total_nav += val
        cname = str(row.get("custodian","") or "").strip()
        cp    = cp_map.get(cname.lower())
        positions.append({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "portfolio_id": portfolio_id,
            "asset_symbol": row["asset_symbol"],
            "asset_name": row.get("asset_name") or row["asset_symbol"],
            "asset_class": (lambda ac: ASSET_CLASS_MAP.get(ac, ac))(
                str(row["asset_class"]).lower().strip()
            ) if row.get("asset_class") and str(row.get("asset_class","")).lower().strip()
                in ["crypto","equity","etf","fund","cash","fixed_income","commodity","stablecoin","defi_protocol","defi","token"]
            else infer_asset_class(row["asset_symbol"]),
            "quantity": float(row["quantity"]),
            "market_value_chf": val or None,
            "custodian_id": cp["counterparty_id"] if cp else None,
            "custodian_name": cname or None,
            "raw_row": row.to_dict(),
            "as_of_date": valuation_date,
        })

    supabase.table("portfolio_positions").insert(positions).execute()
    if total_nav > 0:
        supabase.table("portfolios").update({"total_nav_chf": total_nav}).eq("portfolio_id", portfolio_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type": "portfolio.uploaded",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "portfolios",
        "resource_id": portfolio_id,
        "metadata": {"filename": file.filename, "positions": len(positions), "nav_chf": total_nav},
    }).execute()

    background_tasks.add_task(compute_portfolio_metrics, portfolio_id)

    return {
        "status": "uploaded",
        "portfolio_id": portfolio_id,
        "portfolio_ref": portfolio_ref,
        "position_count": len(positions),
        "total_nav_chf": round(total_nav, 2),
    }


@router.get("/{portfolio_id}/metrics")
async def get_metrics(portfolio_id: str, current_user: CurrentUser = Depends(get_current_user)):
    m = (
        supabase.table("portfolio_metrics")
        .select("*").eq("portfolio_id", portfolio_id)
        .order("computed_at", desc=True).limit(1).execute().data
    )
    if not m:
        raise HTTPException(status_code=404, detail="No metrics yet — metrics compute in the background after upload")
    return m[0]


@router.get("/{portfolio_id}/positions")
async def get_positions(portfolio_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return (
        supabase.table("portfolio_positions")
        .select("*").eq("portfolio_id", portfolio_id)
        .order("market_value_chf", desc=True).execute().data
    )


@router.get("/clients-list")
async def list_clients(current_user: CurrentUser = Depends(get_current_user)):
    return supabase.table("clients").select("client_id,client_ref,display_name").eq("tenant_id", settings.DEFAULT_TENANT_ID).eq("is_active", True).execute().data



@router.get("/{portfolio_id}/risk")
async def get_portfolio_risk(
    portfolio_id: str,
    refresh: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get comprehensive risk analytics for a portfolio. Cached, refresh on demand."""
    from app.workers.portfolio_risk import compute_portfolio_risk

    if not refresh:
        # Try cache first
        cached = (
            supabase.table("portfolio_risk_cache")
            .select("*")
            .eq("portfolio_id", portfolio_id)
            .execute()
            .data
        )
        if cached:
            return cached[0]

    # Compute fresh
    return compute_portfolio_risk(portfolio_id)


@router.post("/{portfolio_id}/risk/refresh")
async def refresh_portfolio_risk(
    portfolio_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Recompute risk analytics for a portfolio."""
    from app.workers.portfolio_risk import compute_portfolio_risk
    from app.workers.tasks import run_in_thread
    run_in_thread(compute_portfolio_risk, portfolio_id)
    return {"status": "computing", "portfolio_id": portfolio_id}


@router.get("/clients/{client_id}/risk")
async def get_client_risk(
    client_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get aggregated risk across all portfolios for a client."""
    from app.workers.portfolio_risk import compute_client_risk
    return compute_client_risk(client_id)


@router.get("/clients/{client_id}/limits")
async def get_client_limits(
    client_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get exposure limits for a client mandate."""
    return (
        supabase.table("client_limits")
        .select("*")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
        .data
    ) or []


@router.put("/clients/{client_id}/limits")
async def update_client_limit(
    client_id: str,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update or create a client exposure limit."""
    supabase.table("client_limits").upsert({
        "tenant_id":  settings.DEFAULT_TENANT_ID,
        "client_id":  client_id,
        "limit_type": body["limit_type"],
        "limit_key":  body["limit_key"],
        "limit_pct":  body["limit_pct"],
    }, on_conflict="client_id,limit_type,limit_key").execute()
    return {"status": "updated"}





@router.post("/{portfolio_id}/ai-analysis")
async def run_ai_analysis(
    portfolio_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Trigger AI risk analysis for a portfolio (runs in background)."""
    from app.workers.portfolio_ai_analysis import analyse_portfolio_risk
    background_tasks.add_task(analyse_portfolio_risk, portfolio_id)
    return {"status": "running", "portfolio_id": portfolio_id,
            "message": "AI analysis running — results ready in 15-30 seconds"}


@router.get("/{portfolio_id}/ai-analysis")
async def get_ai_analysis(
    portfolio_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the latest AI analysis for a portfolio."""
    row = (
        supabase.table("portfolio_risk_cache")
        .select("ai_analysis, ai_analysed_at")
        .eq("portfolio_id", portfolio_id)
        .execute()
        .data
    )
    if not row or not row[0].get("ai_analysis"):
        return {"status": "not_run"}
    return {
        "status": "ready",
        "analysis": row[0]["ai_analysis"],
        "generated_at": row[0].get("ai_analysed_at"),
    }

@router.post("/{portfolio_id}/stress/run-all")
async def run_all_stress(
    portfolio_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Run all stress test scenarios for a portfolio."""
    from app.workers.stress_engine import SCENARIOS, run_stress_test, get_all_scenarios
    from app.workers.tasks import run_in_thread

    all_scenarios = get_all_scenarios()
    results = []

    def run_sequentially():
        for s in all_scenarios:
            try:
                result = run_stress_test(portfolio_id, s["scenario_id"])
                results.append({
                    "scenario": s["display_name"],
                    "pnl_pct":  result.get("pnl_pct"),
                    "pnl_chf":  result.get("pnl_chf"),
                })
            except Exception as e:
                print(f"[stress_all] {s['display_name']}: {e}")

    run_in_thread(run_sequentially)
    return {"status": "running", "scenario_count": len(all_scenarios),
            "message": "All scenarios running in background — refresh in 60s"}

@router.post("/{portfolio_id}/stress")
async def run_stress(
    portfolio_id: str,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Run a stress test scenario against a portfolio."""
    from app.workers.stress_engine import run_stress_test
    scenario_id = body.get("scenario_id")
    if not scenario_id:
        raise HTTPException(status_code=400, detail="scenario_id required")
    try:
        result = run_stress_test(portfolio_id, scenario_id)
        return result
    except Exception as e:
        print(f"[stress] endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a portfolio and all its positions, metrics, and stress test results."""
    # Verify it exists and belongs to this tenant
    p = (
        supabase.table("portfolios")
        .select("portfolio_id, portfolio_ref")
        .eq("portfolio_id", portfolio_id)
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .execute()
        .data
    )
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Delete child records first (FK constraints)
    for table in ["stress_test_results", "portfolio_metrics", "portfolio_positions", "reports"]:
        try:
            supabase.table(table).delete().eq("portfolio_id", portfolio_id).execute()
        except Exception as e:
            print(f"[portfolio delete] {table}: {e}")
    try:
        supabase.table("portfolios").delete().eq("portfolio_id", portfolio_id).execute()
    except Exception as e:
        print(f"[portfolio delete] portfolios: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type":     "portfolio.deleted",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "metadata":       {"portfolio_id": portfolio_id, "portfolio_ref": p[0]["portfolio_ref"]},
    }).execute()

    return {"status": "deleted", "portfolio_id": portfolio_id}
