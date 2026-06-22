from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage
from pydantic_ai.messages import ModelMessagesTypeAdapter

from app.schemas import ChatMessage, SessionDetail, SessionSummary, ToolLogEntry


@dataclass
class SessionState:
    id: str
    created_at: datetime
    updated_at: datetime
    title: str
    messages: list[ChatMessage] = field(default_factory=list)
    tool_logs: list[ToolLogEntry] = field(default_factory=list)
    model_history: list[ModelMessage] = field(default_factory=list)
    run_status: str = "idle"
    pending_assistant_content: str = ""
    run_error: str | None = None


class PersistedSessionRecord(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    title: str
    messages: list[ChatMessage] = []
    tool_logs: list[ToolLogEntry] = []
    model_history_json: str = "[]"
    run_status: str = "idle"
    pending_assistant_content: str = ""
    run_error: str | None = None


class PersistedSessionStore(BaseModel):
    sessions: list[PersistedSessionRecord] = []


class SessionStore:
    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)
        self._sessions: dict[str, SessionState] = {}
        self._load()

    def create(self) -> SessionDetail:
        now = datetime.now(UTC)
        session_id = str(uuid4())
        state = SessionState(
            id=session_id,
            created_at=now,
            updated_at=now,
            title="新会话",
        )
        self._sessions[session_id] = state
        self._save()
        return self.get(session_id)

    def reset(self, session_id: str) -> SessionDetail:
        state = self._require(session_id)
        state.messages.clear()
        state.tool_logs.clear()
        state.model_history.clear()
        state.updated_at = datetime.now(UTC)
        state.title = "新会话"
        self._save()
        return self.get(session_id)

    def delete(self, session_id: str) -> None:
        self._require(session_id)
        del self._sessions[session_id]
        self._save()

    def list(self) -> list[SessionSummary]:
        items = [
            SessionSummary(
                id=state.id,
                created_at=state.created_at,
                updated_at=state.updated_at,
                title=state.title,
                message_count=len(state.messages),
            )
            for state in self._sessions.values()
        ]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get(self, session_id: str) -> SessionDetail:
        state = self._require(session_id)
        return SessionDetail(
            id=state.id,
            created_at=state.created_at,
            updated_at=state.updated_at,
            title=state.title,
            message_count=len(state.messages),
            messages=list(state.messages),
            tool_logs=list(state.tool_logs),
            run_status=state.run_status,
            pending_assistant_content=state.pending_assistant_content,
            run_error=state.run_error,
        )

    def add_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        state = self._require(session_id)
        message = ChatMessage(
            id=str(uuid4()),
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
        state.messages.append(message)
        state.updated_at = message.created_at
        if role == "user" and state.title == "新会话":
            state.title = content[:40] or "新会话"
        self._save()
        return message

    def add_tool_log(self, session_id: str, entry: ToolLogEntry) -> ToolLogEntry:
        state = self._require(session_id)
        state.tool_logs.append(entry)
        state.updated_at = entry.timestamp
        self._save()
        return entry

    def start_run(self, session_id: str) -> None:
        state = self._require(session_id)
        state.run_status = "running"
        state.pending_assistant_content = ""
        state.run_error = None
        state.updated_at = datetime.now(UTC)
        self._save()

    def append_pending_assistant(self, session_id: str, content: str) -> None:
        if not content:
            return
        state = self._require(session_id)
        state.pending_assistant_content += content
        state.updated_at = datetime.now(UTC)
        self._save()

    def finish_run(self, session_id: str, content: str) -> ChatMessage:
        state = self._require(session_id)
        message = ChatMessage(
            id=str(uuid4()),
            role="assistant",
            content=content,
            created_at=datetime.now(UTC),
        )
        state.messages.append(message)
        state.pending_assistant_content = ""
        state.run_status = "idle"
        state.run_error = None
        state.updated_at = message.created_at
        self._save()
        return message

    def fail_run(self, session_id: str, error: str) -> None:
        state = self._require(session_id)
        state.run_status = "error"
        state.run_error = error
        state.updated_at = datetime.now(UTC)
        self._save()

    def clear_run_state(self, session_id: str) -> None:
        state = self._require(session_id)
        state.run_status = "idle"
        state.pending_assistant_content = ""
        state.run_error = None
        state.updated_at = datetime.now(UTC)
        self._save()

    def get_model_history(self, session_id: str) -> list[ModelMessage]:
        state = self._require(session_id)
        return list(state.model_history)

    def set_model_history(self, session_id: str, history: list[ModelMessage]) -> None:
        state = self._require(session_id)
        state.model_history = list(history)
        self._save()

    def _require(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self._sessions[session_id]

    def _load(self) -> None:
        if not self.storage_path.exists():
            return

        raw = self.storage_path.read_text(encoding="utf-8")
        payload = PersistedSessionStore.model_validate_json(raw)
        for record in payload.sessions:
            history = ModelMessagesTypeAdapter.validate_json(record.model_history_json.encode("utf-8"))
            self._sessions[record.id] = SessionState(
                id=record.id,
                created_at=record.created_at,
                updated_at=record.updated_at,
                title=record.title,
                messages=list(record.messages),
                tool_logs=list(record.tool_logs),
                model_history=list(history),
                run_status=record.run_status,
                pending_assistant_content=record.pending_assistant_content,
                run_error=record.run_error,
            )

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = PersistedSessionStore(
            sessions=[
                PersistedSessionRecord(
                    id=state.id,
                    created_at=state.created_at,
                    updated_at=state.updated_at,
                    title=state.title,
                    messages=list(state.messages),
                    tool_logs=list(state.tool_logs),
                    model_history_json=ModelMessagesTypeAdapter.dump_json(state.model_history).decode("utf-8"),
                    run_status=state.run_status,
                    pending_assistant_content=state.pending_assistant_content,
                    run_error=state.run_error,
                )
                for state in self._sessions.values()
            ]
        )
        self.storage_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
