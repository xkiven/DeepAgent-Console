from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillSummary(BaseModel):
    name: str
    description: str
    path: str
    allowed_tools: list[str] = Field(default_factory=list)


class MCPServerStatus(BaseModel):
    name: str
    transport: str
    enabled: bool
    connected: bool
    tool_count: int = 0
    tools: list[str] = Field(default_factory=list)
    detail: str | None = None


class ToolLogEntry(BaseModel):
    id: str
    timestamp: datetime
    event: Literal["tool_start", "tool_end", "tool_error", "status", "message"]
    name: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class SessionSummary(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    title: str
    message_count: int


class SessionDetail(SessionSummary):
    messages: list[ChatMessage]
    tool_logs: list[ToolLogEntry]
    run_status: Literal["idle", "running", "error"] = "idle"
    pending_assistant_content: str = ""
    run_error: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
