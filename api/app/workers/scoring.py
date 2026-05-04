"""
Raven — Scoring Worker
Runs the 6-dimension scoring engine for all counterparties.
Triggered by Celery Beat (daily) or manually via API.
"""

import httpx
from datetime import datetime
from app.workers.celery_app import celery_app
from app.core.database import supabase
from app.core.config import settings
from app.services.scoring_engine import ScoringEngine


def fetch_market_data_for_counterparty(cp: dict) -> dict:
    """
    Fetch live data for a counterparty from CoinGecko and NewsAPI.
    Returns a normalized data dict ready for the scoring engine.
    """
    data = {
        "counterparty_id": cp["counterparty_id"],
        "entity_type": cp["entity_type"],
        "jurisdiction": cp.get("jurisdiction", ""),
        "regulator": cp.get("regulator", ""),
        "license_active": True,          # TODO: pull from regulatory feed
        "enforcement_actions_12m": 0,     # TODO: pull from EDGAR/FCA register
        "is_publicly_listed": cp.get("external_ids", {}).get("ticker") is not None,
        "has_audited_financials": None,
        "years_in_operation": 5,          # TODO: compute from founding date
        "has_soc2": False,               # TODO: pull from certifications DB
        "has_iso27001": False,
        "has_insurance": None,
        "major_security_incidents": 0,    # TODO: pull from incident DB
        "volume_24h_usd": 0,             # filled below for exchanges
        "por_ratio": None,               # filled below if available
        "reserve_quality": None,
        "withdrawal_restrictions_history": False,
        "onchain_reserve_trend_30d": None,
        "news_sentiment_30d": None,       # filled below
    }

    # Fetch CoinGecko volume data for exchanges
    if cp["entity_type"] in ("exchange", "defi_protocol") and settings.COINGECKO_API_KEY:
        slug_map = {
            "binance": "binance", "coinbase": "coinbase", "kraken": "kraken",
            "bitstamp": "bitstamp", "uniswap": "uniswap-v3", "aave": "aave",
        }
        cg_id = slug_map.get(cp["slug"])
        if cg_id:
            try:
                resp = httpx.get(
                    f"https://pro-api.coingecko.com/api/v3/exchanges/{cg_id}",
                    headers={"x-cg-demo-api-key": settings.COINGECKO_API_KEY},
                    timeout=10,
                )
                if resp.status_code == 200:
                    cg = resp.json()
                    data["volume_24h_usd"] = float(cg.get("trade_volume_24h_btc", 0)) * 60000  # rough BTC price
            except Exception:
                pass

    # Fetch news sentiment
    if settings.NEWS_API_KEY:
        try:
            resp = httpx.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": cp["display_name"],
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 20,
                    "from": (datetime.utcnow().strftime("%Y-%m-%d")),
                    "apiKey": settings.NEWS_API_KEY,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                # Simple sentiment: ratio of positive to negative keywords
                positive_kw = ["approved", "secured", "launched", "partnership", "growth", "regulatory approval"]
                negative_kw = ["hack", "breach", "lawsuit", "fraud", "bankrupt", "suspended", "fine", "penalty"]
                pos = sum(1 for a in articles if any(k in (a.get("title", "") + a.get("description", "")).lower() for k in positive_kw))
                neg = sum(1 for a in articles if any(k in (a.get("title", "") + a.get("description", "")).lower() for k in negative_kw))
                total = pos + neg
                if total > 0:
                    data["news_sentiment_30d"] = (pos - neg) / total
        except Exception:
            pass

    return data


@celery_app.task(name="app.workers.scoring.score_all_counterparties_task", bind=True)
def score_all_counterparties_task(self):
    """Score all active counterparties. Run daily."""
    engine = ScoringEngine()

    counterparties = (
        supabase.table("counterparties")
        .select("*")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    )

    results = {"scored": 0, "errors": 0}

    for cp in counterparties:
        try:
            data = fetch_market_data_for_counterparty(cp)
            result = engine.score_counterparty(data)
            db_record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

            # Get previous score for delta computation
            prev = (
                supabase.table("counterparty_scores")
                .select("composite_score, scored_at")
                .eq("counterparty_id", cp["counterparty_id"])
                .order("scored_at", desc=True)
                .limit(1)
                .execute()
                .data
            )

            if prev:
                db_record["score_delta_7d"] = round(result.composite_score - prev[0]["composite_score"], 2)

            # Insert score
            new_score = supabase.table("counterparty_scores").insert(db_record).execute()
            new_score_id = new_score.data[0]["score_id"]

            # Update counterparty with latest score pointer and tier
            supabase.table("counterparties").update({
                "latest_score_id": new_score_id,
                "current_risk_tier": result.risk_tier,
            }).eq("counterparty_id", cp["counterparty_id"]).execute()

            # Check alert triggers
            _check_alert_triggers(cp, result, prev[0] if prev else None)

            # Audit log
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
                    "run_id": result.run_id,
                }
            }).execute()

            results["scored"] += 1

        except Exception as e:
            results["errors"] += 1
            print(f"Error scoring {cp['display_name']}: {e}")

    return results


@celery_app.task(name="app.workers.scoring.recalculate_score_task")
def recalculate_score_task(counterparty_id: str):
    """Re-score a single counterparty (e.g. after human override)."""
    cp = (
        supabase.table("counterparties")
        .select("*")
        .eq("counterparty_id", counterparty_id)
        .single()
        .execute()
        .data
    )
    if not cp:
        return {"error": "counterparty not found"}

    engine = ScoringEngine()
    data = fetch_market_data_for_counterparty(cp)
    result = engine.score_counterparty(data)
    db_record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

    new_score = supabase.table("counterparty_scores").insert(db_record).execute()
    new_score_id = new_score.data[0]["score_id"]

    supabase.table("counterparties").update({
        "latest_score_id": new_score_id,
        "current_risk_tier": result.risk_tier,
    }).eq("counterparty_id", counterparty_id).execute()

    return {"scored": counterparty_id, "composite_score": result.composite_score}


def _check_alert_triggers(cp: dict, result, prev_score):
    """Check if this score update should trigger any alerts."""
    if prev_score:
        delta = prev_score["composite_score"] - result.composite_score
        if delta >= settings.ALERT_SCORE_DROP_THRESHOLD:
            supabase.table("alerts").insert({
                "tenant_id": settings.DEFAULT_TENANT_ID,
                "counterparty_id": cp["counterparty_id"],
                "alert_type": "score_drop",
                "severity": "HIGH" if delta >= 20 else "WARNING",
                "title": f"{cp['display_name']} — Score dropped {delta:.1f} points",
                "body": f"Risk score fell from {prev_score['composite_score']:.1f} to {result.composite_score:.1f}. Investigate immediately.",
                "metadata": {
                    "old_score": prev_score["composite_score"],
                    "new_score": result.composite_score,
                    "delta": delta,
                    "new_tier": result.risk_tier,
                    "flags": result.flags,
                },
            }).execute()

    if result.risk_tier == "CRITICAL":
        supabase.table("alerts").insert({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "counterparty_id": cp["counterparty_id"],
            "alert_type": "critical_tier",
            "severity": "CRITICAL",
            "title": f"{cp['display_name']} — CRITICAL risk tier reached",
            "body": f"Score: {result.composite_score:.1f}. Flags: {', '.join(result.flags[:5])}. Immediate review required.",
            "metadata": {"score": result.composite_score, "flags": result.flags},
        }).execute()
