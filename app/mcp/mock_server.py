from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP


server = FastMCP("mock-tools", instructions="Mock MCP server for local demos.")


@server.tool()
def summarize_text(text: str) -> str:
    """Return a very short summary for demo purposes."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= 80:
        return cleaned
    return cleaned[:77] + "..."


@server.tool()
def time_now() -> str:
    """Return the current Beijing time in a human-friendly format."""
    beijing = timezone(timedelta(hours=8))
    now = datetime.now(UTC).astimezone(beijing)
    return now.strftime("当前北京时间：%Y-%m-%d %H:%M:%S")


@server.tool()
def echo_json(payload: str) -> str:
    """Echo JSON-like text for integration testing."""
    return f"echo:{payload}"


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
