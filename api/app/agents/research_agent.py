"""
Raven — Counterparty Research Agent

Uses Claude claude-opus-4-5 with web search to automatically research
all 6 scoring dimensions for a counterparty.

Output: structured JSON with recommended values, evidence, sources,
and confidence levels per field — ready for analyst review and one-click apply.
"""

import json
from datetime import datetime
from anthropic import Anthropic

from app.core.config import settings
from app.core.database import supabase

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """You are a counterparty risk research agent for a Swiss institutional digital asset platform.
Research a counterparty and extract structured data. For each field: search for it, cite the source URL, assign confidence (high/medium/low/none), provide the value.
Never invent data. Output ONLY valid JSON. No preamble."""


RESEARCH_SCHEMA = """
Return a JSON object with this exact structure:

{
  "entity_name": "string",
  "research_summary": "2-3 sentence overall assessment",
  "data_gaps": ["list of fields where no reliable data was found"],
  "findings": {
    "regulatory": {
      "license_active": {
        "value": true|false|null,
        "confidence": "high|medium|low|none",
        "evidence": "What you found, quoted or paraphrased from source",
        "source": "URL or source name"
      },
      "enforcement_actions_12m": {
        "value": integer|null,
        "confidence": "high|medium|low|none",
        "evidence": "...",
        "source": "..."
      }
    },
    "financial": {
      "is_publicly_listed": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." },
      "has_audited_financials": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." },
      "equity_ratio": { "value": float|null, "confidence": "...", "evidence": "...", "source": "..." },
      "revenue_stability": { "value": "stable|volatile|null", "confidence": "...", "evidence": "...", "source": "..." },
      "debt_level": { "value": "low|moderate|high|null", "confidence": "...", "evidence": "...", "source": "..." }
    },
    "operational": {
      "has_soc2": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." },
      "has_iso27001": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." },
      "has_insurance": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." },
      "major_security_incidents": { "value": integer|null, "confidence": "...", "evidence": "...", "source": "..." },
      "years_in_operation": { "value": integer|null, "confidence": "...", "evidence": "...", "source": "..." }
    },
    "liquidity": {
      "por_ratio": { "value": float|null, "confidence": "...", "evidence": "...", "source": "..." },
      "reserve_quality": { "value": "high|medium|low|null", "confidence": "...", "evidence": "...", "source": "..." },
      "withdrawal_restrictions_history": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." }
    },
    "onchain": {
      "onchain_reserve_trend_30d": { "value": "increasing|stable|declining|critical_outflow|null", "confidence": "...", "evidence": "...", "source": "..." },
      "tvl_change_30d_pct": { "value": float|null, "confidence": "...", "evidence": "...", "source": "..." },
      "audit_count": { "value": integer|null, "confidence": "...", "evidence": "...", "source": "..." }
    },
    "reputation": {
      "industry_reputation_score": { "value": float|null, "confidence": "...", "evidence": "...", "source": "..." },
      "leadership_concerns": { "value": bool|null, "confidence": "...", "evidence": "...", "source": "..." },
      "news_sentiment_30d": { "value": "positive|neutral|negative|null", "confidence": "...", "evidence": "...", "source": "..." }
    }
  }
}
"""


def run_research_agent(counterparty_id: str) -> dict:
    """
    Main entry point. Researches a counterparty and returns structured findings.
    Runs in a background thread — updates counterparty record when complete.
    """
    # Mark as running
    supabase.table("counterparties").update({
        "research_status": "running",
    }).eq("counterparty_id", counterparty_id).execute()

    try:
        # Fetch counterparty details
        cp = (
            supabase.table("counterparties")
            .select("*")
            .eq("counterparty_id", counterparty_id)
            .single()
            .execute()
            .data
        )
        if not cp:
            raise ValueError(f"Counterparty {counterparty_id} not found")

        result = _research_counterparty(cp)

        # Store results
        supabase.table("counterparties").update({
            "research_data":      result,
            "research_status":    "complete",
            "last_researched_at": datetime.utcnow().isoformat(),
        }).eq("counterparty_id", counterparty_id).execute()

        # Audit log
        supabase.table("audit_log").insert({
            "tenant_id":      settings.DEFAULT_TENANT_ID,
            "event_category": "AGENT",
            "event_type":     "counterparty.researched",
            "actor_type":     "AGENT",
            "resource_type":  "counterparties",
            "resource_id":    counterparty_id,
            "metadata": {
                "entity_name":    cp["display_name"],
                "fields_found":   _count_found_fields(result),
                "data_gaps":      result.get("data_gaps", []),
            },
        }).execute()

        return result

    except Exception as e:
        supabase.table("counterparties").update({
            "research_status": "error",
            "research_data": {"error": str(e), "researched_at": datetime.utcnow().isoformat()},
        }).eq("counterparty_id", counterparty_id).execute()
        raise


