"""
Raven — Portfolio Risk Analytics Engine

Computes comprehensive risk analytics for each portfolio:
- Weighted counterparty risk score (exposure-weighted composite scores)
- Risk tier breakdown (AUM in LOW/MEDIUM/HIGH/CRITICAL)
- Jurisdiction concentration (CH/GB/US/offshore)
- Entity type breakdown (exchange/custodian/DeFi/etc.)
- Concentration warnings (>20% single counterparty)
- Limit monitoring (per client mandate limits)
- FINMA compliance flags (SRO-only custodians)
- Correlation risk groups (exchange cluster, regulator cluster)
- Score trends (Δ7d, Δ30d)
- Alert counts and report status
"""

from datetime import datetime, date
from typing import Optional
from app.core.database import supabase
from app.core.config import settings


# Counterparties that correlate — stress event affects all in group
CORRELATION_GROUPS = [
    {
        "group":       "CeFi Exchange Cluster",
        "description": "All centralised exchanges — correlated to crypto market stress / regulatory crackdown",
        "entity_types": ["exchange"],
        "threshold_pct": 0.40,  # warn if >40% in this group
    },
    {
        "group":       "Swiss FINMA Regulated",
        "description": "All FINMA-supervised entities — correlated to Swiss regulatory events",
        "regulator_prefix": "FINMA",
        "threshold_pct": 0.60,
    },
    {
        "group":       "DeFi Protocol Cluster",
        "description": "All DeFi protocols — correlated to smart contract risk / DeFi market stress",
        "entity_types": ["defi_protocol"],
        "threshold_pct": 0.20,
    },
    {
        "group":       "UK FCA Regulated",
        "description": "All FCA-supervised entities — correlated to UK regulatory events",
        "regulator_prefix": "FCA",
        "threshold_pct": 0.40,
    },
]

# Jurisdiction groupings
JURISDICTION_GROUPS = {
    "CH": "Switzerland",
    "GB": "United Kingdom",
    "US": "United States",
    "DE": "Germany",
    "SG": "Singapore",
    "KY": "Cayman Islands",
    "BVI": "British Virgin Islands",
}

OFFSHORE_JURISDICTIONS = {"KY", "BVI", "VG", "BS", "SC"}


