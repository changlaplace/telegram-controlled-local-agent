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

    for name, connection in settings.mcp_servers_json.items():
        if isinstance(connection, dict):
            connections[name] = connection
        else:
            LOGGER.warning(
                "Skipping MCP server %s because its config is not an object.", name
            )

    return connections
