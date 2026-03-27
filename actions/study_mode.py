"""
Study Mode for JARVIS Assistant
actions/study_mode.py

Locks computer to study apps, monitors for distractions,
warns with graduated escalation.
"""

import threading
import queue
import subprocess
import time


try:
    import win32gui  # type: ignore
except ImportError:
    win32gui = None

try:
    import pyautogui  # type: ignore
except ImportError:
    pyautogui = None

from actions.screen_processor import _capture_screenshot  # type: ignore
from memory.config_manager import get_gemini_key
from google import genai  # type: ignore


class StudyModeManager:
    """Singleton study mode controller with hybrid distraction detection."""

    VISION_ANALYSIS_PROMPT = """You are a study monitor AI. Analyze this screenshot.  # noqa: E501

TASK: Is the student STUDYING or DISTRACTED?

STUDYING: documents, educational sites, coding, research, tutorials, notes,
spreadsheets, academic content, calculator, locked/desktop screen.

DISTRACTED: social media, entertainment streaming, games, non-study messaging,
shopping, gossip sites.

RULES:
1. If unclear, respond STUDYING (benefit of doubt)
2. YouTube educational = STUDYING, YouTube entertainment = DISTRACTED
3. Judge browser by ACTIVE tab only
4. Code editor or terminal = ALWAYS studying

Respond line 1: STUDYING or DISTRACTED
Respond line 2: reason (10 words max)"""

    def __init__(self):
        self.is_active = False
        self.strike_count = 0
        self.consecutive_study = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._warning_queue = queue.Queue()
        self._monitor_thread = None

        # ─── FIX 1: Blocklist, not whitelist ───
        self.blocked_processes = {
            'Discord.exe', 'Telegram.exe', 'WhatsApp.exe',
            'Slack.exe', 'Signal.exe', 'Spotify.exe',
            'vlc.exe', 'wmplayer.exe', 'iTunes.exe',
            'Steam.exe', 'steamwebhelper.exe',
            'EpicGamesLauncher.exe', 'GalaxyClient.exe',
            'Riot Client.exe', 'LeagueClient.exe',
            'Valorant.exe', 'MinecraftLauncher.exe',
            'obs64.exe', 'obs32.exe',
        }

        self.protected_processes = {
            'svchost.exe', 'csrss.exe', 'lsass.exe',
            'winlogon.exe', 'dwm.exe', 'taskhostw.exe',
            'sihost.exe', 'fontdrvhost.exe', 'dllhost.exe',
            'ctfmon.exe', 'explorer.exe', 'python.exe',
            'pythonw.exe', 'chrome.exe', 'msedge.exe',
            'firefox.exe', 'code.exe', 'Code.exe',
            'WINWORD.EXE', 'EXCEL.EXE', 'POWERPNT.EXE',
            'notepad.exe', 'Notepad.exe', 'calc.exe', 'Calculator.exe',
            'WindowsTerminal.exe', 'cmd.exe',
            'SearchHost.exe', 'RuntimeBroker.exe',
            'ShellExperienceHost.exe', 'TextInputHost.exe',
            'SecurityHealthSystray.exe', 'ApplicationFrameHost.exe',
            'StartMenuExperienceHost.exe', 'AcroRd32.exe', 'FoxitReader.exe',
            'SumatraPDF.exe', 'Notion.exe', 'Obsidian.exe',
            'Teams.exe', 'Zoom.exe',
        }

        self.distracting_keywords = [
            'instagram', 'reddit', 'twitter', 'facebook',
            'netflix', 'spotify', 'discord', 'whatsapp',
            'tiktok', 'twitch', 'snapchat', 'telegram',
            'game', 'gaming',
        ]

    # ─── Activation / Deactivation ───

    def activate(self):
        """Start study mode: close distractions, begin monitoring."""
        with self._lock:
            self.is_active = True
            self.strike_count = 0
            self.consecutive_study = 0

        self._stop_event.clear()
        self._close_distracting_apps()

        self._monitor_thread = threading.Thread(  # type: ignore
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()  # type: ignore
        print("[StudyMode] Activated")

    def deactivate(self):
        """Stop study mode and reset state."""
        self._stop_event.set()
        with self._lock:
            self.is_active = False
            self.strike_count = 0
            self.consecutive_study = 0
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)  # type: ignore
        print("[StudyMode] Deactivated")

    # ─── FIX 3: Warning Queue ───

    def _queue_warning(self, message):
        self._warning_queue.put(message)
        print(f"[StudyMode] Queued: {message[:60]}...")

    def get_pending_warning(self):
        try:
            return self._warning_queue.get_nowait()
        except queue.Empty:
            return None

    # ─── Monitor Loop ───

    def _monitor_loop(self):
        """Background loop: check every 15 seconds."""
        print("[StudyMode] Monitor started")
        while not self._stop_event.is_set():
            try:
                # TIER 1: Free check
                distraction_detected = self._check_window_title()

                if distraction_detected:
                    # TIER 2: Confirm with Vision API
                    confirmed = self._confirm_with_vision()
                    if confirmed:
                        self._handle_strike()
                    else:
                        self._handle_studying()
                else:
                    self._handle_studying()

            except Exception as e:
                print(f"[StudyMode] Monitor error: {e}")

            self._stop_event.wait(15)

        print("[StudyMode] Monitor stopped")

    # ─── Tier 1: Free Window Title Check ───

    def _get_active_window_title(self):
        if win32gui is None:
            return ""
        try:
            return win32gui.GetWindowText(
                win32gui.GetForegroundWindow()
            )
        except Exception:
            return ""

    def _check_window_title(self):
        title = self._get_active_window_title().lower()
        if not title:
            return False
        return any(kw in title for kw in self.distracting_keywords)

    # ─── FIX 4: Specific Vision Prompt ───

    def _confirm_with_vision(self):
        try:
            img_bytes = _capture_screenshot()

            client = genai.Client(
                api_key=get_gemini_key(),
                http_options={"api_version": "v1beta"}
            )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    genai.types.Part.from_bytes(
                        data=img_bytes,
                        mime_type='image/jpeg'),
                    self.VISION_ANALYSIS_PROMPT])

            result = response.text.strip().split('\n')[0].upper()
            print(f"[StudyMode] Vision: {response.text.strip()}")
            return "DISTRACTED" in result

        except Exception as e:
            print(f"[StudyMode] Vision error: {e}")
            return False  # benefit of doubt

    # ─── Strike System with Decay ───

    def _handle_strike(self):
        with self._lock:
            self.strike_count += 1
            self.consecutive_study = 0
            current = self.strike_count

        print(f"[StudyMode] Strike {current}")

        if current == 1:
            self._queue_warning(
                "Sir, I notice you've drifted from your studies. "
                "Kindly return to your work."
            )
        elif current == 2:
            self._queue_warning(
                "Sir, this is the second warning. Study mode is active. "
                "Please focus, or I will take action."
            )
        elif current == 3:
            killed = self._close_distracting_apps()
            apps = "distracting applications" if not killed else ", ".join(
                killed)
            self._queue_warning(
                f"Sir, I've closed {apps}. "
                f"Your study applications remain open. Please focus."
            )
        elif current >= 4:
            self._queue_warning(
                "Sir, this is my final warning. I am initiating system "
                "shutdown in 2 minutes. Say cancel shutdown to abort."
            )
            subprocess.run(['shutdown', '/s', '/t', '120'])

    def _handle_studying(self):
        with self._lock:
            self.consecutive_study += 1
            if self.consecutive_study >= 2 and self.strike_count > 0:
                self.strike_count -= 1
                self.consecutive_study = 0
                print(f"[StudyMode] Focus! Strikes → {self.strike_count}")

    # ─── FIX 2: Smart App Closing ───

    def _handle_browser_distraction(self):
        if pyautogui is None:
            return False

        title = self._get_active_window_title().lower()
        browsers = ['chrome', 'edge', 'firefox', 'brave', 'opera']

        if not any(b in title for b in browsers):
            return False

        if any(kw in title for kw in self.distracting_keywords):
            print(f"[StudyMode] Closing tab: {title[:50]}")  # type: ignore
            pyautogui.hotkey('ctrl', 'w')
            time.sleep(0.5)
            return True

        return False

    def _close_distracting_apps(self):
        killed = []

        # Close browser tab (not whole browser)
        if self._handle_browser_distraction():
            killed.append("browser tab")

        # Kill blocked processes
        try:
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    parts = line.split('","')
                    if len(parts) >= 1:
                        name = parts[0].strip('"')
                    else:
                        name = line.split('"')[1]
                except IndexError:
                    continue

                if name in self.protected_processes:
                    continue
                if name in self.blocked_processes:
                    subprocess.run(
                        ['taskkill', '/f', '/im', name],
                        capture_output=True
                    )
                    killed.append(name)  # type: ignore
                    print(f"[StudyMode] Killed: {name}")
        except Exception as e:
            print(f"[StudyMode] Process kill error: {e}")

        return killed

    # ─── Shutdown Cancel ───

    def cancel_shutdown(self):
        subprocess.run(['shutdown', '/a'])
        self._queue_warning(
            "Shutdown cancelled, sir. Please return to your studies.")
        print("[StudyMode] Shutdown cancelled")


# ─── FIX 5: Entry Point Matching Tool Pattern ───

_manager = None


def get_study_manager():
    global _manager
    if _manager is None:
        _manager = StudyModeManager()
    return _manager


def study_mode(parameters, player=None):
    """Tool entry point — matches existing tool signature."""
    manager = get_study_manager()
    action = parameters.get("action", "").lower()

    if action == "activate":
        if manager.is_active:
            return "Study mode is already active, sir."
        manager.activate()
        return (
            "Study mode activated, sir. I'll keep you focused. "
            "Only study-relevant applications are permitted."
        )

    elif action == "deactivate":
        if not manager.is_active:
            return "Study mode is not currently active, sir."
        manager.deactivate()
        return "Study mode deactivated, sir. Well done on your session."

    elif action == "status":
        if manager.is_active:
            with manager._lock:
                s = manager.strike_count
            return f"Study mode is active, sir. Current strike count: {s} out of 4."  # noqa: E501
        return "Study mode is not currently active, sir."

    elif action == "cancel_shutdown":
        manager.cancel_shutdown()
        return "Shutdown cancelled, sir. But please focus on your studies."

    return f"Unknown study mode action: {action}"
