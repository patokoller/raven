"""
Raven — Nansen On-Chain Intelligence Provider

API: https://api.nansen.ai
Auth: header name is "apiKey" (camelCase)

Endpoints used:
  POST /api/v1/search/general
    - Search for entities by name (e.g. "Binance", "Coinbase")
    - result_type: "entity" to find exchanges, funds, etc.
    - Returns: name, tags, rank

No API key = available: False (graceful degradation).
"""

import httpx
from typing import Optional
from datetime import datetime
from app.core.config import settings

NANSEN_BASE = "https://api.nansen.ai"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "apiKey": settings.NANSEN_API_KEY,   # camelCase per API spec
    }


# Display name mappings: our slug -> Nansen search term
ENTITY_SEARCH_TERMS = {
    "binance":          "Binance",
    "coinbase":         "Coinbase",
    "coinbase-custody": "Coinbase",
    "kraken":           "Kraken",
    "okx":              "OKX",
    "bybit":            "Bybit",
    "bitfinex":         "Bitfinex",
    "gemini":           "Gemini",
    "bitstamp":         "Bitstamp",
    "deribit":          "Deribit",
    "crypto-com":       "Crypto.com",
    "gate-io":          "Gate.io",
    "kucoin":           "KuCoin",
    "huobi":            "Huobi",
    "fireblocks":       "Fireblocks",
    "copper":           "Copper",
    "aave":             "Aave",
    "uniswap":          "Uniswap",
    "compound":         "Compound",
}


def search_entity(search_term: str) -> Optional[dict]:
    """
    POST /api/v1/search/general
    Search for an entity by name. Returns entity data if found.
    """
    try:
        r = httpx.post(
            f"{NANSEN_BASE}/api/v1/search/general",
            headers=_headers(),
            json={
                "search_query": search_term,
                "result_type":  "entity",
                "limit":        5,
            },
            timeout=15,
        )

        if r.status_code == 401:
            print("[nansen] Auth failed — check NANSEN_API_KEY")
            return None
        if r.status_code == 402:
            print("[nansen] Payment required — check subscription tier")
            return None
        if r.status_code == 403:
            print("[nansen] Forbidden — subscription does not include this endpoint")
            return None
        if r.status_code != 200:
            print(f"[nansen] Search HTTP {r.status_code}: {r.text[:100]}")
            return None

        data = r.json()
        entities = data.get("entities", [])

        if not entities:
            return None

        # Find best match by name
        term_lower = search_term.lower()
        for entity in entities:
            if entity.get("name", "").lower() == term_lower:
                return entity
        # Return top result if no exact match
        return entities[0]

    except Exception as e:
        print(f"[nansen] Search error for '{search_term}': {e}")
        return None


def enrich_counterparty(slug: str, entity_type: str = "", display_name: str = "") -> dict:
    """
    Main entry point. Search Nansen for entity data.
    Returns entity name, tags, and rank if found.
    """
    if not settings.NANSEN_API_KEY:
        return {"source": "nansen", "available": False, "reason": "no_api_key"}

    # Determine search term
    search_term = (
        ENTITY_SEARCH_TERMS.get(slug) or
        ENTITY_SEARCH_TERMS.get(slug.lower().replace(" ", "-")) or
        display_name or
        slug.replace("-", " ").title()
    )

    result = {
        "source":     "nansen",
        "available":  False,
        "fetched_at": datetime.utcnow().isoformat(),
        "searched":   search_term,
    }

    entity = search_entity(search_term)

    if not entity:
        # Try with display_name if different from slug-derived term
        if display_name and display_name != search_term:
            entity = search_entity(display_name)

    if not entity:
        result["reason"] = "entity_not_found"
        return result

    result["available"]     = True
    result["nansen_name"]   = entity.get("name")
    result["nansen_tags"]   = entity.get("tags", [])
    result["nansen_rank"]   = entity.get("rank")

    # Map tags to scoring fields
    tags = [t.lower() for t in entity.get("tags", [])]

    # Exchange / custodian signals from tags
    if any(t in tags for t in ("exchange", "cex", "centralized exchange")):
        result["entity_type_confirmed"] = "exchange"
    if any(t in tags for t in ("custodian", "custody")):
        result["entity_type_confirmed"] = "custodian"
    if any(t in tags for t in ("defi", "protocol", "dex")):
        result["entity_type_confirmed"] = "defi_protocol"

    # Risk signals
    if any(t in tags for t in ("hacked", "exploit", "rug")):
        result["nansen_risk_flag"]       = True
        result["enforcement_actions_12m"] = 1

    result["nansen_url"] = f"https://app.nansen.ai/smart-money?search={search_term}"

    return result
