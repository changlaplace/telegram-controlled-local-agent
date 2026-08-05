from __future__ import annotations

import os
import threading

from langchain_core.tools import BaseTool, tool

RESTART_EXIT_CODE = 75


class RestartManager:
    def __init__(self) -> None:
        self.supervised = os.getenv("REPORTS_WAGENT_SUPERVISED") == "1"
        self._requested = False
        self._lock = threading.Lock()
        self.tool = self._build_tool()

    def _build_tool(self) -> BaseTool:
        @tool
        def restart_agent(reason: str = "Requested by the user") -> str:
            """Restart this Telegram agent after the current reply is delivered.

            Use this only after finishing and testing requested changes. The restart
            loads updated source code, environment settings, skills, and MCP config.
            """
            self.request()
            if self.supervised:
                return f"Agent restart requested: {reason}."
            return (
                "Restart requested, but automatic restart requires launching with "
                "start_agent.bat or restart_agent.bat."
            )

        return restart_agent

    def request(self) -> None:
        with self._lock:
            self._requested = True

    def consume(self) -> bool:
        with self._lock:
            requested = self._requested
            self._requested = False
            return requested
