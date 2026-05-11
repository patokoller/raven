"""
Raven — Zefix Swiss Commercial Register Data Provider
Federal Commercial Registry Office (EHRA/FCRO)
Base URL: https://www.zefix.admin.ch/ZefixPublicREST/api/v1

Authentication: HTTP Basic Auth (username + password)
Data: All legally registered Swiss companies, daily updated.

What this provides for scoring:
- Registration status (active/liquidation/deleted) → license_active
- Legal form (AG, GmbH, Stiftung, Genossenschaft) → entity validation
- Registration date → years_in_operation
- Purpose/Zweck → business activity confirmation
- SOGC publications → recent changes, capital changes, leadership changes
- Registered office / canton → jurisdiction confirmation
- UID (CHE-xxx) → authoritative Swiss company identifier

Relevant counterparties in Raven registry:
- taurus        → Taurus Group SA (CHE-XXX)
- metaco        → METACO SA (CHE-XXX)
- bitcoin-suisse → Bitcoin Suisse AG (CHE-XXX)
- sygnum        → Sygnum Bank AG (CHE-XXX)
- seba-bank     → SEBA Bank AG (CHE-XXX)
- maerki-baumann → Maerki Baumann & Co. AG (CHE-XXX)
- bbva-digital  → BBVA subsidiary (partial — Spanish domicile)
"""

import httpx
from typing import Optional
from datetime import datetime, date
from app.core.config import settings

ZEFIX_BASE = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"

# Known UIDs for our Swiss counterparties (saves a search call)
# Format: CHE-xxx.xxx.xxx
UID_MAP = {
    "taurus":         "CHE-215.326.827",
    "bitcoin-suisse": "CHE-184.974.020",
    "sygnum":         "CHE-440.296.842",
    "seba-bank":      "CHE-222.926.907",
    "maerki-baumann": "CHE-105.913.367",
    "metaco":         None,   # search by name
}

# Legal form codes → human readable + risk relevance
LEGAL_FORMS = {
    "0020": ("Einzelfirma", "sole_proprietorship"),
    "0030": ("Kollektivgesellschaft", "general_partnership"),
    "0040": ("Kommanditgesellschaft", "limited_partnership"),
    "0100": ("Aktiengesellschaft (AG)", "joint_stock"),          # most common
    "0101": ("Kommandit-Aktiengesellschaft", "partnership_ltd"),
    "0107": ("Gesellschaft mit beschränkter Haftung (GmbH)", "gmbh"),
    "0108": ("Genossenschaft", "cooperative"),
    "0109": ("Verein", "association"),
    "0110": ("Stiftung", "foundation"),
    "0130": ("Institut des öffentlichen Rechts", "public_law"),
    "0150": ("Zweigniederlassung (ausländisch)", "foreign_branch"),
}


def _auth():
    """Return Basic Auth credentials tuple, or None if not configured."""
    if settings.ZEFIX_USERNAME and settings.ZEFIX_PASSWORD:
        return (settings.ZEFIX_USERNAME, settings.ZEFIX_PASSWORD)
    return None