def _research_counterparty(cp: dict) -> dict:
    """
    Run the Claude agent with web search for a specific counterparty.
    Uses a structured multi-step research approach.
    """
    name         = cp["display_name"]
    entity_type  = cp["entity_type"]
    jurisdiction = cp.get("jurisdiction", "")
    regulator    = cp.get("regulator", "")
    website      = cp.get("website", "")

    # Build the research prompt
    user_prompt = f"""Research the following counterparty for our institutional risk scoring system.

ENTITY: {name}
TYPE: {entity_type}
JURISDICTION: {jurisdiction}
REGULATOR: {regulator}
WEBSITE: {website}

RESEARCH INSTRUCTIONS:

1. REGULATORY: Search "{name} license {regulator}" and "{name} regulatory status". 
   Check primary regulatory registers (FINMA, FCA, SEC, CFTC, OCC, MAS as applicable).
   Search "{name} enforcement action fine penalty" for last 12 months.

2. FINANCIAL: Search "{name} annual report" or "{name} financial statements".
   Check if publicly listed on any exchange. Search "{name} audited financials".
   For public companies, check SEC EDGAR or equivalent.

3. OPERATIONAL: Search "{name} SOC2" and "{name} ISO 27001".
   Search "{name} hack breach security incident" on rekt.news and crypto news sites.
   Find founding year from Wikipedia or Crunchbase for years in operation.

4. LIQUIDITY & RESERVES: Search "{name} proof of reserves" and "{name} reserves attestation".
   For exchanges, check CryptoQuant or Nansen for reserve trends.
   Search "{name} withdrawal halt suspended" for historical restrictions.

5. ON-CHAIN (if exchange/custodian/DeFi): Check DefiLlama for TVL data.
   Search api.llama.fi for protocol data if DeFi. Check on-chain reserve trends.
   For DeFi protocols: search "{name} audit" and count independent security audits.

6. REPUTATION: Search "{name}" in news from last 30 days.
   Classify overall sentiment. Search "{name} CEO leadership" for any concerns.
   Check industry reputation from analyst coverage and peer assessments.

After thorough research, return your findings in the exact JSON schema provided.

{RESEARCH_SCHEMA}"""

    # Use Haiku for research — 100k token/min limit vs 30k for Opus
    # Haiku is fast, cheap, and sufficient for structured data extraction
    RESEARCH_MODEL = "claude-haiku-4-5-20251001"

    # Retry with exponential backoff on rate limit errors
    import time
    from anthropic import RateLimitError

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=RESEARCH_MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": user_prompt}],
            )
            break  # success
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) * 30  # 30s, 60s, 120s, 240s
            print(f"[research] Rate limited on {cp.get('display_name')} — waiting {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)

    # Extract the final text response (after tool use)
    final_text = ""
    for block in response.content:
        if block.type == "text":
            final_text += block.text

    # Parse JSON from response
    parsed = _extract_json(final_text)
    parsed["researched_at"]    = datetime.utcnow().isoformat()
    parsed["agent_model"]      = settings.ANTHROPIC_MODEL
    parsed["counterparty_id"]  = cp["counterparty_id"]

    return parsed


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude's response, handling markdown code blocks."""
    text = text.strip()
    for tag in ["```json", "```"]:
        if tag in text:
            parts = text.split(tag)
            if len(parts) >= 2:
                text = parts[1].split("```")[0].strip()
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Could not parse JSON from agent response: {text[:200]}")


def _count_found_fields(result: dict) -> int:
    """Count how many fields have actual data (non-null values)."""
    count = 0
    for dimension in result.get("findings", {}).values():
        for field_data in dimension.values():
            if isinstance(field_data, dict) and field_data.get("value") is not None:
                count += 1
    return count


def extract_enrichment_from_research(research_data: dict) -> dict:
    """
    Convert research findings to enrichment data format.
    Only includes fields where the agent found data (non-null values).
    Used for one-click apply.
    """
    enrichment = {}
    findings   = research_data.get("findings", {})

    field_map = {
        # regulatory
        "regulatory.license_active":            "license_active",
        "regulatory.enforcement_actions_12m":   "enforcement_actions_12m",
        # financial
        "financial.is_publicly_listed":         "is_publicly_listed",
        "financial.has_audited_financials":     "has_audited_financials",
        "financial.equity_ratio":               "equity_ratio",
        "financial.revenue_stability":          "revenue_stability",
        "financial.debt_level":                 "debt_level",
        # operational
        "operational.has_soc2":                 "has_soc2",
        "operational.has_iso27001":             "has_iso27001",
        "operational.has_insurance":            "has_insurance",
        "operational.major_security_incidents": "major_security_incidents",
        "operational.years_in_operation":       "years_in_operation",
        # liquidity
        "liquidity.por_ratio":                  "por_ratio",
        "liquidity.reserve_quality":            "reserve_quality",
        "liquidity.withdrawal_restrictions_history": "withdrawal_restrictions_history",
        # onchain
        "onchain.onchain_reserve_trend_30d":    "onchain_reserve_trend_30d",
        "onchain.tvl_change_30d_pct":           "tvl_change_30d_pct",
        "onchain.audit_count":                  "audit_count",
        # reputation
        "reputation.industry_reputation_score": "industry_reputation_score",
        "reputation.leadership_concerns":       "leadership_concerns",
    }

    for path, enrich_key in field_map.items():
        dim, field = path.split(".", 1)
        field_data = findings.get(dim, {}).get(field, {})
        value = field_data.get("value")
        if value is not None:
            enrichment[enrich_key] = value

    return enrichment
