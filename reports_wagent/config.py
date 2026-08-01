from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when required application settings are missing or invalid."""


def _parse_user_ids(raw_value: str) -> frozenset[int]:
    values = [value for value in re.split(r"[\s,]+", raw_value.strip()) if value]
    try:
        return frozenset(int(value) for value in values)
    except ValueError as exc:
        raise ConfigurationError(
            "TELEGRAM_ALLOWED_USER_IDS must contain numeric IDs separated by commas."
        ) from exc


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str = field(repr=False)
    deepseek_api_key: str = field(repr=False)
    allowed_user_ids: frozenset[int]
    deepseek_model: str
    agent_workspace: Path
    agent_memory_db: Path
    tavily_api_key: str | None = field(default=None, repr=False)
    tavily_mcp_url: str = "https://mcp.tavily.com/mcp/"
    tavily_default_parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        missing = [
            name
            for name, value in (
                ("TELEGRAM_BOT_TOKEN", telegram_token),
                ("DEEPSEEK_API_KEY", deepseek_key),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        workspace = (
            Path(os.getenv("AGENT_WORKSPACE", "agent_workspace")).expanduser().resolve()
        )
        if not workspace.is_dir():
            raise ConfigurationError(f"AGENT_WORKSPACE is not a directory: {workspace}")
        memory_db = (
            Path(os.getenv("AGENT_MEMORY_DB", ".agent_memory/checkpoints.sqlite"))
            .expanduser()
            .resolve()
        )
        tavily_default_parameters = _parse_json_object(
            os.getenv("TAVILY_DEFAULT_PARAMETERS", "").strip(),
            "TAVILY_DEFAULT_PARAMETERS",
        )

        return cls(
            telegram_bot_token=telegram_token,
            deepseek_api_key=deepseek_key,
            allowed_user_ids=_parse_user_ids(
                os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            agent_workspace=workspace,
            agent_memory_db=memory_db,
            tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip() or None,
            tavily_mcp_url=os.getenv(
                "TAVILY_MCP_URL", "https://mcp.tavily.com/mcp/"
            ).strip(),
            tavily_default_parameters=tavily_default_parameters,
        )


def _parse_json_object(raw_value: str, name: str) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{name} must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a JSON object.")
    return value
