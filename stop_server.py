"""Stop the background server started by start_server.py.

Usage:
    venv/Scripts/python.exe stop_server.py
    python stop_server.py
"""
import os
import subprocess
import sys

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.pid")

if not os.path.exists(PID_FILE):
    print("No server.pid found — server may not be running.")
    sys.exit(0)

with open(PID_FILE) as f:
    pid = f.read().strip()

result = subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, text=True)

os.remove(PID_FILE)

if result.returncode == 0:
    print(f"Server (PID {pid}) stopped.")
else:
    print(f"Process {pid} was not running (may have already stopped).")
