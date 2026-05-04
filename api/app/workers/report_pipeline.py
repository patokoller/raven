"""
Raven — Report Generation Pipeline
Orchestrates 4-agent pipeline: Data → Scoring → Portfolio → Writer
Uses Claude claude-opus-4-5 via Anthropic API.
"""

import json
from datetime import datetime
from anthropic import Anthropic

from app.workers.celery_app import celery_app
from app.core.database import supabase
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _fetch_report_context(portfolio_id: str, client_id: str) -> dict:
    """Fetch all data needed for report generation."""
    portfolio = supabase.table("portfolios").select("*").eq("portfolio_id", portfolio_id).single().execute().data
    positions = supabase.table("portfolio_positions").select("*").eq("portfolio_id", portfolio_id).order("market_value_chf", desc=True).execute().data
    metrics = supabase.table("portfolio_metrics").select("*").eq("portfolio_id", portfolio_id).order("computed_at", desc=True).limit(1).execute().data
    cl = supabase.table("clients").select("*").eq("client_id", client_id).single().execute().data
    stress_results = supabase.table("stress_test_results").select("*, stress_scenarios(display_name)").eq("portfolio_id", portfolio_id).order("run_at", desc=True).limit(5).execute().data
    counterparties = supabase.table("counterparties").select("*, counterparty_scores!latest_score_id(*)").eq("tenant_id", settings.DEFAULT_TENANT_ID).execute().data
    alerts = supabase.table("alerts").select("*").eq("tenant_id", settings.DEFAULT_TENANT_ID).in_("status", ["OPEN", "ACKNOWLEDGED"]).execute().data

    return {
        "client": cl,
        "portfolio": portfolio,
        "positions": positions[:20],   # top 20 positions
        "metrics": metrics[0] if metrics else {},
        "stress_results": stress_results,
        "counterparties": counterparties,
        "open_alerts": alerts,
        "report_date": datetime.utcnow().strftime("%d %B %Y"),
    }


def _generate_section(system_prompt: str, user_prompt: str) -> dict:
    """Call Claude to generate a report section. Returns structured JSON."""
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = response.content[0].text
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception:
        return {"raw_text": text, "parse_error": True}


SYSTEM_REPORT_WRITER = """You are the Report Generation Agent for Raven, a Swiss institutional digital asset risk platform.
You write in the style of a Tier 1 Swiss private bank. Your output is ALWAYS valid JSON.
Tone: precise, professional, Swiss-grade. No hedging, no filler. Every claim is evidence-backed.
FINMA-aligned terminology. All figures in CHF unless otherwise specified.
You output ONLY the requested JSON structure, no preamble, no markdown outside the JSON."""


