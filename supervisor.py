from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from reports_wagent.restart_management import RESTART_EXIT_CODE


def main() -> None:
    project_root = Path(__file__).resolve().parent
    environment = os.environ.copy()
    environment["REPORTS_WAGENT_SUPERVISED"] = "1"
    environment["REPORTS_WAGENT_ROOT"] = str(project_root)

    while True:
        result = subprocess.run(
            [sys.executable, "-u", "main.py"],
            cwd=project_root,
            env=environment,
            check=False,
        )
        if result.returncode != RESTART_EXIT_CODE:
            raise SystemExit(result.returncode)
        time.sleep(1)


if __name__ == "__main__":
    main()
