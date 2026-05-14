"""
Telegram Bot Integration for JARVIS
Receives commands via polling, sends responses back.
Run as a background task inside FastAPI lifespan.
"""
import asyncio
import logging
import os
import json
from typing import Optional

import httpx

from backend.config.settings import get_settings

logger = logging.getLogger("integrations.telegram")

TELEGRAM_API_URL = "https://api.telegram.org/bot"


class TelegramBot:
    """Lightweight polling bot for local daemon."""

    def __init__(self, token: str, allowed_chat_id: str):
        self.token = token
        self.allowed_chat_id = allowed_chat_id
        self.api_url = f"{TELEGRAM_API_URL}{token}"
        self._running = False
        self._offset = 0
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start polling for updates."""
        if self._running:
            logger.warning("Telegram bot already running")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"📱 Telegram bot started (polling for user {self.allowed_chat_id})")

    async def stop(self):
        """Stop polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram bot stopped")

    async def send_message(self, text: str, chat_id: str = None):
        """Send a message to the user."""
        target = chat_id or self.allowed_chat_id
        url = f"{self.api_url}/sendMessage"

        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": "Markdown",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json=payload, timeout=10)
                if resp.status_code != 200:
                    logger.warning(f"Telegram send failed: {resp.text}")
                return resp.status_code == 200
            except Exception as e:
                logger.error(f"Telegram send error: {e}")
                return False

    async def _poll_loop(self):
        """Poll for updates every few seconds."""
        while self._running:
            try:
                await self._fetch_updates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5)  # Back off on error

            await asyncio.sleep(2)  # Normal poll interval

    async def _fetch_updates(self):
        """Fetch and process updates from Telegram."""
        url = f"{self.api_url}/getUpdates"
        params = {"offset": self._offset, "timeout": 30}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, timeout=35)
                data = resp.json()

                if not data.get("ok"):
                    logger.warning(f"Telegram API error: {data}")
                    return

                for update in data.get("result", []):
                    self._offset = update["update_id"] + 1
                    await self._process_update(update)

            except httpx.TimeoutException:
                # Normal timeout, just retry
                pass
            except Exception as e:
                logger.error(f"Fetch error: {e}")

    async def _process_update(self, update: dict):
        """Process a single update."""
        msg = update.get("message")
        if not msg:
            return

        chat = msg.get("chat", {})
        chat_id = str(chat.get("id"))

        # Security: Only accept messages from allowed chat
        if chat_id != self.allowed_chat_id:
            logger.warning(f"Ignored message from unknown chat {chat_id}")
            return

        text = msg.get("text", "")
        if not text:
            return

        logger.info(f"Telegram command from user: {text}")

        # Route to JARVIS backend
        response = await self._route_to_jarvis(text)

        # Send response back
        if response:
            await self.send_message(response, chat_id)

    async def _route_to_jarvis(self, text: str) -> str:
        """Send command to JARVIS backend and get response."""
        from backend.main import _orchestrator, _router, _coordinator, _planner

        if not _orchestrator:
            return "⚠️ JARVIS not ready. Backend not initialized."

        try:
            # Use the chat/stream endpoint
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/api/v1/chat/stream",
                    json={"message": text, "session_id": f"telegram_{self.allowed_chat_id}"},
                    timeout=60,
                )

                # Collect response from SSE
                full_response = ""
                async for line in resp.aiter_lines():
                    if line.startswith("event: token"):
                        data = json.loads(line.replace("event: token\ndata: ", ""))
                        full_response += data.get("text", "")
                    elif line.startswith("event: answer"):
                        data = json.loads(line.replace("event: answer\ndata: ", ""))
                        full_response = data.get("content", "")
                        break

                return full_response[:4000]  # Telegram limit

        except Exception as e:
            logger.error(f"Route to JARVIS failed: {e}")
            return f"⚠️ Error processing request: {e}"


# Global instance
_telegram_bot: Optional[TelegramBot] = None


def init_telegram_bot(token: str, chat_id: str) -> TelegramBot:
    """Initialize the Telegram bot."""
    global _telegram_bot
    _telegram_bot = TelegramBot(token, chat_id)
    return _telegram_bot


def get_telegram_bot() -> Optional[TelegramBot]:
    """Get the telegram bot instance."""
    return _telegram_bot