from pathlib import Path
from uuid import uuid4

from pydantic_ai.messages import PartStartEvent, TextPart, ToolReturnPart

from app.agent import (
    AgentRuntime,
    _format_time_text,
    _format_tool_summary,
    _infer_skill_name,
    _strip_read_file_line_numbers,
)
from app.config import Settings
from app.schemas import MCPServerStatus
from app.session_store import SessionStore


def _workspace_store_path(prefix: str) -> Path:
    root = Path(".test-data")
    root.mkdir(exist_ok=True)
    return root / f"{prefix}-{uuid4().hex}.json"


def test_agent_runtime_creation() -> None:
    settings = Settings(skills_dir="skills", project_root=".", llm_mode="mock")
    runtime = AgentRuntime(
        settings=settings,
        session_store=SessionStore(_workspace_store_path("agent-runtime")),
        mcp_toolsets=[],
        mcp_statuses=[MCPServerStatus(name="mock", transport="stdio", enabled=True, connected=False)],
    )
    assert runtime.agent is not None
    assert any(skill.name == "code-review" for skill in runtime.skill_summaries)


def test_infer_skill_name_for_code_review_prompt() -> None:
    assert _infer_skill_name("帮我做一次代码评审，看看这段 Python 代码有没有问题") == "code-review"


def test_strip_read_file_line_numbers() -> None:
    numbered = "     1\t---\n     2\tname: code-review\n    13\t1. 先阅读目标文件。"
    cleaned = _strip_read_file_line_numbers(numbered)
    assert cleaned == "---\nname: code-review\n1. 先阅读目标文件。"


def test_format_tool_summary_for_read_skill() -> None:
    part = ToolReturnPart(
        tool_name="read_skill",
        content="     1\t---\n     2\tname: code-review\n    13\t1. 先阅读目标文件。",
        tool_call_id="call_1",
    )
    summary = _format_tool_summary(part)
    assert summary == "read_skill: ---\nname: code-review\n1. 先阅读目标文件。"


def test_format_time_text_for_iso_utc() -> None:
    formatted = _format_time_text("2026-06-21T14:27:49.399378+00:00")
    assert formatted == "当前北京时间：2026-06-21 22:27:49"


def test_map_event_persists_pending_assistant_content() -> None:
    settings = Settings(skills_dir="skills", project_root=".", llm_mode="mock")
    store = SessionStore(_workspace_store_path("agent-runtime"))
    session = store.create()
    runtime = AgentRuntime(
        settings=settings,
        session_store=store,
        mcp_toolsets=[],
        mcp_statuses=[MCPServerStatus(name="mock", transport="stdio", enabled=True, connected=False)],
    )

    event = PartStartEvent(index=0, part=TextPart(content="partial reply"))
    mapped = runtime._map_event(session.id, event)
    session_after = store.get(session.id)

    assert mapped == {"type": "token", "content": "partial reply"}
    assert session_after.pending_assistant_content == "partial reply"
