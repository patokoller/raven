"""Raven — Report Generation Pipeline"""

import json
import traceback
from datetime import datetime
from decimal import Decimal
from anthropic import Anthropic
from app.core.database import supabase
from app.services.finma_custody import build_portfolio_disclosure
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM = """You are the Report Generation Agent for Raven, a Swiss institutional digital asset counterparty risk platform.
You write in the style of a Tier 1 Swiss private bank: precise, professional, evidence-backed.
FINMA-aligned. Figures in CHF unless noted. Output ONLY valid JSON, no preamble, no markdown."""


class _Encoder(json.JSONEncoder):
    """Handle Decimal and datetime from PostgreSQL."""
    def default(self, o):
        if isinstance(o, Decimal): return float(o)
        if isinstance(o, datetime): return o.isoformat()
        return super().default(o)


def _j(obj) -> str:
    """Safe JSON serialization."""
    return json.dumps(obj, cls=_Encoder, ensure_ascii=False)


def _safe(val, fallback=0):
    """Convert any numeric-ish value to float safely."""
    if val is None: return fallback
    if isinstance(val, dict): return fallback
    if isinstance(val, list): return fallback
    try: return float(val)
    except Exception: return fallback


def _safe_str(val, fallback="") -> str:
    """Convert anything to a safe string."""
    if val is None: return fallback
    if isinstance(val, dict): return fallback
    if isinstance(val, list): return fallback
    return str(val)


def _call(prompt: str) -> dict:
    """Call Claude and parse JSON response."""
    r = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = r.content[0].text.strip()
    # Strip markdown fences if present
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                text = part
                break
    try:
        return json.loads(text)
    except Exception:
        # Return a minimal valid dict so the report doesn't crash
        return {"narrative": text[:500], "error": "json_parse_failed"}


