"""
Raven — SECO Swiss Sanctions Provider
Uses OpenSanctions API (opensanctions.org) which aggregates the SECO
Swiss Sanctions/Embargoes list and provides a proper matching API.

API: https://api.opensanctions.org/match/ch_seco_sanctions
POST with JSON body: {"queries": {"q1": {"schema": "LegalEntity", "properties": {"name": ["..."]} }}}
Requires API key for commercial use.

Bulk download fallback (no auth): 
https://data.opensanctions.org/datasets/latest/ch_seco_sanctions/names.txt
"""

import httpx
import re
from datetime import datetime, timedelta
from app.core.config import settings

# In-memory cache: entity_name -> (result, timestamp)
# Prevents burning API quota on repeated lookups of the same entity
_RESULT_CACHE: dict = {}
_RESULT_CACHE_TTL = timedelta(days=30)  # Cache for 30 days (within monthly quota)

OPENSANCTIONS_MATCH  = "https://api.opensanctions.org/match/ch_seco_sanctions"
OPENSANCTIONS_SEARCH = "https://api.opensanctions.org/search/ch_seco_sanctions"
NAMES_TXT_URL        = "https://data.opensanctions.org/datasets/latest/ch_seco_sanctions/names.txt"

_NAMES_CACHE: dict = {}
_CACHE_TTL = 3600 * 24  # 24h


def _get_api_headers() -> dict:
    headers = {"Accept": "application/json", "User-Agent": "Raven Risk Intelligence / raven.internal"}
    api_key = getattr(settings, "OPENSANCTIONS_API_KEY", None)
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    return headers


def _screen_via_api(name: str, legal_name: str = None) -> dict:
    """Use OpenSanctions match API (preferred — requires API key for commercial use)."""
    names = [n for n in [name, legal_name] if n]
    body = {
        "queries": {
            "q1": {
                "schema": "LegalEntity",
                "properties": {"name": names},
            }
        }
    }
    r = httpx.post(
        OPENSANCTIONS_MATCH,
        json=body,
        headers=_get_api_headers(),
        timeout=15,
    )
    if r.status_code == 200:
        data   = r.json()
        result = data.get("responses", {}).get("q1", {})
        hits   = result.get("results", [])
        if hits:
            top = hits[0]
            score = top.get("score", 0)
            # OpenSanctions score >0.7 = likely match
            if score > 0.5:
                return {
                    "source":        "seco_opensanctions",
                    "available":     True,
                    "match":         score > 0.7,
                    "score":         score,
                    "matched_name":  top.get("caption"),
                    "entity_id":     top.get("id"),
                    "topics":        top.get("properties", {}).get("topics", []),
                    "screened_at":   datetime.utcnow().isoformat(),
                }
        match_result = {
            "source": "seco_opensanctions", "available": True,
            "match": False, "score": 0,
            "screened_at": datetime.utcnow().isoformat(),
        }
        _RESULT_CACHE[entity_name.lower().strip()] = (match_result, datetime.utcnow())
        return match_result
    return {}


def _screen_via_search(name: str) -> dict:
    """Use OpenSanctions search endpoint (free, less precise)."""
    r = httpx.get(
        OPENSANCTIONS_SEARCH,
        params={"q": name, "limit": 5},
        headers=_get_api_headers(),
        timeout=12,
    )
    if r.status_code == 200:
        data    = r.json()
        results = data.get("results", [])
        for hit in results:
            caption = (hit.get("caption") or "").lower()
            if name.lower() in caption or caption in name.lower():
                return {
                    "source":       "seco_opensanctions",
                    "available":    True,
                    "match":        True,
                    "matched_name": hit.get("caption"),
                    "screened_at":  datetime.utcnow().isoformat(),
                }
        return {
            "source": "seco_opensanctions", "available": True,
            "match": False, "screened_at": datetime.utcnow().isoformat(),
        }
    return {}


def _screen_via_bulk(name: str) -> dict:
    """Fallback: download names.txt bulk file and check."""
    cache_key = "seco_names"
    if cache_key in _NAMES_CACHE:
        entry = _NAMES_CACHE[cache_key]
        if (datetime.utcnow() - entry["ts"]).seconds < _CACHE_TTL:
            names_text = entry["data"]
        else:
            names_text = None
    else:
        names_text = None

    if names_text is None:
        try:
            r = httpx.get(NAMES_TXT_URL, timeout=20, follow_redirects=True,
                          headers={"User-Agent": "Raven Risk Intelligence"})
            if r.status_code == 200:
                names_text = r.text
                _NAMES_CACHE[cache_key] = {"data": names_text, "ts": datetime.utcnow()}
        except Exception as e:
            print(f"[seco] Bulk download error: {e}")
            return {}

    if not names_text:
        return {}

    name_lower = name.lower().strip()
    lines      = names_text.lower().splitlines()
    for line in lines:
        line = line.strip()
        if len(line) < 4:
            continue
        if name_lower in line or (len(name_lower) >= 5 and line in name_lower):
            return {
                "source":       "seco_bulk",
                "available":    True,
                "match":        True,
                "matched_name": line,
                "screened_at":  datetime.utcnow().isoformat(),
            }

    return {
        "source": "seco_bulk", "available": True,
        "match": False, "screened_at": datetime.utcnow().isoformat(),
    }


def screen(entity_name: str, legal_name: str = None) -> dict:
    """
    Screen an entity against SECO Swiss sanctions list via OpenSanctions.
    Tries match API → search API → bulk names.txt fallback.
    Caches results for 30 days to conserve API quota (50 req/month).
    """
    # Check cache first
    cache_key = (entity_name or "").lower().strip()
    if cache_key in _RESULT_CACHE:
        cached_result, cached_at = _RESULT_CACHE[cache_key]
        if datetime.utcnow() - cached_at < _RESULT_CACHE_TTL:
            cached_result["from_cache"] = True
            return cached_result

    # Try match API first (most accurate)
    try:
        result = _screen_via_api(entity_name, legal_name)
        if result:
            return result
    except Exception as e:
        print(f"[seco] Match API error: {e}")

    # Try search endpoint
    try:
        result = _screen_via_search(entity_name)
        if result:
            return result
    except Exception as e:
        print(f"[seco] Search API error: {e}")

    # Fallback: bulk file (no quota cost)
    try:
        result = _screen_via_bulk(entity_name)
        if result:
            _RESULT_CACHE[cache_key] = (result, datetime.utcnow())
            return result
    except Exception as e:
        print(f"[seco] Bulk fallback error: {e}")

    final = {
        "source": "seco", "available": False,
        "reason": "all_methods_failed",
        "screened_at": datetime.utcnow().isoformat(),
    }
    _RESULT_CACHE[cache_key] = (final, datetime.utcnow())
    return final
