"""Smoke tests for the TriageBot core services.

Deterministic tests only — no LLM calls. They validate the behaviors
that define the project:

- security messages escalate before anything else
- self-serve classification hits the known-issue procedures
- the assistant refuses to answer for unknown conversations
- every outcome (resolution or escalation) produces a ticket
- the audit log records classifications and interventions
- takeover silences the assistant; hand-back restores it

Run:  cd backend && pytest
"""

import tempfile
from pathlib import Path

import pytest

from app.config import get_settings
from app.services.audit_service import AuditLogService
from app.services.conversation_service import ConversationService
from app.services.takeover_service import (
    MODE_ASSISTANT,
    MODE_JOINED,
    MODE_TAKEOVER,
    TakeoverService,
)
from app.services.ticket_service import (
    SEVERITY_CRITICAL,
    TicketService,
)
from app.services.triage_service import (
    TIER_ASSISTED,
    TIER_SECURITY,
    TIER_SELF_SERVE,
    TriageService,
)


@pytest.fixture
def tmp_dirs(tmp_path: Path) -> tuple[Path, Path]:
    return (
        tmp_path / "triagebot_test.db",
        tmp_path / "audit_test.jsonl",
    )


@pytest.fixture
def triage() -> TriageService:
    return TriageService(use_llm_assist=False)


@pytest.fixture
def conversation_service(tmp_dirs) -> ConversationService:
    return ConversationService(database_path=tmp_dirs[0])


@pytest.fixture
def ticket_service(tmp_dirs) -> TicketService:
    return TicketService(database_path=tmp_dirs[0])


@pytest.fixture
def audit_service(tmp_dirs) -> AuditLogService:
    return AuditLogService(log_path=tmp_dirs[1])


# =====================================================================
# Triage
# =====================================================================


def test_phishing_escalates_immediately(triage):
    result = triage.classify(
        "I think I clicked a phishing link and entered my password"
    )

    assert result.tier == TIER_SECURITY
    assert result.confidence == 1.0


def test_lost_device_is_security(triage):
    result = triage.classify("Help, my laptop was stolen last night")

    assert result.tier == TIER_SECURITY


def test_password_reset_is_self_serve(triage):
    result = triage.classify("I forgot my password")

    assert result.tier == TIER_SELF_SERVE
    assert result.procedure_id == "password-reset"


def test_vpn_is_self_serve(triage):
    result = triage.classify("The VPN keeps disconnecting")

    assert result.tier == TIER_SELF_SERVE
    assert result.procedure_id == "vpn-setup"


def test_vague_problem_defaults_to_assisted(triage):
    result = triage.classify("Something feels off with my laptop")

    assert result.tier == TIER_ASSISTED


def test_security_beats_self_serve_keywords(triage):
    # "compromised" must outrank any incidental keyword match.
    result = triage.classify(
        "I think my password got compromised during a password reset"
    )

    assert result.tier == TIER_SECURITY


# =====================================================================
# Tickets
# =====================================================================


def test_escalation_ticket_contains_full_history(
    ticket_service,
    conversation_service,
):
    conversation_id = conversation_service.create_conversation(
        title="Phishing report"
    )

    conversation_service.add_message(
        conversation_id=conversation_id,
        role="user",
        content="I clicked a bad link",
    )
    conversation_service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content="Escalating immediately, do not click anything else.",
    )

    ticket_id = ticket_service.create_ticket(
        conversation_id=conversation_id,
        problem="Phishing click",
        troubleshooting_history=conversation_service.get_messages(
            conversation_id
        ),
        severity=SEVERITY_CRITICAL,
        source="triage",
    )

    ticket = ticket_service.get_ticket(ticket_id)

    assert ticket["severity"] == SEVERITY_CRITICAL
    assert "I clicked a bad link" in ticket["troubleshooting_history"]
    assert (
        "do not click anything else"
        in ticket["troubleshooting_history"]
    )