def generate_report(report_id: str, portfolio_id: str, client_id: str):
    try:
        # ── Fetch data ─────────────────────────────────────────────────────
        portfolio = supabase.table("portfolios").select("*").eq("portfolio_id", portfolio_id).single().execute().data or {}
        positions = supabase.table("portfolio_positions").select("*").eq("portfolio_id", portfolio_id).order("market_value_chf", desc=True).limit(20).execute().data or []
        cl        = supabase.table("clients").select("*").eq("client_id", client_id).single().execute().data or {}
        stress_r  = supabase.table("stress_test_results").select("*, stress_scenarios(display_name)").eq("portfolio_id", portfolio_id).order("run_at", desc=True).limit(8).execute().data or []
        cps_raw   = supabase.table("counterparties").select("counterparty_id,slug,display_name,entity_type,jurisdiction,regulator,current_risk_tier,finma_custody_status,enrichment_data").eq("tenant_id", settings.DEFAULT_TENANT_ID).execute().data or []
        alerts    = supabase.table("alerts").select("title,severity,alert_type").eq("tenant_id", settings.DEFAULT_TENANT_ID).in_("status", ["OPEN","ACKNOWLEDGED"]).execute().data or []

        # Strip enrichment_data from cps to avoid JSONB serialization issues in f-strings
        # Keep it only for finma_custody lookups
        cps_light = [{k: v for k, v in cp.items() if k != "enrichment_data"} for cp in cps_raw]

        client_type = _safe_str(cl.get("client_type"), "qualified_investor")
        nav         = _safe(portfolio.get("total_nav_chf"), 0)

        # Risk cache
        risk_rows  = supabase.table("portfolio_risk_cache").select("*").eq("portfolio_id", portfolio_id).execute().data or []
        risk       = risk_rows[0] if risk_rows else {}
        cp_exposures_raw = risk.get("counterparty_exposures") or []
        # Ensure cp_exposures is a list of dicts
        cp_exposures = [e for e in cp_exposures_raw if isinstance(e, dict)]

        # ── Build custodian summary (safe types only) ──────────────────────
        portfolio_custodians = []
        for exp in cp_exposures:
            portfolio_custodians.append({
                "name":         _safe_str(exp.get("name"), "Unknown"),
                "entity_type":  _safe_str(exp.get("entity_type"), ""),
                "jurisdiction": _safe_str(exp.get("jurisdiction"), ""),
                "regulator":    _safe_str(exp.get("regulator"), ""),
                "value_chf":    round(_safe(exp.get("value_chf"), 0)),
                "weight_pct":   round(_safe(exp.get("pct"), 0) * 100 if _safe(exp.get("pct"), 0) < 1 else _safe(exp.get("pct"), 0), 1),
                "risk_tier":    _safe_str(exp.get("tier"), "UNKNOWN"),
                "risk_score":   round(_safe(exp.get("score"), 50)),
                "delta_7d":     round(_safe(exp.get("delta_7d"), 0), 1),
            })

        # ── Pre-compute all JSON strings used in f-string prompts ───────────
        # CRITICAL: dict literals CANNOT be inside f-strings ({{ }} is a set in Python)
        # All list-of-dicts must be serialized BEFORE the f-string.
        custodians_json   = _j(portfolio_custodians)
        custodians_brief  = _j([{"name": c["name"], "tier": c["risk_tier"], "weight_pct": c["weight_pct"]} for c in portfolio_custodians])
        custodian_summary = _j([{"name": c["name"], "value_chf": c["value_chf"], "weight_pct": c["weight_pct"], "tier": c["risk_tier"]} for c in portfolio_custodians])

        # ── Positions grouped by custodian ─────────────────────────────────
        pos_by_custodian: dict = {}
        for p in positions:
            cname = p.get("custodian_name") or "Unknown"
            if not isinstance(cname, str):
                cname = "Unknown"
            pos_by_custodian.setdefault(cname, []).append({
                "symbol":     _safe_str(p.get("asset_symbol")),
                "name":       _safe_str(p.get("asset_name")),
                "value_chf":  round(_safe(p.get("market_value_chf"), 0)),
                "weight_pct": round(_safe(p.get("weight_pct"), 0) * 100, 1),
            })

        # ── Stress test summary ────────────────────────────────────────────
        stress_summary = []
        for r in stress_r:
            sc = r.get("stress_scenarios")
            if not isinstance(sc, dict): sc = {}
            stress_summary.append({
                "scenario": _safe_str(sc.get("display_name"), "?"),
                "pnl_pct":  round(_safe(r.get("portfolio_pnl_pct"), 0) * 100, 1),
                "pnl_chf":  round(_safe(r.get("portfolio_pnl_chf"), 0)),
            })

        pos_json    = _j(pos_by_custodian)
        stress_json = _j(stress_summary) if stress_summary else "None run yet"

        # ── Risk metrics (all safe) ────────────────────────────────────────
        weighted_score  = round(_safe(risk.get("weighted_risk_score"), 50))
        finma_ok        = bool(risk.get("finma_compliant", True))
        conc_warnings   = [w for w in (risk.get("concentration_warnings") or []) if isinstance(w, dict)]
        limit_breaches  = [b for b in (risk.get("limit_breaches") or []) if isinstance(b, dict)]
        alerts_count    = len(alerts)
        alert_titles    = [_safe_str(a.get("title")) for a in alerts]
        warn_names      = [_safe_str(w.get("name")) for w in conc_warnings]
        custodian_names = [c["name"] for c in portfolio_custodians]
        custodian_tiers = [f"{c['name']} ({c['risk_tier']}, {c['risk_score']}/100)" for c in portfolio_custodians]

        conc_json = _j(conc_warnings)

        # ── FINMA Custody Disclosure (s7) — computed first ─────────────────
        s7 = build_portfolio_disclosure(
            counterparty_exposures=cp_exposures,
            client_type=client_type,
            all_counterparties=cps_raw,  # full records needed for custody classification
        )
        # Ensure s7 is JSON-safe
        s7_json = json.loads(_j(s7))

        finma_status     = _safe_str(s7_json.get("overall_status"), "UNKNOWN")
        disclosure_cps   = s7_json.get("disclosure_custodians", [])
        compliant_cps    = s7_json.get("compliant_custodians", [])
        consent_required = bool(s7_json.get("consent_required", False))

        # ── Section 01: Executive Summary ─────────────────────────────────
        s1 = _call(f"""Executive Summary — Raven Counterparty Risk Report.
Do NOT mention VaR, Sharpe ratio, volatility, or drawdown.

Client: {cl.get('display_name')} ({client_type.replace('_',' ')}) | AUM: CHF {nav:,.0f}
Date: {datetime.utcnow().strftime('%d %B %Y')}
Weighted Counterparty Risk Score: {weighted_score}/100
FINMA 01/2026 custody status: {finma_status}
Custodians: {custodian_tiers}
Open alerts: {alerts_count} | Concentration warnings: {warn_names} | Limit breaches: {len(limit_breaches)}

Return JSON: {{"headline":"one sentence","key_findings":["..."],"overall_assessment":"2-3 paragraphs on counterparty risk only","immediate_actions":["..."],"risk_indicator":"GREEN|AMBER|RED"}}""")

        # ── Section 02: Portfolio & Custody Composition ────────────────────
        s2 = _call(f"""Portfolio Composition — Raven Counterparty Risk Report.
Focus on which custodian holds what. Not asset performance.

Client: {cl.get('display_name')} | AUM: CHF {nav:,.0f}
Positions by custodian: {pos_json}
Custodian summary: {custodian_summary}

Return JSON: {{"narrative":"2 paragraphs on custody structure","concentration_assessment":"...","key_exposures":["..."],"diversification_score":"LOW|MEDIUM|HIGH"}}""")

        # ── Section 03: Counterparty Risk Scorecard ────────────────────────
        s3 = _call(f"""Counterparty Risk Scorecard — Raven Report.
This is a counterparty risk report, not a market risk report.
The 6 scoring dimensions are: Regulatory (25%), Financial (20%), Operational (20%), Liquidity (15%), On-Chain (10%), Reputation (10%).

Portfolio weighted score: {weighted_score}/100
FINMA compliant: {'YES' if finma_ok else 'NO'}
Custodians: {custodians_json}

Return JSON: {{"narrative":"2 paragraphs interpreting counterparty risk scores","scorecard_by_custodian":[{{"name":"...","overall_score":0,"tier":"...","strongest_dimension":"...","weakest_dimension":"...","key_risk":"..."}}],"weighted_portfolio_score":{weighted_score},"trend":"improving|stable|deteriorating","trend_rationale":"..."}}""")

        # ── Section 04: Counterparty Analysis ─────────────────────────────
        s4 = _call(f"""Counterparty Analysis — Raven Report.
Analyse ONLY the custodians listed below. Do NOT reference other entities.

Client: {cl.get('display_name')} | AUM: CHF {nav:,.0f}
Custodians: {custodians_json}
FINMA status: {finma_status}
Disclosure required for: {disclosure_cps}
Compliant: {compliant_cps}
Concentration warnings: {warn_names}
Open alerts: {alert_titles}

Return JSON: {{"narrative":"2-3 paragraphs","custodian_concentration_risk":"...","highlighted_concerns":["..."],"watchlist":["..."],"overall_counterparty_assessment":"LOW|MEDIUM|HIGH|CRITICAL"}}""")

        # ── Section 05: Stress Tests ───────────────────────────────────────
        s5 = _call(f"""Stress Test Results — Raven Counterparty Risk Report.
Focus on custody and counterparty failure scenarios.

Portfolio NAV: CHF {nav:,.0f} | Custodians: {custodian_names}
Executed scenarios: {stress_json}

Return JSON: {{"narrative":"...","worst_scenario":"...","resilience_assessment":"...","tail_risk_commentary":"..."}}""")

        # ── Section 06: Recommendations ───────────────────────────────────
        s6 = _call(f"""Recommendations — Raven Counterparty Risk Report.
ALL recommendations about counterparty risk only. No market risk or VaR.

Client: {cl.get('display_name')} ({client_type.replace('_',' ')}) | AUM: CHF {nav:,.0f}
Weighted score: {weighted_score}/100 | FINMA: {finma_status}
Custodians: {custodians_brief}
Disclosure required: {disclosure_cps} | Consent required: {consent_required}
Concentration warnings: {warn_names} | Limit breaches: {len(limit_breaches)}

Return JSON: {{"immediate":[{{"priority":"HIGH","action":"...","rationale":"...","timeline":"..."}}],"short_term":[{{"priority":"MEDIUM","action":"...","rationale":"...","timeline":"..."}}],"monitoring":[{{"item":"...","threshold":"..."}}],"disclaimer":"FINMA/FinSA disclaimer"}}""")

        # ── Save to DB ─────────────────────────────────────────────────────
        supabase.table("reports").update({
            "section_executive_summary":     s1,
            "section_portfolio_composition": s2,
            "section_risk_scorecard":        s3,
            "section_counterparty_analysis": s4,
            "section_stress_test_results":   s5,
            "section_recommendations":       s6,
            "section_regulatory_disclosure": s7_json,
            "status":                        "IN_REVIEW",
            "generation_completed_at":       datetime.utcnow().isoformat(),
            "model_version":                 settings.ANTHROPIC_MODEL,
        }).eq("report_id", report_id).execute()

        supabase.table("audit_log").insert({
            "tenant_id":      settings.DEFAULT_TENANT_ID,
            "event_category": "AGENT",
            "event_type":     "report.generation_completed",
            "actor_type":     "AGENT",
            "resource_type":  "reports",
            "resource_id":    report_id,
            "metadata":       {"model": settings.ANTHROPIC_MODEL, "sections": 7},
        }).execute()

    except Exception as e:
        full_tb = traceback.format_exc()
        print(f"[report_pipeline] ERROR: {full_tb}")
        supabase.table("reports").update({
            "generation_error": f"{str(e)}\n\nTraceback:\n{full_tb}",
            "status": "DRAFT",
        }).eq("report_id", report_id).execute()
        raise
