"""Security incident escalation with named responders and an SLA.

Design stance: a channel post is not an escalation. A security incident
must reach a named human, be acknowledged by them within a deadline, and
re-escalate loudly if nobody responds. Silence is treated as an incident
condition in itself.

Components:

- PagePlan: who gets paged, how, in what order.
- SecurityIncident: tracked state (paged, acked, re-escalations).
- SecurityEscalationService: page -> ack -> watchdog re-escalation.
- NotificationChannel: pluggable delivery (console/print here; Slack
  DMs via the adapter; PagerDuty/Opsgenie webhooks can be added as
  further channels without touching the core).

Escalation ladder: responders in order -> re-escalation broadcast to
ALL responders after the ack deadline expires. Containment actions
(disable account, wipe device) are deliberately NOT automated here;
they remain human decisions recorded in the ticket and audit log.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


INCIDENT_OPEN = "open"
INCIDENT_ACKNOWLEDGED = "acknowledged"
INCIDENT_REESCALATED = "re_escalated"
INCIDENT_CLOSED = "closed"


@dataclass
class PageTarget:
    """One named human and how to reach them."""

    handle: str            # Slack user ID or email
    channel: str = "dm"    # dm | email | webhook


@dataclass
class PagePlan:
    """Ordered responders for one incident, plus broadcast channels."""

    targets: list[PageTarget] = field(default_factory=list)
    broadcast_channels: list[str] = field(default_factory=list)  # channel IDs

    def is_empty(self) -> bool:
        return not self.targets and not self.broadcast_channels


@dataclass
class SecurityIncident:
    """State of one escalated security incident."""

    ticket_id: int
    conversation_id: int
    reporter: str
    summary: str
    status: str = INCIDENT_OPEN
    paged: list[str] = field(default_factory=list)
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    re_escalation_count: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def ack_deadline(self, deadline_minutes: int) -> datetime:
        created = datetime.fromisoformat(self.created_at)
        return created + timedelta(minutes=deadline_minutes)


class NotificationChannel:
    """Delivery interface; the concrete sender is injected.

    The core service never talks to Slack or email directly — it emits
    structured notifications, and the adapter decides what those look
    like on each platform. Tests can inject a recorder.
    """

    def send_to_target(self, target: PageTarget, message: str) -> None:
        raise NotImplementedError

    def broadcast(self, channel: str, message: str) -> None:
        raise NotImplementedError


class ConsoleNotificationChannel(NotificationChannel):
    """Fallback channel: logs notifications where stdout goes."""

    def send_to_target(self, target: PageTarget, message: str) -> None:
        print(f"[SECURITY PAGE -> {target.handle}] {message}")

    def broadcast(self, channel: str, message: str) -> None:
        print(f"[SECURITY BROADCAST -> {channel}] {message}")


class SecurityEscalationService:
    def __init__(
        self,
        notification_channel: NotificationChannel,
        plan_provider,
        ack_deadline_minutes: int = 15,
    ) -> None:
        """plan_provider() -> PagePlan, rebuilt per incident so config
        changes take effect without restarts."""

        self.notification_channel = notification_channel
        self.plan_provider = plan_provider
        self.ack_deadline_minutes = ack_deadline_minutes
        self._incidents: dict[int, SecurityIncident] = {}

    # ------------------------------------------------------------------
    # Paging
    # ------------------------------------------------------------------

    def escalate(
        self,
        ticket_id: int,
        conversation_id: int,
        reporter: str,
        summary: str,
    ) -> SecurityIncident:
        """Page named responders for a new security incident."""

        incident = SecurityIncident(
            ticket_id=ticket_id,
            conversation_id=conversation_id,
            reporter=reporter,
            summary=summary,
        )

        self._incidents[ticket_id] = incident

        plan = self.plan_provider()

        message = (
            f"SECURITY INCIDENT (ticket #{ticket_id}) reported by "
            f"{reporter}: {summary}. Acknowledge within "
            f"{self.ack_deadline_minutes} minutes."
        )

        for target in plan.targets:
            self.notification_channel.send_to_target(target, message)
            incident.paged.append(target.handle)

        for channel in plan.broadcast_channels:
            self.notification_channel.broadcast(channel, message)

        return incident

    # ------------------------------------------------------------------
    # Acknowledgment
    # ------------------------------------------------------------------

    def acknowledge(
        self,
        ticket_id: int,
        responder: str,
    ) -> SecurityIncident:
        """A named human takes ownership of the incident."""

        incident = self._require_incident(ticket_id)

        if incident.status == INCIDENT_CLOSED:
            raise ValueError(
                f"Incident for ticket {ticket_id} is already closed."
            )

        incident.status = INCIDENT_ACKNOWLEDGED
        incident.acknowledged_by = responder
        incident.acknowledged_at = datetime.now(
            timezone.utc
        ).isoformat()

        return incident

    # ------------------------------------------------------------------
    # Watchdog: the dead-man's switch
    # ------------------------------------------------------------------

    def sweep_unacknowledged(
        self,
        now: datetime | None = None,
    ) -> list[SecurityIncident]:
        """Re-escalate any open incident past its ack deadline.

        Called periodically (cron, background task, or the Slack
        adapter's scheduler). Unacknowledged is treated as an incident
        condition: the re-escalation goes to ALL responders with an
        explicit warning that nobody has acknowledged.
        """

        now = now or datetime.now(timezone.utc)

        re_escalated: list[SecurityIncident] = []

        for incident in self._incidents.values():

            if incident.status != INCIDENT_OPEN:
                continue

            if now < incident.ack_deadline(self.ack_deadline_minutes):
                continue

            plan = self.plan_provider()

            message = (
                f":rotating_light: RE-ESCALATION (ticket #{incident.ticket_id}): "
                f"NOBODY has acknowledged this security incident after "
                f"{self.ack_deadline_minutes} minutes. Reported by "
                f"{incident.reporter}: {incident.summary}. Someone must "
                "acknowledge now or escalate externally."
            )

            for target in plan.targets:
                self.notification_channel.send_to_target(target, message)

            for channel in plan.broadcast_channels:
                self.notification_channel.broadcast(channel, message)

            incident.status = INCIDENT_REESCALATED
            incident.re_escalation_count += 1

            re_escalated.append(incident)

        return re_escalated

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self, ticket_id: int, closed_by: str) -> SecurityIncident:
        incident = self._require_incident(ticket_id)

        if incident.status == INCIDENT_CLOSED:
            raise ValueError(
                f"Incident for ticket {ticket_id} is already closed."
            )

        incident.status = INCIDENT_CLOSED
        incident.acknowledged_by = incident.acknowledged_by or closed_by

        return incident

    def get_incident(self, ticket_id: int) -> SecurityIncident:
        return self._require_incident(ticket_id)

    def list_open(self) -> list[SecurityIncident]:
        return [
            incident
            for incident in self._incidents.values()
            if incident.status != INCIDENT_CLOSED
        ]

    def _require_incident(self, ticket_id: int) -> SecurityIncident:
        if ticket_id not in self._incidents:
            raise ValueError(f"No security incident for ticket {ticket_id}.")

        return self._incidents[ticket_id]