def test_resolved_ticket_roundtrip(ticket_service, conversation_service):
    conversation_id = conversation_service.create_conversation(
        title="VPN fix"
    )

    ticket_id = ticket_service.create_ticket(
        conversation_id=conversation_id,
        problem="VPN not connecting",
        troubleshooting_history=[
            {"role": "user", "content": "VPN is down"},
        ],
        resolution="Re-entered the server address; connected.",
        status="resolved",
    )

    ticket = ticket_service.get_ticket(ticket_id)

    assert ticket["status"] == "resolved"
    assert "Re-entered the server address" in ticket["resolution"]


def test_unknown_severity_rejected(ticket_service, conversation_service):
    conversation_id = conversation_service.create_conversation(title="x")

    with pytest.raises(ValueError):
        ticket_service.create_ticket(
            conversation_id=conversation_id,
            problem="p",
            troubleshooting_history=[],
            severity="catastrophic",
        )


def test_list_tickets_filters_by_status(ticket_service):
    for index in range(3):
        conversation_id = index + 1

        ticket_service.create_ticket(
            conversation_id=conversation_id,
            problem=f"problem {index}",
            troubleshooting_history=[],
            status="resolved" if index < 2 else "open",
        )

    resolved = ticket_service.list_tickets(status="resolved")

    assert len(resolved) == 2
    assert all(t["status"] == "resolved" for t in resolved)


# =====================================================================
# Audit log
# =====================================================================


def test_audit_log_appends_and_tails(audit_service):
    audit_service.record(
        event_type="triage_classified",
        actor="assistant",
        conversation_id=1,
        details={"tier": TIER_SECURITY},
    )

    audit_service.record(
        event_type="it_takeover",
        actor="technician@example.com",
        conversation_id=1,
    )

    events = audit_service.tail(limit=10)

    assert len(events) == 2
    assert events[0]["event_type"] == "triage_classified"
    assert events[1]["actor"] == "technician@example.com"
    assert "timestamp" in events[0]


def test_audit_tail_filters_by_conversation(audit_service):
    audit_service.record(
        event_type="a", actor="assistant", conversation_id=1
    )
    audit_service.record(
        event_type="b", actor="assistant", conversation_id=2
    )

    events = audit_service.tail(limit=10, conversation_id=2)

    assert len(events) == 1
    assert events[0]["event_type"] == "b"


def test_audit_log_empty_when_missing(audit_service):
    assert audit_service.tail() == []


# =====================================================================
# Takeover
# =====================================================================


def test_takeover_silences_then_restores():
    takeover = TakeoverService()

    assert takeover.get_mode(42) == MODE_ASSISTANT

    session = takeover.take_over(42, "tech@example.com")

    assert session["mode"] == MODE_TAKEOVER
    assert session["taken_over_by"] == "tech@example.com"
    assert takeover.get_mode(42) == MODE_TAKEOVER

    takeover.hand_back(42, "tech@example.com")

    assert takeover.get_mode(42) == MODE_ASSISTANT


def test_join_keeps_assistant_alive():
    takeover = TakeoverService()

    session = takeover.join(42, "tech@example.com")

    assert session["mode"] == MODE_JOINED
    assert takeover.get_mode(42) == MODE_JOINED


def test_hand_back_without_takeover_is_noop():
    takeover = TakeoverService()

    session = takeover.hand_back(42, "tech@example.com")

    assert session["mode"] == MODE_ASSISTANT


def test_takeover_lists_active():
    takeover = TakeoverService()

    takeover.watch(1)
    takeover.join(2, "tech@example.com")

    active = takeover.list_active()

    assert len(active) == 2
    assert {session["conversation_id"] for session in active} == {1, 2}


# =====================================================================
# Conversation persistence
# =====================================================================


def test_conversation_history_roundtrip(conversation_service):
    conversation_id = conversation_service.create_conversation(
        title="roundtrip"
    )

    conversation_service.add_message(
        conversation_id, "user", "first message"
    )
    conversation_service.add_message(
        conversation_id, "assistant", "second message"
    )

    messages = conversation_service.get_messages(conversation_id)

    assert len(messages) == 2
    assert messages[0] == {
        "role": "user",
        "content": "first message",
    }


def test_missing_conversation_returns_false(conversation_service):
    assert not conversation_service.conversation_exists(9999)
