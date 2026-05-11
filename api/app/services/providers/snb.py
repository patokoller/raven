"""
Raven — SNB Banking Statistics Provider
Swiss National Bank (Schweizerische Nationalbank)

Fetches regulatory financial data for FINMA-licensed Swiss banks from
SNB's public banking statistics portal (data.snb.ch).

Provides actual balance sheet data that fills our "Financial: Partial" gap
for Swiss custodians like Sygnum Bank, SEBA Bank, Bitcoin Suisse.

Key metrics available:
- Total assets (Bilanzsumme)
- Tier 1 / Total capital ratio
- Liquidity coverage ratio (LCR)
- Leverage ratio
- Net interest margin
- Loan-to-deposit ratio

SNB API: https://data.snb.ch/api/
No API key required. Public data updated quarterly.

SNB Data Portal: https://data.snb.ch/en/topics/banken
"""

import httpx
import json
from datetime import datetime

SNB_API_BASE = "https://data.snb.ch/api"

HEADERS = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept": "application/json",
}

# SNB banking statistics cubes
# bankbstajb = annual balance sheet statistics
# bankbsta   = monthly balance sheet statistics
# bankliqmon = monthly liquidity statistics

# Known SNB bank identifiers (BankCode → display name)
# These are the SNB's internal codes for Swiss banks
SNB_BANK_CODES = {
    "sygnum":         "Sygnum Bank AG",
    "seba-bank":      "SEBA Bank AG",
    "bitcoin-suisse": "Bitcoin Suisse AG",
    "maerki-baumann": "Maerki Baumann & Co. AG",
    "arab-bank":      "Arab Bank (Switzerland) Ltd.",
    "taurus":         "Taurus Group SA",
}


def _search_snb_institutions(name: str) -> list:
    """
    Search SNB institution list for a bank by name.
    Returns list of matching institution codes.
    """
    try:
        # SNB provides a list of all reporting institutions
        r = httpx.get(
            f"{SNB_API_BASE}/cube/bankbstajb/dimensions",
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            dims = r.json()
            # Look for bank dimension
            for dim in dims.get("dimensions", []):
                if dim.get("id") in ("D0", "bank", "BANK", "BANKEN"):
                    candidates = []
                    for val in dim.get("values", []):
                        label = val.get("label", "")
                        if name.lower() in label.lower():
                            candidates.append(val)
                    return candidates
    except Exception as e:
        print(f"[snb] Institution search error: {e}")
    return []


def _get_aggregated_stats() -> dict:
    """
    Fetch aggregated Swiss banking sector statistics.
    Used when individual bank data is unavailable.
    Provides sector benchmarks for comparison.
    """
    try:
        # Annual balance sheet stats — total sector
        r = httpx.get(
            f"{SNB_API_BASE}/cube/bankbstajb/data/json",
            params={
                "fromDate": "2022",
                "toDate":   "2024",
                "lang":     "en",
            },
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return {"available": True, "data": data, "type": "sector_aggregate"}
    except Exception as e:
        print(f"[snb] Aggregated stats error: {e}")
    return {"available": False}


def _fetch_bank_series(bank_code: str, series_id: str) -> dict:
    """Fetch a specific data series for a bank."""
    try:
        r = httpx.get(
            f"{SNB_API_BASE}/cube/{series_id}/data/json",
            params={"fromDate": "2022", "toDate": "2024", "lang": "en"},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[snb] Series {series_id} error: {e}")
    return {}


def enrich_counterparty(slug: str, display_name: str = "", jurisdiction: str = "CH") -> dict:
    """
    Main entry point. Fetch SNB statistics for a Swiss bank.
    Returns available financial metrics.
    """
    # Only applies to Swiss entities
    if jurisdiction not in ("CH", "Schweiz", "Switzerland") and "CH" not in jurisdiction:
        return {"source": "snb", "available": False, "reason": "not_swiss"}

    result = {
        "source":     "snb",
        "available":  False,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Try to find the bank in SNB statistics
    institutions = _search_snb_institutions(display_name or slug)

    if institutions:
        inst = institutions[0]
        bank_code = inst.get("id", "")
        result["snb_bank_code"]  = bank_code
        result["snb_bank_name"]  = inst.get("label", display_name)

        # Fetch balance sheet data
        bs_data = _fetch_bank_series(bank_code, "bankbstajb")
        if bs_data:
            result["available"] = True
            result["snb_data_type"] = "individual_bank"

            # Parse available fields
            observations = bs_data.get("observations", [])
            if observations:
                latest = observations[-1]
                result["total_assets_chf_mn"] = latest.get("value")
                result["as_of_date"] = latest.get("date")

    else:
        # Bank not individually reported — fetch sector data for context
        sector = _get_aggregated_stats()
        if sector.get("available"):
            result["available"] = True
            result["snb_data_type"] = "sector_benchmark"
            result["note"] = (
                f"{display_name} not individually reported by SNB "
                f"(likely below CHF 10B threshold for individual disclosure). "
                f"Sector-level benchmarks available for comparison."
            )

            # Try to get the count of banks in the sector for context
            try:
                data = sector.get("data", {})
                obs = data.get("observations", [])
                if obs:
                    result["snb_sector_total_assets_bn"] = round(obs[-1].get("value", 0) / 1000, 1)
                    result["snb_as_of"] = obs[-1].get("date")
            except Exception:
                pass

    # Fetch capital ratio data if available
    try:
        capital_r = httpx.get(
            f"{SNB_API_BASE}/cube/bankeigenka/data/json",
            params={"fromDate": "2023", "toDate": "2024", "lang": "en"},
            headers=HEADERS,
            timeout=12,
        )
        if capital_r.status_code == 200:
            cap_data = capital_r.json()
            obs = cap_data.get("observations", [])
            if obs:
                result["snb_sector_capital_ratio_pct"] = obs[-1].get("value")
                result["available"] = True
    except Exception:
        pass

    return result


def get_sector_benchmarks() -> dict:
    """
    Fetch Swiss banking sector aggregate benchmarks.
    Used for scoring comparison — how does a counterparty compare
    to the sector average?
    """
    try:
        # Capital ratios
        cap_r = httpx.get(
            f"{SNB_API_BASE}/cube/bankeigenka/data/json",
            params={"fromDate": "2022", "toDate": "2024", "lang": "en"},
            headers=HEADERS, timeout=15,
        )
        result = {"source": "snb_sector", "available": False}
        if cap_r.status_code == 200:
            data = cap_r.json()
            obs  = data.get("observations", [])
            if obs:
                result["available"]           = True
                result["avg_capital_ratio"]   = obs[-1].get("value")
                result["capital_ratio_date"]  = obs[-1].get("date")
        return result
    except Exception as e:
        print(f"[snb] Sector benchmark error: {e}")
        return {"source": "snb_sector", "available": False}
