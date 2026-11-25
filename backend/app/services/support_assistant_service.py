"""The assistant orchestration layer.

One entry point, `handle_employee_message`, drives the full flow:

1. Triage the message (security escalations fire before anything else).
2. Check whether IT has taken over the conversation — if so, the
   assistant stays silent.
3. Attempt resolution using the knowledge base (RAG search + LLM).
4. Track clarifying questions so the assistant asks before it guesses;
   missing mandatory details are requested, never fabricated.
5. On resolution, auto-create a fully documented ticket.
6. On failure to resolve, escalate: structured ticket with the complete
   troubleshooting history.
7. Record every step in the append-only audit log.
"""

from app.config import get_settings
from app.services.audit_service import AuditLogService
from app.services.anthropic_service import AnthropicService
from app.services.search_service import SearchService
from app.services.takeover_service import MODE_TAKEOVER, TakeoverService
from app.services.ticket_service import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    TicketService,
)
from app.services.triage_service import (
    TIER_SECURITY,
    TIER_SELF_SERVE,
    TriageResult,
    TriageService,
)


SYSTEM_PROMPT = """
You are IT Copilot, the first-line IT assistant for a small company.

Rules you must never break:
1. Never fabricate missing information. If a required detail (device,
   OS, application, error message) is missing, ask for it instead of
   guessing.
2. Prefer the knowledge base procedures provided. If none apply, say so.
3. Keep troubleshooting conversational: one focused question or one
   step at a time.
4. When the issue appears resolved, state the resolution clearly so it
   can be documented in a ticket.
5. If after {max_questions} clarifying exchanges the issue is still
   unresolved, say the word ESCALATE on its own line so a ticket is
   opened for a human technician with the full history attached.
""".strip()