def compute_portfolio_risk(portfolio_id: str) -> dict:
    """
    Main entry point. Computes all risk analytics for a portfolio.
    Stores results in portfolio_risk_cache.
    Returns the computed analytics dict.
    """
    # Load portfolio
    pf = (
        supabase.table("portfolios")
        .select("*, clients(client_id, display_name, mandate_params)")
        .eq("portfolio_id", portfolio_id)
        .single()
        .execute()
        .data
    )
    if not pf:
        return {"error": "Portfolio not found"}

    # Load positions with counterparty data
    positions = (
        supabase.table("portfolio_positions")
        .select("*, custodian:counterparties!custodian_id(counterparty_id, display_name, entity_type, jurisdiction, regulator, current_risk_tier, latest_score_id, enrichment_data)")
        .eq("portfolio_id", portfolio_id)
        .execute()
        .data
    ) or []

    total_nav = float(pf.get("total_nav_chf") or 0)
    if not total_nav:
        total_nav = sum(float(p.get("market_value_chf") or 0) for p in positions)

    if total_nav == 0:
        return {"error": "Portfolio has no NAV"}

    # Load all counterparty scores for positions
    cp_ids = list({p["custodian"]["counterparty_id"] for p in positions
                   if p.get("custodian") and p["custodian"].get("counterparty_id")})

    scores_by_cp = {}
    if cp_ids:
        scores_raw = (
            supabase.table("counterparties")
            .select("counterparty_id, latest_score_id, current_risk_tier, composite_score:counterparty_scores(composite_score, score_delta_7d, score_delta_30d)")
            .in_("counterparty_id", cp_ids)
            .execute()
            .data
        ) or []
        for row in scores_raw:
            scores_by_cp[row["counterparty_id"]] = row

    # ── Build counterparty exposure map ───────────────────────
    cp_exposure = {}  # counterparty_id → {name, value_chf, pct, tier, jurisdiction, entity_type, regulator, score}

    for pos in positions:
        cp = pos.get("custodian")
        if not cp or not cp.get("counterparty_id"):
            continue
        cp_id   = cp["counterparty_id"]
        val     = float(pos.get("market_value_chf") or 0)
        if val <= 0:
            continue

        if cp_id not in cp_exposure:
            score_row = scores_by_cp.get(cp_id, {})
            score_data = score_row.get("composite_score")
            if isinstance(score_data, list):
                score_data = score_data[0] if score_data else {}

            cp_exposure[cp_id] = {
                "name":        cp.get("display_name", "Unknown"),
                "entity_type": cp.get("entity_type", ""),
                "jurisdiction": cp.get("jurisdiction", "Unknown"),
                "regulator":   cp.get("regulator", ""),
                "tier":        cp.get("current_risk_tier", "MEDIUM"),
                "score":       float(score_data.get("composite_score", 50)) if score_data else 50.0,
                "delta_7d":    float(score_data.get("score_delta_7d") or 0) if score_data else 0.0,
                "delta_30d":   float(score_data.get("score_delta_30d") or 0) if score_data else 0.0,
                "enrichment":  cp.get("enrichment_data") or {},
                "value_chf":   0.0,
            }
        cp_exposure[cp_id]["value_chf"] += val

    # Add percentage
    for cp_id, data in cp_exposure.items():
        data["pct"] = data["value_chf"] / total_nav

    # ── Weighted risk score ───────────────────────────────────
    weighted_score = sum(d["score"] * d["pct"] for d in cp_exposure.values()) if cp_exposure else 50.0
    weighted_score = round(weighted_score, 2)

    # ── Score delta (weighted) ────────────────────────────────
    delta_7d  = sum(d["delta_7d"]  * d["pct"] for d in cp_exposure.values())
    delta_30d = sum(d["delta_30d"] * d["pct"] for d in cp_exposure.values())

    # ── Risk tier breakdown ───────────────────────────────────
    tier_breakdown = {"LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0, "CRITICAL": 0.0}
    for d in cp_exposure.values():
        tier = d["tier"] or "MEDIUM"
        tier_breakdown[tier] = tier_breakdown.get(tier, 0.0) + d["value_chf"]

    # ── Jurisdiction breakdown ────────────────────────────────
    juris_breakdown = {}
    for d in cp_exposure.values():
        j = d["jurisdiction"] or "Unknown"
        juris_breakdown[j] = juris_breakdown.get(j, 0.0) + d["value_chf"]

    offshore_total = sum(v for k, v in juris_breakdown.items() if k in OFFSHORE_JURISDICTIONS)

    # ── Entity type breakdown ─────────────────────────────────
    type_breakdown = {}
    for d in cp_exposure.values():
        t = d["entity_type"] or "other"
        type_breakdown[t] = type_breakdown.get(t, 0.0) + d["value_chf"]

    # ── Concentration warnings (>15% single counterparty) ─────
    concentration_warnings = []
    for cp_id, d in sorted(cp_exposure.items(), key=lambda x: -x[1]["pct"]):
        if d["pct"] >= 0.15:
            concentration_warnings.append({
                "counterparty_id": cp_id,
                "name":       d["name"],
                "pct":        round(d["pct"] * 100, 1),
                "value_chf":  round(d["value_chf"], 0),
                "tier":       d["tier"],
                "severity":   "CRITICAL" if d["pct"] >= 0.30 else "HIGH" if d["pct"] >= 0.20 else "WARNING",
            })

    # ── Limit monitoring ──────────────────────────────────────
    client_id = pf.get("client_id")
    limits = []
    if client_id:
        limits_raw = (
            supabase.table("client_limits")
            .select("*")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .execute()
            .data
        ) or []
        limits = limits_raw

    limit_breaches = []
    for lim in limits:
        limit_pct = float(lim["limit_pct"])
        ltype     = lim["limit_type"]
        lkey      = lim["limit_key"]
        actual    = 0.0

        if ltype == "counterparty" and lkey == "any_single":
            if cp_exposure:
                actual = max(d["pct"] for d in cp_exposure.values())
        elif ltype == "jurisdiction" and lkey == "any_single":
            if juris_breakdown:
                actual = max(v / total_nav for v in juris_breakdown.values())
        elif ltype == "risk_tier":
            actual = tier_breakdown.get(lkey, 0.0) / total_nav
        elif ltype == "counterparty":
            # specific counterparty slug
            for d in cp_exposure.values():
                if d["name"].lower().replace(" ", "-") == lkey:
                    actual = d["pct"]

        status = "OK"
        if actual > limit_pct:
            status = "BREACH"
        elif actual > limit_pct * 0.85:
            status = "WARNING"

        if status != "OK":
            limit_breaches.append({
                "type":       ltype,
                "key":        lkey,
                "limit_pct":  round(limit_pct * 100, 1),
                "actual_pct": round(actual * 100, 1),
                "status":     status,
            })

    # ── FINMA compliance flags ────────────────────────────────
    finma_flags = []
    for cp_id, d in cp_exposure.items():
        enrichment = d.get("enrichment", {})
        # Check for FINMA non-compliance flag from regulatory engine
        if enrichment.get("_finma_compliance_flag"):
            finma_flags.append({
                "counterparty_id": cp_id,
                "name":   d["name"],
                "pct":    round(d["pct"] * 100, 1),
                "reason": enrichment["_finma_compliance_flag"],
            })
        # Check for custodians with license_active=False
        elif (d["entity_type"] == "custodian" and
              enrichment.get("license_active") is False and
              d["jurisdiction"] != "CH"):
            finma_flags.append({
                "counterparty_id": cp_id,
                "name":   d["name"],
                "pct":    round(d["pct"] * 100, 1),
                "reason": "Custodian licence not confirmed active — requires FINMA equivalence verification",
            })

    finma_compliant = len(finma_flags) == 0

    # ── Correlation risk groups ───────────────────────────────
    correlation_groups = []
    for group in CORRELATION_GROUPS:
        group_cps   = []
        group_value = 0.0

        for cp_id, d in cp_exposure.items():
            in_group = False
            if "entity_types" in group and d["entity_type"] in group["entity_types"]:
                in_group = True
            if "regulator_prefix" in group and d["regulator"].startswith(group["regulator_prefix"]):
                in_group = True
            if in_group:
                group_cps.append({"name": d["name"], "pct": round(d["pct"] * 100, 1)})
                group_value += d["value_chf"]

        if len(group_cps) >= 2:
            group_pct = group_value / total_nav
            if group_pct >= group["threshold_pct"]:
                correlation_groups.append({
                    "group":       group["group"],
                    "description": group["description"],
                    "entities":    group_cps,
                    "combined_pct": round(group_pct * 100, 1),
                    "value_chf":   round(group_value, 0),
                    "severity":    "HIGH" if group_pct >= group["threshold_pct"] * 1.5 else "WARNING",
                })

    # ── Alert count ───────────────────────────────────────────
    alert_count = 0
    if cp_ids:
        alerts = (
            supabase.table("alerts")
            .select("alert_id")
            .in_("counterparty_id", cp_ids)
            .eq("status", "OPEN")
            .execute()
            .data
        ) or []
        alert_count = len(alerts)

    # ── Report status ─────────────────────────────────────────
    latest_report = (
        supabase.table("reports")
        .select("status, created_at, approved_at")
        .eq("portfolio_id", portfolio_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    report_status = latest_report[0]["status"] if latest_report else None
    report_date   = latest_report[0]["created_at"][:10] if latest_report else None

    # ── Assemble result ───────────────────────────────────────
    result = {
        "portfolio_id":         portfolio_id,
        "computed_at":          datetime.utcnow().isoformat(),
        "total_nav_chf":        round(total_nav, 2),
        "weighted_risk_score":  weighted_score,
        "score_delta_7d":       round(delta_7d, 2),
        "score_delta_30d":      round(delta_30d, 2),
        "risk_tier_breakdown":  {k: round(v, 2) for k, v in tier_breakdown.items()},
        "jurisdiction_breakdown": {k: round(v, 2) for k, v in juris_breakdown.items()},
        "entity_type_breakdown": {k: round(v, 2) for k, v in type_breakdown.items()},
        "offshore_total_chf":   round(offshore_total, 2),
        "concentration_warnings": concentration_warnings,
        "limit_breaches":       limit_breaches,
        "finma_compliant":      finma_compliant,
        "finma_flags":          finma_flags,
        "correlation_groups":   correlation_groups,
        "open_alert_count":     alert_count,
        "latest_report_status": report_status,
        "latest_report_date":   report_date,
        "counterparty_exposures": [
            {
                "counterparty_id": cp_id,
                "name":       d["name"],
                "entity_type": d["entity_type"],
                "jurisdiction": d["jurisdiction"],
                "tier":       d["tier"],
                "score":      d["score"],
                "pct":        round(d["pct"] * 100, 1),
                "value_chf":  round(d["value_chf"], 2),
            }
            for cp_id, d in sorted(cp_exposure.items(), key=lambda x: -x[1]["value_chf"])
        ],
    }

    # Cache results
    try:
        supabase.table("portfolio_risk_cache").upsert({
            "tenant_id":             settings.DEFAULT_TENANT_ID,
            "portfolio_id":          portfolio_id,
            "computed_at":           result["computed_at"],
            "weighted_risk_score":   weighted_score,
            "risk_tier_breakdown":   result["risk_tier_breakdown"],
            "jurisdiction_breakdown": result["jurisdiction_breakdown"],
            "entity_type_breakdown": result["entity_type_breakdown"],
            "concentration_warnings": concentration_warnings,
            "limit_breaches":        limit_breaches,
            "finma_compliant":       finma_compliant,
            "finma_flags":           finma_flags,
            "correlation_groups":    correlation_groups,
            "score_delta_7d":        round(delta_7d, 2),
            "score_delta_30d":       round(delta_30d, 2),
            "open_alert_count":      alert_count,
            "latest_report_status":  report_status,
            "latest_report_date":    report_date,
            "counterparty_exposures": result["counterparty_exposures"],
        }, on_conflict="portfolio_id").execute()
    except Exception as e:
        print(f"[portfolio_risk] Cache write error: {e}")

    return result


def compute_client_risk(client_id: str) -> dict:
    """
    Aggregate risk across all portfolios for a client.
    Used for client overview page and cross-portfolio limit checks.
    """
    portfolios = (
        supabase.table("portfolios")
        .select("portfolio_id, display_name, total_nav_chf, base_currency")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
        .data
    ) or []

    if not portfolios:
        return {"client_id": client_id, "portfolios": [], "total_aum_chf": 0}

    total_aum = sum(float(p.get("total_nav_chf") or 0) for p in portfolios)

    # Get risk cache for each portfolio
    portfolio_ids = [p["portfolio_id"] for p in portfolios]
    caches = (
        supabase.table("portfolio_risk_cache")
        .select("*")
        .in_("portfolio_id", portfolio_ids)
        .execute()
        .data
    ) or []

    cache_by_pf = {c["portfolio_id"]: c for c in caches}

    # Aggregate counterparty exposure across all portfolios
    combined_cp_exposure = {}
    total_weighted_score = 0.0
    total_alerts = 0

    for pf in portfolios:
        pf_id  = pf["portfolio_id"]
        nav    = float(pf.get("total_nav_chf") or 0)
        cache  = cache_by_pf.get(pf_id, {})

        if cache.get("weighted_risk_score") and total_aum > 0:
            total_weighted_score += float(cache["weighted_risk_score"]) * (nav / total_aum)

        total_alerts += int(cache.get("open_alert_count") or 0)

        # Aggregate counterparty exposures
        if cache.get("concentration_warnings"):
            for warning in cache["concentration_warnings"]:
                name = warning["name"]
                val  = float(warning.get("value_chf") or 0)
                if name not in combined_cp_exposure:
                    combined_cp_exposure[name] = {"value_chf": 0, "tier": warning.get("tier")}
                combined_cp_exposure[name]["value_chf"] += val

    # Find cross-portfolio concentration breaches
    cross_portfolio_warnings = []
    if total_aum > 0:
        for name, data in sorted(combined_cp_exposure.items(), key=lambda x: -x[1]["value_chf"]):
            pct = data["value_chf"] / total_aum
            if pct >= 0.15:
                cross_portfolio_warnings.append({
                    "name":      name,
                    "pct":       round(pct * 100, 1),
                    "value_chf": round(data["value_chf"], 0),
                    "tier":      data.get("tier"),
                    "note":      "Combined exposure across all portfolios",
                })

    return {
        "client_id":                 client_id,
        "total_aum_chf":             round(total_aum, 2),
        "weighted_risk_score":       round(total_weighted_score, 2),
        "total_open_alerts":         total_alerts,
        "portfolio_count":           len(portfolios),
        "cross_portfolio_warnings":  cross_portfolio_warnings,
        "portfolios":                [
            {
                **p,
                "risk": cache_by_pf.get(p["portfolio_id"], {}),
            }
            for p in portfolios
        ],
    }
