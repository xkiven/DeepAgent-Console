from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.schemas import ChatRequest
from app.skills import discover_skills


def create_api_router(
    settings: Settings,
):
    router = APIRouter(prefix="/api")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/skills")
    async def list_skills():
        return discover_skills(settings.skills_dir)

    @router.get("/mcp/servers")
    async def list_mcp_servers(request: Request):
        return request.app.state.agent_runtime.mcp_statuses

    @router.get("/sessions")
    async def list_sessions(request: Request):
        return request.app.state.session_store.list()

    @router.post("/sessions")
    async def create_session(request: Request):
        return request.app.state.session_store.create()

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str, request: Request):
        try:
            return request.app.state.session_store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/sessions/{session_id}/reset")
    async def reset_session(session_id: str, request: Request):
        try:
            return request.app.state.session_store.reset(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/chat/stream")
    async def chat_stream(payload: ChatRequest, request: Request):
        async def event_stream() -> AsyncIterator[str]:
            try:
                async for item in request.app.state.agent_runtime.stream_chat(payload.session_id, payload.message):
                    yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
            except KeyError as exc:
                error = {"type": "error", "content": str(exc)}
                yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return router