def _headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def search_company(name: str, active_only: bool = True) -> list:
    """
    Search for a Swiss company by name.
    Returns list of matching companies with basic info.
    """
    try:
        r = httpx.post(
            f"{ZEFIX_BASE}/company/search",
            auth=_auth(),
            headers=_headers(),
            json={
                "name":       name,
                "activeOnly": active_only,
                "maxEntries": 5,
            },
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json()
            # Handle both list response and dict with 'list' key
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("list", data.get("items", data.get("results", [])))
            return []
        elif r.status_code == 401:
            print("[zefix] Authentication failed — check ZEFIX_USERNAME/PASSWORD secrets in Fly.io")
        else:
            print(f"[zefix] Search error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[zefix] Search exception for '{name}': {e}")
    return []


def get_company_by_uid(uid: str) -> Optional[dict]:
    """
    Fetch full company details by UID (CHE-xxx.xxx.xxx format).
    Returns complete company record.
    """
    # Zefix accepts CHE-XXX.XXX.XXX format directly
    uid_formatted = uid if uid.startswith("CHE-") else f"CHE-{uid}"
    # Also prepare numeric-only version
    uid_numeric = uid.replace("CHE-", "").replace(".", "").strip()

    # Try formatted version first (CHE-184.974.020)
    urls_to_try = [
        f"{ZEFIX_BASE}/company/uid/{uid_formatted}",
        f"{ZEFIX_BASE}/company/uid/CHE{uid_numeric}",
    ]

    auth = _auth()
    for url in urls_to_try:
        # Try without auth first (UID lookup is public on Zefix)
        # then with auth if credentials available
        for attempt_auth in ([None, auth] if auth else [None]):
            try:
                r = httpx.get(url, auth=attempt_auth, headers=_headers(), timeout=12)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        return data[0] if data else None
                    return data
                elif r.status_code == 401:
                    if attempt_auth is None and auth:
                        continue  # retry with auth
                    print(f"[zefix] Auth failed for {url}")
                    break
                elif r.status_code == 404:
                    break  # try next URL format
            except Exception as e:
                print(f"[zefix] UID lookup error {url}: {e}")
                break

    print(f"[zefix] UID {uid} not found")
    return None


def get_company_publications(uid: str, limit: int = 10) -> list:
    """
    Get recent SOGC publications for a company.
    Publications include capital changes, board changes, liquidations, purpose changes.
    """
    uid_clean = uid.replace("CHE-", "").replace(".", "").strip()
    try:
        r = httpx.get(
            f"{ZEFIX_BASE}/company/uid/CHE{uid_clean}/shab",
            auth=_auth(),
            headers=_headers(),
            params={"limit": limit},
            timeout=12,
        )
        if r.status_code == 200:
            return r.json() if isinstance(r.json(), list) else r.json().get("list", [])
    except Exception as e:
        print(f"[zefix] Publications error: {e}")
    return []


def _parse_company_data(company: dict) -> dict:
    """
    Parse a Zefix company record into Raven scoring fields.
    """
    result = {
        "source":    "zefix",
        "available": True,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Registration status
    status = (company.get("status") or "").lower()
    is_active = status in ("active", "aktiv", "actif", "attivo", "")
    in_liquidation = "liquid" in status or "aufgelöst" in status
    result["license_active"]    = is_active and not in_liquidation
    result["in_liquidation"]    = in_liquidation
    result["registration_status"] = status

    # Legal form
    lf_code = company.get("legalForm", {})
    if isinstance(lf_code, dict):
        lf_code = lf_code.get("id", "")
    lf_info = LEGAL_FORMS.get(str(lf_code), (str(lf_code), "unknown"))
    result["legal_form"]      = lf_info[0]
    result["legal_form_type"] = lf_info[1]

    # Registration date → years in operation
    reg_date = company.get("registrationDate") or company.get("foundationDate")
    if reg_date:
        try:
            if isinstance(reg_date, str):
                d = datetime.strptime(reg_date[:10], "%Y-%m-%d").date()
            else:
                d = date.fromisoformat(str(reg_date))
            years = (date.today() - d).days // 365
            result["years_in_operation"] = years
            result["registration_date"]  = str(d)
        except Exception:
            pass

    # Legal names
    result["legal_name_de"] = company.get("name") or company.get("firma")
    names = company.get("translations", {})
    if names:
        result["legal_name_fr"] = names.get("fr")
        result["legal_name_en"] = names.get("en")

    # UID (authoritative identifier)
    result["uid"]  = company.get("uid") or company.get("chid")
    result["chid"] = company.get("chid")

    # Registered office
    seat = company.get("seat") or company.get("sitz") or ""
    result["registered_office"] = seat
    result["canton"] = company.get("canton") or (seat[:2] if len(seat) >= 2 else "")

    # Purpose / business activity
    purpose = company.get("purpose") or company.get("zweck") or ""
    result["business_purpose"] = purpose[:300] if purpose else None

    # Capital (if disclosed)
    capital = company.get("capital") or company.get("kapital")
    if capital:
        result["share_capital"] = capital

    # Registry link
    if result.get("uid"):
        uid_num = result["uid"].replace("CHE-","").replace(".","")
        result["registry_url"] = f"https://www.zefix.admin.ch/en/search/entity/list/firm/{uid_num}"

    return result


def _analyse_publications(publications: list) -> dict:
    """
    Analyse recent SOGC publications for risk signals.
    Returns flags for leadership changes, capital changes, liquidation proceedings.
    """
    result = {
        "publication_count_12m": 0,
        "has_liquidation_publication": False,
        "has_capital_change": False,
        "has_purpose_change": False,
        "has_leadership_change": False,
    }

    if not publications:
        return result

    cutoff = datetime.utcnow().timestamp() - (365 * 24 * 3600)
    recent = []
    for pub in publications:
        pub_date = pub.get("publicationDate") or pub.get("datum") or ""
        try:
            pd = datetime.strptime(pub_date[:10], "%Y-%m-%d").timestamp()
            if pd >= cutoff:
                recent.append(pub)
        except Exception:
            recent.append(pub)

    result["publication_count_12m"] = len(recent)

    for pub in recent:
        text = (pub.get("text") or pub.get("content") or "").lower()
        rubric = (pub.get("rubric") or "").lower()

        if any(k in text + rubric for k in ["liquidation", "aufgelöst", "dissolution", "liquidé"]):
            result["has_liquidation_publication"] = True
        if any(k in text + rubric for k in ["kapital", "capital", "aktienkapital"]):
            result["has_capital_change"] = True
        if any(k in text + rubric for k in ["zweck", "purpose", "but social"]):
            result["has_purpose_change"] = True
        if any(k in text + rubric for k in ["verwaltungsrat", "geschäftsführer", "director", "board"]):
            result["has_leadership_change"] = True

    return result


def enrich_counterparty(slug: str, display_name: str = "") -> dict:
    """
    Main entry point. Returns enrichment data for a Swiss counterparty.
    Tries known UID first, falls back to search by name.
    """
    # Try known UID
    uid = UID_MAP.get(slug)
    company = None

    if uid:
        company = get_company_by_uid(uid)

    # Fall back to search by display name
    if not company and display_name:
        results = search_company(display_name)
        if results:
            # Pick first exact or best match
            for r in results:
                name = (r.get("name") or r.get("firma") or "").lower()
                if display_name.lower() in name or name in display_name.lower():
                    company = r
                    break
            if not company:
                company = results[0]

    if not company:
        return {"source": "zefix", "available": False, "slug": slug}

    result = _parse_company_data(company)

    # Get SOGC publications for risk signals
    if result.get("uid"):
        publications = get_company_publications(result["uid"])
        pub_analysis = _analyse_publications(publications)
        result.update(pub_analysis)

        # Set enforcement proxy based on liquidation publication
        if pub_analysis["has_liquidation_publication"]:
            result["license_active"] = False
            result["enforcement_actions_12m"] = 1

    return result