class SupportAssistantService:
    def __init__(
        self,
        triage_service: TriageService,
        search_service: SearchService,
        anthropic_service: AnthropicService,
        conversation_service,
        ticket_service: TicketService,
        audit_service: AuditLogService,
        takeover_service: TakeoverService,
    ) -> None:
        self.triage_service = triage_service
        self.search_service = search_service
        self.anthropic_service = anthropic_service
        self.conversation_service = conversation_service
        self.ticket_service = ticket_service
        self.audit_service = audit_service
        self.takeover_service = takeover_service

        settings = get_settings()
        self.max_clarifying_questions = settings.max_clarifying_questions
        self.auto_ticket = settings.auto_ticket_on_resolution

    def handle_employee_message(
        self,
        message: str,
        conversation_id: int | None = None,
        employee_name: str | None = None,
        employee_email: str | None = None,
        device_info: str | None = None,
    ) -> dict:
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        if conversation_id is None:
            conversation_id = self.conversation_service.create_conversation(
                title=self._derive_title(message),
            )

            self.audit_service.record(
                event_type="conversation_started",
                actor=employee_name or "employee",
                conversation_id=conversation_id,
                details={"first_message": message},
            )

        # Live oversight check: after a takeover the assistant is silent.
        if self.takeover_service.get_mode(conversation_id) == MODE_TAKEOVER:
            self.audit_service.record(
                event_type="assistant_suppressed",
                actor="assistant",
                conversation_id=conversation_id,
                details={"reason": "IT takeover active"},
            )
            return {
                "conversation_id": conversation_id,
                "suppressed": True,
                "reply": None,
                "note": "IT has taken over this conversation.",
            }

        triage = self.triage_service.classify(message)

        self.audit_service.record(
            event_type="triage_classified",
            actor="assistant",
            conversation_id=conversation_id,
            details={
                "tier": triage.tier,
                "confidence": triage.confidence,
                "reason": triage.reason,
            },
        )

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )

        if triage.tier == TIER_SECURITY:
            return self._handle_security(
                conversation_id=conversation_id,
                message=message,
                triage=triage,
                employee_name=employee_name,
                employee_email=employee_email,
                device_info=device_info,
            )

        if triage.tier == TIER_SELF_SERVE:
            return self._handle_self_serve(
                conversation_id=conversation_id,
                message=message,
                triage=triage,
                employee_name=employee_name,
                employee_email=employee_email,
                device_info=device_info,
            )

        return self._handle_assisted(
            conversation_id=conversation_id,
            message=message,
            employee_name=employee_name,
            employee_email=employee_email,
            device_info=device_info,
        )

    # ------------------------------------------------------------------
    # Tier handlers
    # ------------------------------------------------------------------

    def _handle_security(
        self,
        conversation_id: int,
        message: str,
        triage: TriageResult,
        employee_name: str | None,
        employee_email: str | None,
        device_info: str | None,
    ) -> dict:
        """Security reports escalate immediately, before any routing.

        The design belief: the fastest path from 'someone clicked
        something weird' to a human should be zero clicks.
        """
        ticket_id = self.ticket_service.create_ticket(
            conversation_id=conversation_id,
            problem=f"SECURITY: {message}",
            troubleshooting_history=self.conversation_service.get_messages(
                conversation_id
            ),
            severity=SEVERITY_CRITICAL,
            source="triage",
            employee_name=employee_name,
            employee_email=employee_email,
            device_info=device_info,
            status="open",
        )

        self.audit_service.record(
            event_type="security_escalation",
            actor="assistant",
            conversation_id=conversation_id,
            ticket_id=ticket_id,
            details={"reason": triage.reason},
        )

        reply = (
            "This looks like a possible security issue, so I've escalated "
            f"it to the security team immediately (ticket #{ticket_id}). "
            "Please don't click any more links or attachments, and leave "
            "the device on — a technician will take it from here."
        )

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
        )

        return {
            "conversation_id": conversation_id,
            "tier": TIER_SECURITY,
            "ticket_id": ticket_id,
            "reply": reply,
        }

    def _handle_self_serve(
        self,
        conversation_id: int,
        message: str,
        triage: TriageResult,
        employee_name: str | None,
        employee_email: str | None,
        device_info: str | None,
    ) -> dict:
        """Known issues: resolve from the knowledge base, then document."""
        search_results = self.search_service.search(
            query=message,
            number_of_results=3,
        )

        context = self._build_context(search_results)

        prompt = (
            f"{SYSTEM_PROMPT.format(max_questions=self.max_clarifying_questions)}\n\n"
            "The triage classifier identified this as a known, low-risk "
            f"issue (procedure: {triage.procedure_id}).\n"
            "Give the employee the step-by-step fix from the knowledge "
            "base. If the procedure is not in the context, say so and "
            "escalate rather than inventing steps.\n\n"
            f"Knowledge base context:\n{context}\n\n"
            f"Employee request: {message}"
        )

        reply = self.anthropic_service.generate_response(prompt)

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
        )

        ticket_id = None

        if self.auto_ticket:
            ticket_id = self.ticket_service.create_ticket(
                conversation_id=conversation_id,
                problem=message,
                troubleshooting_history=(
                    self.conversation_service.get_messages(conversation_id)
                ),
                resolution=reply,
                severity=SEVERITY_HIGH if False else "low",
                source="assistant",
                employee_name=employee_name,
                employee_email=employee_email,
                device_info=device_info,
                status="resolved",
            )

            self.audit_service.record(
                event_type="ticket_created",
                actor="assistant",
                conversation_id=conversation_id,
                ticket_id=ticket_id,
                details={"outcome": "self_serve_resolved"},
            )

        return {
            "conversation_id": conversation_id,
            "tier": TIER_SELF_SERVE,
            "ticket_id": ticket_id,
            "reply": reply,
        }

    def _handle_assisted(
        self,
        conversation_id: int,
        message: str,
        employee_name: str | None,
        employee_email: str | None,
        device_info: str | None,
    ) -> dict:
        """Assisted flow: clarify, attempt resolution, escalate if stuck."""
        search_results = self.search_service.search(
            query=message,
            number_of_results=5,
        )

        context = self._build_context(search_results)
        history = self.conversation_service.get_messages(conversation_id)

        question_count = sum(
            1
            for entry in history
            if entry["role"] == "assistant"
            and "?" in entry["content"]
        )

        prompt = (
            SYSTEM_PROMPT.format(max_questions=self.max_clarifying_questions)
            + "\n\n"
            + f"Knowledge base context:\n{context}\n\n"
            + "Conversation so far:\n"
            + self._format_history(history)
            + "\n\nCurrent employee message: "
            + message
            + f"\n\n(Clarifying exchanges used so far: {question_count} "
            f"of {self.max_clarifying_questions})"
        )

        reply = self.anthropic_service.generate_response(prompt)

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
        )

        self.audit_service.record(
            event_type="assistant_reply",
            actor="assistant",
            conversation_id=conversation_id,
            details={"tier": "assisted"},
        )

        if "ESCALATE" in reply.upper():
            return self._escalate(
                conversation_id=conversation_id,
                employee_name=employee_name,
                employee_email=employee_email,
                device_info=device_info,
            )

        return {
            "conversation_id": conversation_id,
            "tier": "assisted",
            "ticket_id": None,
            "reply": reply,
        }

    def _escalate(
        self,
        conversation_id: int,
        employee_name: str | None,
        employee_email: str | None,
        device_info: str | None,
    ) -> dict:
        history = self.conversation_service.get_messages(conversation_id)

        problem = next(
            (
                entry["content"]
                for entry in history
                if entry["role"] == "user"
            ),
            "Unresolved IT issue",
        )

        ticket_id = self.ticket_service.create_ticket(
            conversation_id=conversation_id,
            problem=problem,
            troubleshooting_history=history,
            severity=SEVERITY_HIGH,
            source="assistant_escalation",
            employee_name=employee_name,
            employee_email=employee_email,
            device_info=device_info,
            status="open",
        )

        self.audit_service.record(
            event_type="ticket_created",
            actor="assistant",
            conversation_id=conversation_id,
            ticket_id=ticket_id,
            details={"outcome": "escalated_to_it"},
        )

        reply = (
            "I wasn't able to resolve this on my own, so I've opened "
            f"ticket #{ticket_id} for the IT team. Your full "
            "troubleshooting history is attached, so you won't need to "
            "start over with them."
        )

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
        )

        return {
            "conversation_id": conversation_id,
            "tier": "assisted",
            "escalated": True,
            "ticket_id": ticket_id,
            "reply": reply,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(search_results: list[dict]) -> str:
        if not search_results:
            return "No relevant knowledge base information was found."

        parts = []

        for index, result in enumerate(search_results, start=1):
            parts.append(
                f"Source {index} "
                f"({result['category']}/{result['filename']}):\n"
                f"{result['text']}"
            )

        return "\n\n".join(parts)

    @staticmethod
    def _format_history(history: list[dict[str, str]]) -> str:
        if not history:
            return "(no messages yet)"

        return "\n\n".join(
            f"{entry['role'].capitalize()}: {entry['content']}"
            for entry in history
        )

    @staticmethod
    def _derive_title(message: str) -> str:
        title = " ".join(message.split())

        if len(title) <= 50:
            return title

        return f"{title[:47]}..."
