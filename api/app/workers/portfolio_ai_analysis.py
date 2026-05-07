"""
Raven — AI Portfolio Risk Analysis

Generates senior risk manager quality analysis of a portfolio's
counterparty risk profile, with concrete action recommendations.

Uses Claude Opus with full portfolio context:
- Counterparty risk score and dimension breakdown
- Position-level exposures with custodian attribution
- Stress test results
- Regulatory compliance flags (FINMA 01/2026)
- Client mandate limits and any breaches
- Active alerts
- Relevant regulatory intelligence

Output:
- Risk verdict (plain English, 2-3 sentences)
- Key risk drivers (top 3, ranked by severity)
- Specific action items (ranked, with CHF impact)
- Client communication draft (non-technical)
- Analyst notes (technical detail for internal use)
"""

import json
from datetime import datetime
from anthropic import Anthropic
from app.core.database import supabase
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a senior risk manager at a Swiss institutional wealth manager with 20 years of experience.
You specialise in digital asset counterparty risk for UHNW and institutional mandates under FINMA supervision.

Your analysis style:
- Direct and precise. No hedging with "may" or "could" when the data is clear.
- Swiss regulatory context always in mind (FINMA 01/2026, FINMA circular on outsourcing)
- Quantified wherever possible: CHF amounts, percentages, score numbers
- Action-oriented: every concern maps to a specific action with a deadline
- Client-appropriate: you can translate technical risk into language a sophisticated investor understands

You output ONLY valid JSON. No preamble, no markdown, no text outside the JSON object."""


def _build_analysis_prompt(context: dict) -> str:
    portfolio    = context["portfolio"]
    risk         = context["risk"]
    positions    = context["positions"]
    stress       = context["stress_results"]
    alerts       = context["alerts"]
    reg_flags    = context["regulatory_flags"]
    limits       = context["limit_breaches"]
    metrics      = context["metrics"]

    nav_chf  = portfolio.get("total_nav_chf", 0)
    nav_fmt  = f"CHF {nav_chf:,.0f}" if nav_chf else "unknown"
    cp_score = risk.get("weighted_risk_score")
    mr_score = metrics.get("risk_score_composite") if metrics else None

    # Top positions summary
    top_positions = sorted(
        [p for p in positions if p.get("market_value_chf")],
        key=lambda x: float(x.get("market_value_chf", 0)),
        reverse=True
    )[:10]

    pos_lines = []
    for p in top_positions:
        val = float(p.get("market_value_chf", 0))
        pct = (val / nav_chf * 100) if nav_chf else 0
        pos_lines.append(
            f"  {p['asset_symbol']:8} {p['asset_class']:12} "
            f"CHF {val:>10,.0f} ({pct:5.1f}%) @ {p.get('custodian_name', 'Unknown')}"
        )

    # Concentration warnings
    warnings = risk.get("concentration_warnings", [])
    conc_lines = [
        f"  {w['name']}: {w['pct']}% of NAV (severity: {w['severity']})"
        for w in warnings
    ]

    # Stress test results (top losses)
    stress_sorted = sorted(
        [s for s in stress if s.get("portfolio_pnl_pct") is not None],
        key=lambda x: x.get("portfolio_pnl_pct", 0)
    )[:5]

    stress_lines = []
    for s in stress_sorted:
        pct = float(s.get("portfolio_pnl_pct", 0)) * 100
        chf = float(s.get("portfolio_pnl_chf", 0))
        name = s.get("stress_scenarios", {}).get("display_name", "Unknown") if isinstance(s.get("stress_scenarios"), dict) else "Unknown"
        stress_lines.append(f"  {name}: {pct:+.1f}% (CHF {chf:+,.0f})")

    # FINMA flags
    finma_lines = [
        f"  {f['name']}: {f['reason']} ({f['pct']}% of portfolio)"
        for f in reg_flags
    ]

    # Limit breaches
    breach_lines = [
        f"  {b['type']} {b['key']}: limit {b['limit_pct']}%, actual {b['actual_pct']}% [{b['status']}]"
        for b in limits
    ]

    # Jurisdiction breakdown
    juris = risk.get("jurisdiction_breakdown", {})
    juris_lines = [
        f"  {j}: CHF {v:,.0f} ({v/nav_chf*100:.0f}%)"
        for j, v in sorted(juris.items(), key=lambda x: -x[1])
        if nav_chf > 0
    ]

    # Correlation groups
    corr = risk.get("correlation_groups", [])
    corr_lines = [
        f"  {g['group']}: {g['combined_pct']}% combined ({g['severity']})"
        for g in corr
    ]

    # Active alerts
    alert_lines = [
        f"  [{a['severity']}] {a['title']}"
        for a in alerts[:5]
    ]

    prompt = f"""Analyse this portfolio and produce a comprehensive risk assessment.

PORTFOLIO: {portfolio.get('display_name', 'Unknown')}
CLIENT: {portfolio.get('clients', {}).get('display_name', 'Unknown') if isinstance(portfolio.get('clients'), dict) else 'Unknown'}
NAV: {nav_fmt}
AS OF: {datetime.utcnow().strftime('%d %B %Y')}

RISK SCORES:
  Counterparty Risk Score: {(str(round(cp_score, 1)) + '/100') if cp_score else 'Not computed'} (exposure-weighted: regulatory + financial + operational + liquidity)
  Market Risk Score: {(str(round(mr_score, 1)) + '/100') if mr_score else 'Not computed'} (VaR + concentration + volatility)

TOP 10 POSITIONS BY VALUE:
{chr(10).join(pos_lines) if pos_lines else '  No positions found'}

