"""
Raven — EBA Register of Institutions Provider
European Banking Authority

The EBA maintains the authoritative register of EU/EEA-licensed credit institutions,
investment firms, payment institutions, and e-money institutions.

For European counterparties (DE, FR, LU, IE, NL, etc.) this is the equivalent
of FINMA for Swiss entities — the ground truth for regulatory standing.

EBA also publishes:
- Capital Requirements Regulation (CRR) compliance data
- Pillar 3 transparency data for large institutions
- Supervisory convergence data

API: https://registers.eba.europa.eu/solrweb/
No API key required. Public register.

EBA EUCLID: https://euclid.eba.europa.eu/register/
"""

import httpx
import json
from datetime import datetime

EBA_SOLR_API   = "https://registers.eba.europa.eu/solrweb/public/institution/search"
EBA_EUCLID_API = "https://euclid.eba.europa.eu/register/api/v1"
EBA_BASE       = "https://registers.eba.europa.eu"

HEADERS = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept":     "application/json",
}

# EU/EEA jurisdictions covered by EBA
EBA_JURISDICTIONS = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU",
    "MT", "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}

INSTITUTION_TYPE_MAP = {
    "CI":  "Credit Institution",
    "IF":  "Investment Firm",
    "PI":  "Payment Institution",
    "EMI": "E-Money Institution",
    "CCP": "Central Counterparty",
    "CSD": "Central Securities Depository",
}


def _search_eba_register(name: str, jurisdiction: str = None) -> list:
    """
    Search EBA register by institution name.
    Returns list of matching institutions.
    """
    params = {
        "q":            name,
        "rows":         10,
        "wt":           "json",
    }
    if jurisdiction:
        params["fq"] = f"countryCode:{jurisdiction}"

    # Try EBA Solr search endpoint
    try:
        r = httpx.get(
            EBA_SOLR_API,
            params=params,
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            docs = (data.get("response") or {}).get("docs", [])
            return docs
    except Exception as e:
        print(f"[eba] Solr search error: {e}")

    # Try EUCLID API
    try:
        r2 = httpx.get(
            f"{EBA_EUCLID_API}/CRD/institutions",
            params={
                "institutionName": name,
                "countryCode":     jurisdiction or "",
                "pageSize":        10,
                "pageNumber":      1,
            },
            headers=HEADERS,
            timeout=15,
        )
        if r2.status_code == 200:
            data2 = r2.json()
            return data2.get("items", data2.get("data", []))
    except Exception as e:
        print(f"[eba] EUCLID search error: {e}")

    return []


def _parse_eba_record(record: dict) -> dict:
    """Parse EBA institution record into Raven scoring fields."""
    result = {
        "source":     "eba",
        "available":  True,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Status — EBA uses "Authorised", "Withdrawn", "Rejected"
    status = (
        record.get("status") or
        record.get("authorisationStatus") or
        record.get("institutionStatus") or ""
    ).lower()

    active_statuses = ("authorised", "active", "registered")
    result["license_active"] = any(s in status for s in active_statuses)
    result["eba_status"]     = status

    # Institution type
    inst_type = record.get("institutionType") or record.get("type") or record.get("typeCode", "")
    result["eba_institution_type"] = INSTITUTION_TYPE_MAP.get(
        str(inst_type).upper(), str(inst_type)
    )

    # Jurisdiction / home member state
    result["eba_home_member_state"] = (
        record.get("countryCode") or
        record.get("homeCountry") or
        record.get("jurisdiction")
    )

    # Legal name
    result["eba_legal_name"] = (
        record.get("institutionName") or
        record.get("name") or
        record.get("legalName")
    )

    # LEI (Legal Entity Identifier)
    lei = record.get("lei") or record.get("legalEntityIdentifier")
    if lei:
        result["lei"] = lei

    # Authorisation date
    auth_date = record.get("authorisationDate") or record.get("licenceDate")
    if auth_date:
        result["eba_auth_date"] = str(auth_date)[:10]
        try:
            d = datetime.strptime(str(auth_date)[:10], "%Y-%m-%d")
            result["years_regulated"] = (datetime.utcnow() - d).days // 365
        except Exception:
            pass

    # EBA register URL
    inst_id = record.get("institutionId") or record.get("id") or record.get("eba_id")
    if inst_id:
        result["eba_url"] = f"{EBA_BASE}/solrweb/public/institution/{inst_id}"

    # Enforcement / supervisory measures
    measures = record.get("supervisoryMeasures") or record.get("measures") or []
    if isinstance(measures, list) and measures:
        result["enforcement_actions_12m"] = len(measures)
        result["eba_supervisory_measures"] = measures

    return result


def enrich_counterparty(slug: str, display_name: str = "", jurisdiction: str = "") -> dict:
    """
    Main entry point. Fetch EBA register data for a European institution.
    """
    # Only applies to EU/EEA entities
    if jurisdiction and jurisdiction.upper() not in EBA_JURISDICTIONS:
        return {
            "source": "eba", "available": False,
            "reason": "not_eu_eea",
            "jurisdiction": jurisdiction,
        }

    # Try searching by display name
    records = _search_eba_register(display_name or slug, jurisdiction or None)

    if not records:
        # Try first word of name (handles "Deutsche Bank AG" → "Deutsche")
        first_word = (display_name or slug).split()[0] if display_name or slug else ""
        if len(first_word) >= 4:
            records = _search_eba_register(first_word, jurisdiction or None)

    if not records:
        return {
            "source":     "eba",
            "available":  False,
            "reason":     "not_found",
            "searched":   display_name or slug,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    # Best match: name contains our search term
    name_lower = (display_name or slug).lower()
    best = None
    for r in records:
        r_name = (
            r.get("institutionName") or
            r.get("name") or
            r.get("legalName") or ""
        ).lower()
        if name_lower in r_name or r_name in name_lower:
            best = r
            break
    if not best:
        best = records[0]

    return _parse_eba_record(best)
