"""
Raven — DefiLlama Data Provider
Free, no API key required. Best source for DeFi TVL and exchange on-chain data.

Covers:
- Protocol TVL (Aave, Uniswap, Compound, Maple Finance)
- TVL 30d change
- Exchange on-chain volumes
- Chain-level breakdown
"""

import httpx
from typing import Optional
from datetime import datetime, timedelta

BASE = "https://api.llama.fi"

# Slug mappings: our counterparty slug → DefiLlama protocol slug
PROTOCOL_SLUGS = {
    "aave":        "aave",
    "uniswap":     "uniswap",
    "compound":    "compound-finance",
    "maple-finance": "maple-finance",
}

# Exchange slug mappings for DefiLlama exchange tracker
EXCHANGE_SLUGS = {
    "binance":    "binance",
    "coinbase":   "coinbase",
    "kraken":     "kraken",
    "okx":        "okx",
    "bybit":      "bybit",
    "deribit":    "deribit",
    "gemini":     "gemini",
    "bitstamp":   "bitstamp",
}


def get_protocol_tvl(slug: str) -> Optional[dict]:
    """
    Get current TVL and 30d change for a DeFi protocol.
    Returns dict with tvl_usd, tvl_change_30d_pct, chains, audits.
    """
    dl_slug = PROTOCOL_SLUGS.get(slug)
    if not dl_slug:
        return None

    try:
        r = httpx.get(f"{BASE}/protocol/{dl_slug}", timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        tvl_current = data.get("currentChainTvls", {})
        total_tvl   = sum(tvl_current.values()) if tvl_current else data.get("tvl", 0)

        # Calculate 30d change from historical TVL
        tvl_history = data.get("tvl", [])
        change_30d  = None
        if isinstance(tvl_history, list) and len(tvl_history) >= 30:
            current = tvl_history[-1].get("totalLiquidityUSD", 0)
            past_30 = tvl_history[-30].get("totalLiquidityUSD", 0)
            if past_30 > 0:
                change_30d = (current - past_30) / past_30

        # Audit count from DefiLlama
        audits = data.get("audits", [])

        return {
            "source":           "defillama",
            "tvl_usd":          total_tvl,
            "tvl_change_30d":   change_30d,
            "chains":           list(tvl_current.keys()),
            "audit_count":      len(audits) if isinstance(audits, list) else 0,
            "category":         data.get("category"),
            "fetched_at":       datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"[defillama] Error fetching protocol {dl_slug}: {e}")
        return None


def get_exchange_volume(slug: str) -> Optional[dict]:
    """
    Get 24h and 7d volume for an exchange from DefiLlama DEX tracker.
    Returns dict with volume_24h_usd, volume_7d_usd.
    """
    dl_slug = EXCHANGE_SLUGS.get(slug)
    if not dl_slug:
        return None

    try:
        r = httpx.get(
            f"{BASE}/overview/dexs/{dl_slug}",
            params={"excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "source":        "defillama",
                "volume_24h":    data.get("total24h"),
                "volume_7d":     data.get("total7d"),
                "volume_30d":    data.get("total30d"),
                "fetched_at":    datetime.utcnow().isoformat(),
            }
    except Exception as e:
        print(f"[defillama] Error fetching exchange {dl_slug}: {e}")

    return None


def get_all_protocols() -> list:
    """Fetch summary list of all DeFi protocols with TVL."""
    try:
        r = httpx.get(f"{BASE}/protocols", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def enrich_counterparty(slug: str, entity_type: str) -> dict:
    """
    Main entry point. Returns enrichment data for a counterparty from DefiLlama.
    """
    result = {"source": "defillama", "fetched_at": datetime.utcnow().isoformat()}

    if entity_type == "defi_protocol":
        tvl_data = get_protocol_tvl(slug)
        if tvl_data:
            result["tvl_usd"]          = tvl_data["tvl_usd"]
            result["tvl_change_30d"]   = tvl_data["tvl_change_30d"]
            result["audit_count"]      = tvl_data["audit_count"]
            result["chains"]           = tvl_data["chains"]

            # Map to scoring engine fields
            if tvl_data["tvl_change_30d"] is not None:
                pct = tvl_data["tvl_change_30d"]
                if pct > 0.10:
                    result["onchain_reserve_trend_30d"] = "increasing"
                elif pct > -0.10:
                    result["onchain_reserve_trend_30d"] = "stable"
                elif pct > -0.30:
                    result["onchain_reserve_trend_30d"] = "declining"
                else:
                    result["onchain_reserve_trend_30d"] = "critical_outflow"

            result["tvl_change_30d_pct"] = tvl_data["tvl_change_30d"]

    elif entity_type == "exchange":
        vol_data = get_exchange_volume(slug)
        if vol_data:
            result["volume_24h_usd"] = vol_data["volume_24h"]

    return result
