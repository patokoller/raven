"""
Raven — Alpaca Market Data Service

Fetches real-time and historical prices for traditional financial instruments.
Used to price equity positions in portfolios (AAPL, MSFT, ETFs, etc.)

Alpaca free tier: 15-min delayed data
Alpaca paid tier: real-time data

Setup: get API keys from https://alpaca.markets (paper trading account = free)
Add to Fly.io secrets:
  ALPACA_API_KEY=...
  ALPACA_API_SECRET=...
  ALPACA_BASE_URL=https://data.alpaca.markets  (paper) or https://data.alpaca.markets (live)
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from app.core.config import settings


# Market data endpoint — works with both paper and live API keys
ALPACA_DATA_URL = "https://data.alpaca.markets/v2"
# Paper trading base URL (for order/account endpoints later)
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets/v2"


def _alpaca_headers() -> dict:
    """Auth headers for Alpaca API."""
    if not settings.ALPACA_API_KEY or not settings.ALPACA_API_SECRET:
        raise ValueError("Alpaca API keys not configured. Set ALPACA_API_KEY and ALPACA_API_SECRET.")
    return {
        "APCA-API-KEY-ID":     settings.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET,
    }


def get_latest_price(symbol: str) -> Optional[float]:
    """
    Get latest trade price for an equity symbol.
    Returns price in USD.
    """
    try:
        r = httpx.get(
            f"{ALPACA_DATA_URL}/stocks/{symbol}/trades/latest",
            headers=_alpaca_headers(),
            timeout=8,
        )
        if r.status_code == 200:
            return float(r.json()["trade"]["p"])
    except Exception as e:
        print(f"[alpaca] Failed to get price for {symbol}: {e}")
    return None


def get_latest_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Get latest prices for multiple symbols in one request.
    Returns dict of {symbol: price_usd}
    """
    if not symbols:
        return {}
    try:
        r = httpx.get(
            f"{ALPACA_DATA_URL}/stocks/trades/latest",
            headers=_alpaca_headers(),
            params={"symbols": ",".join(symbols)},
            timeout=10,
        )
        if r.status_code == 200:
            trades = r.json().get("trades", {})
            return {sym: float(data["p"]) for sym, data in trades.items()}
    except Exception as e:
        print(f"[alpaca] Failed to get batch prices: {e}")
    return {}


def get_historical_bars(
    symbol: str,
    days: int = 90,
    timeframe: str = "1Day",
) -> List[dict]:
    """
    Get historical OHLCV bars for a symbol.
    Returns list of {t, o, h, l, c, v} dicts.
    """
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        r = httpx.get(
            f"{ALPACA_DATA_URL}/stocks/{symbol}/bars",
            headers=_alpaca_headers(),
            params={
                "timeframe": timeframe,
                "start":     start,
                "limit":     1000,
                "adjustment": "all",  # adjusted for splits/dividends
            },
            timeout=12,
        )
        if r.status_code == 200:
            return r.json().get("bars", [])
    except Exception as e:
        print(f"[alpaca] Failed to get bars for {symbol}: {e}")
    return []


def get_usd_to_chf_rate() -> float:
    """
    Get approximate USD/CHF exchange rate.
    Uses Alpaca forex data if available, falls back to a cached approximate.
    """
    try:
        # Try Alpaca forex (available on some tiers)
        r = httpx.get(
            f"{ALPACA_DATA_URL}/forex/latest",
            headers=_alpaca_headers(),
            params={"currency_pairs": "USDCHF"},
            timeout=5,
        )
        if r.status_code == 200:
            rates = r.json().get("rates", {})
            if "USDCHF" in rates:
                return float(rates["USDCHF"]["bp"])
    except Exception:
        pass
    # Fallback: approximate rate (update manually if needed)
    return 0.90


def enrich_positions_with_equity_prices(positions: List[dict]) -> List[dict]:
    """
    For portfolio positions identified as equities, fetch live prices from Alpaca
    and update market_value_chf if not already set.

    Args:
        positions: list of position dicts from portfolio_positions table

    Returns:
        Updated positions list with market_value_chf populated for equities
    """
    # Identify equity symbols that need pricing
    equity_symbols = [
        p["asset_symbol"]
        for p in positions
        if p.get("asset_class") == "equity"
        and p.get("market_value_chf") is None
        and p.get("quantity")
    ]

    if not equity_symbols:
        return positions

    prices_usd = get_latest_prices(list(set(equity_symbols)))
    chf_rate   = get_usd_to_chf_rate()

    updated = []
    for p in positions:
        if (
            p.get("asset_class") == "equity"
            and p.get("market_value_chf") is None
            and p["asset_symbol"] in prices_usd
        ):
            price_usd   = prices_usd[p["asset_symbol"]]
            qty         = float(p.get("quantity", 0))
            value_usd   = price_usd * qty
            value_chf   = value_usd * chf_rate
            p = {
                **p,
                "market_value_chf": round(value_chf, 2),
                "price_source": "alpaca",
                "price_usd":    price_usd,
            }
        updated.append(p)
    return updated


def is_configured() -> bool:
    """Check if Alpaca API keys are set."""
    return bool(settings.ALPACA_API_KEY and settings.ALPACA_API_SECRET)
