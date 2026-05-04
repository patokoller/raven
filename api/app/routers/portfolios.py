"""
Raven — Portfolios Router
POST /api/v1/portfolios/upload       — CSV/XLSX ingestion
GET  /api/v1/portfolios              — list portfolios
GET  /api/v1/portfolios/{id}/metrics — latest risk metrics
POST /api/v1/portfolios/{id}/stress  — trigger stress test
"""

import io
import uuid
from datetime import date, datetime
from typing import Optional, List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel

from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()

# Canonical column name mappings from various upload formats
SYMBOL_ALIASES = {"ticker": "asset_symbol", "symbol": "asset_symbol", "coin": "asset_symbol", "asset": "asset_symbol"}
QTY_ALIASES    = {"qty": "quantity", "amount": "quantity", "units": "quantity", "holdings": "quantity"}
VALUE_ALIASES  = {"value": "market_value_chf", "value_chf": "market_value_chf", "nav_chf": "market_value_chf", "mkt_val": "market_value_chf"}
CLASS_ALIASES  = {"type": "asset_class", "class": "asset_class", "category": "asset_class"}

CRYPTO_SYMBOLS = {
    "BTC","ETH","SOL","BNB","ADA","DOT","AVAX","MATIC","LINK","UNI",
    "AAVE","COMP","MKR","SNX","CRV","SUSHI","1INCH","DYDX","LDO",
    "ATOM","NEAR","FTM","ALGO","XRP","LTC","BCH","ETC","XLM","TRX",
    "USDT","USDC","DAI","BUSD","TUSD","FRAX","USDP",
}
STABLECOINS = {"USDT","USDC","DAI","BUSD","TUSD","FRAX","USDP","GUSD","USDD"}


def infer_asset_class(symbol: str) -> str:
    sym = symbol.upper().strip()
    if sym in STABLECOINS:
        return "stablecoin"
    if sym in CRYPTO_SYMBOLS:
        return "crypto"
    # Simple equity heuristics
    if len(sym) <= 5 and sym.isalpha():
        return "equity"
    return "crypto"  # default for unknown


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to canonical form."""
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
    for aliases, canonical in [
        (SYMBOL_ALIASES, "asset_symbol"),
        (QTY_ALIASES, "quantity"),
        (VALUE_ALIASES, "market_value_chf"),
        (CLASS_ALIASES, "asset_class"),
    ]:
        for alias in aliases:
            if alias in df.columns and canonical not in df.columns:
                df = df.rename(columns={alias: canonical})
    return df


@router.get("")
async def list_portfolios(
    client_id: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    q = (
        supabase.table("portfolios")
        .select("*, clients(display_name, client_ref)")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
    )
    if client_id:
        q = q.eq("client_id", client_id)
    return q.order("created_at", desc=True).execute().data


@router.post("/upload")
async def upload_portfolio(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    portfolio_name: str = Form(...),
    valuation_date: str = Form(...),   # YYYY-MM-DD
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Ingest a CSV or XLSX portfolio file.
    Required columns: symbol/ticker, quantity/qty
    Optional: value_chf, custodian, asset_class
    """
    # Parse file
    content = await file.read()
    try:
        if file.filename.endswith(".xlsx") or file.filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {str(e)}")

    df = normalize_columns(df)

    if "asset_symbol" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="File must contain a column named: symbol, ticker, coin, or asset"
        )
    if "quantity" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="File must contain a column named: quantity, qty, amount, or units"
        )

    # Clean data
    df = df.dropna(subset=["asset_symbol", "quantity"])
    df["asset_symbol"] = df["asset_symbol"].str.upper().str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df = df[df["quantity"] > 0]

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="No valid positions found in file")

    # Verify client exists
    client = (
        supabase.table("clients")
        .select("client_id, display_name")
        .eq("client_id", client_id)
        .single()
        .execute()
    )
    if not client.data:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create portfolio record
    portfolio_ref = f"PF-{client.data['client_ref'] if 'client_ref' in client.data else client_id[:8]}-{datetime.utcnow().strftime('%Y%m%d')}"
    portfolio_id = str(uuid.uuid4())

    supabase.table("portfolios").insert({
        "portfolio_id": portfolio_id,
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "client_id": client_id,
        "portfolio_ref": portfolio_ref,
        "display_name": portfolio_name,
        "valuation_date": valuation_date,
        "is_active": True,
        "source_file_path": file.filename,
        "last_uploaded_at": datetime.utcnow().isoformat(),
        "last_uploaded_by": current_user.user_id,
    }).execute()

    # Map custodian names to IDs (best-effort)
    cps = supabase.table("counterparties").select("counterparty_id, slug, display_name").execute().data
    cp_by_name = {c["display_name"].lower(): c for c in cps}
    cp_by_slug = {c["slug"]: c for c in cps}

    def find_custodian(name: str):
        if not name or pd.isna(name):
            return None, None
        n = str(name).lower().strip()
        match = cp_by_name.get(n) or cp_by_slug.get(n.replace(" ", "-"))
        if match:
            return match["counterparty_id"], match["display_name"]
        return None, str(name)

    # Build positions
    positions = []
    total_nav = 0.0
    val_date = datetime.strptime(valuation_date, "%Y-%m-%d").date()

    for _, row in df.iterrows():
        mkt_val = float(row.get("market_value_chf", 0) or 0)
        total_nav += mkt_val

        custodian_name = row.get("custodian") or row.get("custodian_name") or ""
        cid, cname = find_custodian(custodian_name)

        asset_class_raw = row.get("asset_class", "")
        if asset_class_raw and str(asset_class_raw).lower() in ["crypto","equity","etf","fund","cash","fixed_income","commodity","stablecoin"]:
            asset_class = str(asset_class_raw).lower()
        else:
            asset_class = infer_asset_class(row["asset_symbol"])

        positions.append({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "portfolio_id": portfolio_id,
            "asset_symbol": row["asset_symbol"],
            "asset_name": row.get("asset_name") or row.get("name") or row["asset_symbol"],
            "asset_class": asset_class,
            "quantity": float(row["quantity"]),
            "cost_basis_chf": float(row.get("cost_basis_chf") or row.get("cost_basis") or 0) or None,
            "market_value_chf": mkt_val or None,
            "custodian_id": cid,
            "custodian_name": cname,
            "raw_row": row.to_dict(),
            "as_of_date": valuation_date,
        })

    # Bulk insert positions
    if positions:
        supabase.table("portfolio_positions").insert(positions).execute()

    # Update total NAV
    if total_nav > 0:
        supabase.table("portfolios").update({"total_nav_chf": total_nav}).eq("portfolio_id", portfolio_id).execute()

    # Compute weight_pct
    if total_nav > 0:
        for p in positions:
            if p.get("market_value_chf"):
                supabase.table("portfolio_positions").update({
                    "weight_pct": round(p["market_value_chf"] / total_nav, 6)
                }).eq("portfolio_id", portfolio_id).eq("asset_symbol", p["asset_symbol"]).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type": "portfolio.uploaded",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "portfolios",
        "resource_id": portfolio_id,
        "metadata": {
            "filename": file.filename,
            "position_count": len(positions),
            "total_nav_chf": total_nav,
            "client_id": client_id,
        }
    }).execute()

    # Queue overnight metric calculation
    from app.workers.analytics import compute_portfolio_metrics_task
    compute_portfolio_metrics_task.delay(portfolio_id)

    return {
        "status": "uploaded",
        "portfolio_id": portfolio_id,
        "portfolio_ref": portfolio_ref,
        "position_count": len(positions),
        "total_nav_chf": round(total_nav, 2),
        "metrics_computation": "queued",
    }


