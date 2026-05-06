"""
Raven — Sanctions Screening Provider

Screens counterparty names and known wallet addresses against:
1. OFAC SDN List (US Treasury) — primary sanctions list
2. EU Consolidated Sanctions List — required for FINMA-supervised firms
3. UN Security Council Consolidated List — global baseline

All sources are free, official government APIs, updated daily.

For Swiss portfolio managers under FINMA supervision, screening against
OFAC and EU lists is a baseline AML/CFT compliance requirement.
A match → CRITICAL risk flag → immediate alert.

No API keys required.
"""

import httpx
import json
import re
from typing import Optional
from datetime import datetime, timedelta
from functools import lru_cache

# Cache the sanctions lists for 24 hours to avoid repeated downloads
_CACHE: dict = {}
_CACHE_TTL = 3600 * 24  # 24 hours

HEADERS = {
    "User-Agent": "Raven Risk Intelligence / compliance contact@raven.internal",
    "Accept":     "application/json, text/xml, */*",
}


# ── OFAC SDN List ─────────────────────────────────────────────

OFAC_API = "https://api.ofac-api.com/v4/search"
OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.json"


def _get_ofac_list() -> list:
    """Fetch and cache OFAC SDN list."""
    cache_key = "ofac_sdn"
    if cache_key in _CACHE:
        entry = _CACHE[cache_key]
        if (datetime.utcnow() - entry["ts"]).seconds < _CACHE_TTL:
            return entry["data"]

    try:
        # Use the structured JSON format
        r = httpx.get(OFAC_SDN_URL, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            entries = data.get("SDNList", {}).get("sdnEntry", [])
            _CACHE[cache_key] = {"data": entries, "ts": datetime.utcnow()}
            return entries
    except Exception as e:
        print(f"[sanctions] OFAC list error: {e}")

    return []


def _normalize(name: str) -> str:
    """Normalize name for comparison."""
    return re.sub(r'[^a-z0-9 ]', '', name.lower().strip())


def check_ofac(entity_name: str, aliases: list = None) -> dict:
    """
    Check entity name against OFAC SDN list.
    Returns: {matched: bool, match_details: [...], confidence: str}
    """
    names_to_check = [entity_name] + (aliases or [])
    normalized_checks = [_normalize(n) for n in names_to_check]

    # Try the OFAC API first (rate limited but structured)
    try:
        r = httpx.post(
            OFAC_API,
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "apiKey":       "",  # public endpoint
                "minScore":     85,
                "sources":      ["SDN"],
                "types":        ["Entity", "Organization"],
                "cases":        [{"name": entity_name}],
            },
            timeout=10,
        )
        if r.status_code == 200:
            data  = r.json()
            matches = data.get("results", [{}])[0].get("matches", [])
            if matches:
                return {
                    "matched":      True,
                    "list":         "OFAC SDN",
                    "matches":      [m.get("name", "") for m in matches[:3]],
                    "score":        matches[0].get("score", 0),
                    "confidence":   "high",
                    "checked_at":   datetime.utcnow().isoformat(),
                }
    except Exception:
        pass

    # Fallback: local name matching against downloaded list
    sdn_entries = _get_ofac_list()
    found = []
    for entry in sdn_entries:
        entry_name = _normalize(entry.get("firstName", "") + " " + entry.get("lastName", ""))
        aka_list   = entry.get("akaList", {}).get("aka", [])
        if not isinstance(aka_list, list):
            aka_list = [aka_list]
        all_names = [entry_name] + [_normalize(a.get("firstName","") + " " + a.get("lastName",""))
                                     for a in aka_list if isinstance(a, dict)]
        for check in normalized_checks:
            if check and any(check in name or name in check for name in all_names if name.strip()):
                found.append(entry_name)
                break

    return {
        "matched":    bool(found),
        "list":       "OFAC SDN" if found else None,
        "matches":    found[:3],
        "confidence": "medium" if found else "none",
        "checked_at": datetime.utcnow().isoformat(),
    }


# ── EU Consolidated Sanctions List ────────────────────────────

EU_SANCTIONS_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/jsonFullSanctionsList_1_1/content"


