"""
run.py – Launch both the FastAPI backend and Streamlit frontend in one command.

Usage:
    python run.py

This starts:
  - FastAPI on http://127.0.0.1:8000  (API + docs at /docs)
  - Streamlit on http://127.0.0.1:8501
"""
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    print("=" * 60)
    print("  AyuSynk Sales Pipeline")
    print("=" * 60)
    print()
    print("  Starting API backend at http://127.0.0.1:8000")
    print("  Starting Streamlit UI at http://127.0.0.1:8501")
    print()
    print("  API Docs:  http://127.0.0.1:8000/docs")
    print()
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 60)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    api_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload",
        ],
        cwd=str(ROOT),
        env=env,
    )

    # Give the API a moment to start
    time.sleep(2)

    ui_proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(ROOT / "app" / "streamlit" / "main.py"),
            "--server.port", "8501",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(ROOT),
        env=env,
    )

    def shutdown(sig, frame):
        print("\nShutting down…")
        api_proc.terminate()
        ui_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    api_proc.wait()
    ui_proc.wait()


if __name__ == "__main__":
    main()
