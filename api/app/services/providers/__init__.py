"""
Raven — Data Provider Orchestrator
Coordinates DefiLlama, SEC EDGAR, FCA Register, CoinGecko, and NewsAPI
to build the richest possible data profile for each counterparty.

Priority order (highest wins for each field):
1. SEC EDGAR (primary source for public companies)
2. FCA Register (primary source for UK-regulated entities)
3. DefiLlama (primary source for DeFi and exchange on-chain data)
4. CoinGecko (exchange volume and market data)
5. NewsAPI (sentiment — always refreshed)
6. Defaults (scoring engine fallbacks)
"""

import httpx
from datetime import datetime
from typing import Optional
from app.core.config import settings
from app.services.providers import defillama, edgar, fca


def fetch_coingecko_exchange(slug: str) -> dict:
    """Fetch exchange data from CoinGecko."""
    EXCHANGE_IDS = {
        "binance": "binance", "coinbase": "coinbase", "kraken": "kraken",
        "bitstamp": "bitstamp", "deribit": "deribit", "lmax-digital": "lmax",
        "gemini": "gemini", "okx": "okx", "bybit": "bybit",
        "cex-io": "cex", "bitcoin-suisse": None,
    }
    cg_id = EXCHANGE_IDS.get(slug)
    if not cg_id or not settings.COINGECKO_API_KEY:
        return {}

    try:
        r = httpx.get(
            f"https://pro-api.coingecko.com/api/v3/exchanges/{cg_id}",
            headers={"x-cg-demo-api-key": settings.COINGECKO_API_KEY},
            timeout=8,
        )
        if r.status_code == 200:
            d = r.json()
            btc_vol = float(d.get("trade_volume_24h_btc", 0) or 0)
            trust   = d.get("trust_score", 0)
            year    = d.get("year_established")

            result = {
                "source":              "coingecko",
                "volume_24h_usd":      btc_vol * 65000,
                "trust_score":         trust,
                "has_trading_incentive": d.get("has_trading_incentive", False),
            }
            if year:
                current_year = datetime.utcnow().year
                result["years_in_operation"] = current_year - int(year)
            return result
    except Exception as e:
        print(f"[coingecko] Error for {slug}: {e}")
    return {}


def fetch_news_sentiment(display_name: str) -> Optional[float]:
    """Fetch news sentiment from NewsAPI."""
    if not settings.NEWS_API_KEY:
        return None
    try:
        r = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        f'"{display_name}" crypto',
                "language": "en",
                "sortBy":   "relevancy",
                "pageSize": 20,
                "apiKey":   settings.NEWS_API_KEY,
            },
            timeout=8,
        )
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            pos_kw = ["approved","secured","partnership","launched","regulated",
                      "compliant","expansion","growth","licensed","audited"]
            neg_kw = ["hack","breach","fraud","bankrupt","suspended","fine",
                      "lawsuit","penalty","scam","exploit","insolvent","arrested",
                      "charges","criminal","seized","shutdown"]
            pos = sum(1 for a in articles if any(
                k in (a.get("title","") + a.get("description","")).lower() for k in pos_kw))
            neg = sum(1 for a in articles if any(
                k in (a.get("title","") + a.get("description","")).lower() for k in neg_kw))
            if pos + neg > 0:
                return round((pos - neg) / (pos + neg), 3)
    except Exception:
        pass
    return None


