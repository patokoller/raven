"""
Raven — OpenSanctions Swiss SECO Sanctions Provider

Screens counterparties against the Swiss SECO sanctions list via OpenSanctions.
Dataset: ch_seco_sanctions
Source: https://www.opensanctions.org/datasets/ch_seco_sanctions/

API endpoints:
  Match:  POST https://api.opensanctions.org/match/ch_seco_sanctions
  Search: GET  https://api.opensanctions.org/search/ch_seco_sanctions?q=...
  Bulk:   GET  https://data.opensanctions.org/datasets/latest/ch_seco_sanctions/names.txt

API key required for match/search (commercial use).
Bulk names.txt is always free and used as fallback.

50 req/month quota — results cached 30 days per entity.
"""

import httpx
from datetime import datetime, timedelta
from app.core.config import settings

MATCH_URL  = "https://api.opensanctions.org/match/ch_seco_sanctions"
SEARCH_URL = "https://api.opensanctions.org/search/ch_seco_sanctions"
NAMES_URL  = "https://data.opensanctions.org/datasets/latest/ch_seco_sanctions/names.txt"

# In-memory cache — avoids burning quota on repeat lookups
_RESULT_CACHE: dict = {}
_NAMES_CACHE:  dict = {}
RESULT_TTL = timedelta(days=30)
NAMES_TTL  = timedelta(hours=24)


def _headers() -> dict:
    h = {
        "Accept":     "application/json",
        "User-Agent": "Raven Risk Intelligence / raven.internal",
    }
    key = getattr(settings, "OPENSANCTIONS_API_KEY", "")
    if key:
        h["Authorization"] = f"ApiKey {key}"
    return h


def _via_match_api(name: str, legal_name: str = None) -> dict:
    """POST to /match/ch_seco_sanctions — most accurate, costs 1 quota unit."""
    names = [n for n in [name, legal_name] if n]
    try:
        r = httpx.post(
            MATCH_URL,
            json={"queries": {"q1": {"schema": "LegalEntity", "properties": {"name": names}}}},
            headers=_headers(),
            timeout=15,
        )
        if r.status_code == 200:
            hits = r.json().get("responses", {}).get("q1", {}).get("results", [])
            if hits:
                top   = hits[0]
                score = top.get("score", 0)
                return {
                    "available":    True,
                    "match":        score >= 0.7,
                    "score":        round(score, 3),
                    "matched_name": top.get("caption"),
                    "entity_id":    top.get("id"),
                    "topics":       top.get("properties", {}).get("topics", []),
                    "method":       "match_api",
                }
            return {"available": True, "match": False, "score": 0, "method": "match_api"}
        if r.status_code == 402:
            print("[opensanctions] Quota exceeded — falling back to bulk")
    except Exception as e:
        print(f"[opensanctions] Match API error: {e}")
    return {}


def _via_search_api(name: str) -> dict:
    """GET /search/ch_seco_sanctions — costs 1 quota unit."""
    try:
        r = httpx.get(
            SEARCH_URL,
            params={"q": name, "limit": 5},
            headers=_headers(),
            timeout=12,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            for hit in results:
                caption = (hit.get("caption") or "").lower()
                if name.lower() in caption or caption in name.lower():
                    return {
                        "available":    True,
                        "match":        True,
                        "matched_name": hit.get("caption"),
                        "method":       "search_api",
                    }
            return {"available": True, "match": False, "method": "search_api"}
    except Exception as e:
        print(f"[opensanctions] Search API error: {e}")
    return {}


def _via_bulk_names(name: str) -> dict:
    """Free fallback: download names.txt and check locally. No quota cost."""
    now = datetime.utcnow()
    if "data" in _NAMES_CACHE and now - _NAMES_CACHE["ts"] < NAMES_TTL:
        text = _NAMES_CACHE["data"]
    else:
        try:
            r = httpx.get(NAMES_URL, timeout=20, follow_redirects=True,
                          headers={"User-Agent": "Raven Risk Intelligence"})
            if r.status_code != 200:
                return {}
            text = r.text
            _NAMES_CACHE["data"] = text
            _NAMES_CACHE["ts"]   = now
        except Exception as e:
            print(f"[opensanctions] Bulk download error: {e}")
            return {}

    name_lower = name.lower().strip()
    for line in text.lower().splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        if name_lower in line or (len(name_lower) >= 5 and line in name_lower):
            return {"available": True, "match": True, "matched_name": line, "method": "bulk_names"}

    return {"available": True, "match": False, "method": "bulk_names"}


def screen(entity_name: str, legal_name: str = None) -> dict:
    """
    Screen an entity against Swiss SECO sanctions via OpenSanctions.

    Strategy (quota-aware):
    1. Check 30-day in-memory cache
    2. Match API (precise, costs quota)
    3. Search API (fallback, costs quota)
    4. Bulk names.txt (free, always available)
    """
    cache_key = (entity_name or "").lower().strip()

    # Return cached result if fresh
    if cache_key in _RESULT_CACHE:
        cached, ts = _RESULT_CACHE[cache_key]
        if datetime.utcnow() - ts < RESULT_TTL:
            return {**cached, "from_cache": True}

    result = {}

    # Try match API (most precise)
    if getattr(settings, "OPENSANCTIONS_API_KEY", ""):
        result = _via_match_api(entity_name, legal_name)

    # Fall back to search API
    if not result and getattr(settings, "OPENSANCTIONS_API_KEY", ""):
        result = _via_search_api(entity_name)

    # Always fall back to free bulk check
    if not result:
        result = _via_bulk_names(entity_name)

    if not result:
        result = {"available": False, "reason": "all_methods_failed"}

    result["source"]       = "opensanctions_ch_seco"
    result["dataset"]      = "ch_seco_sanctions"
    result["screened_at"]  = datetime.utcnow().isoformat()
    result["dataset_url"]  = "https://www.opensanctions.org/datasets/ch_seco_sanctions/"

    # Cache the result
    _RESULT_CACHE[cache_key] = (result, datetime.utcnow())

    return result
