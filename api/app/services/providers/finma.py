"""
Raven — FINMA Supervised Institutions Provider
Swiss Financial Market Supervisory Authority

Scrapes the FINMA public supervised institutions list to confirm:
- Exact licence type (banking licence, securities firm, asset manager,
  fintech licence, DLT trading venue)
- Supervision status (active, withdrawn, revoked, expired)
- Licence grant date
- Licence conditions

No API key required. Public data from finma.ch.

Search endpoint: https://www.finma.ch/en/authorisation/supervised-institutions/
API: https://www.finma.ch/api/supervised-institutions (internal JSON API)

Relevant counterparties:
- Sygnum Bank AG       → banking licence
- SEBA Bank AG         → banking licence
- Bitcoin Suisse AG    → SRO/securities dealer
- Taurus Group SA      → securities firm
- Maerki Baumann       → banking licence (private bank)
- Bitcoin Suisse       → ARIF/VQF SRO member
"""

import httpx
from typing import Optional
from datetime import datetime

# FINMA uses an internal JSON API on their website
FINMA_SEARCH = "https://www.finma.ch/api/supervised-institutions"
FINMA_BASE   = "https://www.finma.ch"

HEADERS = {
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent":      "Raven Risk Intelligence / contact@raven.internal",
    "Referer":         "https://www.finma.ch/en/authorisation/supervised-institutions/",
}

# Licence category mappings (FINMA category codes → human readable)
LICENCE_CATEGORIES = {
    "bank":              "Banking Licence",
    "bank_fintech":      "Fintech Licence (Banking Act Art. 1b)",
    "securities_firm":   "Securities Firm Licence",
    "asset_manager":     "Asset Manager Licence",
    "fund_management":   "Fund Management Company Licence",
    "insurance":         "Insurance Licence",
    "dlt_trading":       "DLT Trading Venue Licence",
    "sro":               "Self-Regulatory Organisation",
    "cis":               "Collective Investment Schemes",
}

# Known FINMA entity IDs for our counterparties (avoids search)
FINMA_ID_MAP = {
    "sygnum":         None,  # search by name
    "seba-bank":      None,
    "bitcoin-suisse": None,
    "taurus":         None,
    "maerki-baumann": None,
}


