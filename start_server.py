"""Start the FastAPI server as a background process that survives closing the terminal.

Usage:
    venv/Scripts/python.exe start_server.py
    python start_server.py

Logs go to server.log. Stop with: python stop_server.py
"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(SCRIPT_DIR, "venv", "Scripts", "python.exe")
PID_FILE = os.path.join(SCRIPT_DIR, "server.pid")
LOG_FILE = os.path.join(SCRIPT_DIR, "server.log")

# Windows flags: detach from parent process and console
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def _already_running() -> bool:
    if not os.path.exists(PID_FILE):
        return False
    with open(PID_FILE) as f:
        pid = f.read().strip()
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True, text=True,
    )
    return pid in result.stdout


if _already_running():
    with open(PID_FILE) as f:
        pid = f.read().strip()
    print(f"Server is already running (PID {pid}).")
    print("Stop it first with:  python stop_server.py")
    sys.exit(0)

with open(LOG_FILE, "w") as log:
    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "main:app", "--port", "8000"],
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=SCRIPT_DIR,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    )

with open(PID_FILE, "w") as f:
    f.write(str(proc.pid))

print(f"Server started (PID {proc.pid})")
print(f"Dashboard: http://localhost:8000/")
print(f"Logs:      {LOG_FILE}")
print(f"Stop:      python stop_server.py")
