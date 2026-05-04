"""
Raven — Scoring Worker
Runs the 6-dimension scoring engine for all counterparties.
Triggered via API endpoint or background task.
"""

import httpx
from datetime import datetime
from app.core.database import supabase
from app.core.config import settings
from app.services.scoring_engine import ScoringEngine


def fetch_counterparty_data(cp: dict) -> dict:
    """
    Fetch live signals for a counterparty.
    Augments static profile with CoinGecko volume + NewsAPI sentiment.
    """
    data = {
        "counterparty_id": cp["counterparty_id"],
        "entity_type": cp["entity_type"],
        "jurisdiction": cp.get("jurisdiction", ""),
        "regulator": cp.get("regulator", ""),
        "license_active": True,
        "enforcement_actions_12m": 0,
        "is_publicly_listed": bool((cp.get("external_ids") or {}).get("ticker")),
        "has_audited_financials": None,
        "years_in_operation": 5,
        "has_soc2": False,
        "has_iso27001": False,
        "has_insurance": None,
        "major_security_incidents": 0,
        "volume_24h_usd": 0,
        "por_ratio": None,
        "reserve_quality": None,
        "withdrawal_restrictions_history": False,
        "onchain_reserve_trend_30d": None,
        "news_sentiment_30d": None,
    }

    # CoinGecko volume for exchanges
    EXCHANGE_IDS = {
        "binance": "binance", "coinbase": "coinbase", "kraken": "kraken",
        "bitstamp": "bitstamp", "deribit": "deribit", "lmax-digital": "lmax",
    }
    cg_id = EXCHANGE_IDS.get(cp["slug"])
    if cg_id and settings.COINGECKO_API_KEY:
        try:
            r = httpx.get(
                f"https://pro-api.coingecko.com/api/v3/exchanges/{cg_id}",
                headers={"x-cg-demo-api-key": settings.COINGECKO_API_KEY},
                timeout=8,
            )
            if r.status_code == 200:
                btc_vol = r.json().get("trade_volume_24h_btc", 0)
                data["volume_24h_usd"] = float(btc_vol) * 65000
        except Exception:
            pass

    # NewsAPI sentiment
    if settings.NEWS_API_KEY:
        try:
            r = httpx.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f'"{cp["display_name"]}" crypto',
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 15,
                    "apiKey": settings.NEWS_API_KEY,
                },
                timeout=8,
            )
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                pos_kw = ["approved", "secured", "partnership", "launched", "regulated", "compliant"]
                neg_kw = ["hack", "breach", "fraud", "bankrupt", "suspended", "fine", "lawsuit", "penalty", "scam"]
                pos = sum(1 for a in articles if any(k in (a.get("title","") + a.get("description","")).lower() for k in pos_kw))
                neg = sum(1 for a in articles if any(k in (a.get("title","") + a.get("description","")).lower() for k in neg_kw))
                if pos + neg > 0:
                    data["news_sentiment_30d"] = (pos - neg) / (pos + neg)
        except Exception:
            pass

    return data


def score_all_counterparties():
    """Score all active counterparties. Runs in background thread."""
    engine = ScoringEngine()
    counterparties = (
        supabase.table("counterparties")
        .select("*")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    )

    results = {"scored": 0, "errors": 0, "total": len(counterparties)}

    for cp in counterparties:
        try:
            data    = fetch_counterparty_data(cp)
            result  = engine.score_counterparty(data)
            record  = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

            # Compute delta vs previous score
            prev = (
                supabase.table("counterparty_scores")
                .select("composite_score")
                .eq("counterparty_id", cp["counterparty_id"])
                .order("scored_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            if prev:
                record["score_delta_7d"] = round(result.composite_score - prev[0]["composite_score"], 2)

            new_score    = supabase.table("counterparty_scores").insert(record).execute()
            new_score_id = new_score.data[0]["score_id"]

            supabase.table("counterparties").update({
                "latest_score_id": new_score_id,
                "current_risk_tier": result.risk_tier,
            }).eq("counterparty_id", cp["counterparty_id"]).execute()

            _check_alert_triggers(cp, result, prev[0] if prev else None)

            supabase.table("audit_log").insert({
                "tenant_id": settings.DEFAULT_TENANT_ID,
                "event_category": "AGENT",
                "event_type": "score.computed",
                "actor_type": "AGENT",
                "resource_type": "counterparty_scores",
                "resource_id": new_score_id,
                "metadata": {
                    "counterparty_id": cp["counterparty_id"],
                    "composite_score": result.composite_score,
                    "risk_tier": result.risk_tier,
                },
            }).execute()

            results["scored"] += 1

        except Exception as e:
            results["errors"] += 1
            print(f"[scoring] Error scoring {cp.get('display_name')}: {e}")

    return results


def score_single_counterparty(counterparty_id: str):
    """Re-score one counterparty."""
    engine = ScoringEngine()
    cp = (
        supabase.table("counterparties")
        .select("*")
        .eq("counterparty_id", counterparty_id)
        .single()
        .execute()
        .data
    )
    if not cp:
        return {"error": "not found"}

    data   = fetch_counterparty_data(cp)
    result = engine.score_counterparty(data)
    record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

    new_score    = supabase.table("counterparty_scores").insert(record).execute()
    new_score_id = new_score.data[0]["score_id"]

    supabase.table("counterparties").update({
        "latest_score_id": new_score_id,
        "current_risk_tier": result.risk_tier,
    }).eq("counterparty_id", counterparty_id).execute()

    return {"scored": counterparty_id, "composite_score": result.composite_score, "tier": result.risk_tier}


def _check_alert_triggers(cp, result, prev_score):
    threshold = settings.ALERT_SCORE_DROP_THRESHOLD
    if prev_score:
        delta = prev_score["composite_score"] - result.composite_score
        if delta >= threshold:
            supabase.table("alerts").insert({
                "tenant_id": settings.DEFAULT_TENANT_ID,
                "counterparty_id": cp["counterparty_id"],
                "alert_type": "score_drop",
                "severity": "HIGH" if delta >= 20 else "WARNING",
                "title": f"{cp['display_name']} — Score dropped {delta:.1f} pts",
                "body": f"Score fell from {prev_score['composite_score']:.1f} to {result.composite_score:.1f}.",
                "metadata": {"old_score": prev_score["composite_score"], "new_score": result.composite_score, "delta": delta},
            }).execute()

    if result.risk_tier == "CRITICAL":
        supabase.table("alerts").insert({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "counterparty_id": cp["counterparty_id"],
            "alert_type": "critical_tier",
            "severity": "CRITICAL",
            "title": f"{cp['display_name']} — CRITICAL risk tier",
            "body": f"Score: {result.composite_score:.1f}. Flags: {', '.join(result.flags[:5])}.",
            "metadata": {"score": result.composite_score, "flags": result.flags},
        }).execute()
