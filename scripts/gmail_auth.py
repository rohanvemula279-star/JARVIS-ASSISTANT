import os
import json
from pathlib import Path
from google_auth_oauthlib.flow import Flow


def get_base_dir():
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CREDENTIALS_PATH = BASE_DIR / "config" / "gmail_credentials.json"
TOKEN_PATH = BASE_DIR / "memory" / "gmail_token.json"


def run_oauth_flow():
    """Run OAuth flow to get Gmail access token."""

    if not CREDENTIALS_PATH.exists():
        print("ERROR: gmail_credentials.json not found!")
        return

    creds_data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))

    # Create flow with proper configuration
    client_config = {
        "web": {
            "client_id": creds_data["client_id"],
            "client_secret": creds_data["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"],
        }
    }

    flow = Flow.from_client_config(client_config, scopes=creds_data["scopes"])

    # Use urn:ietf:wg:oauth:2.0:oob for desktop apps (no localhost needed)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    print("Starting OAuth flow...")
    print("A URL will be shown below. Please open it in a browser,")
    print("login, and copy the verification code.")
    print()

    auth_url, _ = flow.authorization_url(prompt="consent")
    print(f"Please go to this URL:\n{auth_url}\n")

    verification_code = input("Enter the verification code here: ").strip()

    flow.fetch_token(code=verification_code)
    creds = flow.credentials

    # Save token
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n✅ SUCCESS! Token saved to {TOKEN_PATH}")
    print("Gmail integration is now ready!")


if __name__ == "__main__":
    run_oauth_flow()