CONCENTRATION WARNINGS (>15% single counterparty):
{chr(10).join(conc_lines) if conc_lines else '  None'}

JURISDICTION BREAKDOWN:
{chr(10).join(juris_lines) if juris_lines else '  Not computed'}

CORRELATION RISK GROUPS:
{chr(10).join(corr_lines) if corr_lines else '  None identified'}

STRESS TEST RESULTS (worst 5 scenarios):
{chr(10).join(stress_lines) if stress_lines else '  No stress tests run yet - run scenarios first'}

FINMA REGULATORY FLAGS:
{chr(10).join(finma_lines) if finma_lines else '  None - all custodians appear FINMA-compliant'}

MANDATE LIMIT BREACHES:
{chr(10).join(breach_lines) if breach_lines else '  None - all limits within mandate'}

ACTIVE ALERTS:
{chr(10).join(alert_lines) if alert_lines else '  No active alerts'}

Produce a JSON object with exactly this structure:
{{
  "risk_verdict": "2-3 sentence plain English summary of the overall risk posture. Be direct. State the most important risk first.",

  "overall_assessment": "LOW|MEDIUM|HIGH|CRITICAL",

  "key_risk_drivers": [
    {{
      "rank": 1,
      "driver": "Short name of risk",
      "description": "Specific description with numbers",
      "severity": "HIGH|MEDIUM|LOW",
      "chf_at_risk": 0,
      "action_required": true
    }}
  ],

  "action_items": [
    {{
      "priority": "IMMEDIATE|SHORT_TERM|MEDIUM_TERM",
      "action": "Specific action to take",
      "rationale": "Why this action is needed",
      "chf_impact": "Estimated CHF impact if action taken",
      "deadline": "within X days/weeks/months"
    }}
  ],

  "rebalancing_suggestions": [
    {{
      "from_counterparty": "Name",
      "to_counterparty": "Name",
      "amount_chf": 0,
      "rationale": "Why this move improves the risk profile",
      "score_impact": "Estimated change in counterparty risk score"
    }}
  ],

  "client_communication": "2-3 paragraph draft for the client meeting or letter. Professional, non-technical, reassuring but honest. In English.",

  "analyst_notes": "Technical notes for internal use. References to specific regulatory requirements, scoring methodology, data gaps, recommended follow-up actions.",

  "data_quality_flags": ["Any gaps in data that affected this analysis"]
}}"""

    return prompt


def analyse_portfolio_risk(portfolio_id: str) -> dict:
    """
    Main entry point. Gathers all portfolio context and runs Claude analysis.
    Stores result in portfolio_risk_cache.
    Returns the analysis dict.
    """
    # ── Gather all context ────────────────────────────────────

    portfolio = (
        supabase.table("portfolios")
        .select("*, clients(display_name, client_ref)")
        .eq("portfolio_id", portfolio_id)
        .single()
        .execute()
        .data
    ) or {}

    positions = (
        supabase.table("portfolio_positions")
        .select("asset_symbol, asset_class, market_value_chf, custodian_name, weight_pct")
        .eq("portfolio_id", portfolio_id)
        .order("market_value_chf", desc=True)
        .execute()
        .data
    ) or []

    metrics = (
        supabase.table("portfolio_metrics")
        .select("*")
        .eq("portfolio_id", portfolio_id)
        .order("as_of_date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    metrics = metrics[0] if metrics else {}

    risk = (
        supabase.table("portfolio_risk_cache")
        .select("*")
        .eq("portfolio_id", portfolio_id)
        .execute()
        .data
    )
    risk = risk[0] if risk else {}

    stress_results = (
        supabase.table("stress_test_results")
        .select("*, stress_scenarios(display_name)")
        .eq("portfolio_id", portfolio_id)
        .order("run_at", desc=True)
        .limit(20)
        .execute()
        .data
    ) or []

    alerts = (
        supabase.table("alerts")
        .select("severity, title, alert_type")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("status", "OPEN")
        .execute()
        .data
    ) or []

    # Filter alerts to counterparties in this portfolio
    portfolio_custodians = {p.get("custodian_name") for p in positions}
    alerts = [a for a in alerts if any(c and c in a.get("title", "") for c in portfolio_custodians)][:10]

    reg_flags   = risk.get("finma_flags", []) or []
    limit_breaches = risk.get("limit_breaches", []) or []

    context = {
        "portfolio":         portfolio,
        "risk":              risk,
        "positions":         positions,
        "stress_results":    stress_results,
        "alerts":            alerts,
        "regulatory_flags":  reg_flags,
        "limit_breaches":    limit_breaches,
        "metrics":           metrics,
    }

    # ── Call Claude ───────────────────────────────────────────
    prompt = _build_analysis_prompt(context)

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    for tag in ["```json", "```"]:
        if tag in raw:
            raw = raw.split(tag)[1].split("```")[0].strip()
            break

    analysis = json.loads(raw)
    analysis["generated_at"] = datetime.utcnow().isoformat()
    analysis["portfolio_id"] = portfolio_id
    analysis["nav_chf"]      = portfolio.get("total_nav_chf")
    analysis["cp_score"]     = risk.get("weighted_risk_score")
    analysis["mr_score"]     = metrics.get("risk_score_composite")

    # Cache the analysis
    try:
        supabase.table("portfolio_risk_cache").update({
            "ai_analysis":      analysis,
            "ai_analysed_at":   datetime.utcnow().isoformat(),
        }).eq("portfolio_id", portfolio_id).execute()
    except Exception as e:
        print(f"[ai_analysis] Cache write error: {e}")

    return analysis
