"""
Raven — DefiLlama Provider

Based on official API docs (api.llama.fi):
  GET /protocols                    — all protocols with TVL
  GET /protocol/{protocol}          — TVL + token breakdown for one protocol
  GET /tvl/{protocol}               — simplified current TVL
  GET /summary/dexs/{protocol}      — DEX volume summary
  GET /summary/fees/{protocol}      — fees & revenue summary

For CEX reserves (Binance, Coinbase etc.):
  GET /protocol/{cex-slug}          — DefiLlama tracks CEX reserves as protocols
  Slugs: binance-cex, coinbase-cex, kraken-cex, okx-cex, bybit-cex

For DeFi protocols (Aave, Uniswap etc.):
  Slugs: aave, uniswap, compound-finance, maple-finance

No API key required for public endpoints.
"""

import httpx
from typing import Optional
from datetime import datetime

BASE    = "https://api.llama.fi"
HEADERS = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept":     "application/json",
}

# DeFi protocol slug mappings
PROTOCOL_SLUGS = {
    "aave":          "aave",
    "uniswap":       "uniswap",
    "compound":      "compound-finance",
    "maple-finance": "maple-finance",
    "curve":         "curve-finance",
    "maker":         "makerdao",
    "lido":          "lido",
}

# CEX slugs — DefiLlama tracks exchange reserves as protocols with -cex suffix
CEX_PROTOCOL_SLUGS = {
    "binance":          "binance-cex",
    "coinbase":         "coinbase-cex",
    "coinbase-custody": "coinbase-cex",
    "kraken":           "kraken-cex",
    "okx":              "okx-cex",
    "bybit":            "bybit-cex",
    "gemini":           "gemini-cex",
    "bitfinex":         "bitfinex",
    "bitstamp":         "bitstamp",
    "deribit":          "deribit",
    "crypto-com":       "crypto-com",
    "gate-io":          "gate-io",
    "huobi":            "huobi",
    "kucoin":           "kucoin",
}

# DEX slugs for volume data
DEX_SLUGS = {
    "uniswap":       "uniswap",
    "curve":         "curve-dex",
    "1inch":         "1inch",
    "sushiswap":     "sushiswap",
    "dydx":          "dydx",
    "gmx":           "gmx",
}


def get_protocol_tvl(slug: str) -> Optional[dict]:
    """
    GET /protocol/{protocol}
    Returns TVL, token breakdown, 30d change.
    Works for both DeFi protocols and CEX reserves.
    """
    try:
        r = httpx.get(f"{BASE}/protocol/{slug}", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"[defillama] /protocol/{slug}: HTTP {r.status_code}")
            return None

        data = r.json()

        # Current TVL
        chain_tvls = data.get("currentChainTvls", {})
        total_tvl  = sum(float(v) for v in chain_tvls.values()) if chain_tvls else 0
        if not total_tvl:
            # Try tvl array
            tvl_arr = data.get("tvl", [])
            if isinstance(tvl_arr, list) and tvl_arr:
                total_tvl = float(tvl_arr[-1].get("totalLiquidityUSD", 0))

        # 30d change
        tvl_history = data.get("tvl", [])
        change_30d  = None
        if isinstance(tvl_history, list) and len(tvl_history) >= 30:
            cur  = float(tvl_history[-1].get("totalLiquidityUSD", 0))
            past = float(tvl_history[-30].get("totalLiquidityUSD", 0))
            if past > 0:
                change_30d = (cur - past) / past

        # Audit count from data
        audit_count = len(data.get("audits", []))
        chains      = list(chain_tvls.keys()) if chain_tvls else data.get("chains", [])

        # Token breakdown (latest)
        tokens_hist = data.get("tokensInUsd", [])
        tokens      = tokens_hist[-1].get("tokens", {}) if tokens_hist else {}

        return {
            "tvl_usd":         total_tvl,
            "tvl_change_30d":  change_30d,
            "chains":          chains,
            "audit_count":     audit_count,
            "name":            data.get("name"),
            "category":        data.get("category"),
            "tokens":          tokens,
        }
    except Exception as e:
        print(f"[defillama] protocol {slug} error: {e}")
    return None


def get_dex_volume(slug: str) -> Optional[dict]:
    """
    GET /summary/dexs/{protocol}
    Returns DEX trading volume summary.
    """
    try:
        r = httpx.get(f"{BASE}/summary/dexs/{slug}", headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            return {
                "volume_24h": data.get("total24h"),
                "volume_7d":  data.get("total7d"),
                "volume_30d": data.get("total30d"),
            }
    except Exception as e:
        print(f"[defillama] dex volume {slug} error: {e}")
    return None


def get_fees(slug: str) -> Optional[dict]:
    """
    GET /summary/fees/{protocol}
    Returns protocol fees and revenue.
    """
    try:
        r = httpx.get(f"{BASE}/summary/fees/{slug}", headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            return {
                "fees_24h":    data.get("total24h"),
                "revenue_24h": data.get("revenue24h"),
                "fees_30d":    data.get("total30d"),
            }
    except Exception as e:
        print(f"[defillama] fees {slug} error: {e}")
    return None


def enrich_counterparty(slug: str, entity_type: str) -> dict:
    """Main entry point."""
    result = {"source": "defillama", "fetched_at": datetime.utcnow().isoformat()}

    if entity_type == "defi_protocol":
        dl_slug = PROTOCOL_SLUGS.get(slug, slug)
        tvl     = get_protocol_tvl(dl_slug)
        if tvl:
            result["tvl_usd"]    = tvl["tvl_usd"]
            result["audit_count"] = tvl["audit_count"]
            result["chains"]     = tvl["chains"]
            change = tvl.get("tvl_change_30d")
            if change is not None:
                result["tvl_change_30d_pct"] = change
                if change > 0.10:
                    result["onchain_reserve_trend_30d"] = "increasing"
                elif change > -0.10:
                    result["onchain_reserve_trend_30d"] = "stable"
                elif change > -0.30:
                    result["onchain_reserve_trend_30d"] = "declining"
                else:
                    result["onchain_reserve_trend_30d"] = "critical_outflow"

        # Also try DEX volume
        dex_slug = DEX_SLUGS.get(slug)
        if dex_slug:
            vol = get_dex_volume(dex_slug)
            if vol:
                result["volume_24h_usd"] = vol["volume_24h"]

    elif entity_type == "exchange":
        # CEX reserves via /protocol/{cex-slug}
        cex_slug = CEX_PROTOCOL_SLUGS.get(slug)
        if cex_slug:
            tvl = get_protocol_tvl(cex_slug)
            if tvl:
                result["tvl_usd"]        = tvl["tvl_usd"]
                result["volume_24h_usd"] = tvl["tvl_usd"]  # total reserves as proxy
                change = tvl.get("tvl_change_30d")
                if change is not None:
                    result["onchain_reserve_trend_30d"] = (
                        "increasing"      if change > 0.10  else
                        "stable"          if change > -0.10 else
                        "declining"       if change > -0.30 else
                        "critical_outflow"
                    )

    return result
