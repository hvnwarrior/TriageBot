"""Instant triage of employee IT requests into routing tiers.

Tiers mirror the design from the playtest/writeup pipeline:

1. SECURITY — phishing/incident keywords escalate immediately, before any
   other processing. IT is a sensor for security, not just a helpdesk.
2. SELF_SERVE — known issues (password reset, VPN setup, etc.) that the
   assistant can resolve with a procedure from the knowledge base.
3. ASSISTED — everything else: the assistant asks clarifying questions
   and attempts resolution with a human able to watch or intervene.

The classifier is deliberately deterministic keyword rules with an
optional LLM assist stub — it fails safe and predictably, and swapping
in a local model is a single-method change.
"""

from dataclasses import dataclass

from app.services.anthropic_service import AnthropicService


TIER_SECURITY = "security"
TIER_SELF_SERVE = "self_serve"
TIER_ASSISTED = "assisted"


# Escalate immediately, before anything else can misroute it.
SECURITY_KEYWORDS = (
    "phishing",
    "malware",
    "ransomware",
    "clicked a link",
    "clicked the link",
    "strange email",
    "suspicious email",
    "suspicious attachment",
    "compromised",
    "hacked",
    "data breach",
    "lost laptop",
    "lost phone",
    "stolen laptop",
    "stolen phone",
)


# High-frequency, low-risk requests the assistant handles end-to-end.
SELF_SERVE_KEYWORDS = {
    "password reset": "password-reset",
    "reset my password": "password-reset",
    "forgot my password": "password-reset",
    "locked out": "password-reset",
    "vpn": "vpn-setup",
    "mfa": "mfa-setup",
    "2fa": "mfa-setup",
    "printer": "printer-config",
    "wifi": "wifi-config",
}


@dataclass
class TriageResult:
    tier: str
    procedure_id: str | None
    confidence: float
    reason: str


class TriageService:
    def __init__(
        self,
        anthropic_service: AnthropicService | None = None,
        use_llm_assist: bool = False,
    ) -> None:
        self.anthropic_service = anthropic_service
        self.use_llm_assist = use_llm_assist

    def classify(self, message: str) -> TriageResult:
        normalized = message.lower()

        # Tier 1: security. Fires before any other logic, always.
        for keyword in SECURITY_KEYWORDS:
            if keyword in normalized:
                return TriageResult(
                    tier=TIER_SECURITY,
                    procedure_id=None,
                    confidence=1.0,
                    reason=f"security keyword match: '{keyword}'",
                )

        # Tier 2: self-serve known issues.
        for keyword, procedure_id in SELF_SERVE_KEYWORDS.items():
            if keyword in normalized:
                return TriageResult(
                    tier=TIER_SELF_SERVE,
                    procedure_id=procedure_id,
                    confidence=0.9,
                    reason=f"known-issue keyword match: '{keyword}'",
                )

        # Tier 3: assisted — assistant-driven clarification + resolution
        # attempt, with IT able to watch and take over.
        if self.use_llm_assist and self.anthropic_service is not None:
            llm_result = self._classify_with_llm(message, normalized)
            if llm_result is not None:
                return llm_result

        return TriageResult(
            tier=TIER_ASSISTED,
            procedure_id=None,
            confidence=0.5,
            reason="no keyword match; defaulting to assisted triage",
        )

    def _classify_with_llm(
        self,
        message: str,
        normalized: str,
    ) -> TriageResult | None:
        """Optional LLM assist; returns None to fall back to assisted."""
        try:
            response = self.anthropic_service.generate_response(
                prompt=(
                    "Classify this IT support request into exactly one "
                    "tier: security, self_serve, or assisted. "
                    "Reply with the tier name only.\n\n"
                    f"Request: {message}"
                ),
                max_tokens=10,
            )
        except Exception:
            return None

        tier = response.strip().lower()

        if tier in (TIER_SECURITY, TIER_SELF_SERVE, TIER_ASSISTED):
            return TriageResult(
                tier=tier,
                procedure_id=None,
                confidence=0.7,
                reason="llm assist classification",
            )

        return None
