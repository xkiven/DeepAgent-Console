from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterable
from uuid import uuid4

from pydantic_ai import Agent
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import Settings
from app.schemas import MCPServerStatus, SkillSummary, ToolLogEntry
from app.session_store import SessionStore
from app.skills import discover_skills


ISO_UTC_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00$")


def _chunk_text(text: str, size: int = 18) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [text]


def _extract_latest_user_text(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        for part in reversed(message.parts):
            if isinstance(part, UserPromptPart):
                return str(part.content)
    return ""


def _extract_latest_tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    if not messages:
        return []
    latest = messages[-1]
    return [part for part in latest.parts if isinstance(part, ToolReturnPart)]


def _infer_skill_name(user_text: str) -> str | None:
    lowered = user_text.lower()

    code_review_keywords = [
        "code-review",
        "code review",
        "review code",
        "代码评审",
        "代码审查",
        "代码review",
        "做一次评审",
        "帮我评审",
        "缺陷排查",
        "回归评估",
    ]
    if any(keyword in lowered or keyword in user_text for keyword in code_review_keywords):
        return "code-review"

    test_generator_keywords = [
        "test-generator",
        "test generator",
        "generate test",
        "generate tests",
        "写测试",
        "生成测试",
        "补测试",
        "测试用例",
        "回归测试",
    ]
    if any(keyword in lowered or keyword in user_text for keyword in test_generator_keywords):
        return "test-generator"

    data_analysis_keywords = [
        "data-analysis",
        "data analysis",
        "分析数据",
        "数据分析",
        "趋势分析",
        "csv",
        "报表分析",
    ]
    if any(keyword in lowered or keyword in user_text for keyword in data_analysis_keywords):
        return "data-analysis"

    return None


def _format_time_text(text: str) -> str:
    value = text.strip()
    if value.startswith("当前北京时间："):
        return value
    if ISO_UTC_TIME_RE.match(value):
        dt = datetime.fromisoformat(value)
        beijing = dt.astimezone(timezone(timedelta(hours=8)))
        return beijing.strftime("当前北京时间：%Y-%m-%d %H:%M:%S")
    return value


def _strip_read_file_line_numbers(text: str) -> str:
    return re.sub(r"(?m)^\s*\d+\t", "", text).strip()


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _format_time_text(value)
    if isinstance(value, list):
        return "\n".join(_stringify_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return _format_time_text(str(value))


def _format_tool_summary(part: ToolReturnPart) -> str:
    content = _stringify_value(part.content)
    if part.tool_name in {"read_file", "read_skill"}:
        content = _strip_read_file_line_numbers(content)
    return f"{part.tool_name}: {content}"


def _mock_select_tools(user_text: str, available_tool_names: set[str]) -> list[tuple[str, dict[str, Any]]]:
    lowered = user_text.lower()
    inferred_skill = _infer_skill_name(user_text)
    selections: list[tuple[str, dict[str, Any]]] = []

    if (("skill" in lowered or "技能" in user_text) or inferred_skill is not None) and "read_skill" in available_tool_names:
        selections.append(("read_skill", {"name": inferred_skill or "data-analysis"}))

    if (
        any(word in lowered for word in ["summary", "summarize"])
        or any(word in user_text for word in ["总结", "概括"])
    ) and "mock-tools_summarize_text" in available_tool_names:
        selections.append(("mock-tools_summarize_text", {"text": user_text}))
    elif (
        "time" in lowered or any(word in user_text for word in ["时间", "几点", "当前时间"])
    ) and "mock-tools_time_now" in available_tool_names:
        selections.append(("mock-tools_time_now", {}))

    if ("echo" in lowered or "回显" in user_text) and "mock-tools_echo_json" in available_tool_names:
        selections.append(("mock-tools_echo_json", {"payload": json.dumps({"message": user_text}, ensure_ascii=False)}))

    if (
        "available skills" in lowered or "可用技能" in user_text or "有哪些技能" in user_text
    ) and "list_skills" in available_tool_names:
        selections.append(("list_skills", {}))

    deduped: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for name, args in selections:
        if name not in seen:
            seen.add(name)
            deduped.append((name, args))
    return deduped[:2]


def _mock_final_text(messages: list[ModelMessage]) -> str:
    user_text = _extract_latest_user_text(messages)
    tool_returns = _extract_latest_tool_returns(messages)
    lines = ["执行完成。"]
    if "skill" in user_text.lower() or "技能" in user_text or _infer_skill_name(user_text):
        lines.append("已从本地 SKILL.md 文件加载相关技能说明。")
    if tool_returns:
        lines.append("工具执行结果：")
        lines.extend(f"- {_format_tool_summary(part)}" for part in tool_returns)
    return "\n".join(lines)


def _mock_fallback_text(user_text: str) -> str:
    return (
        "当前演示运行在 mock 模式下。"
        "你可以让我查看可用技能、总结一段文本，或者查询当前时间，"
        "这样会触发本地工具和 MCP 工具。\n\n"
        f"你刚才的问题是：{user_text}"
    )


def _mock_model_response(messages: list[ModelMessage], agent_info: AgentInfo):
    tool_returns = _extract_latest_tool_returns(messages)
    if tool_returns:
        return TextPart(_mock_final_text(messages))

    user_text = _extract_latest_user_text(messages)
    available_tool_names = {tool.name for tool in agent_info.function_tools}
    requested_tools = _mock_select_tools(user_text, available_tool_names)
    if requested_tools:
        return [
            DeltaToolCall(
                name=name,
                json_args=json.dumps(args, ensure_ascii=False, separators=(",", ":")),
                tool_call_id=f"mock_call_{index}_{name}",
            )
            for index, (name, args) in enumerate(requested_tools)
        ]

    return TextPart(_mock_fallback_text(user_text))


def _mock_model_function(messages: list[ModelMessage], agent_info: AgentInfo):
    result = _mock_model_response(messages, agent_info)
    from pydantic_ai.messages import ModelResponse, ToolCallPart

    if isinstance(result, TextPart):
        return ModelResponse(parts=[result], model_name="mock")

    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=delta.name or "",
                args=json.loads(delta.json_args or "{}"),
                tool_call_id=delta.tool_call_id or f"mock_call_{index}",
            )
            for index, delta in enumerate(result)
        ],
        model_name="mock",
    )


