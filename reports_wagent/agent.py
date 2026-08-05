from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_core.tools import BaseTool
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from reports_wagent.config import Settings

AGENT_REQUEST_TIMEOUT_SECONDS = 600

SYSTEM_PROMPT = """You are a careful coding agent working through Telegram.

You may inspect and edit files inside the configured workspace using your filesystem
tools. Paths are virtual and rooted at the workspace. You also have shell access
whose current working directory is the configured workspace. Use shell commands for
running Python, tests, and package management when needed. Prefer uv commands for
Python project setup and dependency installation.

When Tavily MCP tools are available, use them for live web search, URL extraction,
crawling, and web research. Summarize web findings with source URLs.

When the user explicitly asks you to modify this Telegram agent's own source code,
the host project is available at the REPORTS_WAGENT_ROOT environment variable. Make
focused changes there, run relevant tests, and call restart_agent only after the
work is complete. Never modify .env or credentials unless explicitly requested.

Make focused changes, explain what you changed, and ask before making broad,
destructive, or system-level changes. Stay inside the configured workspace unless
the user explicitly asks otherwise. Never request, reveal, or attempt to access
credentials or secret files.
"""

SHELL_ENV_ALLOWLIST = {
    "CODEX_CLI_PATH",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "REPORTS_WAGENT_ROOT",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PSMODULEPATH",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERDOMAIN",
    "USERNAME",
    "USERPROFILE",
    "WINDIR",
}


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return str(content).strip()

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


class AgentService:
    def __init__(
        self,
        settings: Settings,
        checkpointer: AsyncSqliteSaver,
        tools: Sequence[BaseTool] = (),
    ) -> None:
        self._checkpointer = checkpointer
        self._locks: dict[str, asyncio.Lock] = {}
        self._active_tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}
        model = ChatDeepSeek(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            temperature=0,
            max_retries=2,
            timeout=120,
        )
        backend = LocalShellBackend(
            root_dir=settings.agent_workspace,
            virtual_mode=True,
            timeout=300,
            max_output_bytes=80_000,
            env=_sanitized_shell_env(),
            inherit_env=False,
        )
        self._agent = create_deep_agent(
            model=model,
            tools=tools,
            skills=["/skills"],
            system_prompt=SYSTEM_PROMPT,
            backend=backend,
            checkpointer=self._checkpointer,
        )

    async def ask(self, thread_id: str, prompt: str) -> str:
        async with self._lock_for(thread_id):
            task = asyncio.create_task(
                self._agent.ainvoke(
                    {"messages": [{"role": "user", "content": prompt}]},
                    config={
                        "configurable": {"thread_id": thread_id},
                        "recursion_limit": 50,
                    },
                )
            )
            self._active_tasks[thread_id] = task
            try:
                result = await asyncio.wait_for(
                    task, timeout=AGENT_REQUEST_TIMEOUT_SECONDS
                )
            finally:
                if self._active_tasks.get(thread_id) is task:
                    del self._active_tasks[thread_id]

        messages = result.get("messages", [])
        if not messages:
            return "The agent finished without returning a text response."
        return _message_text(messages[-1]) or (
            "The agent finished without returning a text response."
        )

    async def reset(self, thread_id: str) -> None:
        async with self._lock_for(thread_id):
            await self._checkpointer.adelete_thread(thread_id)

    def cancel(self, thread_id: str) -> bool:
        task = self._active_tasks.get(thread_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def _lock_for(self, thread_id: str) -> asyncio.Lock:
        return self._locks.setdefault(thread_id, asyncio.Lock())


def _sanitized_shell_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in SHELL_ENV_ALLOWLIST
    }
