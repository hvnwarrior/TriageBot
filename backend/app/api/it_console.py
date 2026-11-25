"""IT-facing API: ticket queue, audit trail, and live conversation control.

These endpoints are what a technician dashboard (or a future Slack
admin surface) consumes: see active conversations, watch one, join,
take it over completely, hand it back, and work tickets.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import get_services
from app.services.security_escalation_service import (
    SecurityIncident,
)
from app.services.takeover_service import MODE_ASSISTANT, MODE_JOINED, MODE_TAKEOVER


router = APIRouter(prefix="/it", tags=["IT Console"])


class InterventionRequest(BaseModel):
    technician: str


class TicketResolutionRequest(BaseModel):
    resolution: str
    resolver: str


class TicketEscalationRequest(BaseModel):
    technician: str
    note: str | None = None


@router.get("/conversations/active")
def list_active_conversations() -> dict:
    """All conversations IT can currently watch or intervene in."""
    _, takeover = get_services()

    return {"active": takeover.list_active()}


@router.get("/conversations/{conversation_id}/watch")
def watch_conversation(conversation_id: int) -> dict:
    """Watch a conversation without affecting the assistant's behavior."""
    assistant, takeover = get_services()

    if not assistant.conversation_service.conversation_exists(
        conversation_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found.",
        )

    session = takeover.watch(conversation_id)
    messages = assistant.conversation_service.get_messages(conversation_id)

    return {
        "session": session,
        "mode": session["mode"],
        "messages": messages,
    }


@router.post("/conversations/{conversation_id}/join")
def join_conversation(
    conversation_id: int,
    request: InterventionRequest,
) -> dict:
    """Join the conversation; the assistant keeps responding."""
    _, takeover = get_services()

    session = takeover.join(conversation_id, request.technician)

    return {"session": session}


@router.post("/conversations/{conversation_id}/takeover")
def take_over_conversation(
    conversation_id: int,
    request: InterventionRequest,
) -> dict:
    """Take the conversation over completely; the assistant goes silent."""
    assistant, takeover = get_services()

    if not assistant.conversation_service.conversation_exists(
        conversation_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found.",
        )

    session = takeover.take_over(conversation_id, request.technician)

    assistant.audit_service.record(
        event_type="it_takeover",
        actor=request.technician,
        conversation_id=conversation_id,
        details={"mode": session["mode"]},
    )

    return {"session": session}


@router.post("/conversations/{conversation_id}/hand-back")
def hand_back_conversation(
    conversation_id: int,
    request: InterventionRequest,
) -> dict:
    """Hand a taken-over conversation back to the assistant."""
    assistant, takeover = get_services()

    session = takeover.hand_back(conversation_id, request.technician)

    assistant.audit_service.record(
        event_type="it_hand_back",
        actor=request.technician,
        conversation_id=conversation_id,
        details={"mode": session["mode"]},
    )

    return {"session": session}


@router.post("/conversations/{conversation_id}/technician-message")
def send_technician_message(
    conversation_id: int,
    request: InterventionRequest,
) -> dict:
    """Record a technician message sent into the conversation directly.

    The message body is appended by the caller via the conversation
    history endpoint; here we register the intervention in the audit
    log so the trail shows IT drove the conversation.
    """
    assistant, _ = get_services()

    if not assistant.conversation_service.conversation_exists(
        conversation_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found.",
        )

    assistant.audit_service.record(
        event_type="technician_message",
        actor=request.technician,
        conversation_id=conversation_id,
    )

    return {"status": "recorded"}


