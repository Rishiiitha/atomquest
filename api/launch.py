"""Start the local API and Vite UI for `make demo`."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ui_dir = ROOT / "web"
    if not (ui_dir / "node_modules").exists():
        raise SystemExit("Web dependencies are missing; run `make setup` first.")
    api = subprocess.Popen([sys.executable, "-m", "api.server"], cwd=ROOT)
    if os.name == "nt":
        web = subprocess.Popen(
            [
                "cmd.exe",
                "/d",
                "/s",
                "/c",
                "pnpm",
                "--dir",
                str(ui_dir),
                "dev",
                "--host",
                "127.0.0.1",
            ],
            cwd=ROOT,
        )
    else:
        web = subprocess.Popen(
            ["pnpm", "--dir", str(ui_dir), "dev", "--host", "127.0.0.1"], cwd=ROOT
        )
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5173/twin")
    print("FilterTwin is running at http://127.0.0.1:5173/twin (API on http://127.0.0.1:8000)")
    try:
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, api):
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
