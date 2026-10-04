#!/usr/bin/env python3
"""
dev.py — start both servers, wait for the backend to be healthy, then keep
running until Ctrl-C.  Works on Windows (PowerShell / cmd), macOS, and Linux.

Usage (from the repo root):
    python scripts/dev.py

What it does:
  1. Kills any process already listening on ports 8080 and 3000.
  2. Starts the backend:  uvicorn framegen.api:app --port 8080
  3. Starts the frontend: npm run dev -- -p 3000  (from the frontend/ dir)
  4. Writes each server's stdout+stderr to logs/backend.log and logs/frontend.log
     inside the repo (gitignored).
  5. Polls GET /health until the backend responds (up to 30 s).
  6. Prints the catalog version and git commit from the health response.
  7. Keeps both processes alive until Ctrl-C, then stops them cleanly.
"""

import json
import os
import platform
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
BACKEND_PORT = 8080
FRONTEND_PORT = 3000
HEALTH_URL = f"http://localhost:{BACKEND_PORT}/health"
HEALTH_TIMEOUT_S = 30

IS_WINDOWS = platform.system() == "Windows"


# ── Port freeing ──────────────────────────────────────────────────────────────

def _pids_on_port_windows(port: int) -> list[int]:
    """Use netstat to find PIDs listening on *port* (Windows)."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return []
    pids: list[int] = []
    for line in out.splitlines():
        cols = line.split()
        # netstat columns: Proto  Local  Foreign  State  PID
        if len(cols) < 5:
            continue
        local = cols[1]
        state = cols[3] if len(cols) > 4 else ""
        pid_str = cols[-1]
        if f":{port}" in local and state in ("LISTENING", "LISTEN"):
            try:
                pids.append(int(pid_str))
            except ValueError:
                pass
    return list(set(pids))


def _pids_on_port_unix(port: int) -> list[int]:
    """Use lsof to find PIDs listening on *port* (macOS / Linux)."""
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f"tcp:{port}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return [int(p) for p in out.split() if p.strip().isdigit()]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []


def free_port(port: int) -> None:
    """Kill any process listening on *port*."""
    if IS_WINDOWS:
        pids = _pids_on_port_windows(port)
        for pid in pids:
            print(f"  Stopping PID {pid} on port {port}")
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        pids = _pids_on_port_unix(port)
        for pid in pids:
            print(f"  Stopping PID {pid} on port {port}")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if IS_WINDOWS:
        time.sleep(0.5)  # give Windows a moment to release the port


# ── Server start ──────────────────────────────────────────────────────────────

def start_backend(log_path: Path) -> subprocess.Popen:  # type: ignore[type-arg]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "framegen.api:app",
        "--port", str(BACKEND_PORT),
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=log_file,
        stderr=log_file,
    )


def start_frontend(log_path: Path) -> subprocess.Popen:  # type: ignore[type-arg]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", encoding="utf-8")
    frontend_dir = REPO_ROOT / "frontend"
    if IS_WINDOWS:
        # On Windows, npm is a .cmd file; shell=True resolves it
        cmd = f"npm run dev -- -p {FRONTEND_PORT}"
        return subprocess.Popen(
            cmd,
            cwd=str(frontend_dir),
            stdout=log_file,
            stderr=log_file,
            shell=True,
        )
    else:
        return subprocess.Popen(
            ["npm", "run", "dev", "--", "-p", str(FRONTEND_PORT)],
            cwd=str(frontend_dir),
            stdout=log_file,
            stderr=log_file,
        )


# ── Health polling ────────────────────────────────────────────────────────────

def wait_for_health(timeout: int = HEALTH_TIMEOUT_S) -> dict:  # type: ignore[type-arg]
    deadline = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError):
            sys.stdout.write(f"\r  Waiting for backend{'.' * (attempt % 4 + 1)}   ")
            sys.stdout.flush()
            time.sleep(1)
    print()
    return {}


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== frame_designer dev ===")

    print("Freeing ports…")
    free_port(BACKEND_PORT)
    free_port(FRONTEND_PORT)

    print("Starting backend  -> logs/backend.log")
    backend = start_backend(LOG_DIR / "backend.log")

    print("Starting frontend -> logs/frontend.log")
    frontend = start_frontend(LOG_DIR / "frontend.log")

    procs = [backend, frontend]

    def stop_all(signum=None, frame=None):  # type: ignore[no-untyped-def]
        print("\nStopping servers…")
        for p in procs:
            try:
                if IS_WINDOWS:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    health = wait_for_health()
    print()

    if not health:
        print("ERROR: backend did not start in time.", file=sys.stderr)
        log_tail = LOG_DIR / "backend.log"
        if log_tail.exists():
            lines = log_tail.read_text(encoding="utf-8", errors="replace").splitlines()
            print("--- last 20 lines of logs/backend.log ---", file=sys.stderr)
            for line in lines[-20:]:
                print(line, file=sys.stderr)
        stop_all()

    print(
        f"Backend ready    catalog=v{health.get('catalog_version', '?')}  "
        f"commit={health.get('git_commit', '?')}"
    )
    print(f"Frontend         http://localhost:{FRONTEND_PORT}")
    print("Press Ctrl-C to stop both servers.")

    # Keep running until a signal arrives
    try:
        while True:
            # If either process dies unexpectedly, report it
            for name, proc in [("backend", backend), ("frontend", frontend)]:
                if proc.poll() is not None:
                    msg = f"\n{name} exited with code {proc.returncode}."
                    print(msg, file=sys.stderr)
                    stop_all()
            time.sleep(2)
    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
