"""Start the local API and Vite UI for `make demo`."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _wait_for_service(process: subprocess.Popen, name: str, port: int, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(f"{name} exited before it was ready (exit code {return_code}).")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"{name} did not start listening on 127.0.0.1:{port} within {timeout:g}s.")


def main() -> None:
    ui_dir = ROOT / "web"
    if not (ui_dir / "node_modules").exists():
        raise SystemExit("Web dependencies are missing; run `make setup` first.")
    if not shutil.which("pnpm"):
        raise SystemExit("pnpm is not on PATH; run `scripts\\setup.ps1` to install web dependencies.")

    api: subprocess.Popen | None = None
    web: subprocess.Popen | None = None
    try:
        api = subprocess.Popen([sys.executable, "-m", "api.server"], cwd=ROOT)
        if os.name == "nt":
            # Run from web/ so cmd.exe never has to parse the workspace path (which may contain spaces).
            web = subprocess.Popen(
                ["cmd.exe", "/d", "/s", "/c", "pnpm dev --host 127.0.0.1"], cwd=ui_dir
            )
        else:
            web = subprocess.Popen(["pnpm", "dev", "--host", "127.0.0.1"], cwd=ui_dir)

        _wait_for_service(api, "FastAPI", 8000, timeout=20)
        _wait_for_service(web, "Vite", 5173, timeout=60)
        url = "http://127.0.0.1:5173/twin"
        print(f"FilterTwin is running at {url} (API on http://127.0.0.1:8000)", flush=True)
        webbrowser.open(url)
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    except RuntimeError as error:
        raise SystemExit(f"FilterTwin failed to start: {error}") from error
    finally:
        for process in (web, api):
            if process is not None and process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