def build_counterparty_data(cp: dict) -> dict:
    """
    Build the complete data dict for the scoring engine.
    Pulls from all available providers, with clear source attribution.
    """
    slug         = cp.get("slug", "")
    entity_type  = cp.get("entity_type", "")
    display_name = cp.get("display_name", "")
    enrichment   = cp.get("enrichment_data") or {}

    # Start with enrichment data (highest priority — analyst-verified)
    data = {
        "counterparty_id": cp["counterparty_id"],
        "entity_type":     entity_type,
        "jurisdiction":    cp.get("jurisdiction", ""),
        "regulator":       cp.get("regulator", ""),
        "_sources":        [],  # track which providers contributed
    }

    # ── 1. DefiLlama ──────────────────────────────────────────
    if entity_type in ("defi_protocol", "exchange"):
        dl_data = defillama.enrich_counterparty(slug, entity_type)
        if dl_data.get("tvl_usd") or dl_data.get("volume_24h_usd"):
            data["_sources"].append("defillama")
            if dl_data.get("onchain_reserve_trend_30d"):
                data.setdefault("onchain_reserve_trend_30d", dl_data["onchain_reserve_trend_30d"])
            if dl_data.get("tvl_change_30d_pct") is not None:
                data.setdefault("tvl_change_30d_pct", dl_data["tvl_change_30d_pct"])
            if dl_data.get("audit_count") is not None:
                data.setdefault("audit_count", dl_data["audit_count"])
            if dl_data.get("volume_24h_usd"):
                data.setdefault("volume_24h_usd", dl_data["volume_24h_usd"])

    # ── 2. SEC EDGAR ──────────────────────────────────────────
    edgar_data = edgar.enrich_counterparty(slug)
    if edgar_data.get("available"):
        data["_sources"].append("sec_edgar")
        for field in ("is_publicly_listed", "has_audited_financials",
                      "equity_ratio", "debt_level", "revenue_stability"):
            if edgar_data.get(field) is not None:
                data.setdefault(field, edgar_data[field])

    # ── 3. FCA Register ───────────────────────────────────────
    if cp.get("jurisdiction") == "GB" or cp.get("regulator", "").upper().startswith("FCA"):
        fca_data = fca.enrich_counterparty(slug, display_name)
        if fca_data.get("available"):
            data["_sources"].append("fca_register")
            if fca_data.get("license_active") is not None:
                data.setdefault("license_active", fca_data["license_active"])
            if fca_data.get("enforcement_actions_12m") is not None:
                data.setdefault("enforcement_actions_12m", fca_data["enforcement_actions_12m"])

    # ── 4. CoinGecko ──────────────────────────────────────────
    if entity_type == "exchange":
        cg_data = fetch_coingecko_exchange(slug)
        if cg_data:
            data["_sources"].append("coingecko")
            data.setdefault("volume_24h_usd", cg_data.get("volume_24h_usd", 0))
            if cg_data.get("years_in_operation"):
                data.setdefault("years_in_operation", cg_data["years_in_operation"])

    # ── 5. NewsAPI ────────────────────────────────────────────
    sentiment = fetch_news_sentiment(display_name)
    if sentiment is not None:
        data["news_sentiment_30d"] = sentiment
        data["_sources"].append("newsapi")

    # ── 6. Enrichment data (analyst overrides — highest priority) ──
    # These override anything from APIs
    for field, value in enrichment.items():
        if value is not None and field != "analyst_notes":
            data[field] = value

    # ── 7. Defaults for missing fields ────────────────────────
    defaults = {
        "license_active":                    None,
        "enforcement_actions_12m":           0,
        "is_publicly_listed":                bool((cp.get("external_ids") or {}).get("ticker")),
        "has_audited_financials":            None,
        "equity_ratio":                      None,
        "revenue_stability":                 None,
        "debt_level":                        None,
        "has_soc2":                          False,
        "has_iso27001":                      False,
        "has_insurance":                     None,
        "major_security_incidents":          0,
        "years_in_operation":                5,
        "por_ratio":                         None,
        "reserve_quality":                   None,
        "withdrawal_restrictions_history":   False,
        "volume_24h_usd":                    0,
        "onchain_reserve_trend_30d":         None,
        "tvl_change_30d_pct":                None,
        "audit_count":                       None,
        "news_sentiment_30d":                None,
        "industry_reputation_score":         None,
        "leadership_concerns":               False,
    }
    for field, default in defaults.items():
        data.setdefault(field, default)

    return data
