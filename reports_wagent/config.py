from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

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

        return cls(
            telegram_bot_token=telegram_token,
            deepseek_api_key=deepseek_key,
            allowed_user_ids=_parse_user_ids(
                os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            agent_workspace=workspace,
            agent_memory_db=memory_db,
        )
