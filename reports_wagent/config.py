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
    agent_status_file: Path
    openai_api_key: str | None = field(default=None, repr=False)
    transcription_provider: str = "local"
    transcription_model: str = "gpt-4o-mini-transcribe"
    transcription_language: str | None = None
    local_transcription_model: str = "base"
    local_transcription_device: str = "cpu"
    local_transcription_compute_type: str = "int8"
    local_transcription_model_dir: Path | None = None
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
        status_file = (
            Path(os.getenv("AGENT_STATUS_FILE", ".agent_runtime/status.json"))
            .expanduser()
            .resolve()
        )
        tavily_default_parameters = _parse_json_object(
            os.getenv("TAVILY_DEFAULT_PARAMETERS", "").strip(),
            "TAVILY_DEFAULT_PARAMETERS",
        )
        transcription_provider = os.getenv("TRANSCRIPTION_PROVIDER", "local").strip()
        if transcription_provider not in {"local", "openai", "off"}:
            raise ConfigurationError(
                "TRANSCRIPTION_PROVIDER must be one of: local, openai, off."
            )
        local_transcription_model_dir = (
            Path(
                os.getenv(
                    "LOCAL_TRANSCRIPTION_MODEL_DIR",
                    ".agent_runtime/whisper_models",
                )
            )
            .expanduser()
            .resolve()
        )

        return cls(
            telegram_bot_token=telegram_token,
            deepseek_api_key=deepseek_key,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            allowed_user_ids=_parse_user_ids(
                os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            agent_workspace=workspace,
            agent_memory_db=memory_db,
            agent_status_file=status_file,
            transcription_provider=transcription_provider,
            transcription_model=os.getenv(
                "TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
            ).strip(),
            transcription_language=os.getenv("TRANSCRIPTION_LANGUAGE", "").strip()
            or None,
            local_transcription_model=os.getenv(
                "LOCAL_TRANSCRIPTION_MODEL", "base"
            ).strip(),
            local_transcription_device=os.getenv(
                "LOCAL_TRANSCRIPTION_DEVICE", "cpu"
            ).strip(),
            local_transcription_compute_type=os.getenv(
                "LOCAL_TRANSCRIPTION_COMPUTE_TYPE", "int8"
            ).strip(),
            local_transcription_model_dir=local_transcription_model_dir,
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
