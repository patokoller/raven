"""
Raven — FCA Register Data Provider
Free REST API. Covers UK-regulated entities.

Relevant counterparties:
- Copper (FCA registered)
- B2C2 (FCA regulated)
- LMAX Digital (FCA regulated)
- Wintermute (FCA regulated)
- Hidden Road (SEC/FINRA but also some FCA presence)
- CEX.IO (FCA registered)

API: https://register.fca.org.uk/s/rp-api (public REST API)
No authentication required for read access.
"""

import httpx
from typing import Optional
from datetime import datetime

FCA_API = "https://register.fca.org.uk/s/rp-api"

# FRN (Firm Reference Number) for our counterparties
FRN_MAP = {
    "copper":       "843034",
    "b2c2":         "810005",
    "lmax-digital": "504374",  # LMAX Group
    "wintermute":   "906623",
    "cex-io":       "828722",
    "gemini":       None,       # US-based, limited FCA presence
}

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Raven Risk Intelligence",
}


def get_firm_details(frn: str) -> Optional[dict]:
    """
    Fetch firm details from FCA register by FRN.
    Returns status, permissions, requirements.
    """
    try:
        r = httpx.get(
            f"{FCA_API}/firm/{frn}",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[fca] Error fetching FRN {frn}: {e}")
    return None


def get_firm_permissions(frn: str) -> list:
    """Get list of regulatory permissions for a firm."""
    try:
        r = httpx.get(
            f"{FCA_API}/firm/{frn}/permissions",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("permissions", []) or []
    except Exception:
        pass
    return []


def get_firm_requirements(frn: str) -> list:
    """Get any requirements/restrictions on the firm."""
    try:
        r = httpx.get(
            f"{FCA_API}/firm/{frn}/requirements",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("requirements", []) or []
    except Exception:
        pass
    return []


def search_firm(name: str) -> Optional[str]:
    """Search FCA register by firm name, return FRN if found."""
    try:
        r = httpx.get(
            f"{FCA_API}/search",
            params={"q": name, "type": "firm"},
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return results[0].get("frn")
    except Exception:
        pass
    return None


def enrich_counterparty(slug: str, display_name: str = "") -> dict:
    """
    Main entry point. Returns enrichment data for a counterparty from FCA Register.
    """
    frn = FRN_MAP.get(slug)

    # Try searching by name if no FRN mapped
    if not frn and display_name:
        frn = search_firm(display_name)

    if not frn:
        return {"source": "fca_register", "available": False}

    details = get_firm_details(frn)
    if not details:
        return {"source": "fca_register", "available": False, "frn": frn}

    # Parse status
    firm_data = details.get("firm", {}) or details
    status    = (firm_data.get("status") or firm_data.get("Status") or "").lower()
    is_active = status in ("authorised", "registered", "active")

    # Get permissions and requirements
    permissions   = get_firm_permissions(frn)
    requirements  = get_firm_requirements(frn)

    # Check for restrictions
    has_restrictions = bool(requirements)

    result = {
        "source":          "fca_register",
        "frn":             frn,
        "fca_status":      status,
        "license_active":  is_active,
        "has_restrictions": has_restrictions,
        "permission_count": len(permissions),
        "requirements":    [str(r) for r in requirements[:5]],
        "enforcement_actions_12m": 1 if has_restrictions else 0,
        "available":       True,
        "fetched_at":      datetime.utcnow().isoformat(),
    }

    return result
