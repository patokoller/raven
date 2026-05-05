"""
Raven — Scoring Worker
Uses the provider orchestrator (DefiLlama + SEC EDGAR + FCA + CoinGecko + NewsAPI)
to build enriched data profiles before scoring.
"""

from datetime import datetime
from app.core.database import supabase
from app.core.config import settings
from app.services.scoring_engine import ScoringEngine
from app.services.providers import build_counterparty_data


def score_all_counterparties():
    """Score all active counterparties using all data providers."""
    engine = ScoringEngine()
    cps = (
        supabase.table("counterparties")
        .select("*")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    )

    results = {"scored": 0, "errors": 0, "total": len(cps)}

    for cp in cps:
        try:
            data   = build_counterparty_data(cp)
            result = engine.score_counterparty(data)
            record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

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
                record["score_delta_7d"] = round(
                    result.composite_score - prev[0]["composite_score"], 2)

            new_score    = supabase.table("counterparty_scores").insert(record).execute()
            new_score_id = new_score.data[0]["score_id"]

            supabase.table("counterparties").update({
                "latest_score_id":   new_score_id,
                "current_risk_tier": result.risk_tier,
            }).eq("counterparty_id", cp["counterparty_id"]).execute()

            _check_alert_triggers(cp, result, prev[0] if prev else None)

            supabase.table("audit_log").insert({
                "tenant_id":      settings.DEFAULT_TENANT_ID,
                "event_category": "AGENT",
                "event_type":     "score.computed",
                "actor_type":     "AGENT",
                "resource_type":  "counterparty_scores",
                "resource_id":    new_score_id,
                "metadata": {
                    "counterparty_id":  cp["counterparty_id"],
                    "composite_score":  result.composite_score,
                    "risk_tier":        result.risk_tier,
                    "data_sources":     data.get("_sources", []),
                },
            }).execute()

            results["scored"] += 1
            print(f"[scoring] {cp['display_name']}: {result.composite_score:.1f} "
                  f"({result.risk_tier}) sources={data.get('_sources', [])}")

        except Exception as e:
            results["errors"] += 1
            print(f"[scoring] Error scoring {cp.get('display_name')}: {e}")

    return results


def score_single_counterparty(counterparty_id: str):
    """Re-score one counterparty using all data providers."""
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

    data   = build_counterparty_data(cp)
    result = engine.score_counterparty(data)
    record = engine.to_db_record(result, settings.DEFAULT_TENANT_ID)

    new_score    = supabase.table("counterparty_scores").insert(record).execute()
    new_score_id = new_score.data[0]["score_id"]

    supabase.table("counterparties").update({
        "latest_score_id":   new_score_id,
        "current_risk_tier": result.risk_tier,
    }).eq("counterparty_id", counterparty_id).execute()

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
                    "flags":     result.flags,
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
