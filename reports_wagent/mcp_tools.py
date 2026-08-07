from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from reports_wagent.config import Settings

LOGGER = logging.getLogger(__name__)


async def load_mcp_tools(settings: Settings) -> list[BaseTool]:
    connections = _mcp_connections(settings)
    if not connections:
        LOGGER.info("No MCP servers are enabled.")
        return []

    client = MultiServerMCPClient(connections, tool_name_prefix=True)
    tools = await client.get_tools()
    LOGGER.info(
        "Loaded %d MCP tool(s) from server(s): %s.",
        len(tools),
        ", ".join(connections),
    )
    return tools


def _mcp_connections(settings: Settings) -> dict[str, dict[str, Any]]:
    connections: dict[str, dict[str, Any]] = {}

    if settings.tavily_api_key is not None:
        headers = {"Authorization": f"Bearer {settings.tavily_api_key}"}
        if settings.tavily_default_parameters:
            headers["DEFAULT_PARAMETERS"] = json.dumps(
                settings.tavily_default_parameters
            )
        connections["tavily"] = {
            "transport": "streamable_http",
            "url": settings.tavily_mcp_url,
            "headers": headers,
        }

    if settings.linkedin_mcp_enabled:
        connections["linkedin"] = {
            "transport": "stdio",
            "command": settings.linkedin_mcp_command,
            "args": settings.linkedin_mcp_args,
            "env": settings.linkedin_mcp_env,
        }

    if settings.xiaohongshu_mcp_enabled:
        connections["xiaohongshu"] = {
            "transport": "http",
            "url": settings.xiaohongshu_mcp_url,
        }

    for name, connection in settings.mcp_servers_json.items():
        if isinstance(connection, dict):
            connections[name] = connection
        else:
            LOGGER.warning(
                "Skipping MCP server %s because its config is not an object.", name
            )

    dynamic_mcp_path = settings.agent_workspace / "mcp_servers.json"
    if dynamic_mcp_path.is_file():
        try:
            dynamic_config = json.loads(dynamic_mcp_path.read_text(encoding="utf-8"))
            mcp_servers = dynamic_config.get("mcpServers", dynamic_config)
            if isinstance(mcp_servers, dict):
                for name, connection in mcp_servers.items():
                    if isinstance(connection, dict):
                        connections[name] = connection
                    else:
                        LOGGER.warning("Skipping dynamic MCP server %s because its config is not an object.", name)
            else:
                LOGGER.warning("Dynamic MCP config in %s is not an object.", dynamic_mcp_path)
        except Exception as exc:
            LOGGER.warning("Failed to parse dynamic MCP config from %s: %s", dynamic_mcp_path, exc)

    return connections
