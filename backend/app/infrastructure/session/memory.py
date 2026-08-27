"""In-memory conversation store (SPEC 2 §6.2). History trimming lives in
`app.application.session_memory`: it is pure shaping logic, not an adapter.
"""

from app.domain.session import ConversationSession


class ConversationStore:
    """Holds one ConversationSession per session_id, isolated from every other."""

    def __init__(self, history_max_turns: int) -> None:
        self.history_max_turns = history_max_turns
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: str) -> ConversationSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(session_id=session_id)
        return self._sessions[session_id]

    def save(self, session: ConversationSession) -> None:
        self._sessions[session.session_id] = session
