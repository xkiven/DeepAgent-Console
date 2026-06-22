from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai import AbstractToolset
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP

from app.config import MCPServerConfig
from app.schemas import MCPServerStatus


def _prefixed_tool_name(server_name: str, tool_name: str) -> str:
    return f"{server_name}_{tool_name}"


def to_client_connection(config: MCPServerConfig) -> dict[str, Any]:
    if config.transport == "stdio":
        return {
            "transport": "stdio",
            "command": config.command,
            "args": config.args,
            "cwd": config.cwd,
            "env": config.env or None,
        }
    if config.transport == "sse":
        return {
            "transport": "sse",
            "url": config.url,
        }
    if config.transport in {"http", "streamable_http", "streamable-http"}:
        return {
            "transport": "streamable_http" if config.transport != "http" else "http",
            "url": config.url,
        }
    return {"transport": config.transport, "url": config.url}


def build_mcp_server(config: MCPServerConfig):
    common_kwargs = {
        "tool_prefix": config.name,
        "timeout": 10,
        "read_timeout": 300,
    }

    if config.transport == "stdio":
        if not config.command:
            raise ValueError(f"MCP stdio server `{config.name}` 缺少 command")
        return MCPServerStdio(
            config.command,
            config.args,
            cwd=config.cwd,
            env=config.env or None,
            **common_kwargs,
        )

    if config.transport == "sse":
        if not config.url:
            raise ValueError(f"MCP SSE server `{config.name}` 缺少 url")
        return MCPServerSSE(config.url, **common_kwargs)

    if config.transport in {"http", "streamable_http", "streamable-http"}:
        if not config.url:
            raise ValueError(f"MCP HTTP server `{config.name}` 缺少 url")
        return MCPServerStreamableHTTP(config.url, **common_kwargs)

    raise ValueError(f"Unsupported transport: {config.transport}")


@dataclass
class MCPInventory:
    toolsets: list[AbstractToolset[Any]]
    statuses: list[MCPServerStatus]


class MCPService:
    def __init__(self, servers: list[MCPServerConfig]) -> None:
        self.servers = servers

    async def load(self) -> MCPInventory:
        statuses: list[MCPServerStatus] = []
        toolsets: list[AbstractToolset[Any]] = []

        for server_config in self.servers:
            if not server_config.enabled:
                statuses.append(
                    MCPServerStatus(
                        name=server_config.name,
                        transport=server_config.transport,
                        enabled=False,
                        connected=False,
                        detail="disabled",
                    )
                )
                continue

            try:
                server = build_mcp_server(server_config)
                async with server:
                    raw_tools = await server.list_tools()

                tool_names = [_prefixed_tool_name(server_config.name, tool.name) for tool in raw_tools]
                toolsets.append(server)
                statuses.append(
                    MCPServerStatus(
                        name=server_config.name,
                        transport=server_config.transport,
                        enabled=True,
                        connected=True,
                        tool_count=len(tool_names),
                        tools=tool_names,
                        detail="ok",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                statuses.append(
                    MCPServerStatus(
                        name=server_config.name,
                        transport=server_config.transport,
                        enabled=True,
                        connected=False,
                        detail=str(exc),
                    )
                )

        return MCPInventory(toolsets=toolsets, statuses=statuses)
