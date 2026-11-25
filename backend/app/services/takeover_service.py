"""Live conversation oversight for IT staff.

IT can watch active conversations in real time and intervene at any
point: join as a participant or take the conversation over completely.
Once a takeover happens, the assistant goes silent for that conversation
unless IT hands it back.

State is intentionally in-memory: it describes *live* sessions. Tickets
and the audit log persist what happened; this only tracks who is driving
right now.
"""

from datetime import datetime, timezone


MODE_ASSISTANT = "assistant"
MODE_JOINED = "joined"          # IT present, assistant still responding
MODE_TAKEOVER = "takeover"      # IT is driving; assistant silent


class TakeoverService:
    def __init__(self) -> None:
        # conversation_id -> session state
        self._sessions: dict[int, dict] = {}

    def _session(self, conversation_id: int) -> dict:
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = {
                "conversation_id": conversation_id,
                "mode": MODE_ASSISTANT,
                "it_participants": [],
                "taken_over_by": None,
                "taken_over_at": None,
            }

        return self._sessions[conversation_id]

    def watch(self, conversation_id: int) -> dict:
        """Register IT interest in a conversation without interfering."""
        return self._session(conversation_id)

    def join(
        self,
        conversation_id: int,
        technician: str,
    ) -> dict:
        """IT joins the conversation; assistant keeps responding."""
        session = self._session(conversation_id)

        if technician not in session["it_participants"]:
            session["it_participants"].append(technician)

        session["mode"] = MODE_JOINED

        return session

    def take_over(
        self,
        conversation_id: int,
        technician: str,
    ) -> dict:
        """IT takes the conversation over completely; assistant goes silent."""
        session = self._session(conversation_id)

        if technician not in session["it_participants"]:
            session["it_participants"].append(technician)

        session["mode"] = MODE_TAKEOVER
        session["taken_over_by"] = technician
        session["taken_over_at"] = datetime.now(timezone.utc).isoformat()

        return session

    def hand_back(
        self,
        conversation_id: int,
        technician: str,
    ) -> dict:
        """IT hands the conversation back to the assistant."""
        session = self._session(conversation_id)

        if session["mode"] == MODE_TAKEOVER:
            if technician in session["it_participants"]:
                session["it_participants"].remove(technician)

            session["mode"] = (
                MODE_JOINED
                if session["it_participants"]
                else MODE_ASSISTANT
            )
            session["taken_over_by"] = None
            session["taken_over_at"] = None

        return session

    def get_mode(self, conversation_id: int) -> str:
        if conversation_id not in self._sessions:
            return MODE_ASSISTANT

        return self._sessions[conversation_id]["mode"]

    def list_active(self) -> list[dict]:
        return list(self._sessions.values())
