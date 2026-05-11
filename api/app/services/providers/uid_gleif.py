"""
Raven — Swiss UID Register + GLEIF LEI Provider

1. Swiss UID Register (uid.admin.ch)
   Provides: company registration number, VAT status, legal form, activity status
   API: https://www.uid.admin.ch/app/json/search (POST)
   No auth required.

2. GLEIF Global LEI Register (gleif.org)
   Provides: Legal Entity Identifier, registration status, jurisdiction
   API: https://api.gleif.org/api/v1/lei-records
   No auth required. Public REST API (JSON:API spec).
   Docs: https://documenter.getpostman.com/view/7679680/SVYrrxuU
"""

import httpx
from typing import Optional
from datetime import datetime

UID_API   = "https://www.uid.admin.ch/app/json"
GLEIF_API = "https://api.gleif.org/api/v1"

HEADERS = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept":     "application/json",
}


# ── Swiss UID Register ─────────────────────────────────────────

def enrich_uid(slug: str, display_name: str = "") -> dict:
    """Search Swiss UID register by company name."""
    if not display_name and not slug:
        return {"source": "uid", "available": False}

    search_term = display_name or slug
    try:
        r = httpx.post(
            f"{UID_API}/search",
            json={"name": search_term, "maxEntries": 5, "offset": 0},
            headers=HEADERS,
            timeout=12,
        )
        if r.status_code != 200:
            return {"source": "uid", "available": False}

        data = r.json()
        entries = data.get("organisations") or data.get("results") or []
        if not entries:
            return {"source": "uid", "available": False}

        # Best match
        best = None
        name_lower = search_term.lower()
        for entry in entries:
            org_name = (entry.get("organisation", {}).get("organisationName", [{}])[0] or {})
            org_name_str = org_name.get("organisationName", "").lower()
            if name_lower in org_name_str or org_name_str in name_lower:
                best = entry
                break
        if not best:
            best = entries[0]

        uid_raw = best.get("uidOrganisationIdCategorie", {}).get("uidOrganisationId", "")
        is_active = best.get("organisation", {}).get("organisationState") == "A"

        return {
            "source":    "uid",
            "available": True,
            "uid_number": f"CHE-{uid_raw}" if uid_raw and not str(uid_raw).startswith("CHE") else str(uid_raw),
            "is_commercially_active": is_active,
            "vat_registered": best.get("vatRegisterInformation", {}).get("vatStatus") == "registered",
            "legal_form": best.get("organisation", {}).get("legalForm"),
            "business_type": best.get("organisation", {}).get("uid"),
        }
    except Exception as e:
        print(f"[uid] Search error for '{display_name}': {e}")
        return {"source": "uid", "available": False}


# ── GLEIF LEI Register ─────────────────────────────────────────

def _search_by_name(name: str, jurisdiction: str = None) -> Optional[dict]:
    """Search GLEIF by entity name. Returns first matching LEI record."""
    params = {
        "filter[entity.legalName]": name,
        "page[size]": 5,
        "page[number]": 1,
    }
    if jurisdiction:
        params["filter[entity.legalAddress.country]"] = jurisdiction

    try:
        r = httpx.get(
            f"{GLEIF_API}/lei-records",
            params=params,
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", [])
            if items:
                return _best_match(items, name)
    except Exception as e:
        print(f"[gleif] Name search error: {e}")

    # Try fulltext search as fallback
    try:
        r2 = httpx.get(
            f"{GLEIF_API}/lei-records",
            params={"filter[fulltext]": name, "page[size]": 5},
            headers=HEADERS,
            timeout=15,
        )
        if r2.status_code == 200:
            items = r2.json().get("data", [])
            if items:
                return _best_match(items, name)
    except Exception as e:
        print(f"[gleif] Fulltext search error: {e}")

    return None


def _best_match(items: list, search_name: str) -> Optional[dict]:
    """Find the best matching record from GLEIF results."""
    name_lower = search_name.lower()
    for item in items:
        attrs  = item.get("attributes", {})
        entity = attrs.get("entity", {})
        legal_name = (entity.get("legalName") or {}).get("name", "").lower()
        if name_lower in legal_name or legal_name in name_lower:
            return item
    return items[0] if items else None


def _parse_lei_record(record: dict) -> dict:
    """Parse a GLEIF LEI record into Raven fields."""
    attrs  = record.get("attributes", {})
    entity = attrs.get("entity", {})
    reg    = attrs.get("registration", {})
    lei    = record.get("id", "")

    # Jurisdiction
    legal_addr   = entity.get("legalAddress", {})
    hq_addr      = entity.get("headquartersAddress", {})
    country      = legal_addr.get("country") or hq_addr.get("country", "")

    # Status
    reg_status   = reg.get("status", "")
    entity_status = entity.get("status", "")
    lei_valid    = reg_status in ("ISSUED", "PENDING_TRANSFER", "PENDING_ARCHIVAL")

    # Registration date
    initial_reg  = reg.get("initialRegistrationDate", "")[:10] if reg.get("initialRegistrationDate") else ""

    return {
        "source":                "gleif",
        "available":             True,
        "fetched_at":            datetime.utcnow().isoformat(),
        "lei":                   lei,
        "lei_status":            reg_status,
        "lei_registration_valid": lei_valid,
        "license_active_gleif":  lei_valid,
        "gleif_legal_name":      (entity.get("legalName") or {}).get("name"),
        "gleif_country":         country,
        "gleif_entity_status":   entity_status,
        "gleif_initial_reg":     initial_reg,
        "gleif_last_updated":    reg.get("lastUpdateDate", "")[:10] if reg.get("lastUpdateDate") else "",
        "gleif_url":             f"https://search.gleif.org/#/record/{lei}",
        "gleif_next_renewal":    reg.get("nextRenewalDate", "")[:10] if reg.get("nextRenewalDate") else "",
    }


def enrich_gleif(slug: str, display_name: str = "", jurisdiction: str = "") -> dict:
    """
    Main entry point. Fetch GLEIF LEI data for any counterparty.
    Uses official GLEIF REST API — public, no auth required.
    """
    if not display_name and not slug:
        return {"source": "gleif", "available": False}

    search_name = display_name or slug

    record = _search_by_name(search_name, jurisdiction or None)

    # Retry with first two words if full name not found
    if not record and len(search_name.split()) > 2:
        short = " ".join(search_name.split()[:2])
        record = _search_by_name(short, jurisdiction or None)

    if not record:
        return {"source": "gleif", "available": False, "searched": search_name}

    return _parse_lei_record(record)