async def _mock_stream_function(messages: list[ModelMessage], agent_info: AgentInfo):
    result = _mock_model_response(messages, agent_info)
    if isinstance(result, TextPart):
        for chunk in _chunk_text(result.content):
            yield chunk
        return

    yield {index: delta for index, delta in enumerate(result)}


def _build_model(settings: Settings):
    if settings.llm_mode == "mock":
        return FunctionModel(
            function=_mock_model_function,
            stream_function=_mock_stream_function,
            model_name="mock",
        )

    if settings.llm_mode == "ark":
        if not settings.ark_api_key:
            raise ValueError("LLM_MODE=ark 时必须设置 ARK_API_KEY。")
        provider = OpenAIProvider(base_url=settings.ark_base_url, api_key=settings.ark_api_key)
        return OpenAIChatModel(settings.ark_model, provider=provider)

    raise ValueError(f"Unsupported llm mode: {settings.llm_mode}")


def _build_system_prompt(skills: list[SkillSummary]) -> str:
    skill_lines = "\n".join(f"- {skill.name}: {skill.description}" for skill in skills)
    return (
        "你是一个智能体控制台演示助手。\n"
        "当用户请求代码评审、测试生成或数据分析时，必须优先调用 read_skill(name) 读取对应技能说明，再继续回答。\n"
        "当用户询问可用技能时，调用 list_skills。\n"
        "如有可用的 MCP 工具，可根据任务需要调用。\n"
        "当前可用技能：\n"
        f"{skill_lines}"
    )