@router.get("/{portfolio_id}/metrics")
async def get_metrics(
    portfolio_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Latest computed risk metrics for a portfolio."""
    metrics = (
        supabase.table("portfolio_metrics")
        .select("*")
        .eq("portfolio_id", portfolio_id)
        .order("computed_at", desc=True)
        .limit(1)
        .execute()
    )
    if not metrics.data:
        raise HTTPException(status_code=404, detail="No metrics computed yet. Upload portfolio and wait for nightly batch.")
    return metrics.data[0]


@router.get("/{portfolio_id}/positions")
async def get_positions(
    portfolio_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    positions = (
        supabase.table("portfolio_positions")
        .select("*")
        .eq("portfolio_id", portfolio_id)
        .order("market_value_chf", desc=True)
        .execute()
    )
    return positions.data


@router.post("/{portfolio_id}/stress")
async def run_stress_test(
    portfolio_id: str,
    scenario_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Trigger a stress test run asynchronously. Poll /stress/{result_id} for results."""
    # Verify portfolio exists
    portfolio = (
        supabase.table("portfolios")
        .select("portfolio_id, total_nav_chf")
        .eq("portfolio_id", portfolio_id)
        .single()
        .execute()
    )
    if not portfolio.data:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Verify scenario exists
    scenario = (
        supabase.table("stress_scenarios")
        .select("scenario_id, display_name")
        .eq("scenario_id", scenario_id)
        .single()
        .execute()
    )
    if not scenario.data:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.workers.analytics import run_stress_test_task
    task = run_stress_test_task.delay(portfolio_id, scenario_id)

    return {
        "status": "queued",
        "portfolio_id": portfolio_id,
        "scenario_id": scenario_id,
        "scenario_name": scenario.data["display_name"],
        "task_id": task.id,
    }
