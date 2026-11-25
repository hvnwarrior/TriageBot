"""Employee-facing API: start a support conversation with the assistant.

Platform adapters (Slack, Teams) call these same endpoints, so the
core logic stays platform-independent. A REST/HTML demo page rides on
them too, so the assistant can be tried without a Slack workspace.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import get_support_assistant_service


router = APIRouter(prefix="/assistant", tags=["Assistant"])


class AssistantMessageRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    employee_name: str | None = None
    employee_email: str | None = None
    device_info: str | None = None


class AssistantMessageResponse(BaseModel):
    conversation_id: int
    reply: str | None
    tier: str | None = None
    ticket_id: int | None = None
    escalated: bool = False
    suppressed: bool = False
    note: str | None = None


@router.post("/message", response_model=AssistantMessageResponse)
def send_assistant_message(
    request: AssistantMessageRequest,
) -> AssistantMessageResponse:
    """Handle one employee message through the full assistant flow."""
    service = get_support_assistant_service()

    try:
        result = service.handle_employee_message(
            message=request.message,
            conversation_id=request.conversation_id,
            employee_name=request.employee_name,
            employee_email=request.employee_email,
            device_info=request.device_info,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return AssistantMessageResponse(
        conversation_id=result["conversation_id"],
        reply=result.get("reply"),
        tier=result.get("tier"),
        ticket_id=result.get("ticket_id"),
        escalated=result.get("escalated", False),
        suppressed=result.get("suppressed", False),
        note=result.get("note"),
    )


@router.get("/conversations/{conversation_id}/history")
def get_conversation_history(conversation_id: int) -> dict:
    """Return the full message history of a conversation."""
    service = get_support_assistant_service()

    if not service.conversation_service.conversation_exists(
        conversation_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found.",
        )

    messages = service.conversation_service.get_messages(conversation_id)

    return {
        "conversation_id": conversation_id,
        "messages": messages,
    }
