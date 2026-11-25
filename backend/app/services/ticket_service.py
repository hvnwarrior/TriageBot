"""Ticket creation for both assistant resolutions and escalations.

Every conversation ends in a ticket, no exceptions:

- Resolved by the assistant -> a fully documented ticket (problem,
  troubleshooting performed, resolution, severity, employee/device info)
  for tracking and audit purposes.
- Escalated to IT -> a structured ticket containing the complete
  troubleshooting history so the technician never starts from scratch.

Tickets live in the operational SQLite database, distinct from the
append-only audit log.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"


SEVERITY_ORDER = {
    SEVERITY_LOW: 0,
    SEVERITY_MEDIUM: 1,
    SEVERITY_HIGH: 2,
    SEVERITY_CRITICAL: 3,
}


class TicketService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    severity TEXT NOT NULL DEFAULT 'medium',
                    source TEXT NOT NULL DEFAULT 'assistant',
                    problem TEXT NOT NULL,
                    troubleshooting_history TEXT NOT NULL,
                    resolution TEXT,
                    employee_name TEXT,
                    employee_email TEXT,
                    device_info TEXT,
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.commit()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_ticket(
        self,
        conversation_id: int,
        problem: str,
        troubleshooting_history: list[dict],
        resolution: str | None = None,
        severity: str = SEVERITY_MEDIUM,
        source: str = "assistant",
        employee_name: str | None = None,
        employee_email: str | None = None,
        device_info: str | None = None,
        status: str = "open",
    ) -> int:
        if severity not in SEVERITY_ORDER:
            raise ValueError(f"Unknown severity: {severity}")

        history_text = self._format_history(troubleshooting_history)

        with self._get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tickets (
                    conversation_id,
                    status,
                    severity,
                    source,
                    problem,
                    troubleshooting_history,
                    resolution,
                    employee_name,
                    employee_email,
                    device_info,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    status,
                    severity,
                    source,
                    problem,
                    history_text,
                    resolution,
                    employee_name,
                    employee_email,
                    device_info,
                    self._utc_now(),
                    self._utc_now(),
                ),
            )

            connection.commit()

            return int(cursor.lastrowid)

    def escalate_ticket(
        self,
        ticket_id: int,
        technician: str,
        note: str | None = None,
    ) -> dict:
        with self._get_connection() as connection:
            connection.execute(
                """
                UPDATE tickets
                SET status = 'escalated',
                    resolution = COALESCE(resolution, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    f"Escalated to IT ({technician})"
                    + (f": {note}" if note else ""),
                    self._utc_now(),
                    ticket_id,
                ),
            )

            connection.commit()

        return self.get_ticket(ticket_id)

    def resolve_ticket(
        self,
        ticket_id: int,
        resolution: str,
        resolver: str,
    ) -> dict:
        with self._get_connection() as connection:
            connection.execute(
                """
                UPDATE tickets
                SET status = 'resolved',
                    resolution = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    f"{resolution} (resolved by {resolver})",
                    self._utc_now(),
                    ticket_id,
                ),
            )

            connection.commit()

        return self.get_ticket(ticket_id)

    def get_ticket(self, ticket_id: int) -> dict:
        with self._get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM tickets WHERE id = ?
                """,
                (ticket_id,),
            ).fetchone()

        if row is None:
            raise ValueError(f"Ticket {ticket_id} not found.")

        return dict(row)

    def list_tickets(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = "SELECT * FROM tickets"
        parameters: tuple = ()

        if status is not None:
            query += " WHERE status = ?"
            parameters = (status,)

        query += " ORDER BY id DESC LIMIT ?"
        parameters = parameters + (limit,)

        with self._get_connection() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def _format_history(troubleshooting_history: list[dict]) -> str:
        """Serialize the full troubleshooting transcript into the ticket.

        Technicians receiving an escalated ticket should never have to
        ask the employee to repeat anything already covered.
        """
        if not troubleshooting_history:
            return "No troubleshooting history recorded."

        parts = []

        for entry in troubleshooting_history:
            role = str(entry.get("role", "unknown"))
            content = str(entry.get("content", "")).strip()
            parts.append(f"[{role}] {content}")

        return "\n\n".join(parts)
