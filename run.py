#!/usr/bin/env python
"""Start FleetSense with one command: python run.py

Default is the offline demo: recorded DeepSeek runs, live tools, no API key and no cost.
  python run.py --live     use the real model (needs DEEPSEEK_API_KEY in .env)
  python run.py --build    rebuild the frontend first
  python run.py --port N   another port (default 8000)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist" / "index.html"
REQUIRED = ["fastapi", "uvicorn", "sse_starlette", "dotenv", "openai", "networkx"]


def ensure_python_deps() -> None:
    if all(importlib.util.find_spec(m) for m in REQUIRED):
        return
    print("Installing Python dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(BACKEND / "requirements.txt")])


def frontend_stale() -> bool:
    if not DIST.exists():
        return True
    built = DIST.stat().st_mtime
    sources = [p for d in (FRONTEND / "src", FRONTEND / "public", ROOT / "shared") for p in d.rglob("*") if p.is_file()]
    return any(p.stat().st_mtime > built for p in sources)


def build_frontend() -> None:
    npm = shutil.which("npm")
    if not npm:
        sys.exit("Node.js is needed once to build the frontend: https://nodejs.org (20+), then run this again.")
    if not (FRONTEND / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.check_call([npm, "ci"], cwd=FRONTEND)
    print("Building the frontend...")
    subprocess.check_call([npm, "run", "build"], cwd=FRONTEND)


def open_when_up(url: str) -> None:
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    ap = argparse.ArgumentParser(description="Start FleetSense")
    ap.add_argument("--live", action="store_true", help="call the real model instead of the recorded runs")
    ap.add_argument("--build", action="store_true", help="rebuild the frontend first")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    ensure_python_deps()
    if args.build or frontend_stale():
        build_frontend()

    if args.live:
        os.environ["REPLAY"] = "0"
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        if not os.getenv("DEEPSEEK_API_KEY"):
            sys.exit("--live needs DEEPSEEK_API_KEY: copy .env.example to .env and add your key.")
    else:
        os.environ["REPLAY"] = "1"
        os.environ.setdefault("REPLAY_STEP_SEC", "1.1")  # the feed builds up like a live run, in about 20 s

    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and loses 200 ms per connection.
    url = f"http://127.0.0.1:{args.port}"
    print(f"\nFleetSense · {'live model' if args.live else 'offline demo (recorded runs)'} · {url}  (Ctrl+C to stop)\n")
    if not args.no_browser:
        threading.Thread(target=open_when_up, args=(url,), daemon=True).start()

    sys.path.insert(0, str(BACKEND))
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
