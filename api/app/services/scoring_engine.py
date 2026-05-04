"""
Raven — 6-Dimension Scoring Engine
Rule-based weighted scoring across:
  1. Regulatory Standing    (weight: 0.25)
  2. Financial Strength     (weight: 0.20)
  3. Operational Resilience (weight: 0.20)
  4. Liquidity & Reserves   (weight: 0.15)
  5. On-Chain Health        (weight: 0.10)
  6. Reputation & Market    (weight: 0.10)

Domain Expert calibration: weights are in config.py
All scoring is explainable — no black boxes.
Every sub-metric feeds a specific dimension.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from app.core.config import settings


@dataclass
class DimensionScore:
    score: float           # 0–100
    confidence: float      # 0–1
    signals: Dict[str, Any] = field(default_factory=dict)
    flags: list = field(default_factory=list)
    explanation: str = ""


@dataclass
class ScoringResult:
    counterparty_id: str
    scored_at: datetime
    composite_score: float
    risk_tier: str
    regulatory: DimensionScore
    financial: DimensionScore
    operational: DimensionScore
    liquidity: DimensionScore
    onchain: DimensionScore
    reputation: DimensionScore
    weights_used: Dict[str, float]
    overall_confidence: float
    flags: list = field(default_factory=list)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def score_to_tier(score: float) -> str:
    """Convert composite score to risk tier."""
    if score >= 75:
        return "LOW"
    elif score >= 55:
        return "MEDIUM"
    elif score >= 35:
        return "HIGH"
    else:
        return "CRITICAL"


class ScoringEngine:
    """
    Rule-based scoring engine. Weights calibrated by Domain Expert.
    Data must be pre-fetched and passed as a structured dict.
    """

    def __init__(self):
        self.weights = settings.SCORING_WEIGHTS

    def score_counterparty(self, data: Dict[str, Any]) -> ScoringResult:
        """
        Main entry point. data is a normalized dict from the data pipeline.
        Returns a fully populated ScoringResult.
        """
        counterparty_id = data["counterparty_id"]
        entity_type = data.get("entity_type", "exchange")

        regulatory = self._score_regulatory(data)
        financial = self._score_financial(data)
        operational = self._score_operational(data)
        liquidity = self._score_liquidity(data)
        onchain = self._score_onchain(data, entity_type)
        reputation = self._score_reputation(data)

        # Weighted composite
        composite = (
            regulatory.score  * self.weights["regulatory"] +
            financial.score   * self.weights["financial"] +
            operational.score * self.weights["operational"] +
            liquidity.score   * self.weights["liquidity"] +
            onchain.score     * self.weights["onchain"] +
            reputation.score  * self.weights["reputation"]
        )

        # Overall confidence = weighted average of dimension confidences
        overall_confidence = (
            regulatory.confidence  * self.weights["regulatory"] +
            financial.confidence   * self.weights["financial"] +
            operational.confidence * self.weights["operational"] +
            liquidity.confidence   * self.weights["liquidity"] +
            onchain.confidence     * self.weights["onchain"] +
            reputation.confidence  * self.weights["reputation"]
        )

        # Collect critical flags
        all_flags = []
        for dim in [regulatory, financial, operational, liquidity, onchain, reputation]:
            all_flags.extend(dim.flags)

        return ScoringResult(
            counterparty_id=counterparty_id,
            scored_at=datetime.utcnow(),
            composite_score=round(composite, 2),
            risk_tier=score_to_tier(composite),
            regulatory=regulatory,
            financial=financial,
            operational=operational,
            liquidity=liquidity,
            onchain=onchain,
            reputation=reputation,
            weights_used=self.weights,
            overall_confidence=round(overall_confidence, 3),
            flags=all_flags,
        )

    # ── Dimension 1: Regulatory ─────────────────────────────

    def _score_regulatory(self, data: dict) -> DimensionScore:
        """
        Signals:
        - License type and regulator tier (0–40 pts)
        - License is current/not suspended (0–30 pts)
        - Jurisdiction risk (0–20 pts)
        - No regulatory actions in 12 months (0–10 pts)
        """
        score = 0
        confidence = 1.0
        signals = {}
        flags = []

        # License tier scoring
        regulator = data.get("regulator", "").upper()
        TIER_1_REGULATORS = {"OCC", "SEC", "CFTC", "FINRA", "FCA", "FINMA", "BaFin", "CSSF", "MAS", "AMF"}
        TIER_2_REGULATORS = {"FINCEN", "NYDFS", "DNB", "ASIC", "JFSA", "FSB"}

        if regulator in TIER_1_REGULATORS:
            score += 40
            signals["regulator_tier"] = "tier_1"
        elif regulator in TIER_2_REGULATORS:
            score += 25
            signals["regulator_tier"] = "tier_2"
        elif regulator:
            score += 10
            signals["regulator_tier"] = "tier_3"
        else:
            score += 0
            signals["regulator_tier"] = "none"
            flags.append("NO_REGULATORY_OVERSIGHT")
            confidence -= 0.1

        # License status
        license_active = data.get("license_active", None)
        if license_active is True:
            score += 30
            signals["license_status"] = "active"
        elif license_active is False:
            score += 0
            flags.append("LICENSE_SUSPENDED_OR_REVOKED")
            confidence -= 0.3
        else:
            score += 15   # unknown — partial credit
            signals["license_status"] = "unknown"
            confidence -= 0.15

        # Jurisdiction risk
        jurisdiction = data.get("jurisdiction", "")
        LOW_RISK_JURISDICTIONS = {"US", "GB", "CH", "LU", "DE", "FR", "NL", "SG", "JP", "AU", "CA"}
        MEDIUM_RISK_JURISDICTIONS = {"MT", "GI", "IM", "JE", "BVI", "CY"}
        if jurisdiction in LOW_RISK_JURISDICTIONS:
            score += 20
            signals["jurisdiction_risk"] = "low"
        elif jurisdiction in MEDIUM_RISK_JURISDICTIONS:
            score += 10
            signals["jurisdiction_risk"] = "medium"
            flags.append("MEDIUM_RISK_JURISDICTION")
        elif jurisdiction:
            score += 3
            signals["jurisdiction_risk"] = "high"
            flags.append("HIGH_RISK_JURISDICTION")
        else:
            score += 0
            signals["jurisdiction_risk"] = "unknown"
            confidence -= 0.1

        # Regulatory actions
        enforcement_actions = data.get("enforcement_actions_12m", 0)
        if enforcement_actions == 0:
            score += 10
        elif enforcement_actions == 1:
            score += 3
            flags.append("REGULATORY_ACTION_RECENT")
        else:
            score += 0
            flags.append("MULTIPLE_REGULATORY_ACTIONS")

        return DimensionScore(
            score=min(score, 100),
            confidence=max(0, confidence),
            signals=signals,
            flags=flags,
            explanation=f"Regulator: {regulator or 'None'}, Jurisdiction: {jurisdiction or 'Unknown'}",
        )

    # ── Dimension 2: Financial ──────────────────────────────

    def _score_financial(self, data: dict) -> DimensionScore:
        """
        Signals:
        - Publicly listed / audited financials (0–30 pts)
        - Capital adequacy / equity ratio (0–30 pts)
        - Revenue stability (0–20 pts)
        - Liabilities / credit risk (0–20 pts)
        """
        score = 0
        confidence = 0.7    # financial data often incomplete
        signals = {}
        flags = []

        # Public listing
        is_public = data.get("is_publicly_listed", False)
        if is_public:
            score += 30
            signals["financial_transparency"] = "publicly_listed"
            confidence = min(confidence + 0.2, 1.0)
        else:
            audited = data.get("has_audited_financials", None)
            if audited is True:
                score += 20
                signals["financial_transparency"] = "audited"
                confidence = min(confidence + 0.1, 1.0)
            elif audited is False:
                score += 0
                signals["financial_transparency"] = "unaudited"
                flags.append("NO_AUDITED_FINANCIALS")
                confidence -= 0.2
            else:
                score += 10
                signals["financial_transparency"] = "unknown"
                confidence -= 0.1

        # Equity / capital
        equity_ratio = data.get("equity_ratio", None)
        if equity_ratio is not None:
            if equity_ratio >= 0.30:
                score += 30
            elif equity_ratio >= 0.15:
                score += 20
            elif equity_ratio >= 0.05:
                score += 10
            else:
                score += 0
                flags.append("LOW_CAPITAL_RATIO")
            signals["equity_ratio"] = equity_ratio
        else:
            score += 15   # partial credit — unknown
            confidence -= 0.1

        # Revenue / business model
        revenue_stable = data.get("revenue_stability", None)
        if revenue_stable == "stable":
            score += 20
        elif revenue_stable == "volatile":
            score += 8
            flags.append("REVENUE_VOLATILE")
        else:
            score += 10
            confidence -= 0.05

        # Debt / liabilities
        debt_level = data.get("debt_level", None)
        if debt_level == "low":
            score += 20
        elif debt_level == "moderate":
            score += 12
        elif debt_level == "high":
            score += 3
            flags.append("HIGH_DEBT_LEVEL")
        else:
            score += 10
            confidence -= 0.05

        return DimensionScore(
            score=min(score, 100),
            confidence=max(0, confidence),
            signals=signals,
            flags=flags,
        )

    # ── Dimension 3: Operational ────────────────────────────

    def _score_operational(self, data: dict) -> DimensionScore:
        """
        Signals:
        - Security certifications (SOC2, ISO27001) (0–30 pts)
        - Historical security incidents (0–30 pts)
        - Insurance / crime coverage (0–20 pts)
        - Years in operation (0–20 pts)
        """
        score = 0
        confidence = 0.8
        signals = {}
        flags = []

        # Security certs
        has_soc2 = data.get("has_soc2", False)
        has_iso27001 = data.get("has_iso27001", False)
        if has_soc2 and has_iso27001:
            score += 30
        elif has_soc2 or has_iso27001:
            score += 20
        else:
            score += 5
            flags.append("NO_SECURITY_CERTIFICATION")
        signals["security_certs"] = {"soc2": has_soc2, "iso27001": has_iso27001}

        # Security incidents
        major_hacks = data.get("major_security_incidents", 0)
        if major_hacks == 0:
            score += 30
        elif major_hacks == 1:
            score += 15
            flags.append("HISTORICAL_SECURITY_INCIDENT")
        else:
            score += 0
            flags.append("MULTIPLE_SECURITY_INCIDENTS")
        signals["security_incidents_count"] = major_hacks

        # Insurance
        has_insurance = data.get("has_insurance", None)
        if has_insurance is True:
            score += 20
        elif has_insurance is False:
            score += 0
            flags.append("NO_INSURANCE_COVERAGE")
        else:
            score += 10
            confidence -= 0.05

        # Years in operation
        years_operating = data.get("years_in_operation", 0)
        if years_operating >= 8:
            score += 20
        elif years_operating >= 5:
            score += 15
        elif years_operating >= 3:
            score += 8
        elif years_operating >= 1:
            score += 4
        else:
            score += 0
            flags.append("LESS_THAN_1_YEAR_OPERATING")
        signals["years_operating"] = years_operating

        return DimensionScore(
            score=min(score, 100),
            confidence=max(0, confidence),
            signals=signals,
            flags=flags,
        )

    # ── Dimension 4: Liquidity & Reserves ──────────────────

    def _score_liquidity(self, data: dict) -> DimensionScore:
        """
        Signals:
        - Proof of Reserves coverage ratio (0–40 pts)
        - Average daily trading volume (0–30 pts)
        - Reserve composition quality (0–20 pts)
        - Withdrawal restriction history (0–10 pts)
        """
        score = 0
        confidence = 0.75
        signals = {}
        flags = []

        # PoR coverage ratio (assets / liabilities)
        por_ratio = data.get("por_ratio", None)
        if por_ratio is not None:
            if por_ratio >= 1.10:
                score += 40
            elif por_ratio >= 1.00:
                score += 30
            elif por_ratio >= 0.90:
                score += 10
                flags.append("PROOF_OF_RESERVES_GAP")
            else:
                score += 0
                flags.append("CRITICAL_RESERVES_SHORTFALL")
            signals["por_ratio"] = por_ratio
            confidence = min(confidence + 0.15, 1.0)
        else:
            score += 15   # no PoR — partial, penalise confidence
            flags.append("NO_PROOF_OF_RESERVES")
            confidence -= 0.2

        # Daily volume (USD)
        daily_volume = data.get("volume_24h_usd", 0)
        if daily_volume >= 5_000_000_000:   # $5B+
            score += 30
        elif daily_volume >= 1_000_000_000:  # $1B+
            score += 22
        elif daily_volume >= 100_000_000:    # $100M+
            score += 14
        elif daily_volume >= 10_000_000:     # $10M+
            score += 8
        else:
            score += 2
            flags.append("LOW_TRADING_VOLUME")
        signals["daily_volume_usd"] = daily_volume

        # Reserve composition
        reserve_quality = data.get("reserve_quality", None)
        if reserve_quality == "high":
            score += 20    # BTC/ETH/stablecoins, no illiquid altcoins
        elif reserve_quality == "medium":
            score += 12
        elif reserve_quality == "low":
            score += 3
            flags.append("LOW_QUALITY_RESERVES")
        else:
            score += 8
            confidence -= 0.05

        # Withdrawal restrictions
        withdrawal_restrictions = data.get("withdrawal_restrictions_history", False)
        if withdrawal_restrictions:
            score += 0
            flags.append("HISTORICAL_WITHDRAWAL_RESTRICTIONS")
        else:
            score += 10

        return DimensionScore(
            score=min(score, 100),
            confidence=max(0, confidence),
            signals=signals,
            flags=flags,
        )

    # ── Dimension 5: On-Chain Health ────────────────────────

    def _score_onchain(self, data: dict, entity_type: str) -> DimensionScore:
        """
        Only meaningful for exchanges, custodians, and DeFi protocols.
        For OTC desks/prime brokers, returns a neutral score.
        """
        score = 50  # default for non-on-chain entities
        confidence = 0.5
        signals = {}
        flags = []

        ON_CHAIN_RELEVANT = {"exchange", "custodian", "defi_protocol"}
        if entity_type not in ON_CHAIN_RELEVANT:
            return DimensionScore(score=50, confidence=0.4, signals={"note": "on-chain n/a for entity type"})

        # Wallet reserve trend (BTC/ETH balance on known addresses)
        reserve_trend = data.get("onchain_reserve_trend_30d", None)
        if reserve_trend == "increasing":
            score = 80
            signals["reserve_trend"] = "increasing"
        elif reserve_trend == "stable":
            score = 65
            signals["reserve_trend"] = "stable"
        elif reserve_trend == "declining":
            score = 35
            signals["reserve_trend"] = "declining"
            flags.append("DECLINING_ONCHAIN_RESERVES")
        elif reserve_trend == "critical_outflow":
            score = 10
            signals["reserve_trend"] = "critical_outflow"
            flags.append("CRITICAL_ONCHAIN_OUTFLOW")
        else:
            score = 50
            confidence = 0.3

        # DeFi TVL trend (for protocols)
        if entity_type == "defi_protocol":
            tvl_change_30d = data.get("tvl_change_30d_pct", None)
            if tvl_change_30d is not None:
                if tvl_change_30d > 0.10:
                    score = min(score + 15, 100)
                elif tvl_change_30d < -0.30:
                    score = max(score - 20, 0)
                    flags.append("MAJOR_TVL_DECLINE")
                confidence = min(confidence + 0.2, 1.0)

        # Smart contract audit (for DeFi)
        if entity_type == "defi_protocol":
            audit_count = data.get("audit_count", 0)
            if audit_count >= 3:
                score = min(score + 10, 100)
            elif audit_count == 0:
                flags.append("NO_SMART_CONTRACT_AUDIT")
                score = max(score - 15, 0)

        return DimensionScore(
            score=min(score, 100),
            confidence=max(0, confidence),
            signals=signals,
            flags=flags,
        )

    # ── Dimension 6: Reputation & Market Signals ────────────

    def _score_reputation(self, data: dict) -> DimensionScore:
        """
        Signals:
        - Negative news volume and severity (0–40 pts)
        - Social sentiment (0–20 pts)
        - Industry reputation / peer assessment (0–20 pts)
        - Executive/leadership quality (0–20 pts)
        """
        score = 50  # start neutral
        confidence = 0.6
        signals = {}
        flags = []

        # News sentiment
        news_sentiment = data.get("news_sentiment_30d", None)  # -1 to +1
        if news_sentiment is not None:
            if news_sentiment >= 0.3:
                score += 30
            elif news_sentiment >= 0:
                score += 20
            elif news_sentiment >= -0.3:
                score += 5
                flags.append("NEGATIVE_NEWS_SENTIMENT")
            else:
                score -= 10
                flags.append("STRONGLY_NEGATIVE_NEWS")
            score = max(0, score)
            signals["news_sentiment_30d"] = news_sentiment
            confidence = min(confidence + 0.2, 1.0)
        else:
            confidence -= 0.1

        # Social sentiment
        social_sentiment = data.get("social_sentiment_7d", None)
        if social_sentiment is not None:
            if social_sentiment >= 0.2:
                score = min(score + 10, 100)
            elif social_sentiment <= -0.3:
                score = max(score - 10, 0)
                flags.append("NEGATIVE_SOCIAL_SENTIMENT")
            confidence = min(confidence + 0.1, 1.0)

        # Industry reputation (manual/analyst input)
        industry_rep = data.get("industry_reputation_score", None)
        if industry_rep is not None:
            score = (score + industry_rep) / 2
            confidence = min(confidence + 0.1, 1.0)

        # Leadership
        leadership_concerns = data.get("leadership_concerns", False)
        if leadership_concerns:
            score = max(score - 15, 0)
            flags.append("LEADERSHIP_CONCERNS")

        return DimensionScore(
            score=min(score, 100),
            confidence=max(0, confidence),
            signals=signals,
            flags=flags,
        )

    def to_db_record(self, result: ScoringResult, tenant_id: str) -> dict:
        """Convert ScoringResult to a database-ready dict."""
        return {
            "tenant_id": tenant_id,
            "counterparty_id": result.counterparty_id,
            "scored_at": result.scored_at.isoformat(),
            "composite_score": result.composite_score,
            "risk_tier": result.risk_tier,
            "regulatory_score": result.regulatory.score,
            "financial_score": result.financial.score,
            "operational_score": result.operational.score,
            "liquidity_score": result.liquidity.score,
            "onchain_score": result.onchain.score,
            "reputation_score": result.reputation.score,
            "weights": result.weights_used,
            "data_snapshot": {
                "regulatory_signals": result.regulatory.signals,
                "financial_signals": result.financial.signals,
                "operational_signals": result.operational.signals,
                "liquidity_signals": result.liquidity.signals,
                "onchain_signals": result.onchain.signals,
                "reputation_signals": result.reputation.signals,
                "all_flags": result.flags,
            },
            "agent_run_id": result.run_id,
            "model_version": "scoring-engine-v1.0",
            "confidence": result.overall_confidence,
        }
