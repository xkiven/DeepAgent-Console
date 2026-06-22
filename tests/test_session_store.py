from pathlib import Path
from uuid import uuid4

from pydantic_ai.messages import ModelRequest, UserPromptPart

from app.session_store import SessionStore
from app.schemas import ToolLogEntry


def test_session_store_persists_sessions() -> None:
    test_dir = Path(".test-data")
    test_dir.mkdir(exist_ok=True)
    store_path = test_dir / f"sessions-{uuid4().hex}.json"
    store = SessionStore(store_path)
    session = store.create()
    store.add_message(session.id, "user", "你好")
    store.add_message(session.id, "assistant", "世界")
    store.set_model_history(session.id, [ModelRequest(parts=[UserPromptPart(content="你好")])])
    store.add_tool_log(
        session.id,
        ToolLogEntry(
            id="log-1",
            timestamp=session.created_at,
            event="tool_start",
            name="read_skill",
            content='{"name":"code-review"}',
        ),
    )

    reloaded = SessionStore(store_path)
    session_after = reloaded.get(session.id)

    assert session_after.message_count == 2
    assert session_after.messages[0].content == "你好"
    assert session_after.messages[1].content == "世界"
    assert session_after.tool_logs[0].name == "read_skill"
    assert len(reloaded.get_model_history(session.id)) == 1
