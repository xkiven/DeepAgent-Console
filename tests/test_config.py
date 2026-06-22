from app.config import MCPServerConfig, Settings
from app.mcp.service import to_client_connection


def test_settings_parse_mcp_servers() -> None:
    settings = Settings(
        mcp_servers_json='[{"name":"mock","transport":"stdio","enabled":true,"command":"python","args":["-m","demo"],"cwd":"."}]'
    )
    servers = settings.load_mcp_servers()
    assert len(servers) == 1
    assert servers[0].name == "mock"
    assert servers[0].transport == "stdio"


def test_to_client_connection_stdio() -> None:
    config = MCPServerConfig(
        name="mock",
        transport="stdio",
        enabled=True,
        command="python",
        args=["-m", "demo"],
        cwd=".",
    )
    connection = to_client_connection(config)
    assert connection["transport"] == "stdio"
    assert connection["command"] == "python"
    assert connection["args"] == ["-m", "demo"]


def test_settings_support_ark_mode() -> None:
    settings = Settings(
        llm_mode="ark",
        ark_api_key="test-key",
        ark_base_url="https://ark.cn-beijing.volces.com/api/v3",
        ark_model="doubao-seed-2-0-lite-260215",
    )
    assert settings.llm_mode == "ark"
    assert settings.ark_api_key == "test-key"
    assert settings.ark_model == "doubao-seed-2-0-lite-260215"
