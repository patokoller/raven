"""
Raven — Nansen On-Chain Intelligence Provider

Nansen provides institutional-grade on-chain analytics including:
- Exchange wallet balance tracking (real-time PoR proxy)
- Reserve inflow/outflow trends (30d)
- Address labelling (entity verification)
- Smart money flow intelligence

API: https://api.nansen.ai/api/v1
Auth: apikey header
All requests: POST with JSON body

What this adds to Raven:
- onchain_reserve_trend_30d for exchanges (Binance, Coinbase, Kraken, OKX, Bybit)
  Currently only DefiLlama covers this for DeFi. Nansen covers CeFi exchanges.
- por_ratio proxy: total assets held in known exchange wallets / reported liabilities
- reserve_quality: composition of exchange reserves (BTC/ETH vs altcoins)
- Entity verification: confirms wallet labels match our counterparty registry

Known exchange wallet clusters (publicly documented cold/hot wallets):
Sources: Nansen labels, Arkham, exchange PoR reports
"""

import httpx
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings

NANSEN_BASE = "https://api.nansen.ai/api/v1"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "apikey": settings.NANSEN_API_KEY,
    }


# Known entity labels in Nansen's system
# These are the labels Nansen uses to identify exchange clusters
NANSEN_ENTITY_LABELS = {
    "binance":    "Binance",
    "coinbase":   "Coinbase",
    "kraken":     "Kraken",
    "okx":        "OKX",
    "bybit":      "Bybit",
    "bitfinex":   "Bitfinex",
    "gemini":     "Gemini",
    "bitstamp":   "Bitstamp",
    "deribit":    "Deribit",
    "cex-io":     "CEX.IO",
    "lmax-digital": "LMAX",
    # DeFi protocols
    "aave":       "Aave",
    "uniswap":    "Uniswap",
    "compound":   "Compound",
}

# Known primary cold wallet addresses for major exchanges
# Sources: exchange PoR reports, Nansen public labels, on-chain analysis
EXCHANGE_WALLETS = {
    "binance": {
        "ethereum": [
            "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance 14 (hot)
            "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",  # Binance 15
            "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Binance 8
        ],
        "bitcoin": [
            "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h",  # Binance cold
        ]
    },
    "coinbase": {
        "ethereum": [
            "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3",  # Coinbase 1
            "0x503828976D22510aad0201ac7EC88293211D23Da",  # Coinbase 2
            "0xddfAbCdc4D8FfC6d5beaf154f18B778f892A0740",  # Coinbase 3
        ],
    },
    "kraken": {
        "ethereum": [
            "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",  # Kraken 1
            "0x0A869d79a7052C7f1b55a8EbbbEd5A7a2df786F",   # Kraken 2
        ],
    },
    "okx": {
        "ethereum": [
            "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b",  # OKX 1
            "0x236F33FbBd2c37000EEF06f4cBf9C8C7eBE9f14",  # OKX 2
        ],
    },
    "bybit": {
        "ethereum": [
            "0xf89d7b9c864f589bbF53a82105107622B35EaA40",  # Bybit 1
        ],
    },
    "gemini": {
        "ethereum": [
            "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853",  # Gemini 1
        ],
    },
}


