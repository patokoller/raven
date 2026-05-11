"""
Raven — SNB Banking Statistics Provider
Swiss National Bank Data Portal

Correct API pattern:
  https://data.snb.ch/{language}/warehouse/{ID}/{format}

Warehouse IDs:
  BSTA  = Banking sector balance sheet statistics
  BSEIG = Capital adequacy
  BSLIQ = Liquidity

No auth required. Public data.
"""

import httpx
from datetime import datetime

SNB_BASE = "https://data.snb.ch"
HEADERS  = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept":     "application/json, text/csv, */*",
}

_CACHE: dict = {}
_CACHE_TTL   = 3600 * 6  # 6 hours


def _fetch(warehouse: str, lang: str = "en", fmt: str = "json") -> dict:
    """Fetch from SNB warehouse. URL: /en/warehouse/BSTA/json"""
    key = f"{warehouse}_{fmt}"
    if key in _CACHE:
        entry = _CACHE[key]
        if (datetime.utcnow() - entry["ts"]).seconds < _CACHE_TTL:
            return entry["data"]

    url = f"{SNB_BASE}/{lang}/warehouse/{warehouse}/{fmt}"
    try:
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        if r.status_code == 200:
            data = r.json() if fmt == "json" else {"raw": r.text, "ok": True}
            _CACHE[key] = {"data": data, "ts": datetime.utcnow()}
            return data
        print(f"[snb] {warehouse}: HTTP {r.status_code} — {r.text[:100]}")
    except Exception as e:
        print(f"[snb] {warehouse} error: {e}")
    return {}


def enrich_counterparty(slug: str, display_name: str = "", jurisdiction: str = "CH") -> dict:
    """
    Fetch SNB statistics for a Swiss bank.
    Returns sector benchmark data — individual bank data is not
    published separately for banks below CHF 10B total assets.
    """
    if jurisdiction not in ("CH", "Switzerland", "Schweiz", "Suisse"):
        return {"source": "snb", "available": False, "reason": "not_swiss"}

    result = {
        "source":     "snb",
        "available":  False,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Try banking statistics (BSTA)
    bsta = _fetch("BSTA")
    if not bsta:
        # Try CSV as fallback
        bsta = _fetch("BSTA", fmt="csv")
        if bsta.get("ok"):
            result["available"]   = True
            result["data_type"]   = "sector_csv"
            result["note"]        = f"SNB BSTA sector data available (CSV). {display_name} included in aggregate."
            return result
        return result

    result["available"] = True
    result["data_type"] = "sector_aggregate"

    # Parse the JSON structure — SNB wraps data in various ways
    # Try observations array
    obs = (bsta.get("observations") or bsta.get("data") or
           bsta.get("timeSeries") or bsta.get("rows") or [])

    if isinstance(obs, list) and obs:
        latest = obs[-1] if isinstance(obs[-1], dict) else {}
        val = latest.get("value") or latest.get("v") or latest.get("val")
        if val:
            try:
                result["sector_total_assets_chf_bn"] = round(float(val) / 1000, 1)
            except Exception:
                result["sector_total_assets_raw"] = val
        result["sector_as_of"] = latest.get("date") or latest.get("d") or latest.get("period")
    elif isinstance(bsta, dict):
        # Top-level values
        for k in ("totalAssets", "total_assets", "balanceSheet"):
            if bsta.get(k):
                result["sector_total_assets_raw"] = bsta[k]
                break

    # Capital adequacy
    cap = _fetch("BSEIG")
    if cap:
        cap_obs = cap.get("observations") or cap.get("data") or []
        if isinstance(cap_obs, list) and cap_obs:
            latest = cap_obs[-1] if isinstance(cap_obs[-1], dict) else {}
            val = latest.get("value") or latest.get("v")
            if val:
                try:
                    result["sector_capital_ratio_pct"] = round(float(val), 2)
                except Exception:
                    pass

    result["note"] = (
        f"{display_name} is a FINMA-supervised bank included in Swiss banking sector "
        f"aggregate (BSTA). Individual bank data is not separately published by SNB "
        f"for institutions below CHF 10B total assets threshold."
    )

    return result
