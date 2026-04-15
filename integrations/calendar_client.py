import os
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Literal
from dataclasses import dataclass, asdict
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CALENDAR_TOKEN_PATH = BASE_DIR / "memory" / "calendar_token.json"
CALENDAR_CREDENTIALS_PATH = BASE_DIR / "config" / "calendar_credentials.json"


@dataclass
class CalendarEvent:
    id: str
    title: str
    description: str
    start_time: str
    end_time: str
    location: str
    attendees: list[str]
    reminders: list[dict]
    recurrence: str
    status: str
    color_id: str


class CalendarClient:
    """Google Calendar API client for event management."""

    def __init__(self):
        self._service = None
        self._lock = threading.Lock()

    def _load_credentials(self) -> Optional[dict]:
        if CALENDAR_CREDENTIALS_PATH.exists():
            return json.loads(CALENDAR_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return None

    def _load_token(self) -> Optional[dict]:
        if CALENDAR_TOKEN_PATH.exists():
            return json.loads(CALENDAR_TOKEN_PATH.read_text(encoding="utf-8"))
        return None

    def _save_token(self, token: dict):
        CALENDAR_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        CALENDAR_TOKEN_PATH.write_text(json.dumps(token, indent=2), encoding="utf-8")

    def is_configured(self) -> bool:
        return self._load_credentials() is not None

    def _get_service(self):
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
                "calendar", "v3", credentials=creds, cache_discovery=False
            )
            return self._service
        except Exception as e:
            print(f"[Calendar] ⚠️ Service init failed: {e}")
            return None

    def _parse_event(self, event: dict) -> CalendarEvent:
        start = event.get("start", {})
        end = event.get("end", {})

        return CalendarEvent(
            id=event.get("id", ""),
            title=event.get("summary", "(No title)"),
            description=event.get("description", ""),
            start_time=start.get("dateTime", start.get("date", "")),
            end_time=end.get("dateTime", end.get("date", "")),
            location=event.get("location", ""),
            attendees=[a.get("email", "") for a in event.get("attendees", [])],
            reminders=event.get("reminders", {}).get("overrides", []),
            recurrence=event.get("recurrence", []),
            status=event.get("status", ""),
            color_id=event.get("colorId", ""),
        )

    def get_events(
        self,
        max_results: int = 20,
        time_min: str = None,
        time_max: str = None,
        calendar_id: str = "primary",
    ) -> list[CalendarEvent]:
        """Get calendar events."""
        service = self._get_service()
        if not service:
            return []

        if not time_min:
            time_min = datetime.now().isoformat() + "Z"
        if not time_max:
            time_max = (datetime.now() + timedelta(days=30)).isoformat() + "Z"

        try:
            results = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            return [self._parse_event(e) for e in results.get("items", [])]
        except Exception as e:
            print(f"[Calendar] ⚠️ Get events failed: {e}")
            return []

    def get_today_events(self, calendar_id: str = "primary") -> list[CalendarEvent]:
        """Get today's events."""
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0).isoformat() + "Z"
        end = now.replace(hour=23, minute=59, second=59).isoformat() + "Z"
        return self.get_events(time_min=start, time_max=end, calendar_id=calendar_id)

    def get_upcoming_events(
        self, days: int = 7, calendar_id: str = "primary"
    ) -> list[CalendarEvent]:
        """Get upcoming events."""
        now = datetime.now().isoformat() + "Z"
        future = (datetime.now() + timedelta(days=days)).isoformat() + "Z"
        return self.get_events(time_min=now, time_max=future, calendar_id=calendar_id)

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: list[str] = None,
        calendar_id: str = "primary",
    ) -> Optional[CalendarEvent]:
        """Create a new calendar event."""
        service = self._get_service()
        if not service:
            return None

        event = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
        }

        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]

        try:
            created = (
                service.events()
                .insert(calendarId=calendar_id, body=event, sendUpdates="none")
                .execute()
            )

            print(f"[Calendar] ✅ Created event: {title}")
            return self._parse_event(created)
        except Exception as e:
            print(f"[Calendar] ⚠️ Create event failed: {e}")
            return None

    def update_event(
        self,
        event_id: str,
        title: str = None,
        description: str = None,
        start_time: str = None,
        end_time: str = None,
        location: str = None,
        calendar_id: str = "primary",
    ) -> Optional[CalendarEvent]:
        """Update an existing event."""
        service = self._get_service()
        if not service:
            return None

        try:
            event = (
                service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            )

            if title is not None:
                event["summary"] = title
            if description is not None:
                event["description"] = description
            if start_time is not None:
                event["start"] = {"dateTime": start_time, "timeZone": "UTC"}
            if end_time is not None:
                event["end"] = {"dateTime": end_time, "timeZone": "UTC"}
            if location is not None:
                event["location"] = location

            updated = (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )

            print(f"[Calendar] ✅ Updated event: {event_id}")
            return self._parse_event(updated)
        except Exception as e:
            print(f"[Calendar] ⚠️ Update event failed: {e}")
            return None

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> bool:
        """Delete an event."""
        service = self._get_service()
        if not service:
            return False

        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            print(f"[Calendar] ✅ Deleted event: {event_id}")
            return True
        except Exception as e:
            print(f"[Calendar] ⚠️ Delete event failed: {e}")
            return False

    def find_free_slots(
        self,
        duration_minutes: int = 60,
        days_ahead: int = 7,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Find free time slots."""
        events = self.get_upcoming_events(days_ahead, calendar_id)

        free_slots = []
        now = datetime.now()

        for day in range(days_ahead):
            day_start = (now + timedelta(days=day)).replace(hour=9, minute=0, second=0)
            day_end = (now + timedelta(days=day)).replace(hour=18, minute=0, second=0)

            day_events = [
                e
                for e in events
                if datetime.fromisoformat(e.start_time.replace("Z", "+00:00"))
                >= day_start
                and datetime.fromisoformat(e.start_time.replace("Z", "+00:00"))
                < day_end
            ]

            if not day_events:
                free_slots.append(
                    {
                        "date": day_start.strftime("%Y-%m-%d"),
                        "start": "09:00",
                        "end": "18:00",
                    }
                )
                continue

            current = day_start
            for event in sorted(day_events, key=lambda x: x.start_time):
                event_start = datetime.fromisoformat(
                    event.start_time.replace("Z", "+00:00")
                )
                if event_start > current:
                    free_start = current
                    free_end = event_start
                    if (free_end - free_start).total_seconds() >= duration_minutes * 60:
                        free_slots.append(
                            {
                                "date": free_start.strftime("%Y-%m-%d"),
                                "start": free_start.strftime("%H:%M"),
                                "end": free_end.strftime("%H:%M"),
                            }
                        )
                event_end = datetime.fromisoformat(
                    event.end_time.replace("Z", "+00:00")
                )
                current = max(current, event_end)

            if current < day_end:
                if (day_end - current).total_seconds() >= duration_minutes * 60:
                    free_slots.append(
                        {
                            "date": current.strftime("%Y-%m-%d"),
                            "start": current.strftime("%H:%M"),
                            "end": day_end.strftime("%H:%M"),
                        }
                    )

        return free_slots

    def parse_natural_language(self, text: str) -> dict:
        """Parse natural language into event details using LLM."""
        from memory.config_manager import get_gemini_key
        import google.generativeai as genai

        genai.configure(api_key=get_gemini_key())
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        now = datetime.now()

        prompt = f"""Extract calendar event details from this text. 
Current time: {now.strftime("%Y-%m-%d %H:%M")}

Text: {text}

Return ONLY valid JSON with:
- title: event name
- start_date: YYYY-MM-DD
- start_time: HH:MM (24h format)
- end_time: HH:MM (24h format, default 1 hour after start)
- description: details or null
- location: location or null

Format:
{{"title": "...", "start_date": "2024-01-15", "start_time": "14:00", "end_time": "15:00", "description": null, "location": null}}"""

        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            raw = raw.strip("```json").strip("```").strip()
            return json.loads(raw)
        except:
            return {}


_calendar_client: Optional[CalendarClient] = None


def get_calendar_client() -> CalendarClient:
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = CalendarClient()
    return _calendar_client
