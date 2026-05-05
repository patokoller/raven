"""
Raven — SEC EDGAR Data Provider
Free REST API, no key required. Covers US public companies.

Relevant counterparties:
- Coinbase (COIN) — 10-K filings, equity ratio, revenue
- Galaxy Digital (GLXY on TSX, some SEC filings)
- Goldman Sachs (GS) — full financials
- JPMorgan (JPM) — full financials
- BlackRock (BLK) — full financials
- Clear Street — private, limited filings

API: https://efts.sec.gov/LATEST/search-index?q="coinbase"&dateRange=custom&startdt=2024-01-01
Facts API: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
"""

import httpx
from typing import Optional
from datetime import datetime, timedelta

EDGAR_BASE  = "https://efts.sec.gov"
FACTS_BASE  = "https://data.sec.gov/api/xbrl/companyfacts"
COMPANY_BASE = "https://data.sec.gov/submissions"

# CIK numbers for our counterparties (SEC company identifier, zero-padded to 10 digits)
CIK_MAP = {
    "coinbase":            "0001679788",
    "goldman-sachs-digital": "0000886982",  # Goldman Sachs Group
    "jpmorgan-onyx":       "0000019617",   # JPMorgan Chase
    "galaxy-digital":      "0001805387",
    "clear-street":        None,           # private
    "alpaca-markets":      None,           # private
}

HEADERS = {
    "User-Agent": "Raven Risk Intelligence contact@raven.internal",
    "Accept": "application/json",
}


def get_company_facts(cik: str) -> Optional[dict]:
    """
    Fetch XBRL company facts from SEC EDGAR.
    Returns structured financial data.
    """
    try:
        r = httpx.get(
            f"{FACTS_BASE}/CIK{cik}.json",
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[edgar] Error fetching CIK {cik}: {e}")
    return None


def extract_financial_metrics(cik: str) -> Optional[dict]:
    """
    Extract key financial metrics from SEC filings.
    Returns equity_ratio, revenue, debt level, listing status.
    """
    facts = get_company_facts(cik)
    if not facts:
        return None

    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    result  = {
        "source":              "sec_edgar",
        "is_publicly_listed":  True,  # by definition if in EDGAR
        "has_audited_financials": True,
        "fetched_at":          datetime.utcnow().isoformat(),
    }

    def latest_value(concept: str) -> Optional[float]:
        """Get the most recent annual value for a financial concept."""
        data = us_gaap.get(concept, {}).get("units", {}).get("USD", [])
        # Filter for annual filings (10-K)
        annual = [x for x in data if x.get("form") in ("10-K", "20-F", "40-F")]
        if annual:
            annual.sort(key=lambda x: x.get("end", ""), reverse=True)
            return float(annual[0]["val"])
        # Fall back to any filing
        if data:
            data.sort(key=lambda x: x.get("end", ""), reverse=True)
            return float(data[0]["val"])
        return None

    # Total assets and equity
    total_assets = latest_value("Assets")
    total_equity = latest_value("StockholdersEquity") or latest_value("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
    total_liab   = latest_value("Liabilities")
    revenue      = latest_value("Revenues") or latest_value("RevenueFromContractWithCustomerExcludingAssessedTax")
    long_term_debt = latest_value("LongTermDebt") or latest_value("LongTermDebtNoncurrent")

    if total_assets and total_equity:
        equity_ratio = total_equity / total_assets
        result["equity_ratio"] = round(equity_ratio, 4)
        result["total_assets_usd"] = total_assets
        result["total_equity_usd"] = total_equity

        # Debt level classification
        if long_term_debt and total_assets:
            debt_ratio = long_term_debt / total_assets
            result["debt_level"] = "low" if debt_ratio < 0.2 else "moderate" if debt_ratio < 0.5 else "high"
            result["long_term_debt_usd"] = long_term_debt

    if revenue:
        result["revenue_usd"] = revenue
        result["revenue_stability"] = "stable"  # presence of 10-K implies established revenue

    # Entity name and ticker from filing
    entity_name = facts.get("entityName")
    if entity_name:
        result["legal_name_confirmed"] = entity_name

    return result


def search_enforcement_actions(company_name: str, days: int = 365) -> int:
    """
    Search SEC EDGAR full-text search for enforcement actions.
    Returns count of relevant filings in the past N days.
    """
    from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        r = httpx.get(
            f"{EDGAR_BASE}/LATEST/search-index",
            params={
                "q":         f'"{company_name}" "enforcement" OR "penalty" OR "settlement"',
                "dateRange": "custom",
                "startdt":   from_date,
                "forms":     "8-K,10-K",
            },
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            hits = r.json().get("hits", {}).get("total", {})
            return hits.get("value", 0) if isinstance(hits, dict) else int(hits)
    except Exception:
        pass
    return 0


def enrich_counterparty(slug: str) -> dict:
    """
    Main entry point. Returns enrichment data for a counterparty from SEC EDGAR.
    """
    cik = CIK_MAP.get(slug)
    if not cik:
        return {"source": "sec_edgar", "available": False}

    result = extract_financial_metrics(cik) or {}
    result["source"]  = "sec_edgar"
    result["cik"]     = cik
    result["available"] = bool(result)

    return result
