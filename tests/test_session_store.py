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


def test_session_store_delete_session() -> None:
    test_dir = Path(".test-data")
    test_dir.mkdir(exist_ok=True)
    store_path = test_dir / f"sessions-{uuid4().hex}.json"
    store = SessionStore(store_path)
    session = store.create()
    store.add_message(session.id, "user", "要删除的会话")

    store.delete(session.id)

    reloaded = SessionStore(store_path)
    assert reloaded.list() == []


def test_session_store_persists_running_state() -> None:
    test_dir = Path(".test-data")
    test_dir.mkdir(exist_ok=True)
    store_path = test_dir / f"sessions-{uuid4().hex}.json"
    store = SessionStore(store_path)
    session = store.create()

    store.start_run(session.id)
    store.append_pending_assistant(session.id, "partial reply")

    reloaded = SessionStore(store_path)
    session_after = reloaded.get(session.id)

    assert session_after.run_status == "running"
    assert session_after.pending_assistant_content == "partial reply"
    assert session_after.run_error is None


def test_session_store_finish_run_appends_assistant_message() -> None:
    test_dir = Path(".test-data")
    test_dir.mkdir(exist_ok=True)
    store_path = test_dir / f"sessions-{uuid4().hex}.json"
    store = SessionStore(store_path)
    session = store.create()

    store.start_run(session.id)
    store.append_pending_assistant(session.id, "partial reply")
    message = store.finish_run(session.id, "final reply")

    session_after = store.get(session.id)

    assert message.role == "assistant"
    assert session_after.run_status == "idle"
    assert session_after.pending_assistant_content == ""
    assert session_after.messages[-1].content == "final reply"
