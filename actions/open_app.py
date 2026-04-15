# actions/open_app.py
# MARK XXV — Cross-Platform App Launcher (v2 — Smart Web Fallback)

import os
import time
import subprocess
import platform
import shutil
import webbrowser

try:
    import psutil  # type: ignore

    _PSUTIL = True
except ImportError:
    _PSUTIL = False


# ═══════════════════════════════════════════════════════════════════════
#  1. DESKTOP APP ALIASES  (known installable apps per OS)
# ═══════════════════════════════════════════════════════════════════════
_APP_ALIASES = {
    "whatsapp": {"Windows": "WhatsApp", "Darwin": "WhatsApp", "Linux": "whatsapp"},
    "chrome": {
        "Windows": "chrome",
        "Darwin": "Google Chrome",
        "Linux": "google-chrome",
    },
    "google chrome": {
        "Windows": "chrome",
        "Darwin": "Google Chrome",
        "Linux": "google-chrome",
    },
    "firefox": {"Windows": "firefox", "Darwin": "Firefox", "Linux": "firefox"},
    "spotify": {"Windows": "Spotify", "Darwin": "Spotify", "Linux": "spotify"},
    "vscode": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "visual studio code": {
        "Windows": "code",
        "Darwin": "Visual Studio Code",
        "Linux": "code",
    },
    "discord": {"Windows": "Discord", "Darwin": "Discord", "Linux": "discord"},
    "telegram": {"Windows": "Telegram", "Darwin": "Telegram", "Linux": "telegram"},
    "notepad": {"Windows": "notepad.exe", "Darwin": "TextEdit", "Linux": "gedit"},
    "calculator": {
        "Windows": "calc.exe",
        "Darwin": "Calculator",
        "Linux": "gnome-calculator",
    },
    "terminal": {"Windows": "cmd.exe", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    "cmd": {"Windows": "cmd.exe", "Darwin": "Terminal", "Linux": "bash"},
    "explorer": {"Windows": "explorer.exe", "Darwin": "Finder", "Linux": "nautilus"},
    "file explorer": {
        "Windows": "explorer.exe",
        "Darwin": "Finder",
        "Linux": "nautilus",
    },
    "paint": {"Windows": "mspaint.exe", "Darwin": "Preview", "Linux": "gimp"},
    "word": {
        "Windows": "winword",
        "Darwin": "Microsoft Word",
        "Linux": "libreoffice --writer",
    },
    "excel": {
        "Windows": "excel",
        "Darwin": "Microsoft Excel",
        "Linux": "libreoffice --calc",
    },
    "powerpoint": {
        "Windows": "powerpnt",
        "Darwin": "Microsoft PowerPoint",
        "Linux": "libreoffice --impress",
    },
    "vlc": {"Windows": "vlc", "Darwin": "VLC", "Linux": "vlc"},
    "zoom": {"Windows": "Zoom", "Darwin": "zoom.us", "Linux": "zoom"},
    "slack": {"Windows": "Slack", "Darwin": "Slack", "Linux": "slack"},
    "steam": {"Windows": "steam", "Darwin": "Steam", "Linux": "steam"},
    "task manager": {
        "Windows": "taskmgr.exe",
        "Darwin": "Activity Monitor",
        "Linux": "gnome-system-monitor",
    },
    "settings": {
        "Windows": "ms-settings:",
        "Darwin": "System Preferences",
        "Linux": "gnome-control-center",
    },
    "powershell": {"Windows": "powershell.exe", "Darwin": "Terminal", "Linux": "bash"},
    "edge": {
        "Windows": "msedge",
        "Darwin": "Microsoft Edge",
        "Linux": "microsoft-edge",
    },
    "brave": {"Windows": "brave", "Darwin": "Brave Browser", "Linux": "brave-browser"},
    "obsidian": {"Windows": "Obsidian", "Darwin": "Obsidian", "Linux": "obsidian"},
    "notion": {"Windows": "Notion", "Darwin": "Notion", "Linux": "notion"},
    "blender": {"Windows": "blender", "Darwin": "Blender", "Linux": "blender"},
    "capcut": {"Windows": "CapCut", "Darwin": "CapCut", "Linux": "capcut"},
    "postman": {"Windows": "Postman", "Darwin": "Postman", "Linux": "postman"},
    "figma": {"Windows": "Figma", "Darwin": "Figma", "Linux": "figma"},
}


# ═══════════════════════════════════════════════════════════════════════
#  2. WEB FALLBACK URLs  (official sites for browser fallback)
# ═══════════════════════════════════════════════════════════════════════
_WEB_URLS = {
    # ── Video / Streaming ──
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "youtube studio": "https://studio.youtube.com",
    "netflix": "https://www.netflix.com",
    "amazon prime": "https://www.primevideo.com",
    "prime video": "https://www.primevideo.com",
    "disney plus": "https://www.disneyplus.com",
    "disney+": "https://www.disneyplus.com",
    "hotstar": "https://www.hotstar.com",
    "hulu": "https://www.hulu.com",
    "hbo max": "https://www.max.com",
    "crunchyroll": "https://www.crunchyroll.com",
    "twitch": "https://www.twitch.tv",
    "jio cinema": "https://www.jiocinema.com",
    "sony liv": "https://www.sonyliv.com",
    "zee5": "https://www.zee5.com",
    "voot": "https://www.voot.com",
    # ── Social Media ──
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "tiktok": "https://www.tiktok.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "pinterest": "https://www.pinterest.com",
    "snapchat": "https://www.snapchat.com",
    "tumblr": "https://www.tumblr.com",
    "threads": "https://www.threads.net",
    "quora": "https://www.quora.com",
    # ── Messaging (web versions) ──
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "discord": "https://discord.com/app",
    "slack": "https://slack.com",
    "skype": "https://web.skype.com",
    "messenger": "https://www.messenger.com",
    "signal": "https://signal.org",
    # ── Music ──
    "spotify": "https://open.spotify.com",
    "apple music": "https://music.apple.com",
    "soundcloud": "https://soundcloud.com",
    "gaana": "https://gaana.com",
    "wynk": "https://wynk.in",
    "jiosaavn": "https://www.jiosaavn.com",
    # ── Google Services ──
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com",
    "google photos": "https://photos.google.com",
    "google translate": "https://translate.google.com",
    "google meet": "https://meet.google.com",
    "google classroom": "https://classroom.google.com",
    "google calendar": "https://calendar.google.com",
    "google keep": "https://keep.google.com",
    "google earth": "https://earth.google.com",
    # ── Microsoft Services ──
    "outlook": "https://outlook.live.com",
    "onedrive": "https://onedrive.live.com",
    "teams": "https://teams.microsoft.com",
    "microsoft teams": "https://teams.microsoft.com",
    "office": "https://www.office.com",
    "bing": "https://www.bing.com",
    "copilot": "https://copilot.microsoft.com",
    # ── Developer / Productivity ──
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "chatgpt": "https://chat.openai.com",
    "openai": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "notion": "https://www.notion.so",
    "figma": "https://www.figma.com",
    "canva": "https://www.canva.com",
    "trello": "https://trello.com",
    "jira": "https://www.atlassian.com/software/jira",
    "asana": "https://app.asana.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "replit": "https://replit.com",
    "codepen": "https://codepen.io",
    "medium": "https://medium.com",
    "dev.to": "https://dev.to",
    "vercel": "https://vercel.com",
    "netlify": "https://www.netlify.com",
    "firebase": "https://console.firebase.google.com",
    "heroku": "https://www.heroku.com",
    "aws": "https://aws.amazon.com",
    # ── Shopping ──
    "amazon": "https://www.amazon.com",
    "flipkart": "https://www.flipkart.com",
    "ebay": "https://www.ebay.com",
    "myntra": "https://www.myntra.com",
    "meesho": "https://www.meesho.com",
    "ajio": "https://www.ajio.com",
    # ── Education ──
    "coursera": "https://www.coursera.org",
    "udemy": "https://www.udemy.com",
    "khan academy": "https://www.khanacademy.org",
    "w3schools": "https://www.w3schools.com",
    "geeksforgeeks": "https://www.geeksforgeeks.org",
    "leetcode": "https://leetcode.com",
    # ── Misc ──
    "zoom": "https://zoom.us/join",
    "wikipedia": "https://www.wikipedia.org",
    "weather": "https://weather.com",
    "speed test": "https://www.speedtest.net",
    "whois": "https://who.is",
    "paytm": "https://paytm.com",
}


# ═══════════════════════════════════════════════════════════════════════
#  3. HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════


def _normalize(raw: str) -> str:
    """Map user input → OS-specific binary / app name."""
    system = platform.system()
    key = raw.lower().strip()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(system, raw)
    for alias_key, os_map in _APP_ALIASES.items():
        if alias_key in key or key in alias_key:
            return os_map.get(system, raw)
    return raw


def _get_web_url(app_name: str):
    """Return the official web URL for an app, or None."""
    key = app_name.lower().strip()

    # 1) Exact match
    if key in _WEB_URLS:
        return _WEB_URLS[key]

    # 2) Fuzzy: app_name contains a key or key contains app_name
    #    → pick the LONGEST matching key (most specific)
    best_url = None
    best_len = 0
    for url_key, url in _WEB_URLS.items():
        if url_key in key or key in url_key:
            if len(url_key) > best_len:
                best_len = len(url_key)
                best_url = url
    return best_url


def _is_known_desktop_app(app_name: str) -> bool:
    """Does this app have a known desktop alias (i.e. is installable)?"""
    key = app_name.lower().strip()
    if key in _APP_ALIASES:
        return True
    for alias_key in _APP_ALIASES:
        if alias_key in key or key in alias_key:
            return True
    return False


def _binary_exists(app_name: str) -> bool:
    """Check if a binary/executable is findable on this system."""
    candidates = [
        app_name,
        app_name.lower(),
        app_name.lower().replace(" ", "-"),
        app_name.lower().replace(" ", ""),
    ]
    if platform.system() == "Windows":
        candidates += [c + ".exe" for c in candidates]
    for c in candidates:
        if shutil.which(c):
            return True
    return False


def _is_running(app_name: str) -> bool:
    """Check if app process is running (requires psutil)."""
    if not _PSUTIL:
        return False
    import psutil

    app_lower = app_name.lower().replace(" ", "").replace(".exe", "")
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                pname = proc.info["name"]
                if pname is None:
                    continue
                pname = pname.lower().replace(" ", "").replace(".exe", "")
                if app_lower in pname or pname in app_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False


def _open_in_browser(url: str) -> bool:
    """Open a URL in the system default browser."""
    try:
        webbrowser.open(url)
        time.sleep(1.0)
        return True
    except Exception as e:
        print(f"[open_app] ⚠️ Browser open failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════
#  4. OS-SPECIFIC DESKTOP LAUNCHERS
# ═══════════════════════════════════════════════════════════════════════


def _launch_windows(app_name: str) -> bool:
    """Try every Windows-native method to open a desktop app."""

    # ── Method 1: Direct binary from PATH ──
    for candidate in [
        app_name,
        app_name + ".exe",
        app_name.lower(),
        app_name.lower() + ".exe",
    ]:
        binary = shutil.which(candidate)
        if binary:
            try:
                subprocess.Popen(
                    [binary],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                    if "powershell" in candidate.lower() or "cmd" in candidate.lower()
                    else 0,
                )
                time.sleep(1.5)
                return True
            except Exception:
                pass

    # ── Method 2: os.startfile (protocols like ms-settings:, executables) ──
    try:
        os.startfile(app_name)  # type: ignore
        time.sleep(1.5)
        return True
    except Exception:
        pass

    # ── Method 3: Try shell execute for registered applications ──
    try:
        result = subprocess.run(
            ["powershell", "-Command", f'Start-Process "{app_name}"'],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            time.sleep(1.5)
            return True
    except Exception as e:
        print(f"[open_app] ⚠️ Shell execute failed: {e}")

    # ── Method 4: Start Menu search + psutil verification ──
    try:
        import pyautogui  # type: ignore

        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(3.0)

        if _PSUTIL:
            if _is_running(app_name):
                return True
            print(
                f"[open_app] ⚠️ '{app_name}' not detected in processes after Start Menu search"
            )
            return False

        return True

    except Exception as e:
        print(f"[open_app] ⚠️ Windows Start Menu failed: {e}")
        return False


def _launch_macos(app_name: str) -> bool:
    """Try macOS-native methods to open a desktop app."""

    # ── Method 1: 'open -a' ──
    for name in [app_name, f"{app_name}.app"]:
        try:
            result = subprocess.run(
                ["open", "-a", name],
                capture_output=True,
                timeout=8,
            )
            if result.returncode == 0:
                time.sleep(1.0)
                return True
        except Exception:
            pass

    # ── Method 2: Spotlight via pyautogui ──
    try:
        import pyautogui  # type: ignore

        pyautogui.hotkey("command", "space")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.5)

        if _PSUTIL:
            return _is_running(app_name)
        return True
    except Exception as e:
        print(f"[open_app] ⚠️ macOS Spotlight failed: {e}")
        return False


def _launch_linux(app_name: str) -> bool:
    """Try Linux-native methods to open a desktop app."""

    # ── Method 1: Direct binary ──
    binary = (
        shutil.which(app_name)
        or shutil.which(app_name.lower())
        or shutil.which(app_name.lower().replace(" ", "-"))
    )
    if binary:
        try:
            subprocess.Popen(
                [binary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.0)
            return True
        except Exception:
            pass

    # ── Method 2: xdg-open ──
    try:
        subprocess.run(["xdg-open", app_name], capture_output=True, timeout=5)
        return True
    except Exception:
        pass

    # ── Method 3: gtk-launch ──
    try:
        desktop_name = app_name.lower().replace(" ", "-")
        subprocess.run(
            ["gtk-launch", desktop_name],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        pass

    return False


_OS_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin": _launch_macos,
    "Linux": _launch_linux,
}


# ═══════════════════════════════════════════════════════════════════════
#  5. MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════


def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    app_name = (parameters or {}).get("app_name", "").strip()

    if not app_name:
        return "Please specify which application to open, sir."

    system = platform.system()
    launcher = _OS_LAUNCHERS.get(system)

    if launcher is None:
        return f"Unsupported operating system: {system}"

    normalized = _normalize(app_name)
    web_url = _get_web_url(app_name)
    is_desktop = _is_known_desktop_app(app_name) or _binary_exists(app_name)

    print(f"[open_app] 🚀 Request   : '{app_name}'")
    print(f"[open_app]    Normalized : '{normalized}'")
    print(f"[open_app]    Desktop?   : {is_desktop}")
    print(f"[open_app]    Web URL    : {web_url}")
    print(f"[open_app]    OS         : {system}")

    if player:
        player.write_log(f"[open_app] {app_name}")

    # ──────────────────────────────────────────────────────────────
    #  CASE A: Pure web app — no desktop alias, has a web URL
    #          → go straight to the browser (skip Start Menu)
    # ──────────────────────────────────────────────────────────────
    if not is_desktop and web_url:
        print(f"[open_app] 🌐 Web-only → {web_url}")
        if _open_in_browser(web_url):
            return f"Opening {app_name} in your browser, sir."
        return f"Failed to open {app_name} in the browser, sir."

    # ──────────────────────────────────────────────────────────────
    #  CASE B: Known desktop app → try native launch first
    # ──────────────────────────────────────────────────────────────
    if is_desktop:
        try:
            print(f"[open_app] 🔧 Attempting desktop launch: {normalized}")
            success = launcher(normalized)

            if not success:
                print(f"[open_app] ⚠️ First attempt failed, retrying with: {app_name}")
                success = launcher(app_name)

            if success:
                print(f"[open_app] ✅ Desktop launch succeeded")
                return f"Opened {app_name} successfully, sir."

        except Exception as e:
            print(f"[open_app] ❌ Desktop launch error: {e}")

        # Desktop launch FAILED → fall back to web if available
        if web_url:
            print(f"[open_app] 🌐 Desktop failed → falling back to {web_url}")
            if _open_in_browser(web_url):
                return (
                    f"{app_name} doesn't appear to be installed, sir. "
                    f"I've opened it in your browser instead."
                )

        return (
            f"I couldn't open {app_name}, sir. It may not be installed on this system."
        )

    # ──────────────────────────────────────────────────────────────
    #  CASE C: Unknown app — not in aliases, no web URL
    #          → try to find a binary, then guess a website
    # ──────────────────────────────────────────────────────────────
    print("[open_app] ❓ Unknown app — attempting generic launch")

    # Try native launch anyway (maybe user has it installed)
    try:
        if launcher(normalized):
            return f"Opened {app_name} successfully, sir."
    except Exception:
        pass

    # Last resort: guess the URL → https://www.<name>.com
    clean_name = app_name.lower().strip().replace(" ", "")
    guess_url = f"https://www.{clean_name}.com"
    print(f"[open_app] 🌐 Guessing URL → {guess_url}")
    if _open_in_browser(guess_url):
        return (
            f"I couldn't find {app_name} installed on your system, sir. "
            f"I've tried opening {guess_url} in your browser."
        )

    return (
        f"I couldn't open {app_name}, sir. "
        f"It doesn't seem to be installed, and I couldn't find an official website."
    )