@router.get("/tickets")
def list_tickets(
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """Ticket queue, newest first; filter by status."""
    assistant, _ = get_services()

    tickets = assistant.ticket_service.list_tickets(
        status=status,
        limit=limit,
    )

    return {"tickets": tickets}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int) -> dict:
    assistant, _ = get_services()

    try:
        ticket = assistant.ticket_service.get_ticket(ticket_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    return {"ticket": ticket}


@router.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: int,
    request: TicketResolutionRequest,
) -> dict:
    assistant, _ = get_services()

    try:
        ticket = assistant.ticket_service.resolve_ticket(
            ticket_id=ticket_id,
            resolution=request.resolution,
            resolver=request.resolver,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    assistant.audit_service.record(
        event_type="ticket_resolved",
        actor=request.resolver,
        ticket_id=ticket_id,
    )

    return {"ticket": ticket}


@router.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(
    ticket_id: int,
    request: TicketEscalationRequest,
) -> dict:
    assistant, _ = get_services()

    try:
        ticket = assistant.ticket_service.escalate_ticket(
            ticket_id=ticket_id,
            technician=request.technician,
            note=request.note,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    assistant.audit_service.record(
        event_type="ticket_escalated",
        actor=request.technician,
        ticket_id=ticket_id,
        details={"note": request.note},
    )

    return {"ticket": ticket}


@router.get("/audit")
def get_audit_tail(
    limit: int = 100,
    conversation_id: int | None = None,
) -> dict:
    """Recent audit events, oldest first; optionally per conversation."""
    assistant, _ = get_services()

    events = assistant.audit_service.tail(
        limit=limit,
        conversation_id=conversation_id,
    )

    return {"events": events}


class IncidentAcknowledgeRequest(BaseModel):
    responder: str


class IncidentCloseRequest(BaseModel):
    responder: str


def _incident_to_dict(incident: SecurityIncident) -> dict:
    return {
        "ticket_id": incident.ticket_id,
        "conversation_id": incident.conversation_id,
        "reporter": incident.reporter,
        "summary": incident.summary,
        "status": incident.status,
        "paged": list(incident.paged),
        "acknowledged_by": incident.acknowledged_by,
        "acknowledged_at": incident.acknowledged_at,
        "re_escalation_count": incident.re_escalation_count,
        "created_at": incident.created_at,
    }


@router.get("/security/incidents")
def list_security_incidents() -> dict:
    """Open (non-closed) security incidents, with paging/ack state."""
    assistant, _ = get_services()
    escalation = assistant.security_escalation_service

    if escalation is None:
        raise HTTPException(status_code=503, detail="Security escalation not configured.")

    return {
        "incidents": [
            _incident_to_dict(incident)
            for incident in escalation.list_open()
        ]
    }


@router.post("/security/incidents/{ticket_id}/acknowledge")
def acknowledge_incident(ticket_id: int, request: IncidentAcknowledgeRequest) -> dict:
    """A named responder takes ownership of a security incident."""
    assistant, _ = get_services()
    escalation = assistant.security_escalation_service

    if escalation is None:
        raise HTTPException(status_code=503, detail="Security escalation not configured.")

    try:
        incident = escalation.acknowledge(ticket_id, request.responder)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    assistant.audit_service.record(
        event_type="security_acknowledged",
        actor=request.responder,
        ticket_id=ticket_id,
        conversation_id=incident.conversation_id,
        details={"after_re_escalation": incident.re_escalation_count > 0},
    )

    return {"incident": _incident_to_dict(incident)}


@router.post("/security/incidents/{ticket_id}/close")
def close_incident(ticket_id: int, request: IncidentCloseRequest) -> dict:
    """Close a security incident (after containment/resolution)."""
    assistant, _ = get_services()
    escalation = assistant.security_escalation_service

    if escalation is None:
        raise HTTPException(status_code=503, detail="Security escalation not configured.")

    try:
        incident = escalation.close(ticket_id, request.closed_by if hasattr(request, 'closed_by') else request.responder)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    assistant.audit_service.record(
        event_type="security_incident_closed",
        actor=request.responder,
        ticket_id=ticket_id,
        conversation_id=incident.conversation_id,
    )

    return {"incident": _incident_to_dict(incident)}


@router.post("/security/sweep")
def sweep_security_incidents() -> dict:
    """Manually trigger the unacknowledged-incident watchdog.

    Useful for demos and for cron-less deployments; the Slack adapter
    runs this on a timer in production setups.
    """
    assistant, _ = get_services()
    escalation = assistant.security_escalation_service

    if escalation is None:
        raise HTTPException(status_code=503, detail="Security escalation not configured.")

    re_escalated = escalation.sweep_unacknowledged()

    for incident in re_escalated:
        assistant.audit_service.record(
            event_type="security_re_escalated",
            actor="watchdog",
            ticket_id=incident.ticket_id,
            conversation_id=incident.conversation_id,
            details={"re_escalation_count": incident.re_escalation_count},
        )

    return {
        "re_escalated": [
            _incident_to_dict(incident) for incident in re_escalated
        ]
    }
