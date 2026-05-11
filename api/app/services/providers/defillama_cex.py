"""
Raven — DefiLlama CEX Transparency Provider

DefiLlama tracks CEX proof-of-reserves as protocol TVL.
Correct endpoint: GET https://api.llama.fi/protocol/{cex-slug}

CEX slugs (confirmed from DefiLlama):
  binance-cex, coinbase-cex, kraken-cex, okx-cex, bybit-cex,
  gemini-cex, bitfinex, bitstamp, deribit, crypto-com, gate-io

No API key required.
"""

import httpx
from typing import Optional
from datetime import datetime

BASE    = "https://api.llama.fi"
HEADERS = {
    "User-Agent": "Raven Risk Intelligence / raven.internal",
    "Accept":     "application/json",
}

CEX_SLUGS = {
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
    "lmax-digital":     None,
}


def _classify_quality(total: float, btc: float, eth: float, stable: float) -> str:
    if total == 0:
        return "unknown"
    native_pct = (btc + eth) / total
    stable_pct = stable / total
    if native_pct >= 0.6:
        return "high_native"
    if stable_pct >= 0.5:
        return "stablecoin_heavy"
    if stable_pct + native_pct >= 0.7:
        return "diversified"
    return "mixed"


def _classify_trend(change: Optional[float]) -> str:
    if change is None:
        return "unknown"
    if change > 0.10:
        return "increasing"
    if change > -0.10:
        return "stable"
    if change > -0.30:
        return "declining"
    return "critical_outflow"


def get_cex_reserves(slug: str) -> Optional[dict]:
    """
    Fetch CEX reserves via GET /protocol/{cex-slug}.
    Returns total assets, token breakdown, 30d trend.
    """
    dl_slug = CEX_SLUGS.get(slug)
    if not dl_slug:
        return None

    try:
        r = httpx.get(f"{BASE}/protocol/{dl_slug}", headers=HEADERS, timeout=12)
        if r.status_code != 200:
            print(f"[defillama_cex] /protocol/{dl_slug}: HTTP {r.status_code}")
            return None

        data = r.json()

        # Total reserves (TVL for CEX = proof of reserves)
        chain_tvls = data.get("currentChainTvls", {})
        total_tvl  = sum(float(v) for v in chain_tvls.values()) if chain_tvls else 0
        if not total_tvl:
            tvl_arr = data.get("tvl", [])
            if isinstance(tvl_arr, list) and tvl_arr:
                total_tvl = float(tvl_arr[-1].get("totalLiquidityUSD", 0))

        # 30d trend
        tvl_history = data.get("tvl", [])
        change_30d  = None
        if isinstance(tvl_history, list) and len(tvl_history) >= 30:
            cur  = float(tvl_history[-1].get("totalLiquidityUSD", 0))
            past = float(tvl_history[-30].get("totalLiquidityUSD", 0))
            if past > 0:
                change_30d = (cur - past) / past

        # Token composition for reserve quality
        tokens_hist   = data.get("tokensInUsd", [])
        latest_tokens = tokens_hist[-1].get("tokens", {}) if tokens_hist else {}

        btc_usd    = float(latest_tokens.get("BTC", 0) or latest_tokens.get("WBTC", 0) or 0)
        eth_usd    = float(latest_tokens.get("ETH", 0) or latest_tokens.get("WETH", 0) or 0)
        stable_usd = sum(float(latest_tokens.get(s, 0) or 0)
                         for s in ("USDT", "USDC", "DAI", "BUSD", "FDUSD", "TUSD", "USDE"))
        other_usd  = max(0, total_tvl - btc_usd - eth_usd - stable_usd)

        return {
            "source":           "defillama_cex",
            "total_assets_usd": total_tvl,
            "btc_usd":          btc_usd,
            "eth_usd":          eth_usd,
            "stable_usd":       stable_usd,
            "other_usd":        other_usd,
            "change_30d_pct":   change_30d,
            "reserve_quality":  _classify_quality(total_tvl, btc_usd, eth_usd, stable_usd),
            "reserve_trend":    _classify_trend(change_30d),
            "dl_slug":          dl_slug,
            "dl_url":           f"https://defillama.com/cex/{slug}",
            "fetched_at":       datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"[defillama_cex] {slug} error: {e}")
    return None


def enrich_counterparty(slug: str) -> dict:
    """Main entry point for CEX data."""
    data = get_cex_reserves(slug)
    if not data:
        return {"source": "defillama_cex", "available": False}

    result = {
        "available":                  True,
        "total_assets_usd":           data["total_assets_usd"],
        "reserve_quality":            data["reserve_quality"],
        "onchain_reserve_trend_30d":  data["reserve_trend"],
        "change_30d_pct":             data["change_30d_pct"],
        "dl_url":                     data["dl_url"],
        "source":                     "defillama_cex",
    }
    return result