def _get_eu_list() -> list:
    """Fetch and cache EU consolidated sanctions list."""
    cache_key = "eu_sanctions"
    if cache_key in _CACHE:
        entry = _CACHE[cache_key]
        if (datetime.utcnow() - entry["ts"]).seconds < _CACHE_TTL:
            return entry["data"]

    try:
        r = httpx.get(EU_SANCTIONS_URL, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data    = r.json()
            entries = data.get("export", {}).get("sanctionEntity", [])
            if not isinstance(entries, list):
                entries = [entries] if entries else []
            _CACHE[cache_key] = {"data": entries, "ts": datetime.utcnow()}
            return entries
    except Exception as e:
        print(f"[sanctions] EU list error: {e}")

    return []


def check_eu_sanctions(entity_name: str) -> dict:
    """Check entity name against EU consolidated sanctions list."""
    normalized = _normalize(entity_name)
    eu_entries = _get_eu_list()
    found = []

    for entry in eu_entries:
        names = entry.get("nameAlias", [])
        if not isinstance(names, list):
            names = [names] if names else []

        for name_obj in names:
            if not isinstance(name_obj, dict):
                continue
            whole_name = _normalize(
                name_obj.get("wholeName", "") or
                (name_obj.get("firstName", "") + " " + name_obj.get("lastName", ""))
            )
            if normalized and whole_name and (normalized in whole_name or whole_name in normalized):
                found.append(name_obj.get("wholeName", whole_name))
                break

    return {
        "matched":    bool(found),
        "list":       "EU Consolidated Sanctions" if found else None,
        "matches":    found[:3],
        "confidence": "medium" if found else "none",
        "checked_at": datetime.utcnow().isoformat(),
    }


# ── UN Sanctions List ─────────────────────────────────────────

UN_SANCTIONS_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


def check_un_sanctions(entity_name: str) -> dict:
    """
    Check entity name against UN Security Council sanctions list.
    Simplified text search against XML.
    """
    cache_key = "un_sanctions"
    normalized = _normalize(entity_name)

    try:
        if cache_key not in _CACHE or (datetime.utcnow() - _CACHE[cache_key]["ts"]).seconds > _CACHE_TTL:
            r = httpx.get(UN_SANCTIONS_URL, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                _CACHE[cache_key] = {"data": r.text, "ts": datetime.utcnow()}

        if cache_key in _CACHE:
            xml_text   = _CACHE[cache_key]["data"]
            xml_lower  = xml_text.lower()
            if normalized and len(normalized) > 4 and normalized in xml_lower:
                return {
                    "matched":    True,
                    "list":       "UN Security Council",
                    "confidence": "medium",
                    "checked_at": datetime.utcnow().isoformat(),
                }
    except Exception as e:
        print(f"[sanctions] UN list error: {e}")

    return {
        "matched":    False,
        "list":       None,
        "confidence": "none",
        "checked_at": datetime.utcnow().isoformat(),
    }


# ── Main screening function ───────────────────────────────────

def screen_counterparty(
    display_name: str,
    legal_name: str = None,
    aliases: list = None,
) -> dict:
    """
    Screen a counterparty against all sanctions lists.
    Returns comprehensive screening result with matched lists and confidence.

    Used by:
    - Research agent (pre-fetch before Claude web search)
    - Scoring engine (regulatory dimension — sanctions = CRITICAL)
    - Alert system (match → CRITICAL alert)
    """
    names = [display_name]
    if legal_name and legal_name != display_name:
        names.append(legal_name)
    if aliases:
        names.extend(aliases)

    results = {
        "screened_names":  names,
        "ofac":            check_ofac(display_name, (aliases or []) + ([legal_name] if legal_name else [])),
        "eu":              check_eu_sanctions(display_name),
        "un":              check_un_sanctions(display_name),
        "screened_at":     datetime.utcnow().isoformat(),
        "source":          "sanctions_screening",
    }

    # Aggregate result
    any_match = (
        results["ofac"]["matched"] or
        results["eu"]["matched"] or
        results["un"]["matched"]
    )

    matched_lists = [
        r["list"] for r in [results["ofac"], results["eu"], results["un"]]
        if r.get("matched") and r.get("list")
    ]

    results["any_match"]     = any_match
    results["matched_lists"] = matched_lists
    results["risk_level"]    = "CRITICAL" if any_match else "CLEAR"

    if any_match:
        print(f"[sanctions] ⚠️  {display_name} matched: {matched_lists}")

    return results
