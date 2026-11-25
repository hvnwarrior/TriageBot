"""End-to-end demo conversation for IT Copilot.

Runs the full support-assistant flow without needing the web UI or a
Slack workspace: scripted employee messages go through triage, the
knowledge base, and the LLM, producing tickets and audit entries.

Usage:
    cd backend
    uvicorn app.main:app            # in one terminal (optional)
    python -m scripts.demo_conversation

The script calls the service layer directly, so it works even with the
server down. Scenarios:

  1. SECURITY  - "I think I clicked a phishing link" -> immediate
                 critical ticket, no LLM call needed.
  2. SELF_SERVE - "I forgot my password" -> knowledge-base procedure,
                 documented ticket on resolution.
  3. ASSISTED  - vague issue -> clarifying questions, then either
                 resolution or escalation with full history.

Afterwards it prints the ticket queue and the audit trail so you can
show "every path is documented".
"""

from app.config import get_settings
from app.dependencies import initialize_services
from fastapi import FastAPI


SCENARIOS = [
    {
        "name": "Security escalation",
        "messages": [
            "I think I clicked a phishing link in an email and entered my password.",
        ],
    },
    {
        "name": "Self-serve resolution",
        "messages": [
            "I forgot my password and can't log in to my laptop.",
        ],
    },
    {
        "name": "Assisted troubleshooting",
        "messages": [
            "Something is wrong with my laptop, it's really slow.",
            "It started yesterday after a restart. Everything takes ages to open.",
            "Task Manager shows disk usage at 100% constantly.",
        ],
    },
]


def main() -> None:
    settings = get_settings()

    print("=" * 62)
    print("IT Copilot - end-to-end demo")
    print(f"Database: {settings.database_path}")
    print(f"Audit log: {settings.audit_log_path}")
    print("=" * 62)

    # The FastAPI app is only used as a service container here.
    app = FastAPI()
    assistant, takeover = initialize_services(app)

    employee = {
        "employee_name": "Demo Employee",
        "employee_email": "employee@example.com",
        "device_info": "MacBook Pro, macOS 15",
    }

    for scenario in SCENARIOS:
        print(f"\n--- Scenario: {scenario['name']} ---")

        conversation_id = None

        for message in scenario["messages"]:
            print(f"\nEmployee: {message}")

            result = assistant.handle_employee_message(
                message=message,
                conversation_id=conversation_id,
                **employee,
            )

            conversation_id = result["conversation_id"]

            if result.get("suppressed"):
                print("Assistant: (suppressed - IT takeover active)")
                continue

            reply = result.get("reply") or "(no reply)"
            print(f"Assistant: {reply}")

            labels = []
            if result.get("tier"):
                labels.append(f"tier={result['tier']}")
            if result.get("ticket_id") is not None:
                labels.append(f"ticket=#{result['ticket_id']}")
            if result.get("escalated"):
                labels.append("escalated=True")

            if labels:
                print(" ".join(f"[{label}]" for label in labels))

        # Show IT taking over the last conversation as the final beat.
        session = takeover.take_over(conversation_id, "Demo Technician")
        print(f"\nIT: took over conversation {conversation_id} "
              f"(mode={session['mode']}, assistant silenced)")

    print("\n--- Ticket queue ---")
    for ticket in assistant.ticket_service.list_tickets(limit=10):
        print(
            f"#{ticket['id']} [{ticket['status']}] "
            f"severity={ticket['severity']} source={ticket['source']} "
            f"- {ticket['problem'][:60]}"
        )

    print("\n--- Audit trail (tail) ---")
    for event in assistant.audit_service.tail(limit=15):
        ticket = event.get("ticket_id")
        ticket_part = f" ticket={ticket}" if ticket else ""
        print(
            f"{event['timestamp'][:19]} {event['event_type']}"
            f" actor={event['actor']}{ticket_part}"
        )

    print("\nDemo complete. Every outcome produced a documented ticket;")


if __name__ == "__main__":
    main()
