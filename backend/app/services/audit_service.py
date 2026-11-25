"""Append-only audit log for every assistant and human action.

Every classification, clarifying question, resolution attempt, escalation,
ticket creation, and IT intervention is recorded here with a timestamp and
the acting principal (employee, assistant, or IT staff). The log is
JSON-lines format so it can be tailed, shipped, or imported without parsing
the whole file.

Intentionally kept separate from the operational database: audit data must
survive database resets and be easy to hand to a third party.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLogService:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path

        self.log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def record(
        self,
        event_type: str,
        actor: str,
        details: dict | None = None,
        conversation_id: int | None = None,
        ticket_id: int | None = None,
    ) -> dict:
        """Append one event to the audit log and return it."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "conversation_id": conversation_id,
            "ticket_id": ticket_id,
            "details": details or {},
        }

        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event

    def tail(
        self,
        limit: int = 100,
        conversation_id: int | None = None,
    ) -> list[dict]:
        """Return the most recent audit events, oldest first."""
        if not self.log_path.exists():
            return []

        events: list[dict] = []

        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if (
                    conversation_id is not None
                    and event.get("conversation_id") != conversation_id
                ):
                    continue

                events.append(event)

        return events[-limit:]