@celery_app.task(name="app.workers.report_pipeline.generate_report_task")
def generate_report_task(report_id: str, portfolio_id: str, client_id: str):
    """Full 6-section report generation pipeline."""
    try:
        ctx = _fetch_report_context(portfolio_id, client_id)
        sections = {}

        # ── Section 1: Executive Summary ──────────────────────
        sections["executive_summary"] = _generate_section(
            SYSTEM_REPORT_WRITER,
            f"""Generate the Executive Summary section for a counterparty risk and portfolio report.

Client: {ctx['client'].get('display_name', 'N/A')}
Portfolio NAV: CHF {ctx['portfolio'].get('total_nav_chf', 0):,.0f}
Report Date: {ctx['report_date']}
Open Alerts: {len(ctx['open_alerts'])}
Portfolio Risk Tier: {ctx['metrics'].get('risk_tier', 'N/A')}
Risk Score: {ctx['metrics'].get('risk_score_composite', 'N/A')}/100
VaR 95% (1-day): CHF {ctx['metrics'].get('var_95_1d', 0):,.0f}
Max Drawdown 30d: {(ctx['metrics'].get('max_drawdown_30d', 0) or 0)*100:.1f}%
Top Custodian Exposure: {ctx['metrics'].get('top_custodian_name', 'N/A')} ({(ctx['metrics'].get('top_custodian_pct', 0) or 0)*100:.1f}%)

Return JSON:
{{
  "headline": "one-sentence summary of the portfolio risk posture",
  "key_findings": ["finding 1", "finding 2", "finding 3"],
  "overall_assessment": "2-3 paragraph institutional assessment",
  "immediate_actions": ["action 1", "action 2"],
  "risk_indicator": "GREEN|AMBER|RED",
  "generated_at": "{datetime.utcnow().isoformat()}"
}}"""
        )

        # ── Section 2: Portfolio Composition ──────────────────
        top_positions = [
            {"symbol": p["asset_symbol"], "class": p["asset_class"],
             "weight": round((p.get("weight_pct") or 0)*100, 2),
             "value_chf": p.get("market_value_chf"), "custodian": p.get("custodian_name")}
            for p in ctx["positions"][:10]
        ]
        sections["portfolio_composition"] = _generate_section(
            SYSTEM_REPORT_WRITER,
            f"""Generate the Portfolio Composition section.
Top 10 positions: {json.dumps(top_positions)}
HHI (concentration): {ctx['metrics'].get('hhi', 0):.4f}
Top 3 positions weight: {(ctx['metrics'].get('top3_weight', 0) or 0)*100:.1f}%
Asset class breakdown available in positions data.

Return JSON:
{{
  "narrative": "2-paragraph analysis of portfolio composition and concentration",
  "concentration_assessment": "assessment of HHI and top-position concentration",
  "key_exposures": ["exposure 1", "exposure 2"],
  "diversification_score": "LOW|MEDIUM|HIGH",
  "top_positions_commentary": "commentary on top 3 positions"
}}"""
        )

        # ── Section 3: Risk Scorecard ──────────────────────────
        sections["risk_scorecard"] = _generate_section(
            SYSTEM_REPORT_WRITER,
            f"""Generate the Portfolio Risk Scorecard section.
VaR 95% 1-day: CHF {ctx['metrics'].get('var_95_1d', 0):,.0f}
VaR 99% 1-day: CHF {ctx['metrics'].get('var_99_1d', 0):,.0f}
CVaR 95%: CHF {ctx['metrics'].get('cvar_95_1d', 0):,.0f}
30d Return: {(ctx['metrics'].get('return_30d', 0) or 0)*100:.2f}%
30d Volatility (annualised): {(ctx['metrics'].get('volatility_30d', 0) or 0)*100:.1f}%
Sharpe Ratio (30d): {ctx['metrics'].get('sharpe_ratio_30d', 0):.2f}
Max Drawdown 30d: {(ctx['metrics'].get('max_drawdown_30d', 0) or 0)*100:.1f}%
Composite Risk Score: {ctx['metrics'].get('risk_score_composite', 'N/A')}/100
Risk Tier: {ctx['metrics'].get('risk_tier', 'N/A')}

Return JSON:
{{
  "narrative": "professional interpretation of these risk metrics",
  "var_interpretation": "what this VaR means in plain English for this client",
  "volatility_assessment": "assessment of volatility level",
  "sharpe_assessment": "risk-adjusted return commentary",
  "risk_score_explanation": "what drives the composite risk score",
  "trend_assessment": "improving|stable|deteriorating with rationale"
}}"""
        )

        # ── Section 4: Counterparty Analysis ──────────────────
        critical_cps = [c for c in ctx["counterparties"] if c.get("current_risk_tier") in ("HIGH", "CRITICAL")]
        score_data = [
            {"name": c["display_name"], "tier": c.get("current_risk_tier"), "score": c.get("counterparty_scores", {}).get("composite_score")}
            for c in ctx["counterparties"][:10]
        ]
        sections["counterparty_analysis"] = _generate_section(
            SYSTEM_REPORT_WRITER,
            f"""Generate the Counterparty Analysis section.
Monitored counterparties: {len(ctx['counterparties'])}
HIGH/CRITICAL risk counterparties: {len(critical_cps)}
Scores summary: {json.dumps(score_data)}
Open alerts: {len(ctx['open_alerts'])}
Top custodian: {ctx['metrics'].get('top_custodian_name', 'N/A')} ({(ctx['metrics'].get('top_custodian_pct', 0) or 0)*100:.1f}% of AuM)
Custodian HHI: {ctx['metrics'].get('custodian_hhi', 0):.4f}

Return JSON:
{{
  "narrative": "2-3 paragraph institutional analysis of counterparty risk landscape",
  "custodian_concentration_risk": "specific analysis of custodian concentration",
  "highlighted_concerns": ["concern 1 with evidence", "concern 2 with evidence"],
  "watchlist": ["counterparty names requiring monitoring"],
  "overall_counterparty_assessment": "LOW|MEDIUM|HIGH|CRITICAL"
}}"""
        )

        # ── Section 5: Stress Test Results ────────────────────
        stress_summary = [
            {"scenario": r.get("stress_scenarios", {}).get("display_name", "Unknown"),
             "pnl_pct": round((r.get("portfolio_pnl_pct") or 0)*100, 1),
             "pnl_chf": r.get("portfolio_pnl_chf")}
            for r in ctx["stress_results"]
        ]
        sections["stress_test_results"] = _generate_section(
            SYSTEM_REPORT_WRITER,
            f"""Generate the Stress Test Results section.
Scenarios run: {json.dumps(stress_summary) if stress_summary else 'No stress tests run yet — state this clearly'}
Portfolio NAV: CHF {ctx['portfolio'].get('total_nav_chf', 0):,.0f}

Return JSON:
{{
  "narrative": "professional analysis of stress test outcomes",
  "worst_scenario": "name and impact of worst scenario",
  "resilience_assessment": "overall portfolio resilience under stress",
  "tail_risk_commentary": "specific tail risk findings",
  "scenarios_commentary": {{"scenario_name": "outcome commentary"}}
}}"""
        )

        # ── Section 6: Recommendations ────────────────────────
        sections["recommendations"] = _generate_section(
            SYSTEM_REPORT_WRITER,
            f"""Generate the Recommendations section. Be specific and actionable.
Key findings so far:
- Portfolio risk tier: {ctx['metrics'].get('risk_tier', 'N/A')}
- Top custodian concentration: {(ctx['metrics'].get('top_custodian_pct', 0) or 0)*100:.1f}%
- Open alerts: {len(ctx['open_alerts'])}
- HIGH/CRITICAL counterparties: {len(critical_cps)}
- Max drawdown 30d: {(ctx['metrics'].get('max_drawdown_30d', 0) or 0)*100:.1f}%
Client risk profile: {ctx['client'].get('risk_profile', 'moderate')}

Return JSON:
{{
  "immediate": [
    {{"priority": "HIGH", "action": "action text", "rationale": "why", "timeline": "within X days"}}
  ],
  "short_term": [
    {{"priority": "MEDIUM", "action": "action text", "rationale": "why", "timeline": "within X weeks"}}
  ],
  "monitoring": [
    {{"item": "what to monitor", "threshold": "alert if"}}
  ],
  "disclaimer": "standard FINMA-aligned disclaimer"
}}"""
        )

        # Save all sections to DB
        supabase.table("reports").update({
            "section_executive_summary": sections["executive_summary"],
            "section_portfolio_composition": sections["portfolio_composition"],
            "section_risk_scorecard": sections["risk_scorecard"],
            "section_counterparty_analysis": sections["counterparty_analysis"],
            "section_stress_test_results": sections["stress_test_results"],
            "section_recommendations": sections["recommendations"],
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
            "metadata": {"sections_generated": list(sections.keys()), "model": settings.ANTHROPIC_MODEL},
        }).execute()

        return {"status": "complete", "report_id": report_id, "sections": list(sections.keys())}

    except Exception as e:
        supabase.table("reports").update({
            "generation_error": str(e),
        }).eq("report_id", report_id).execute()
        raise


@celery_app.task(name="app.workers.report_pipeline.render_pdf_task")
def render_pdf_task(report_id: str):
    """Render approved report to PDF. Placeholder — full implementation in Week 9."""
    supabase.table("reports").update({
        "pdf_generated_at": datetime.utcnow().isoformat(),
        "pdf_path": f"reports/{report_id}/report.pdf",
    }).eq("report_id", report_id).execute()
    return {"status": "pdf_queued", "report_id": report_id}
