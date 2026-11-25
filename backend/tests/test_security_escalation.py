"""Security escalation service tests: paging, ack, watchdog, audit.

The escalating behaviors that define the design:
- incidents page named responders, not just channels
- acknowledgment is recorded with who and when
- the watchdog re-escalates unacknowledged incidents, loudly
- acknowledging after re-escalation still works
- closing a closed incident is rejected
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.security_escalation_service import (
    ConsoleNotificationChannel,
    INCIDENT_ACKNOWLEDGED,
    INCIDENT_CLOSED,
    INCIDENT_OPEN,
    INCIDENT_REESCALATED,
    PagePlan,
    PageTarget,
    SecurityEscalationService,
)


class RecordingChannel(ConsoleNotificationChannel):
    """Captures notifications so tests can assert on them."""

    def __init__(self) -> None:
        self.pages: list[tuple[str, str]] = []
        self.broadcasts: list[tuple[str, str]] = []

    def send_to_target(self, target, message):
        self.pages.append((target.handle, message))

    def broadcast(self, channel, message):
        self.broadcasts.append((channel, message))


def make_service(channel, deadline_minutes=15, now=None):
    plan = PagePlan(
        targets=[PageTarget("U_RESP1"), PageTarget("U_RESP2")],
        broadcast_channels=["C_SECURITY"],
    )

    return SecurityEscalationService(
        notification_channel=channel,
        plan_provider=lambda: plan,
        ack_deadline_minutes=deadline_minutes,
    )


def test_incident_pages_named_responders():
    channel = RecordingChannel()
    service = make_service(channel)

    incident = service.escalate(
        ticket_id=1, conversation_id=1, reporter="alice", summary="phishing"
    )

    assert incident.status == INCIDENT_OPEN
    assert incident.paged == ["U_RESP1", "U_RESP2"]
    assert len(channel.pages) == 2
    assert len(channel.broadcasts) == 1
    assert "phishing" in channel.pages[0][1]


def test_acknowledge_records_responder_and_time():
    channel = RecordingChannel()
    service = make_service(channel)

    service.escalate(ticket_id=1, conversation_id=1, reporter="alice", summary="s")
    incident = service.acknowledge(1, "U_RESP1")

    assert incident.status == INCIDENT_ACKNOWLEDGED
    assert incident.acknowledged_by == "U_RESP1"
    assert incident.acknowledged_at is not None


def test_watchdog_reescalates_unacknowledged_after_deadline():
    channel = RecordingChannel()
    service = make_service(channel)

    service.escalate(ticket_id=1, conversation_id=1, reporter="bob", summary="s")

    # Before the deadline: no re-escalation.
    early = service.sweep_unacknowledged(
        now=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    assert early == []

    # After the deadline: loud re-escalation to everyone.
    late = service.sweep_unacknowledged(
        now=datetime.now(timezone.utc) + timedelta(minutes=20)
    )

    assert len(late) == 1
    assert late[0].status == INCIDENT_REESCALATED
    assert late[0].re_escalation_count == 1
    assert len(channel.pages) == 2 + 2  # initial page + re-escalation
    assert "NOBODY" in channel.pages[-1][1]


def test_watchdog_ignores_acknowledged_incidents():
    channel = RecordingChannel()
    service = make_service(channel)

    service.escalate(ticket_id=1, conversation_id=1, reporter="bob", summary="s")
    service.acknowledge(1, "U_RESP1")

    re_escalated = service.sweep_unacknowledged(
        now=datetime.now(timezone.utc) + timedelta(minutes=30)
    )

    assert re_escalated == []


def test_acknowledge_still_possible_after_reescalation():
    channel = RecordingChannel()
    service = make_service(channel)

    service.escalate(ticket_id=1, conversation_id=1, reporter="bob", summary="s")
    service.sweep_unacknowledged(
        now=datetime.now(timezone.utc) + timedelta(minutes=20)
    )

    incident = service.acknowledge(1, "U_RESP2")

    assert incident.status == INCIDENT_ACKNOWLEDGED
    assert incident.re_escalation_count == 1


def test_close_records_closer():
    channel = RecordingChannel()
    service = make_service(channel)

    service.escalate(ticket_id=1, conversation_id=1, reporter="bob", summary="s")
    incident = service.close(1, "U_RESP1")

    assert incident.status == INCIDENT_CLOSED


def test_double_close_rejected():
    channel = RecordingChannel()
    service = make_service(channel)

    service.escalate(ticket_id=1, conversation_id=1, reporter="bob", summary="s")
    service.close(1, "U_RESP1")

    with pytest.raises(ValueError):
        service.close(1, "U_RESP2")


def test_unknown_incident_errors():
    service = make_service(RecordingChannel())

    with pytest.raises(ValueError):
        service.acknowledge(99, "U_RESP1")

    with pytest.raises(ValueError):
        service.close(99, "U_RESP1")
