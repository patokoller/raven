"""Raven — Report Generation Pipeline (no Celery)"""

import json
from datetime import datetime
from anthropic import Anthropic
from app.core.database import supabase
from app.services.finma_custody import build_portfolio_disclosure, classify_custody_status
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM = """You are the Report Generation Agent for Raven, a Swiss institutional digital asset risk platform.
You write in the style of a Tier 1 Swiss private bank: precise, professional, evidence-backed.
FINMA-aligned terminology. Figures in CHF unless noted. Output ONLY valid JSON, no preamble."""


def _call(prompt: str) -> dict:
    r = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=3000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = r.content[0].text
    for tag in ["```json", "```"]:
        if tag in text:
            text = text.split(tag)[1].split("```")[0].strip()
            break
    return json.loads(text)


def generate_report(report_id: str, portfolio_id: str, client_id: str):
    try:
        portfolio = supabase.table("portfolios").select("*").eq("portfolio_id", portfolio_id).single().execute().data
        positions = supabase.table("portfolio_positions").select("*").eq("portfolio_id", portfolio_id).order("market_value_chf", desc=True).limit(15).execute().data
        metrics   = supabase.table("portfolio_metrics").select("*").eq("portfolio_id", portfolio_id).order("computed_at", desc=True).limit(1).execute().data
        cl        = supabase.table("clients").select("*").eq("client_id", client_id).single().execute().data
        stress    = supabase.table("stress_test_results").select("*, stress_scenarios(display_name)").eq("portfolio_id", portfolio_id).order("run_at", desc=True).limit(5).execute().data
        cps       = supabase.table("counterparties").select("counterparty_id,slug,display_name,entity_type,jurisdiction,regulator,current_risk_tier,latest_score_id,finma_custody_status,enrichment_data").eq("tenant_id", settings.DEFAULT_TENANT_ID).execute().data
        open_alerts = supabase.table("alerts").select("title,severity").eq("tenant_id", settings.DEFAULT_TENANT_ID).in_("status", ["OPEN","ACKNOWLEDGED"]).execute().data

        m   = metrics[0] if metrics else {}
        client_type = cl.get("client_type") or "qualified_investor"
        # Fetch counterparty exposures from portfolio risk cache for custody disclosure
        risk_cache = supabase.table("portfolio_risk_cache").select("counterparty_exposures").eq("portfolio_id", portfolio_id).execute().data
        cp_exposures = (risk_cache[0].get("counterparty_exposures") or []) if risk_cache else []
        nav = portfolio.get("total_nav_chf", 0) or 0
        top10 = [{"symbol": p["asset_symbol"], "class": p["asset_class"],
                  "weight_pct": round((p.get("weight_pct") or 0)*100, 1),
                  "value_chf": p.get("market_value_chf"), "custodian": p.get("custodian_name")}
                 for p in positions[:10]]
        critical_cps = [c for c in cps if c.get("current_risk_tier") in ("HIGH","CRITICAL")]
        stress_summary = [{"scenario": r.get("stress_scenarios",{}).get("display_name","?"),
                           "pnl_pct": round((r.get("portfolio_pnl_pct") or 0)*100,1)}
                          for r in stress]

        s1 = _call(f"""Executive Summary for Raven Risk Report.
Client: {cl.get('display_name')} | NAV: CHF {nav:,.0f} | Date: {datetime.utcnow().strftime('%d %B %Y')}
Risk Tier: {m.get('risk_tier','N/A')} | Score: {m.get('risk_score_composite','N/A')}/100
VaR 95% 1d: CHF {m.get('var_95_1d',0):,.0f} | Max DD 30d: {(m.get('max_drawdown_30d',0) or 0)*100:.1f}%
Top custodian: {m.get('top_custodian_name','N/A')} ({(m.get('top_custodian_pct',0) or 0)*100:.0f}% of AuM)
Open alerts: {len(open_alerts)}

Return JSON: {{"headline":"...","key_findings":["..."],"overall_assessment":"2-3 paragraphs","immediate_actions":["..."],"risk_indicator":"GREEN|AMBER|RED"}}""")

        s2 = _call(f"""Portfolio Composition for Raven Risk Report.
Top 10 positions: {json.dumps(top10)}
HHI: {m.get('hhi',0):.4f} | Top-3 weight: {(m.get('top3_weight',0) or 0)*100:.1f}%

Return JSON: {{"narrative":"2 paragraphs","concentration_assessment":"...","key_exposures":["..."],"diversification_score":"LOW|MEDIUM|HIGH"}}""")

        s3 = _call(f"""Risk Scorecard for Raven Risk Report.
VaR 95%: CHF {m.get('var_95_1d',0):,.0f} | VaR 99%: CHF {m.get('var_99_1d',0):,.0f}
CVaR 95%: CHF {m.get('cvar_95_1d',0):,.0f} | 30d Return: {(m.get('return_30d',0) or 0)*100:.2f}%
Volatility 30d ann.: {(m.get('volatility_30d',0) or 0)*100:.1f}% | Sharpe: {m.get('sharpe_ratio_30d',0):.2f}
Max DD 30d: {(m.get('max_drawdown_30d',0) or 0)*100:.1f}% | Score: {m.get('risk_score_composite','N/A')}/100

Return JSON: {{"narrative":"professional interpretation","var_interpretation":"...","volatility_assessment":"...","trend_assessment":"improving|stable|deteriorating with rationale"}}""")

        s4 = _call(f"""Counterparty Analysis for Raven Risk Report.
Monitored: {len(cps)} | HIGH/CRITICAL: {len(critical_cps)}
Top custodian: {m.get('top_custodian_name','N/A')} ({(m.get('top_custodian_pct',0) or 0)*100:.0f}% AuM)
Custodian HHI: {m.get('custodian_hhi',0):.4f}
Critical entities: {[c['display_name'] for c in critical_cps[:5]]}

Return JSON: {{"narrative":"2-3 paragraphs","custodian_concentration_risk":"...","highlighted_concerns":["..."],"watchlist":["..."],"overall_counterparty_assessment":"LOW|MEDIUM|HIGH|CRITICAL"}}""")

        s5 = _call(f"""Stress Test Results for Raven Risk Report.
Portfolio NAV: CHF {nav:,.0f}
Scenarios: {json.dumps(stress_summary) if stress_summary else "No stress tests run yet — note this clearly and recommend running them."}

Return JSON: {{"narrative":"analysis of stress outcomes","worst_scenario":"name and % impact","resilience_assessment":"...","tail_risk_commentary":"..."}}""")

        # Section 7: FINMA Custody Compliance Disclosure (not AI-generated, rule-based)
        s7 = build_portfolio_disclosure(
            counterparty_exposures=cp_exposures,
            client_type=client_type,
            all_counterparties=cps,
        )

        s6 = _call(f"""Recommendations for Raven Risk Report.
Risk tier: {m.get('risk_tier','N/A')} | Top custodian: {(m.get('top_custodian_pct',0) or 0)*100:.0f}%
Open alerts: {len(open_alerts)} | HIGH/CRITICAL CPs: {len(critical_cps)}
Max DD 30d: {(m.get('max_drawdown_30d',0) or 0)*100:.1f}% | Client profile: {cl.get('risk_profile','moderate')}

Return JSON: {{
  "immediate":[{{"priority":"HIGH","action":"...","rationale":"...","timeline":"within X days"}}],
  "short_term":[{{"priority":"MEDIUM","action":"...","rationale":"...","timeline":"within X weeks"}}],
  "monitoring":[{{"item":"...","threshold":"..."}}],
  "disclaimer":"FINMA-aligned disclaimer"
}}""")

        supabase.table("reports").update({
            "section_executive_summary":     s1,
            "section_portfolio_composition": s2,
            "section_risk_scorecard":        s3,
            "section_counterparty_analysis": s4,
            "section_stress_test_results":   s5,
            "section_recommendations":       s6,
            "section_regulatory_disclosure": s7,
            "status": "IN_REVIEW",
            "generation_completed_at": datetime.utcnow().isoformat(),
            "model_version": settings.ANTHROPIC_MODEL,
        }).eq("report_id", report_id).execute()

        supabase.table("audit_log").insert({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "event_category": "AGENT",
            "event_type": "report.generation_completed",
            "actor_type": "AGENT",
            "resource_type": "reports",
            "resource_id": report_id,
            "metadata": {"model": settings.ANTHROPIC_MODEL, "sections": 6},
        }).execute()

    except Exception as e:
        supabase.table("reports").update({"generation_error": str(e)}).eq("report_id", report_id).execute()
        raise
