"""
Raven — Swiss UID Register + GLEIF LEI Provider

Two complementary sources:

1. UID Register (uid.admin.ch)
   - Swiss Federal UID (Unternehmens-Identifikationsnummer)
   - Confirms: VAT registration, active commercial status, NOGA business code
   - Free REST API, no key required
   - Endpoint: https://www.uid.admin.ch/Detail.aspx?uid_id={uid}
   - JSON API: https://www.uid.admin.ch/api/v1/query

2. GLEIF Global LEI Register (gleif.org)
   - Legal Entity Identifier — global standard for financial institutions
   - Confirms: legal name, headquarters, entity status, registration authority
   - Free REST API, no key required
   - Endpoint: https://api.gleif.org/api/v1/lei-records
   - Every major financial institution has an LEI
"""

import httpx
from typing import Optional
from datetime import datetime

# ── UID Register ──────────────────────────────────────────────

UID_API = "https://www.uid.admin.ch/api/v1"

# NOGA codes relevant to financial services
NOGA_FINANCIAL = {
    "6419": "Other monetary intermediation",
    "6491": "Financial leasing",
    "6492": "Other credit granting",
    "6499": "Other financial service activities",
    "6611": "Administration of financial markets",
    "6612": "Security and commodity contracts brokerage",
    "6619": "Other activities auxiliary to financial services",
    "6630": "Fund management activities",
    "9900": "Activities of extraterritorial organisations",
}

# Known UIDs for our counterparties (without CHE- prefix and dots)
UID_NUMBER_MAP = {
    "taurus":         "215326827",
    "bitcoin-suisse": "184974020",
    "sygnum":         "440296842",
    "seba-bank":      "222926907",
    "maerki-baumann": "105913367",
}


def get_uid_details(uid_number: str) -> Optional[dict]:
    """
    Fetch company details from Swiss UID register.
    uid_number: numeric part only, e.g. "215326827"
    """
    try:
        r = httpx.get(
            f"{UID_API}/uid/{uid_number}",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[uid] Error for {uid_number}: {e}")
    return None


def search_uid(name: str) -> Optional[str]:
    """Search UID register by company name, return UID number if found."""
    try:
        r = httpx.get(
            f"{UID_API}/search",
            params={"name": name, "maxEntries": 5},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if r.status_code == 200:
            results = r.json()
            if isinstance(results, list) and results:
                return results[0].get("uidOrganisationId", {}).get("uid")
    except Exception:
        pass
    return None


def enrich_uid(slug: str, display_name: str = "") -> dict:
    """Fetch UID register data for a Swiss counterparty."""
    uid_num = UID_NUMBER_MAP.get(slug)

    if not uid_num and display_name:
        uid_num = search_uid(display_name)

    if not uid_num:
        return {"source": "uid_register", "available": False}

    data = get_uid_details(uid_num)
    if not data:
        return {"source": "uid_register", "available": False}

    result = {
        "source":    "uid_register",
        "available": True,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Status
    status = (data.get("uidEntityStatus") or "").upper()
    result["uid_status"]      = status
    result["vat_registered"]  = data.get("vatStatus") == "REGISTERED"
    result["uid_number"]      = f"CHE-{uid_num[:3]}.{uid_num[3:6]}.{uid_num[6:]}"

    # Active status
    result["is_commercially_active"] = status in ("ACTIVE", "AKTIV")

    # Business category
    noga = data.get("noga") or {}
    noga_code = str(noga.get("code", ""))
    result["noga_code"]     = noga_code
    result["business_type"] = NOGA_FINANCIAL.get(noga_code, noga.get("label", ""))

    # Address
    address = data.get("address", {})
    result["uid_street"]   = address.get("street")
    result["uid_city"]     = address.get("city")
    result["uid_canton"]   = address.get("canton")

    return result


# ── GLEIF LEI Register ────────────────────────────────────────

GLEIF_API = "https://api.gleif.org/api/v1"

# Known LEIs for our counterparties
LEI_MAP = {
    "coinbase":              "549300QK3XBKZX7MZ714",
    "goldman-sachs-digital": "784F5XWPLTWKTBV3E584",
    "jpmorgan-onyx":         "8I5DZWZKVSZI1NUHU748",
    "galaxy-digital":        "2138003FK3J7T9DSV585",
    "wintermute":            "2138005BQ5K6UHJHXI83",
    "b2c2":                  "213800XVSCYWTMR2T518",
    "lmax-digital":          "2138008P0VKWIFZL9Z59",
    "sygnum":                "9845000A26EE33HCMV29",
    "seba-bank":             "9845000JXFB29JWVG044",
    "bitcoin-suisse":        None,  # search
    "taurus":                None,
    "maerki-baumann":        None,
    "anchorage-digital":     None,
    "copper":                "2138002QEBVZMHVD0B34",
}


def get_lei_record(lei: str) -> Optional[dict]:
    """Fetch full LEI record from GLEIF."""
    try:
        r = httpx.get(
            f"{GLEIF_API}/lei-records/{lei}",
            headers={"Accept": "application/vnd.api+json"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("data", {})
    except Exception as e:
        print(f"[gleif] Error for LEI {lei}: {e}")
    return None


def search_lei(name: str) -> Optional[str]:
    """Search GLEIF by company name, return LEI if found."""
    try:
        r = httpx.get(
            f"{GLEIF_API}/lei-records",
            params={
                "filter[entity.legalName]": name,
                "page[size]":              5,
            },
            headers={"Accept": "application/vnd.api+json"},
            timeout=10,
        )
        if r.status_code == 200:
            records = r.json().get("data", [])
            if records:
                return records[0].get("id")
    except Exception:
        pass
    return None


def enrich_gleif(slug: str, display_name: str = "") -> dict:
    """Fetch GLEIF LEI data for a counterparty."""
    lei = LEI_MAP.get(slug)

    if not lei and display_name:
        lei = search_lei(display_name)

    if not lei:
        return {"source": "gleif", "available": False}

    record = get_lei_record(lei)
    if not record:
        return {"source": "gleif", "available": False}

    attrs  = record.get("attributes", {})
    entity = attrs.get("entity", {})
    reg    = attrs.get("registration", {})

    result = {
        "source":    "gleif",
        "available": True,
        "lei":       record.get("id"),
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Entity status
    entity_status = (entity.get("status") or "").upper()
    result["lei_status"]    = entity_status
    result["license_active_gleif"] = entity_status == "ACTIVE"

    # Legal names
    legal_name = entity.get("legalName", {})
    result["gleif_legal_name"] = (
        legal_name.get("name") if isinstance(legal_name, dict) else legal_name
    )

    # Jurisdiction
    result["gleif_jurisdiction"] = entity.get("jurisdiction")

    # Headquarters
    hq = entity.get("headquartersAddress", {})
    result["gleif_country"]  = hq.get("country")
    result["gleif_city"]     = hq.get("city")
    result["gleif_postcode"] = hq.get("postalCode")

    # Registration details
    result["gleif_registration_date"] = reg.get("initialRegistrationDate", "")[:10]
    result["gleif_last_updated"]       = reg.get("lastUpdateDate", "")[:10]
    result["gleif_next_renewal"]       = reg.get("nextRenewalDate", "")[:10]

    # LEI registration status (ISSUED = valid and current)
    reg_status = (reg.get("status") or "").upper()
    result["lei_registration_valid"] = reg_status == "ISSUED"

    # Managing LOU (the authority that issued the LEI)
    result["gleif_lou"] = reg.get("managingLou")

    # Link
    result["gleif_url"] = f"https://search.gleif.org/#/record/{lei}"

    return result
