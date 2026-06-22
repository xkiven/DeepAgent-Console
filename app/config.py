from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class MCPServerConfig(BaseModel):
    name: str
    transport: Literal["stdio", "sse", "http", "streamable_http", "streamable-http", "websocket"]
    enabled: bool = True
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


DEFAULT_MCP_SERVERS = [
    {
        "name": "mock-tools",
        "transport": "stdio",
        "enabled": True,
        "command": ".venv\\Scripts\\python",
        "args": ["-m", "app.mcp.mock_server"],
        "cwd": str(BASE_DIR),
        "env": {},
    }
]


class Settings(BaseSettings):
    app_name: str = "Pydantic AI Web Console"
    host: str = "127.0.0.1"
    port: int = 8000
    app_env: str = "development"
    llm_mode: Literal["mock", "ark"] = "mock"
    ark_api_key: str | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "doubao-seed-2-0-lite-260215"
    skills_dir: str = str(BASE_DIR / "skills")
    project_root: str = str(BASE_DIR)
    session_store_path: str = str(BASE_DIR / ".data" / "sessions.json")
    mcp_servers_json: str = json.dumps(DEFAULT_MCP_SERVERS)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def load_mcp_servers(self) -> list[MCPServerConfig]:
        try:
            raw = json.loads(self.mcp_servers_json)
        except json.JSONDecodeError as exc:
            raise ValidationError.from_exception_data(
                title="Settings",
                line_errors=[],
            ) from exc
        return [MCPServerConfig.model_validate(item) for item in raw]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
