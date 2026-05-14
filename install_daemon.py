"""
JARVIS Windows Daemon Installer
Registers a Task Scheduler entry to launch JARVIS on login with auto-restart.
Run as Administrator.
"""
import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
BATCH_FILE = PROJECT_ROOT / "start_jarvis.bat"
TASK_NAME = "JARVISMarkXL"

def create_task():
    """Create Windows Task Scheduler entry."""

    # Build the schtasks command
    cmd = [
        "schtasks",
        "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{BATCH_FILE}"',
        "/SC", "ONLOGON",          # Run on user login
        "/RL", "HIGHEST",          # Run with highest privileges
        "/F",                      # Force overwrite if exists
    ]

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Batch file: {BATCH_FILE}")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Task created successfully!")
            print(result.stdout)
        else:
            print("❌ Failed to create task")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("❌ schtasks.exe not found. Run as Administrator.")
        return False

    # Add restart on failure (trigger on app crash)
    restart_cmd = [
        "schtasks",
        "/Change",
        "/TN", TASK_NAME,
        "/TR", f'"{BATCH_FILE}"',
    ]

    print("\n📝 To enable auto-restart on failure:")
    print("   1. Open Task Scheduler (taskschd.msc)")
    print("   2. Find 'JARVISMarkXL' task")
    print("   3. In Settings: Enable 'If task fails, restart every 1 minute'")
    print()

    return True


def delete_task():
    """Remove the scheduled task."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    try:
        subprocess.run(cmd, capture_output=True)
        print(f"✅ Task '{TASK_NAME}' deleted")
    except Exception as e:
        print(f"Error deleting task: {e}")


def check_task():
    """Check if task exists."""
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' exists")
            print(result.stdout)
            return True
        else:
            print(f"❌ Task '{TASK_NAME}' not found")
            return False
    except Exception as e:
        print(f"Error checking task: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "delete":
            delete_task()
        elif arg == "check":
            check_task()
        else:
            print("Usage: python install_daemon.py [create|delete|check]")
    else:
        create_task()
        print("\n🎯 To start JARVIS now without waiting for next login:")
        print(f"   Start-Process cmd -ArgumentList '/c \"{BATCH_FILE}\"' -Verb RunAs")