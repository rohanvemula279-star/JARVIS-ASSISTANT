import asyncio
import os
from pathlib import Path

# Load .env manually
env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

API_KEY = os.getenv("GEMINI_API_KEY", "")
print(f"API key found: {'yes' if API_KEY else 'NO - this is your problem'}")
print(f"Key prefix: {API_KEY[:8]}..." if API_KEY else "")

async def test():
    try:
        from google import genai
        client = genai.Client(
            api_key=API_KEY,
            http_options={"api_version": "v1alpha"}
        )
        print("Client created OK")
        
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
        response = await client.aio.models.generate_content(
            model=model_name,
            contents="Say the word: working"
        )
        print(f"SUCCESS: {response.text}")
        
    except ImportError as e:
        print(f"IMPORT ERROR: {e}")
        print("Fix: pip install google-genai")
        
    except Exception as e:
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
