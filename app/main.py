from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent import AgentRuntime
from app.api import create_api_router
from app.config import get_settings
from app.mcp.service import MCPService
from app.session_store import SessionStore


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.on_event("startup")
    async def startup() -> None:
        session_store = SessionStore(settings.session_store_path)
        inventory = await MCPService(settings.load_mcp_servers()).load()
        app.state.session_store = session_store
        app.state.agent_runtime = AgentRuntime(
            settings=settings,
            session_store=session_store,
            mcp_toolsets=inventory.toolsets,
            mcp_statuses=inventory.statuses,
        )

    @app.get("/")
    async def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/logs")
    async def logs():
        return FileResponse(static_dir / "logs.html")

    @app.get("/__config")
    async def config():
        return {
            "app_name": settings.app_name,
            "llm_mode": settings.llm_mode,
        }

    app.include_router(create_api_router(settings))
    return app


app = create_app()