def search_institution(name: str, lang: str = "en") -> list:
    """
    Search FINMA supervised institutions by name.
    Returns list of matching institutions.
    """
    try:
        r = httpx.get(
            FINMA_SEARCH,
            params={
                "name":     name,
                "lang":     lang,
                "maxItems": 10,
            },
            headers=HEADERS,
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json()
            # FINMA returns either a list or a dict with 'items'
            if isinstance(data, list):
                return data
            return data.get("items", data.get("results", []))
        # Try alternative URL format
        r2 = httpx.get(
            f"{FINMA_BASE}/en/authorisation/supervised-institutions/",
            params={"name": name, "format": "json"},
            headers=HEADERS,
            timeout=12,
        )
        if r2.status_code == 200:
            try:
                return r2.json()
            except Exception:
                pass
    except Exception as e:
        print(f"[finma] Search error for '{name}': {e}")
    return []


def get_institution_detail(finma_id: str) -> Optional[dict]:
    """Fetch detailed record for a specific FINMA entity ID."""
    try:
        r = httpx.get(
            f"{FINMA_SEARCH}/{finma_id}",
            headers=HEADERS,
            timeout=12,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[finma] Detail error for {finma_id}: {e}")
    return None


def _parse_institution(record: dict) -> dict:
    """Parse a FINMA institution record into Raven scoring fields."""
    result = {
        "source":    "finma",
        "available": True,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Status
    status = (
        record.get("status") or
        record.get("Status") or
        record.get("authorisationStatus") or ""
    ).lower()

    active_statuses = ("authorised", "active", "bewilligt", "autorisé", "autorizzato")
    result["license_active"]  = any(s in status for s in active_statuses)
    result["finma_status"]    = status

    # Licence type
    category = (
        record.get("category") or
        record.get("licenceCategory") or
        record.get("authorisationType") or
        record.get("type") or ""
    )
    result["finma_licence_type"] = LICENCE_CATEGORIES.get(
        category.lower().replace(" ", "_"),
        category
    )
    result["finma_category_raw"] = category

    # Licence grant date → years in operation (as regulated entity)
    for date_field in ("authorisationDate", "licenceDate", "grantDate", "since"):
        date_val = record.get(date_field)
        if date_val:
            try:
                d = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
                result["licence_granted_date"] = str(d.date())
                # Don't override years_in_operation from Zefix (founding date is earlier)
                result["years_regulated"] = (datetime.utcnow() - d).days // 365
            except Exception:
                pass
            break

    # Legal name and address
    result["finma_legal_name"] = (
        record.get("name") or
        record.get("firmName") or
        record.get("legalName")
    )
    result["finma_domicile"] = record.get("domicile") or record.get("city")

    # FINMA profile link
    finma_id = record.get("id") or record.get("entityId")
    if finma_id:
        result["finma_url"] = f"https://www.finma.ch/en/authorisation/supervised-institutions/supervised-institutions-detail/?institutionId={finma_id}"

    # Conditions / restrictions
    conditions = record.get("conditions") or record.get("requirements") or []
    result["has_finma_conditions"] = bool(conditions)
    if conditions:
        result["enforcement_actions_12m"] = 1  # conservative proxy

    return result



def enrich_counterparty(slug: str, display_name: str = "") -> dict:
    """
    Main entry point. Returns FINMA data for a Swiss counterparty.
    Uses Claude web search since FINMA blocks direct API access (403).
    Falls back to enrichment_data if already cached.
    """
    from anthropic import Anthropic
    import os, json as _json

    try:
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        prompt = f"""Search for FINMA (Swiss Financial Market Supervisory Authority) regulatory information for: {display_name}

Find:
1. Is this entity currently FINMA-supervised? (yes/no)
2. What type of FINMA licence do they hold? (banking licence, securities firm, asset manager, fintech, DLT trading venue, etc.)
3. Is the licence currently active?
4. Any recent enforcement actions or conditions (last 12 months)?
5. Approximate year licence was granted

Check: https://www.finma.ch/en/authorisation/supervised-institutions/

Respond ONLY with valid JSON:
{{"supervised": true/false, "licence_type": "string", "licence_active": true/false, "enforcement_actions_12m": 0, "licence_year": null, "finma_url": "string or null", "notes": "string"}}"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw += block.text

        # Parse JSON
        import re as _re
        match = _re.search(r"\{[^{}]+\}", raw, _re.DOTALL)
        if match:
            data = _json.loads(match.group())
            result = {
                "source":    "finma_websearch",
                "available": data.get("supervised", False),
                "fetched_at": datetime.utcnow().isoformat(),
            }
            if data.get("supervised"):
                result["license_active"]      = data.get("licence_active", True)
                result["finma_licence_type"]  = data.get("licence_type", "")
                result["enforcement_actions_12m"] = data.get("enforcement_actions_12m", 0)
                result["finma_url"]           = data.get("finma_url")
                result["finma_notes"]         = data.get("notes")
                if data.get("licence_year"):
                    result["years_regulated"] = datetime.utcnow().year - int(data["licence_year"])
            return result
    except Exception as e:
        print(f"[finma] Web search error for {display_name}: {e}")

    # If all fails, try legacy HTTP search
    results = search_institution(display_name) if display_name else []
    if not results and display_name:
        results = search_institution(display_name.split()[0])

    if results:
        for r in results:
            r_name = (r.get("name") or r.get("firmName") or "").lower()
            if display_name.lower() in r_name or r_name in display_name.lower():
                return _parse_institution(r)
        return _parse_institution(results[0])

    return {"source": "finma", "available": False, "slug": slug, "reason": "not_found"}
