"""Raven — Alerts Router"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user, CurrentUser
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()

class AlertAction(BaseModel):
    action: str       # "acknowledge", "escalate", "dismiss", "resolve"
    note: Optional[str] = None

@router.get("")
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    q = (
        supabase.table("alerts")
        .select("*, counterparties(display_name, entity_type, current_risk_tier)")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
    )
    if status:
        q = q.eq("status", status.upper())
    else:
        q = q.in_("status", ["OPEN", "ACKNOWLEDGED", "ESCALATED"])
    if severity:
        q = q.eq("severity", severity.upper())
    return q.order("triggered_at", desc=True).execute().data

@router.post("/{alert_id}/action")
async def alert_action(
    alert_id: str,
    body: AlertAction,
    current_user: CurrentUser = Depends(get_current_user),
):
    from datetime import datetime
    valid = {"acknowledge", "escalate", "dismiss", "resolve"}
    if body.action not in valid:
        raise HTTPException(status_code=400, detail=f"Action must be one of: {valid}")

    status_map = {"acknowledge": "ACKNOWLEDGED", "escalate": "ESCALATED", "dismiss": "DISMISSED", "resolve": "RESOLVED"}
    update = {"status": status_map[body.action], "updated_at": datetime.utcnow().isoformat()}
    if body.action == "acknowledge":
        update.update({"acknowledged_by": current_user.user_id, "acknowledged_at": datetime.utcnow().isoformat()})
    elif body.action in ("resolve", "dismiss"):
        update.update({"resolved_by": current_user.user_id, "resolved_at": datetime.utcnow().isoformat(), "resolution_note": body.note})

    supabase.table("alerts").update(update).eq("alert_id", alert_id).execute()
    return {"status": "updated", "new_status": status_map[body.action]}


class AlertExplanationRequest(BaseModel):
    alert_id: str


@router.get("/{alert_id}")
async def get_alert_detail(
    alert_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get full alert detail including counterparty score breakdown."""
    alert = (
        supabase.table("alerts")
        .select("*")
        .eq("alert_id", alert_id)
        .single()
        .execute()
    )
    if not alert.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")

    result = dict(alert.data)

    # Attach counterparty + latest score if available
    if alert.data.get("counterparty_id"):
        cp = (
            supabase.table("counterparties")
            .select("*, counterparty_scores!latest_score_id(*)")
            .eq("counterparty_id", alert.data["counterparty_id"])
            .single()
            .execute()
        )
        if cp.data:
            result["counterparty"] = cp.data

    return result


@router.post("/{alert_id}/explain")
async def explain_alert(
    alert_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Generate an AI explanation of why this alert was triggered.
    Returns plain-English analysis with recommended actions.
    """
    from anthropic import Anthropic
    from app.core.config import settings

    alert = (
        supabase.table("alerts")
        .select("*")
        .eq("alert_id", alert_id)
        .single()
        .execute()
    )
    if not alert.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")

    a = alert.data
    cp_data = {}
    score_data = {}

    if a.get("counterparty_id"):
        cp = (
            supabase.table("counterparties")
            .select("display_name, entity_type, jurisdiction, regulator, current_risk_tier")
            .eq("counterparty_id", a["counterparty_id"])
            .single()
            .execute()
        )
        if cp.data:
            cp_data = cp.data

        # Get latest score breakdown
        score = (
            supabase.table("counterparty_scores")
            .select("composite_score, risk_tier, regulatory_score, financial_score, operational_score, liquidity_score, onchain_score, reputation_score, data_snapshot, scored_at")
            .eq("counterparty_id", a["counterparty_id"])
            .order("scored_at", desc=True)
            .limit(1)
            .execute()
        )
        if score.data:
            score_data = score.data[0]

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    flags = a.get("metadata", {}).get("flags", [])
    delta = a.get("metadata", {}).get("delta")
    old_score = a.get("metadata", {}).get("old_score")
    new_score = a.get("metadata", {}).get("new_score") or score_data.get("composite_score")

    prompt = f"""You are a Swiss institutional digital asset risk analyst. Explain this risk alert in plain, professional English.

ALERT:
- Type: {a.get("alert_type")}
- Severity: {a.get("severity")}
- Title: {a.get("title")}
- Body: {a.get("body")}

COUNTERPARTY:
- Name: {cp_data.get("display_name", "Unknown")}
- Type: {cp_data.get("entity_type", "Unknown")}
- Jurisdiction: {cp_data.get("jurisdiction", "Unknown")}
- Regulator: {cp_data.get("regulator", "Unknown")}
- Current Risk Tier: {cp_data.get("current_risk_tier", "Unknown")}

SCORE BREAKDOWN:
- Composite Score: {new_score}/100
- Previous Score: {old_score if old_score else "N/A"}
- Score Change: {f"-{delta:.1f} points" if delta else "N/A"}
- Regulatory: {score_data.get("regulatory_score", "N/A")}/100
- Financial: {score_data.get("financial_score", "N/A")}/100
- Operational: {score_data.get("operational_score", "N/A")}/100
- Liquidity: {score_data.get("liquidity_score", "N/A")}/100
- On-Chain: {score_data.get("onchain_score", "N/A")}/100
- Reputation: {score_data.get("reputation_score", "N/A")}/100
- Risk Flags: {", ".join(flags) if flags else "None recorded"}

Write a JSON response with this exact structure:
{{
  "headline": "One sentence — what happened and why it matters",
  "explanation": "2-3 paragraphs explaining the risk in institutional terms. Reference the specific scores and flags. Explain what they mean for a Swiss wealth manager with exposure to this counterparty.",
  "risk_drivers": ["specific factor 1", "specific factor 2", "specific factor 3"],
  "recommended_actions": [
    {{"priority": "HIGH", "action": "specific action", "timeline": "within X days"}},
    {{"priority": "MEDIUM", "action": "specific action", "timeline": "within X weeks"}}
  ],
  "context": "1 paragraph of broader market/regulatory context relevant to this counterparty type"
}}"""

    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    text = response.content[0].text
    for tag in ["```json", "```"]:
        if tag in text:
            text = text.split(tag)[1].split("```")[0].strip()
            break

    explanation = json.loads(text)
    explanation["alert_id"]  = alert_id
    explanation["generated_at"] = __import__("datetime").datetime.utcnow().isoformat()

    return explanation
