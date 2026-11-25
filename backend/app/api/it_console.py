"""IT-facing API: ticket queue, audit trail, and live conversation control.

These endpoints are what a technician dashboard (or a future Slack
admin surface) consumes: see active conversations, watch one, join,
take it over completely, hand it back, and work tickets.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import get_services
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
