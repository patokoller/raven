"""
Raven — SECO Swiss Sanctions Provider
State Secretariat for Economic Affairs (Staatssekretariat für Wirtschaft)

Screens counterparties against Swiss domestic sanctions lists which differ
from OFAC/EU in some cases — particularly regarding Russia/Belarus measures
and Swiss autonomous measures not mirrored in EU lists.

Sources:
- SECO Consolidated Sanctions List (XML, updated daily)
  https://www.seco.admin.ch/seco/en/home/Aussenwirtschaftspolitik_Wirtschaftliche_Zusammenarbeit/Wirtschaftsbeziehungen/exportkontrollen-und-sanktionen/sanktionen-embargos.html
- SECO also enforces UN and EU sanctions in Switzerland

No API key required. Public data.
"""

import httpx
import re
from datetime import datetime
from functools import lru_cache

SECO_LIST_URL = "https://www.seco.admin.ch/dam/seco/de/dokumente/Aussenwirtschaft/Wirtschaftliche_Landesversorgung/Embargos/Sanktionsmassnahmen/Sanktionen_konsolidierte_Liste.xml.download.xml/Sanctions_Consolidated_List.xml"

_CACHE: dict = {}
_CACHE_TTL = 3600 * 24  # 24h

HEADERS = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept": "application/xml, text/xml, */*",
}


def _get_seco_list() -> str:
    """Fetch and cache SECO sanctions list XML."""
    cache_key = "seco_list"
    if cache_key in _CACHE:
        entry = _CACHE[cache_key]
        if (datetime.utcnow() - entry["ts"]).seconds < _CACHE_TTL:
            return entry["data"]
    try:
        r = httpx.get(SECO_LIST_URL, headers=HEADERS, timeout=30, follow_redirects=True)
        if r.status_code == 200:
            _CACHE[cache_key] = {"data": r.text, "ts": datetime.utcnow()}
            return r.text
    except Exception as e:
        print(f"[seco] List fetch error: {e}")
    return ""


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def screen(entity_name: str, legal_name: str = None) -> dict:
    """
    Screen an entity against SECO Swiss sanctions list.
    Returns match details if found.
    """
    names_to_check = [n for n in [entity_name, legal_name] if n]
    normalized_checks = [_normalize(n) for n in names_to_check]

    xml = _get_seco_list()
    if not xml:
        return {
            "source": "seco",
            "available": False,
            "screened": False,
            "reason": "list_unavailable",
            "screened_at": datetime.utcnow().isoformat(),
        }

    # Extract names from XML — SECO uses <FNAME> and <NAME1> tags
    all_names_in_list = re.findall(
        r"<(?:FNAME|NAME1|wholeName|name)>([^<]+)</(?:FNAME|NAME1|wholeName|name)>",
        xml, re.IGNORECASE
    )
    normalized_list = [_normalize(n) for n in all_names_in_list]

    matched = False
    matched_entry = None
    for check_norm in normalized_checks:
        if len(check_norm) < 4:
            continue
        for i, list_norm in enumerate(normalized_list):
            # Substring match (catches partial matches like "Sygnum" in "Sygnum Bank AG")
            if check_norm in list_norm or list_norm in check_norm:
                # Require at least 5 chars to reduce false positives
                overlap = min(len(check_norm), len(list_norm))
                if overlap >= 5:
                    matched = True
                    matched_entry = all_names_in_list[i] if i < len(all_names_in_list) else list_norm
                    break
        if matched:
            break

    return {
        "source":      "seco",
        "available":   True,
        "screened":    True,
        "match":       matched,
        "matched_entry": matched_entry,
        "screened_at": datetime.utcnow().isoformat(),
        "list_url":    SECO_LIST_URL,
    }
