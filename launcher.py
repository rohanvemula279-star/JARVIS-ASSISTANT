import subprocess
import sys
import time
import threading
import os

def run_api_server():
    print("[Launcher] Starting API Server...")
    # Using sys.executable to ensure we use the same environment
    subprocess.run([sys.executable, "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"])

def run_desktop_ui():
    print("[Launcher] Starting Desktop UI...")
    subprocess.run([sys.executable, "main.py"])

if __name__ == "__main__":
    print("--- JARVIS Master Launcher ---")
    
    # Start API server in a separate thread/process
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Give the API a moment to start
    time.sleep(2)
    
    # Start Desktop UI in the main thread
    try:
        run_desktop_ui()
    except KeyboardInterrupt:
        print("[Launcher] Shutting down...")
    except Exception as e:
        print(f"[Launcher] Desktop UI error: {e}")
