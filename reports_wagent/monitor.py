from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from tkinter import BOTH, LEFT, Tk, X, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

from dotenv import load_dotenv

STALE_AFTER_SECONDS = 360


def _status_file() -> Path:
    load_dotenv()
    return Path(os.getenv("AGENT_STATUS_FILE", ".agent_runtime/status.json")).resolve()


def _read_status(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _age_seconds(status: dict[str, Any]) -> float | None:
    updated_at = status.get("updated_at")
    if not isinstance(updated_at, str):
        return None
    try:
        updated = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return (datetime.now(UTC) - updated.astimezone(UTC)).total_seconds()


class Monitor:
    def __init__(self) -> None:
        self.status_file = _status_file()
        if not HAS_TKINTER:
            return
        self.root = Tk()
        self.root.title("Reports Agent Monitor")
        self.root.geometry("360x170")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.frame = ttk.Frame(self.root, padding=14)
        self.frame.pack(fill=BOTH, expand=True)

        self.dot = ttk.Label(self.frame, text="●", font=("Segoe UI", 28))
        self.dot.pack(side=LEFT, padx=(0, 12))

        self.text_frame = ttk.Frame(self.frame)
        self.text_frame.pack(fill=BOTH, expand=True)

        self.title = ttk.Label(
            self.text_frame,
            text="Checking agent...",
            font=("Segoe UI", 12, "bold"),
        )
        self.title.pack(anchor="w", fill=X)

        self.detail = ttk.Label(self.text_frame, text="", wraplength=260)
        self.detail.pack(anchor="w", fill=X, pady=(6, 0))

        self.path = ttk.Label(
            self.text_frame, text=str(self.status_file), wraplength=260
        )
        self.path.pack(anchor="w", fill=X, pady=(8, 0))

    def run(self) -> None:
        if not HAS_TKINTER:
            print("Tkinter is not available. Monitor UI cannot be displayed. You can still check status from status.json manually.")
            sys.exit(0)
        self.refresh()
        self.root.mainloop()

    def refresh(self) -> None:
        status = _read_status(self.status_file)
        if status is None:
            self._set_status("red", "Agent not running", "No heartbeat file found.")
        else:
            age = _age_seconds(status)
            state = status.get("state", "unknown")
            pid = status.get("pid", "unknown")
            if state == "running" and age is not None and age <= STALE_AFTER_SECONDS:
                self._set_status(
                    "green",
                    "Agent running",
                    f"PID {pid}. Last heartbeat {age:.0f}s ago.",
                )
            elif state == "stopped":
                self._set_status("red", "Agent stopped", f"Last PID was {pid}.")
            else:
                age_text = "unknown" if age is None else f"{age:.0f}s"
                self._set_status(
                    "orange",
                    "Agent status stale",
                    f"PID {pid}. Last heartbeat {age_text} ago.",
                )
        self.root.after(2000, self.refresh)

    def _set_status(self, color: str, title: str, detail: str) -> None:
        self.dot.configure(foreground=color)
        self.title.configure(text=title)
        self.detail.configure(text=detail)


def main() -> None:
    Monitor().run()
