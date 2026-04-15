import os
import json
import base64
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal
from dataclasses import dataclass, asdict
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
GMAIL_TOKEN_PATH = BASE_DIR / "memory" / "gmail_token.json"
GMAIL_CREDENTIALS_PATH = BASE_DIR / "config" / "gmail_credentials.json"


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str
    recipient: str
    snippet: str
    body: str
    date: str
    labels: list[str]
    is_unread: bool
    is_starred: bool


@dataclass
class EmailDraft:
    to: str
    subject: str
    body: str
    cc: Optional[str] = None


class GmailClient:
    """Gmail API client for email summarization and drafting."""

    def __init__(self):
        self._service = None
        self._lock = threading.Lock()
        self._initialized = False

    def _load_credentials(self) -> Optional[dict]:
        """Load OAuth credentials."""
        if GMAIL_CREDENTIALS_PATH.exists():
            return json.loads(GMAIL_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return None

    def _load_token(self) -> Optional[dict]:
        """Load OAuth token."""
        if GMAIL_TOKEN_PATH.exists():
            return json.loads(GMAIL_TOKEN_PATH.read_text(encoding="utf-8"))
        return None

    def _save_token(self, token: dict):
        """Save OAuth token."""
        GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GMAIL_TOKEN_PATH.write_text(json.dumps(token, indent=2), encoding="utf-8")

    def is_configured(self) -> bool:
        """Check if Gmail API is configured."""
        return self._load_credentials() is not None

    def _get_service(self):
        """Initialize Gmail service."""
        if self._service:
            return self._service

        creds = self._load_credentials()
        if not creds:
            return None

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            token_data = self._load_token()
            if token_data:
                creds = Credentials.from_authorized_user_info(
                    token_data, creds["scopes"]
                )

            self._service = build(
                "gmail", "v1", credentials=creds, cache_discovery=False
            )
            return self._service
        except Exception as e:
            print(f"[Gmail] ⚠️ Service init failed: {e}")
            return None

    def _parse_email(self, msg: dict) -> EmailMessage:
        """Parse email message response."""
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

        body = ""
        if "parts" in msg["payload"]:
            for part in msg["payload"]["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="replace"
                        )
                    break
                elif part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="replace"
                        )
                        break

        labels = msg.get("labelIds", [])

        return EmailMessage(
            id=msg["id"],
            thread_id=msg.get("threadId", ""),
            subject=headers.get("Subject", "(No subject)"),
            sender=headers.get("From", ""),
            recipient=headers.get("To", ""),
            snippet=msg.get("snippet", ""),
            body=body,
            date=headers.get("Date", ""),
            labels=labels,
            is_unread="UNREAD" in labels,
            is_starred="STARRED" in labels,
        )

    def get_messages(
        self, max_results: int = 10, query: str = "", label_ids: list[str] = None
    ) -> list[EmailMessage]:
        """Get email messages."""
        service = self._get_service()
        if not service:
            return []

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=query, labelIds=label_ids)
                .execute()
            )

            messages = []
            for msg in results.get("messages", []):
                msg_detail = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="full")
                    .execute()
                )
                messages.append(self._parse_email(msg_detail))

            return messages
        except Exception as e:
            print(f"[Gmail] ⚠️ Get messages failed: {e}")
            return []

    def get_unread_emails(self, max_results: int = 10) -> list[EmailMessage]:
        """Get unread emails."""
        return self.get_messages(max_results=max_results, label_ids=["UNREAD"])

    def get_recent_emails(self, max_results: int = 10) -> list[EmailMessage]:
        """Get recent emails."""
        return self.get_messages(max_results=max_results)

    def get_sender_emails(
        self, sender: str, max_results: int = 10
    ) -> list[EmailMessage]:
        """Get emails from a specific sender."""
        return self.get_messages(max_results=max_results, query=f"from:{sender}")

    def summarize_email(self, email: EmailMessage) -> str:
        """Summarize an email using LLM."""
        from memory.config_manager import get_gemini_key
        import google.generativeai as genai

        genai.configure(api_key=get_gemini_key())
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        prompt = f"""Summarize this email in 1-2 sentences. Include:
- Key information or request
- Sender name if identifiable
- Action needed (reply, follow-up, etc.)

Email:
Subject: {email.subject}
From: {email.sender}
Body: {email.body[:1500]}"""

        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            return email.snippet

    def summarize_thread(self, thread_id: str) -> str:
        """Summarize an email thread."""
        service = self._get_service()
        if not service:
            return "Gmail not configured"

        try:
            thread = (
                service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )

            messages = []
            for msg in thread.get("messages", []):
                headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
                body = ""
                if "parts" in msg["payload"]:
                    for part in msg["payload"]["parts"]:
                        if part.get("mimeType") == "text/plain":
                            data = part.get("body", {}).get("data", "")
                            if data:
                                body = base64.urlsafe_b64decode(data).decode(
                                    "utf-8", errors="replace"
                                )
                            break
                messages.append(f"From: {headers.get('From', '')}\n{body[:500]}")

            from memory.config_manager import get_gemini_key
            import google.generativeai as genai

            genai.configure(api_key=get_gemini_key())
            model = genai.GenerativeModel("gemini-2.5-flash-lite")

            prompt = f"""Summarize this email thread in 2-3 sentences. What is the main topic and current status?

{"=" * 50}
{chr(10).join(messages)}"""

            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[Gmail] ⚠️ Summarize thread failed: {e}")
            return "Could not summarize thread"

    def create_draft(self, draft: EmailDraft) -> bool:
        """Create an email draft."""
        service = self._get_service()
        if not service:
            return False

        try:
            message = f"From: me\r\nTo: {draft.to}\r\nSubject: {draft.subject}\r\n"
            if draft.cc:
                message += f"Cc: {draft.cc}\r\n"
            message += f"\r\n{draft.body}"

            encoded = base64.urlsafe_b64encode(message.encode("utf-8")).decode("utf-8")

            service.users().drafts().create(
                userId="me", body={"message": {"raw": encoded}}
            ).execute()

            print(f"[Gmail] ✅ Draft created")
            return True
        except Exception as e:
            print(f"[Gmail] ⚠️ Create draft failed: {e}")
            return False

    def extract_tasks_from_emails(self, max_results: int = 20) -> list[dict]:
        """Extract tasks/deadlines from emails."""
        emails = self.get_recent_emails(max_results)

        from memory.config_manager import get_gemini_key
        import google.generativeai as genai

        genai.configure(api_key=get_gemini_key())
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        tasks = []
        for email in emails[:10]:
            prompt = f"""Extract tasks, deadlines, or action items from this email. 
Return ONLY valid JSON array or [] if nothing found.

Email: {email.subject} | {email.sender}
Body: {email.body[:800]}

Format: [{{"task": "...", "deadline": "YYYY-MM-DD or null", "priority": "normal"}}]"""

            try:
                response = model.generate_content(prompt)
                raw = response.text.strip()
                raw = raw.strip("```json").strip("```").strip()
                extracted = json.loads(raw)
                if extracted:
                    tasks.extend(extracted)
            except:
                pass

        return tasks

    def mark_as_read(self, message_id: str) -> bool:
        """Mark email as read."""
        service = self._get_service()
        if not service:
            return False

        try:
            service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except:
            return False

    def mark_as_starred(self, message_id: str) -> bool:
        """Star or unstar email."""
        service = self._get_service()
        if not service:
            return False

        try:
            msg = service.users().messages().get(userId="me", id=message_id).execute()
            labels = msg.get("labelIds", [])

            if "STARRED" in labels:
                service.users().messages().modify(
                    userId="me", id=message_id, body={"removeLabelIds": ["STARRED"]}
                ).execute()
            else:
                service.users().messages().modify(
                    userId="me", id=message_id, body={"addLabelIds": ["STARRED"]}
                ).execute()
            return True
        except:
            return False


_gmail_client: Optional[GmailClient] = None


def get_gmail_client() -> GmailClient:
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient()
    return _gmail_client
