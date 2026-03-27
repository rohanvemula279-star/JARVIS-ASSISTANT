import json
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    return CONFIG_FILE.exists()


def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    # Update both the single key and the list
    data["gemini_api_key"] = gemini_api_key.strip()
    
    if "gemini_api_keys" not in data or not isinstance(data["gemini_api_keys"], list):
        data["gemini_api_keys"] = [data["gemini_api_key"]]
    else:
        # If the key is not in the list, add it as the primary
        if data["gemini_api_key"] not in data["gemini_api_keys"]:
            data["gemini_api_keys"].insert(0, data["gemini_api_key"])

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}


def get_gemini_key() -> str | None:
    data = load_api_keys()
    
    # Try getting from the list first (rotation/multi-key support)
    keys = data.get("gemini_api_keys", [])
    if isinstance(keys, list) and len(keys) > 0:
        # Filter out placeholders
        valid_keys = [k for k in keys if k and len(k) > 15 and "YOUR" not in k.upper()]
        if valid_keys:
            # Current simplest: return the first valid key
            # Could be expanded to random.choice or round-robin if state is kept
            return valid_keys[0]
            
    # Fallback to single key
    return data.get("gemini_api_key")


def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)