class AgentRuntime:
    def __init__(
        self,
        settings: Settings,
        session_store: SessionStore,
        mcp_toolsets: list[MCPServerStdio | MCPServerSSE | MCPServerStreamableHTTP],
        mcp_statuses: list[MCPServerStatus],
    ) -> None:
        self.settings = settings
        self.session_store = session_store
        self.mcp_toolsets = mcp_toolsets
        self.mcp_statuses = mcp_statuses
        self.skill_summaries = discover_skills(settings.skills_dir)
        self.skill_map = {skill.name: Path(skill.path) for skill in self.skill_summaries}
        self.agent = self._build_agent()

    def _build_agent(self) -> Agent[None, str]:
        agent = Agent(
            _build_model(self.settings),
            output_type=str,
            system_prompt=_build_system_prompt(self.skill_summaries),
            toolsets=self.mcp_toolsets,
        )

        @agent.tool_plain(name="list_skills")
        def list_skills() -> str:
            """列出当前可用的本地技能及其用途。"""
            return "\n".join(f"- {skill.name}: {skill.description}" for skill in self.skill_summaries)

        @agent.tool_plain(name="read_skill")
        def read_skill(name: str) -> str:
            """读取指定技能的完整 SKILL.md 内容。当任务与某个技能相关时，先调用此工具。"""
            path = self.skill_map.get(name)
            if path is None:
                available = ", ".join(sorted(self.skill_map))
                raise ValueError(f"未知技能 `{name}`，可用技能有：{available}")
            return path.read_text(encoding="utf-8").strip()

        return agent

    async def stream_chat(self, session_id: str, user_message: str) -> AsyncIterator[dict[str, Any]]:
        self.session_store.add_message(session_id, "user", user_message)
        history = self.session_store.get_model_history(session_id)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        yield {"type": "status", "content": "running"}

        async def event_handler(_: Any, events: AsyncIterator[AgentStreamEvent]) -> None:
            async for event in events:
                item = self._map_event(session_id, event)
                if item is not None:
                    await queue.put(item)

        async def run_agent() -> None:
            try:
                result = await self.agent.run(
                    user_message,
                    message_history=history,
                    event_stream_handler=event_handler,
                )
                self.session_store.set_model_history(session_id, result.all_messages())
                assistant_message = self.session_store.add_message(session_id, "assistant", str(result.output))
                await queue.put({"type": "message", "content": assistant_message.model_dump(mode="json")})
            except Exception as exc:  # noqa: BLE001
                await queue.put({"type": "error", "content": str(exc)})
            finally:
                await queue.put({"type": "done", "content": "complete"})

        task = asyncio.create_task(run_agent())
        try:
            while True:
                item = await queue.get()
                yield item
                if item["type"] == "done":
                    break
        finally:
            await task

    def _map_event(self, session_id: str, event: AgentStreamEvent) -> dict[str, Any] | None:
        if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart) and event.part.content:
            return {"type": "token", "content": event.part.content}

        if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
            return {"type": "token", "content": event.delta.content_delta}

        if isinstance(event, FunctionToolCallEvent):
            payload = ToolLogEntry(
                id=str(uuid4()),
                timestamp=datetime.now(UTC),
                event="tool_start",
                name=event.part.tool_name,
                content=event.part.args_as_json_str(),
            )
            self.session_store.add_tool_log(session_id, payload)
            return {"type": "tool_log", "content": payload.model_dump(mode="json")}

        if isinstance(event, FunctionToolResultEvent):
            payload = ToolLogEntry(
                id=str(uuid4()),
                timestamp=datetime.now(UTC),
                event="tool_end",
                name=event.part.tool_name,
                content=_stringify_value(event.part.content),
            )
            self.session_store.add_tool_log(session_id, payload)
            return {"type": "tool_log", "content": payload.model_dump(mode="json")}

        return None
