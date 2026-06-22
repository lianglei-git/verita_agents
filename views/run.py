#!/usr/bin/env python3
"""Single-command launcher for the views agent console."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

VIEWS_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = VIEWS_ROOT / "frontend"
BACKEND_APP = VIEWS_ROOT / "backend" / "app.py"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_API_PORT = 5000
DEFAULT_VITE_PORT = 5173


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VIEWS_ROOT)
    return env


def _wait_for_api(host: str, port: int, timeout: float = 15.0) -> bool:
    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    return False


def _terminate(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_dev(host: str, api_port: int, vite_port: int) -> int:
    if not (FRONTEND_DIR / "package.json").exists():
        print("frontend/package.json not found. Run npm install in views/frontend first.")
        return 1

    api_proc = subprocess.Popen(
        [sys.executable, str(BACKEND_APP), "--host", host, "--port", str(api_port)],
        cwd=VIEWS_ROOT,
        env=_env(),
    )

    if not _wait_for_api(host, api_port):
        print(f"API failed to start on http://{host}:{api_port}")
        _terminate(api_proc)
        return 1

    vite_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", host, "--port", str(vite_port)],
        cwd=FRONTEND_DIR,
        env=_env(),
    )

    print(f"\n  Dev console: http://{host}:{vite_port}")
    print(f"  API proxy:   /api -> http://{host}:{api_port}\n")

    def shutdown(_signum=None, _frame=None) -> None:
        _terminate(vite_proc)
        _terminate(api_proc)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            if api_proc.poll() is not None:
                print("API process exited unexpectedly.")
                _terminate(vite_proc)
                return api_proc.returncode or 1
            if vite_proc.poll() is not None:
                print("Vite process exited.")
                _terminate(api_proc)
                return vite_proc.returncode or 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()
        return 0


def run_prod(host: str, port: int, build: bool) -> int:
    dist_dir = FRONTEND_DIR / "dist"
    if build or not dist_dir.exists():
        print("Building frontend...")
        result = subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=False)
        if result.returncode != 0:
            return result.returncode

    if not dist_dir.exists():
        print("frontend/dist not found. Build failed or was skipped.")
        return 1

    proc = subprocess.Popen(
        [
            sys.executable,
            str(BACKEND_APP),
            "--host",
            host,
            "--port",
            str(port),
            "--serve-static",
        ],
        cwd=VIEWS_ROOT,
        env=_env(),
    )

    print(f"\n  Production console: http://{host}:{port}\n")

    try:
        return proc.wait()
    except KeyboardInterrupt:
        _terminate(proc)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Views agent console launcher")
    parser.add_argument("--prod", action="store_true", help="Production: build + Flask serves dist")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--vite-port", type=int, default=DEFAULT_VITE_PORT)
    parser.add_argument("--port", type=int, default=DEFAULT_API_PORT, help="Port in production mode")
    parser.add_argument("--no-build", action="store_true", help="Skip npm build in production mode")
    args = parser.parse_args()

    if args.prod:
        return run_prod(args.host, args.port, build=not args.no_build)
    return run_dev(args.host, args.api_port, args.vite_port)


if __name__ == "__main__":
    raise SystemExit(main())
