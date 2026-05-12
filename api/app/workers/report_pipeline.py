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
        portfolio   = supabase.table("portfolios").select("*").eq("portfolio_id", portfolio_id).single().execute().data
        positions   = supabase.table("portfolio_positions").select("*").eq("portfolio_id", portfolio_id).order("market_value_chf", desc=True).limit(20).execute().data
        cl          = supabase.table("clients").select("*").eq("client_id", client_id).single().execute().data
        stress      = supabase.table("stress_test_results").select("*, stress_scenarios(display_name,category,description)").eq("portfolio_id", portfolio_id).order("run_at", desc=True).limit(8).execute().data
        cps         = supabase.table("counterparties").select("counterparty_id,slug,display_name,entity_type,jurisdiction,regulator,current_risk_tier,latest_score_id,finma_custody_status,enrichment_data").eq("tenant_id", settings.DEFAULT_TENANT_ID).execute().data
        open_alerts = supabase.table("alerts").select("title,severity,alert_type").eq("portfolio_id", portfolio_id).in_("status", ["OPEN","ACKNOWLEDGED"]).execute().data

        client_type = cl.get("client_type") or "qualified_investor"
        nav         = portfolio.get("total_nav_chf", 0) or 0

        # Counterparty risk cache — the heart of Raven
        risk_cache   = supabase.table("portfolio_risk_cache").select("*").eq("portfolio_id", portfolio_id).execute().data
        risk         = risk_cache[0] if risk_cache else {}
        cp_exposures = risk.get("counterparty_exposures") or []

        # Build portfolio custodian summary (only custodians in this portfolio)
        portfolio_custodians = []
        for exp in cp_exposures:
            cp_record = next((c for c in cps if c.get("counterparty_id") == exp.get("counterparty_id")), {})
            enrich    = cp_record.get("enrichment_data") or {}
            score_data = enrich.get("_scores") or {}
            portfolio_custodians.append({
                "name":            exp.get("name", "Unknown"),
                "entity_type":     exp.get("entity_type", cp_record.get("entity_type", "")),
                "jurisdiction":    exp.get("jurisdiction", cp_record.get("jurisdiction", "")),
                "regulator":       exp.get("regulator", cp_record.get("regulator", "")),
                "value_chf":       round(exp.get("value_chf", 0), 0),
                "weight_pct":      round((exp.get("pct") or 0) * 100 if exp.get("pct", 0) < 1 else exp.get("pct", 0), 1),
                "risk_tier":       exp.get("tier", cp_record.get("current_risk_tier", "UNKNOWN")),
                "risk_score":      exp.get("score", 50),
                "score_delta_7d":  exp.get("delta_7d", 0),
                "regulatory_dim":  score_data.get("regulatory", 50),
                "financial_dim":   score_data.get("financial", 50),
                "operational_dim": score_data.get("operational", 50),
                "liquidity_dim":   score_data.get("liquidity", 50),
                "onchain_dim":     score_data.get("onchain", 50),
                "reputation_dim":  score_data.get("reputation", 50),
            })

        # Positions grouped by custodian
        pos_by_custodian: dict = {}
        for p in positions:
            cname = p.get("custodian_name", "Unknown")
            pos_by_custodian.setdefault(cname, []).append({
                "symbol": p.get("asset_symbol"), "name": p.get("asset_name"),
                "value_chf": p.get("market_value_chf"), "weight_pct": round((p.get("weight_pct") or 0)*100, 1),
            })

        # Stress summary focused on counterparty scenarios
        stress_summary = []
        for r in stress:
            sc = r.get("stress_scenarios") or {}
            stress_summary.append({
                "scenario":  sc.get("display_name", "?"),
                "category":  sc.get("category", ""),
                "pnl_pct":   round((r.get("portfolio_pnl_pct") or 0)*100, 1),
                "pnl_chf":   round(r.get("portfolio_pnl_chf") or 0, 0),
            })

        # FINMA custody disclosure (computed early — used in multiple sections)
        s7 = build_portfolio_disclosure(
            counterparty_exposures=cp_exposures,
            client_type=client_type,
            all_counterparties=cps,
        )

        # ── Section 01: Executive Summary ─────────────────────────────────────
        weighted_score = risk.get("weighted_risk_score") or 50
        finma_ok       = risk.get("finma_compliant", True)
        alerts_count   = len(open_alerts)
        conc_warnings  = risk.get("concentration_warnings") or []
        limit_breaches = risk.get("limit_breaches") or []

        s1 = _call(f"""Write the Executive Summary for a Raven counterparty risk report.
Raven is a counterparty risk intelligence platform — NOT a portfolio performance tool.
Do NOT mention VaR, Sharpe ratio, volatility, or drawdown. Focus entirely on counterparty risk.

Client: {cl.get('display_name')} ({client_type.replace('_',' ')}) | AUM: CHF {nav:,.0f}
Date: {datetime.utcnow().strftime('%d %B %Y')}
Weighted Counterparty Risk Score: {weighted_score:.0f}/100
FINMA Guidance 01/2026 compliance: {'COMPLIANT' if finma_ok else 'NON-COMPLIANT — disclosure required'}
FINMA custody status: {s7.get('overall_status','UNKNOWN')}
Custodians in portfolio: {[c['name'] for c in portfolio_custodians]}
Custodians by risk tier: {[f"{c['name']} ({c['risk_tier']}, score {c['risk_score']:.0f})" for c in portfolio_custodians]}
Open alerts: {alerts_count}
Concentration warnings: {[w.get('name') for w in conc_warnings]}
Limit breaches: {len(limit_breaches)}

Return JSON: {{"headline":"one sentence counterparty risk summary","key_findings":["4-5 findings about counterparty risk, FINMA status, concentration"],"overall_assessment":"2-3 paragraphs on counterparty risk — no market risk metrics","immediate_actions":["2-3 counterparty-specific actions"],"risk_indicator":"GREEN|AMBER|RED"}}""")

        # ── Section 02: Portfolio & Custody Composition ────────────────────────
        s2 = _call(f"""Write the Portfolio Composition section for a Raven counterparty risk report.
Focus on WHICH CUSTODIAN holds WHAT — not asset performance.

Client: {cl.get('display_name')} | AUM: CHF {nav:,.0f}
Positions by custodian:
{json.dumps(pos_by_custodian, indent=2)}
Custodian concentration:
{json.dumps([{{'name':c['name'],'value_chf':c['value_chf'],'weight_pct':c['weight_pct'],'tier':c['risk_tier']}} for c in portfolio_custodians], indent=2)}

Focus on: what assets sit with which custodian, concentration by custodian, custody risk implications.
Do NOT focus on asset performance, returns, or market risk.

Return JSON: {{"narrative":"2 paragraphs on custody structure and asset allocation by custodian","concentration_assessment":"custodian concentration analysis","key_exposures":["custody-focused exposure points"],"diversification_score":"LOW|MEDIUM|HIGH"}}""")

        # ── Section 03: Counterparty Risk Scorecard ────────────────────────────
        s3 = _call(f"""Write the Counterparty Risk Scorecard section for a Raven report.
This replaces the traditional market risk scorecard. Focus on the 6 counterparty risk dimensions.

Portfolio weighted counterparty risk score: {weighted_score:.0f}/100
FINMA compliant: {'YES' if finma_ok else 'NO'}
Counterparties:
{json.dumps(portfolio_custodians, indent=2)}

For each counterparty interpret their scores across 6 dimensions (0-100, higher=safer):
- Regulatory Standing (25%): licence status, enforcement actions, FINMA supervision
- Financial Strength (20%): capital, audits, proof of reserves
- Operational Resilience (20%): security, uptime, certifications
- Liquidity & Reserves (15%): withdrawal history, reserve ratios
- On-Chain Health (10%): reserve transparency, on-chain activity
- Reputation & Market (10%): media sentiment, leadership, track record

Return JSON: {{"narrative":"2 paragraphs interpreting the counterparty risk scores","scorecard_by_custodian":[{{"name":"...","overall_score":0,"tier":"...","strongest_dimension":"...","weakest_dimension":"...","key_risk":"one sentence"}}],"weighted_portfolio_score":{weighted_score:.0f},"trend":"improving|stable|deteriorating","trend_rationale":"..."}}""")

        # ── Section 04: Counterparty Analysis ─────────────────────────────────
        s4 = _call(f"""Write the Counterparty Analysis section for a Raven counterparty risk report.
Analyse ONLY the custodians in this portfolio. Do NOT reference other entities.

Client: {cl.get('display_name')} | AUM: CHF {nav:,.0f}
Portfolio custodians:
{json.dumps(portfolio_custodians, indent=2)}
FINMA custody status: {s7.get('overall_status','UNKNOWN')}
Custodians requiring FINMA disclosure: {s7.get('disclosure_custodians',[])}
Compliant custodians: {s7.get('compliant_custodians',[])}
Concentration warnings: {json.dumps(conc_warnings)}
Open alerts: {[a.get('title') for a in open_alerts]}

Return JSON: {{"narrative":"2-3 paragraphs on counterparty risk profile of this portfolio","custodian_concentration_risk":"concentration analysis","highlighted_concerns":["specific risks per custodian"],"watchlist":["custodians to monitor and why"],"overall_counterparty_assessment":"LOW|MEDIUM|HIGH|CRITICAL"}}""")

        # ── Section 05: Stress Tests ───────────────────────────────────────────
        s5 = _call(f"""Write the Stress Test Results section for a Raven counterparty risk report.
Focus on counterparty-specific scenarios (custodian failure, regulatory action, liquidity freeze).

Portfolio NAV: CHF {nav:,.0f}
Custodians: {[c['name'] for c in portfolio_custodians]}
Executed scenarios: {json.dumps(stress_summary) if stress_summary else "None run yet"}

If no scenarios run: explain why counterparty stress testing matters specifically for this portfolio
(e.g. what happens if Bitcoin Suisse becomes insolvent — Art. 242a protection, recovery process).
Recommend specific scenarios relevant to this portfolio's custody structure.

Return JSON: {{"narrative":"stress test analysis focused on counterparty and custody risk","worst_scenario":"name and impact","resilience_assessment":"...","tail_risk_commentary":"custody-specific tail risk"}}""")

        # ── Section 06: Recommendations ───────────────────────────────────────
        s6 = _call(f"""Write the Recommendations section for a Raven counterparty risk report.
ALL recommendations must be about counterparty risk — not market risk, VaR, or portfolio performance.

Client: {cl.get('display_name')} ({client_type.replace('_',' ')}) | AUM: CHF {nav:,.0f}
Weighted CP risk score: {weighted_score:.0f}/100 | FINMA status: {s7.get('overall_status','UNKNOWN')}
Custodians: {json.dumps([{{'name':c['name'],'tier':c['risk_tier'],'weight_pct':c['weight_pct'],'finma':s7.get('overall_status')}} for c in portfolio_custodians])}
FINMA disclosure required for: {s7.get('disclosure_custodians',[])}
Concentration warnings: {[w.get('name') for w in conc_warnings]}
Limit breaches: {len(limit_breaches)}
Open alerts: {alerts_count}
Consent required: {s7.get('consent_required', False)}

Focus recommendations on: custodian migration, FINMA disclosure compliance, concentration reduction,
consent documentation, counterparty monitoring. NOT on asset allocation or market risk.

Return JSON: {{
  "immediate":[{{"priority":"HIGH","action":"counterparty action","rationale":"why urgent","timeline":"within X days"}}],
  "short_term":[{{"priority":"MEDIUM","action":"...","rationale":"...","timeline":"within X weeks"}}],
  "monitoring":[{{"item":"counterparty metric to monitor","threshold":"alert condition"}}],
  "disclaimer":"Swiss regulatory disclaimer referencing FINMA and FinSA"
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