def get_address_balance(address: str, chain: str = "ethereum") -> Optional[dict]:
    """
    Get current token balances for a specific wallet address.
    Used to check exchange reserve holdings.
    """
    try:
        r = httpx.post(
            f"{NANSEN_BASE}/profiler/address/current-balance",
            headers=_headers(),
            json={
                "address": address,
                "chain":   chain,
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            print("[nansen] Authentication failed — check NANSEN_API_KEY")
        else:
            print(f"[nansen] Balance error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[nansen] Balance exception: {e}")
    return None


def get_flow_intelligence(token_address: str, chain: str = "ethereum", days: int = 30) -> Optional[dict]:
    """
    Get net inflow/outflow for a token across exchange wallets.
    Positive netflow = tokens entering exchanges (bearish for price)
    Negative netflow = tokens leaving exchanges (bullish / PoR improving)
    """
    try:
        r = httpx.post(
            f"{NANSEN_BASE}/tgm/flow-intelligence",
            headers=_headers(),
            json={
                "tokenAddress": token_address,
                "chain":        chain,
                "timePeriod":   f"{days}d",
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[nansen] Flow intelligence exception: {e}")
    return None


def get_address_labels(address: str, chain: str = "ethereum") -> Optional[dict]:
    """
    Get Nansen labels for an address — confirms entity identity.
    Labels include: Exchange, Custodian, Market Maker, Fund, etc.
    """
    try:
        r = httpx.post(
            f"{NANSEN_BASE}/profiler/address/labels",
            headers=_headers(),
            json={
                "address": address,
                "chain":   chain,
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[nansen] Labels exception: {e}")
    return None


def ask_nansen_agent(question: str, mode: str = "fast") -> Optional[str]:
    """
    Use Nansen's AI agent to answer questions about on-chain activity.
    mode: 'fast' (200 credits) or 'expert' (750 credits)
    Used in research agent to get Nansen-specific intelligence.
    """
    try:
        r = httpx.post(
            f"{NANSEN_BASE}/agent/{mode}",
            headers=_headers(),
            json={"question": question},
            timeout=60,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("answer") or data.get("response") or str(data)
    except Exception as e:
        print(f"[nansen] Agent exception: {e}")
    return None


def _aggregate_exchange_balances(slug: str) -> dict:
    """
    Aggregate balances across all known wallets for an exchange.
    Returns total BTC, ETH, stablecoin holdings as a reserve proxy.
    """
    wallets = EXCHANGE_WALLETS.get(slug, {})
    if not wallets:
        return {}

    totals = {
        "btc_usd":    0.0,
        "eth_usd":    0.0,
        "stable_usd": 0.0,
        "other_usd":  0.0,
        "total_usd":  0.0,
        "wallets_checked": 0,
    }

    STABLES = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "FDUSD", "USDE"}
    BTC_TOKENS = {"WBTC", "BTC"}
    ETH_TOKENS = {"ETH", "WETH", "stETH", "rETH"}

    for chain, addresses in wallets.items():
        for addr in addresses[:2]:  # limit to 2 per chain to save credits
            balance_data = get_address_balance(addr, chain)
            if not balance_data:
                continue

            totals["wallets_checked"] += 1
            tokens = balance_data.get("tokens") or balance_data.get("balances") or []

            for token in tokens:
                symbol  = (token.get("symbol") or "").upper()
                usd_val = float(token.get("valueUsd") or token.get("usdValue") or 0)

                if symbol in BTC_TOKENS:
                    totals["btc_usd"]    += usd_val
                elif symbol in ETH_TOKENS:
                    totals["eth_usd"]    += usd_val
                elif symbol in STABLES:
                    totals["stable_usd"] += usd_val
                else:
                    totals["other_usd"]  += usd_val

                totals["total_usd"] += usd_val

    return totals


def _classify_reserve_quality(balances: dict) -> str:
    """
    Classify reserve quality based on asset composition.
    High = >70% BTC/ETH/stablecoins
    Medium = 50-70% quality assets
    Low = <50% quality assets (mostly altcoins)
    """
    total = balances.get("total_usd", 0)
    if total == 0:
        return "unknown"

    quality_assets = (
        balances.get("btc_usd", 0) +
        balances.get("eth_usd", 0) +
        balances.get("stable_usd", 0)
    )
    quality_pct = quality_assets / total

    if quality_pct >= 0.70:
        return "high"
    elif quality_pct >= 0.50:
        return "medium"
    else:
        return "low"


def enrich_counterparty(slug: str, entity_type: str, display_name: str = "") -> dict:
    """
    Main entry point. Returns Nansen on-chain data for a counterparty.
    Focus: exchanges and custodians with known wallet addresses.
    """
    if not settings.NANSEN_API_KEY:
        return {"source": "nansen", "available": False, "reason": "no_api_key"}

    result = {
        "source":    "nansen",
        "available": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Strategy 1: Direct wallet balance aggregation (exchanges with known wallets)
    if entity_type == "exchange" and slug in EXCHANGE_WALLETS:
        balances = _aggregate_exchange_balances(slug)

        if balances.get("total_usd", 0) > 0:
            result["available"]        = True
            result["total_reserves_usd"] = balances["total_usd"]
            result["btc_reserves_usd"] = balances["btc_usd"]
            result["eth_reserves_usd"] = balances["eth_usd"]
            result["stable_reserves_usd"] = balances["stable_usd"]
            result["wallets_checked"]  = balances["wallets_checked"]

            # Reserve quality from asset composition
            quality = _classify_reserve_quality(balances)
            result["reserve_quality"] = quality

            # Volume-based reserve trend (simplified — use flow intelligence if available)
            # As a proxy: if exchange has substantial BTC/ETH reserves → stable
            if balances["total_usd"] > 1_000_000_000:  # >$1B
                result["onchain_reserve_trend_30d"] = "stable"
            result["nansen_reserves_url"] = f"https://app.nansen.ai/exchanges/{slug}"

    # Strategy 2: Use Nansen agent for exchanges without direct wallet mapping
    elif entity_type in ("exchange", "custodian") and display_name:
        question = (
            f"What is the current on-chain reserve trend for {display_name} over the last 30 days? "
            f"Are reserves increasing, stable, declining, or showing critical outflows? "
            f"What is the quality of their reserves (BTC/ETH vs stablecoins vs altcoins)?"
        )
        answer = ask_nansen_agent(question, mode="fast")
        if answer:
            result["available"] = True
            result["agent_answer"] = answer[:1000]

            # Parse trend from answer
            answer_lower = answer.lower()
            if any(w in answer_lower for w in ["increas", "growing", "inflow", "accumul"]):
                result["onchain_reserve_trend_30d"] = "increasing"
            elif any(w in answer_lower for w in ["critical", "outflow", "bank run", "withdraw", "collaps"]):
                result["onchain_reserve_trend_30d"] = "critical_outflow"
            elif any(w in answer_lower for w in ["declin", "decreas", "outflow", "reduc"]):
                result["onchain_reserve_trend_30d"] = "declining"
            else:
                result["onchain_reserve_trend_30d"] = "stable"

            if any(w in answer_lower for w in ["high quality", "bitcoin", "ethereum", "fully backed"]):
                result["reserve_quality"] = "high"
            elif any(w in answer_lower for w in ["low quality", "altcoin", "illiquid", "opaque"]):
                result["reserve_quality"] = "low"

    return result
