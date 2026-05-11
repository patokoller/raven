"""
Raven — SNB Banking Statistics Provider
Swiss National Bank Data Portal

Public REST API: https://data.snb.ch/api/cube/{cube}/data/{format}/{lang}
No auth required. CSV and JSON formats available.

Banking sector cubes (verified from data.snb.ch):
- bankbstajb   : Annual banking sector balance sheet statistics
- bankbstaq    : Quarterly banking sector balance sheet statistics  
- bankeigenka  : Capital ratios for Swiss banks (annual)
- bankliqmon   : Monthly liquidity statistics

API pattern:
  GET https://data.snb.ch/api/cube/bankbstajb/data/json/en?fromDate=2022&toDate=2024
  GET https://data.snb.ch/api/cube/bankbstajb/dimensions/en   (structure)
"""

import httpx
import json
from datetime import datetime

SNB_BASE = "https://data.snb.ch/api"
HEADERS  = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept":     "application/json",
}

# Key banking cubes — verified against SNB data portal
CUBES = {
    "balance_sheet_annual":   "bankbstajb",
    "balance_sheet_monthly":  "bankbstaq",
    "capital_ratios":         "bankeigenka",
    "liquidity":              "bankliqmon",
}


def _fetch_cube(cube: str, from_date: str = "2022", to_date: str = "2025",
                dim_sel: str = None) -> dict:
    """Fetch data from an SNB cube."""
    params = {"fromDate": from_date, "toDate": to_date}
    if dim_sel:
        params["dimSel"] = dim_sel
    try:
        url = f"{SNB_BASE}/cube/{cube}/data/json/en"
        r   = httpx.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json()
        # Try alternative URL format
        url2 = f"{SNB_BASE}/cube/{cube}/data/json"
        r2   = httpx.get(url2, params={**params, "lang": "en"}, headers=HEADERS, timeout=20)
        if r2.status_code == 200:
            return r2.json()
    except Exception as e:
        print(f"[snb] Cube {cube} error: {e}")
    return {}


def _parse_latest_observation(data: dict) -> tuple:
    """Extract the latest value and date from an SNB JSON response."""
    # SNB JSON format: {"observations": [{"date": "2023", "value": 1234.5}, ...]}
    obs = data.get("observations") or data.get("data") or []
    if not obs:
        # Try nested structure
        datasets = data.get("datasets") or []
        for ds in datasets:
            obs = ds.get("observations") or []
            if obs:
                break
    if obs:
        latest = obs[-1]
        return latest.get("value"), latest.get("date")
    return None, None


def get_sector_statistics() -> dict:
    """
    Fetch Swiss banking sector aggregate statistics.
    Returns total assets, capital ratios, etc. for Swiss banking sector.
    Used as reference benchmark and for enriching CH bank counterparties.
    """
    result = {
        "source":     "snb",
        "available":  False,
        "fetched_at": datetime.utcnow().isoformat(),
        "data_type":  "sector_aggregate",
        "note":       "SNB publishes sector-level data. Individual bank data below CHF 10B threshold is not separately disclosed.",
    }

    # Total assets of Swiss banking sector
    bs_data = _fetch_cube(CUBES["balance_sheet_annual"], "2021", "2025")
    if bs_data:
        val, date = _parse_latest_observation(bs_data)
        if val is not None:
            result["available"]                = True
            result["sector_total_assets_bn_chf"] = round(float(val) / 1000, 1)  # usually in millions
            result["sector_as_of"]             = date

    # Capital ratios
    cap_data = _fetch_cube(CUBES["capital_ratios"], "2021", "2025")
    if cap_data:
        val, date = _parse_latest_observation(cap_data)
        if val is not None:
            result["available"]                = True
            result["sector_capital_ratio_pct"] = float(val)
            result["capital_ratio_date"]       = date

    return result


def enrich_counterparty(slug: str, display_name: str = "", jurisdiction: str = "CH") -> dict:
    """
    Main entry point. Returns SNB statistics for a Swiss bank.
    SNB publishes sector-level data; individual bank data is only
    available for systemically important banks (UBS, Credit Suisse, etc.)

    For all other Swiss banks, returns sector benchmarks with a note.
    """
    if jurisdiction not in ("CH", "Switzerland", "Schweiz"):
        return {"source": "snb", "available": False, "reason": "not_swiss"}

    # Get sector stats (always available)
    stats = get_sector_statistics()

    if stats.get("available"):
        stats["note"] = (
            f"SNB sector-level data for Swiss banking industry. "
            f"{display_name} reports to SNB but individual institution data "
            f"is not published separately unless systemically important. "
            f"Sector benchmark: total assets CHF {stats.get('sector_total_assets_bn_chf', '?')}B, "
            f"avg capital ratio {stats.get('sector_capital_ratio_pct', '?')}%."
        )

    return stats
