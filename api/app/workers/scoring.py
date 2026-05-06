"""
Raven — Scoring Worker

Two modes:
- score_all_counterparties(): FAST mode — uses stored enrichment_data only.
  No external API calls. Runs in seconds. Safe for batch use.
- score_single_counterparty(): FULL mode — uses all providers + enrichment.
  Used after research/enrichment updates on a single entity.
"""

from datetime import datetime
from app.core.database import supabase
from app.core.config import settings
from app.services.scoring_engine import ScoringEngine


def _build_data_from_enrichment(cp: dict) -> dict:
    """
    Build scoring data purely from stored enrichment_data.
    Fast, no external API calls. Used for batch rescoring.
    """
    enrichment = cp.get("enrichment_data") or {}
    external   = cp.get("external_ids") or {}

    return {
        "counterparty_id": cp["counterparty_id"],
        "entity_type":     cp.get("entity_type", ""),
        "jurisdiction":    cp.get("jurisdiction", ""),
        "regulator":       cp.get("regulator", ""),
        "_sources":        ["enrichment_data"],

        # Regulatory
        "license_active":          enrichment.get("license_active"),
        "enforcement_actions_12m": enrichment.get("enforcement_actions_12m", 0),

        # Financial
        "is_publicly_listed":      enrichment.get("is_publicly_listed",
                                       bool(external.get("ticker"))),
        "has_audited_financials":  enrichment.get("has_audited_financials"),
        "equity_ratio":            enrichment.get("equity_ratio"),
        "revenue_stability":       enrichment.get("revenue_stability"),
        "debt_level":              enrichment.get("debt_level"),

        # Operational
        "has_soc2":                enrichment.get("has_soc2", False),
        "has_iso27001":            enrichment.get("has_iso27001", False),
        "has_insurance":           enrichment.get("has_insurance"),
        "major_security_incidents":enrichment.get("major_security_incidents", 0),
        "years_in_operation":      enrichment.get("years_in_operation", 5),

        # Liquidity
        "por_ratio":                       enrichment.get("por_ratio"),
        "reserve_quality":                 enrichment.get("reserve_quality"),
        "withdrawal_restrictions_history": enrichment.get("withdrawal_restrictions_history", False),
        "volume_24h_usd":                  enrichment.get("volume_24h_usd", 0),

        # On-chain
        "onchain_reserve_trend_30d": enrichment.get("onchain_reserve_trend_30d"),
        "tvl_change_30d_pct":        enrichment.get("tvl_change_30d_pct"),
        "audit_count":               enrichment.get("audit_count"),

        # Reputation
        "news_sentiment_30d":        enrichment.get("news_sentiment_30d"),
        "industry_reputation_score": enrichment.get("industry_reputation_score"),
        "leadership_concerns":       enrichment.get("leadership_concerns", False),
    }


def score_all_counterparties():
    """
    Fast batch rescore of all counterparties using stored enrichment data only.
    No external API calls — completes in seconds.
    """
    engine = ScoringEngine()
    cps = (
        supabase.table("counterparties")
        .select("counterparty_id, slug, display_name, entity_type, jurisdiction, "
                "regulator, enrichment_data, external_ids, latest_score_id")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    )

    results = {"scored": 0, "errors": 0, "total": len(cps)}

    for cp in cps:
        try:
            data   = _build_data_from_enrichment(cp)
            result = engine.score_counterparty(data)
            record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

            # Get previous score for delta
            if cp.get("latest_score_id"):
                prev = (
                    supabase.table("counterparty_scores")
                    .select("composite_score")
                    .eq("score_id", cp["latest_score_id"])
                    .execute()
                    .data
                )
                if prev:
                    record["score_delta_7d"] = round(
                        result.composite_score - prev[0]["composite_score"], 2)

            # Insert new score
            new_score    = supabase.table("counterparty_scores").insert(record).execute()
            new_score_id = new_score.data[0]["score_id"]

            # Update counterparty pointer
            supabase.table("counterparties").update({
                "latest_score_id":   new_score_id,
                "current_risk_tier": result.risk_tier,
            }).eq("counterparty_id", cp["counterparty_id"]).execute()

            _check_alert_triggers(cp, result,
                prev[0] if cp.get("latest_score_id") and prev else None)

            results["scored"] += 1
            print(f"[scoring] {cp['display_name']}: {result.composite_score:.1f} ({result.risk_tier})")

        except Exception as e:
            results["errors"] += 1
            print(f"[scoring] Error on {cp.get('display_name', cp.get('counterparty_id'))}: {e}")

    print(f"[scoring] Complete — {results['scored']}/{results['total']} scored, {results['errors']} errors")
    return results


def score_single_counterparty(counterparty_id: str):
    """
    Full rescore of one counterparty — uses all providers.
    Called after research or enrichment update on a single entity.
    """
    from app.services.providers import build_counterparty_data

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

    try:
        data = build_counterparty_data(cp)
    except Exception as e:
        print(f"[scoring] Provider error for {cp.get('display_name')}: {e}, falling back to enrichment")
        data = _build_data_from_enrichment(cp)

    result = engine.score_counterparty(data)
    record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

    new_score    = supabase.table("counterparty_scores").insert(record).execute()
    new_score_id = new_score.data[0]["score_id"]

    supabase.table("counterparties").update({
        "latest_score_id":   new_score_id,
        "current_risk_tier": result.risk_tier,
    }).eq("counterparty_id", counterparty_id).execute()

    print(f"[scoring] Single: {cp['display_name']}: {result.composite_score:.1f} ({result.risk_tier})")

    return {
        "scored":          counterparty_id,
        "composite_score": result.composite_score,
        "tier":            result.risk_tier,
        "data_sources":    data.get("_sources", []),
    }


def _check_alert_triggers(cp, result, prev_score):
    threshold = settings.ALERT_SCORE_DROP_THRESHOLD
    if prev_score:
        delta = prev_score["composite_score"] - result.composite_score
        if delta >= threshold:
            supabase.table("alerts").insert({
                "tenant_id":       settings.DEFAULT_TENANT_ID,
                "counterparty_id": cp["counterparty_id"],
                "alert_type":      "score_drop",
                "severity":        "HIGH" if delta >= 20 else "WARNING",
                "title":           f"{cp['display_name']} — Score dropped {delta:.1f} pts",
                "body":            f"Score fell from {prev_score['composite_score']:.1f} to {result.composite_score:.1f}.",
                "metadata":        {
                    "old_score": prev_score["composite_score"],
                    "new_score": result.composite_score,
                    "delta":     delta,
                },
            }).execute()

    if result.risk_tier == "CRITICAL":
        supabase.table("alerts").insert({
            "tenant_id":       settings.DEFAULT_TENANT_ID,
            "counterparty_id": cp["counterparty_id"],
            "alert_type":      "critical_tier",
            "severity":        "CRITICAL",
            "title":           f"{cp['display_name']} — CRITICAL risk tier",
            "body":            f"Score: {result.composite_score:.1f}. Flags: {', '.join(result.flags[:5])}.",
            "metadata":        {"score": result.composite_score, "flags": result.flags},
        }).execute()
