"""
actions/screen_processor.py — Gemini Live API — IMAGE-ONLY SESSION v8
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v8 Changes:
  - Auto camera detection on first use — saves to config
  - No hardcoded camera index
  - mic_loop removed (no double response issue)
  - Image-only session, no conflict with main.py
"""

import asyncio
import base64
from typing import Any
import io
import json
import re

import sys
import time
import threading
import cv2  # type: ignore[import]
import mss  # type: ignore[import]
import mss.tools  # type: ignore[import]
import sounddevice as sd  # type: ignore[import]
from pathlib import Path

try:
    import PIL.Image  # type: ignore[import]
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from google import genai  # type: ignore[import]
from google.genai import types  # type: ignore[import]


from memory.config_manager import get_gemini_key, BASE_DIR  # type: ignore


API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
FORMAT = 'int16'
CHANNELS = 1
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

IMG_MAX_W = 640
IMG_MAX_H = 360
JPEG_Q = 55

SYSTEM_PROMPT = (
    "You are Rohan Vemula's AI assistant. "
    "Analyze images with technical precision and intelligence. "
    "Help the user in a way they can understand — don't be overly complex. "
    "Be concise, smart, and helpful. "
    "Respond in maximum 2 short sentences. Speed is priority. "
    "Address the user as 'sir' for a tone of respect. "
    "Ask if the user needs any further help with their problem."
)


def _get_camera_index() -> int:
    """
    Reads camera index from config.
    If not set, auto-detects the best camera and saves it for future use.
    Runs only once — after that, config value is used directly.
    """
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "camera_index" in cfg:
            return int(cfg["camera_index"])
    except Exception:
        pass

    print("[Camera] 🔍 No camera index in config. Auto-detecting...")
    best_index = 0

    for idx in range(6):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue

        for _ in range(5):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None and frame.mean() > 5:
            best_index = idx
            print(
                f"[Camera] ✅ Camera found at index {idx} — saving to config.")
            break
        else:
            print(
                f"[Camera] ⚠️  Index {idx}: no valid frame (black or empty).")

    try:
        cfg: dict = {}
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["camera_index"] = best_index  # type: ignore[index]
        with open(API_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"[Camera] 💾 Camera index {best_index} saved to config.")
    except Exception as e:
        print(f"[Camera] ⚠️  Could not save camera index: {e}")

    return best_index


def _to_jpeg(img_bytes: bytes) -> bytes:
    if not _PIL_OK:
        return img_bytes
    img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
    return buf.getvalue()


def _capture_screenshot() -> bytes:
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)
    return _to_jpeg(png_bytes)


def _capture_camera() -> bytes:
    camera_index = _get_camera_index()
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Camera could not be opened: index {camera_index}")

    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError("Could not capture camera frame.")

    if _PIL_OK:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
        return buf.getvalue()

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q])
    return buf.tobytes()


class _LiveSession:
    """
    Image-only analysis session.
    No microphone — no conflict with main.py session.
    Sends image + question, plays audio response.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: Any = None
        self._out_queue: asyncio.Queue[Any] | None = None
        self._audio_in: asyncio.Queue[Any] | None = None
        self._ready: threading.Event = threading.Event()
        self._player: Any = None
        self._pya: Any = None  # Not needed for sounddevice
        self._send_lock: asyncio.Lock | None = None

    def start(self, player: Any = None) -> None:
        if self._thread is not None and self._thread.is_alive(  # type: ignore
        ):  # type: ignore[union-attr]
            return
        self._player = player
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="VisionSessionThread"
        )
        self._thread.start()  # type: ignore[union-attr]
        ok = self._ready.wait(timeout=20)
        if not ok:
            raise RuntimeError("Vision session did not start within 20s.")
        print("[ScreenProcess] ✅ Vision session ready (no mic)")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())  # type: ignore[union-attr]

    async def _main(self):
        self._out_queue = asyncio.Queue(maxsize=30)
        self._audio_in = asyncio.Queue()
        self._send_lock = asyncio.Lock()

        client = genai.Client(
            api_key=get_gemini_key(),
            http_options={"api_version": "v1beta"}
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            system_instruction=SYSTEM_PROMPT,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

        while True:
            try:
                print("[ScreenProcess] 🔌 Vision session connecting...")
                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:  # noqa: E501
                    self._session = session
                    self._ready.set()
                    print("[ScreenProcess] ✅ Vision session connected")

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_loop())
                        tg.create_task(self._recv_loop())
                        tg.create_task(self._play_loop())

            except Exception as e:
                print(
                    f"[ScreenProcess] ⚠️ Disconnected: {e} — reconnecting...")
                self._session = None
                self._ready.clear()
                await asyncio.sleep(2)
                self._ready.set()

    # ── Send loop ──

    async def _send_loop(self):
        """Sends (image_bytes, mime_type, user_text) tuples from queue."""
        while True:
            item = await self._out_queue.get()  # type: ignore[union-attr]
            if self._session:
                image_bytes, mime_type, user_text = item
                try:
                    b64 = base64.b64encode(image_bytes).decode("utf-8")
                    await self._session.send_client_content(  # type: ignore[union-attr]  # noqa: E501
                        turns={
                            "parts": [
                                {"inline_data": {"mime_type": mime_type, "data": b64}},  # noqa: E501
                                {"text": user_text}
                            ]
                        },
                        turn_complete=True
                    )
                    print("[ScreenProcess] ✅ Image sent")
                except Exception as e:
                    print(f"[ScreenProcess] ⚠️ Send error: {e}")

    async def _recv_loop(self):
        transcript_buf: list[str] = []
        try:
            # type: ignore[union-attr]
            async for response in self._session.receive():

                if response.data:
                    # type: ignore[union-attr]
                    await self._audio_in.put(response.data)

                sc = response.server_content
                if not sc:
                    continue

                if sc.output_transcription and sc.output_transcription.text:
                    chunk = sc.output_transcription.text.strip()
                    if chunk:
                        transcript_buf.append(chunk)

                if sc.turn_complete:
                    if transcript_buf and self._player:
                        full = re.sub(
                            r'\s+', ' ', " ".join(transcript_buf)).strip()
                        if full:
                            self._player.write_log(
                                f"Jarvis: {full}")  # type: ignore[union-attr]
                            print(f"[ScreenProcess] 💬 {full}")
                    transcript_buf = []

        except Exception as e:
            print(f"[ScreenProcess] ⚠️ Recv error: {e}")
            transcript_buf = []
            await asyncio.sleep(0.3)

    async def _play_loop(self):
        stream = sd.OutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype=FORMAT,
        )
        await asyncio.to_thread(stream.start)
        try:
            while True:
                chunk = await self._audio_in.get()  # type: ignore[union-attr]
                # Convert bytes to numpy array
                import numpy as np  # type: ignore[import]
                data = np.frombuffer(chunk, dtype=FORMAT)
                await asyncio.to_thread(stream.write, data)
        finally:
            await asyncio.to_thread(stream.stop)
            await asyncio.to_thread(stream.close)

    def analyze(self, image_bytes: bytes, mime_type: str, user_text: str):
        """Called from main thread — puts image into async queue."""
        if not self._loop:
            return
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(
            # type: ignore[union-attr]
            self._out_queue.put((image_bytes, mime_type, user_text)),
            self._loop  # type: ignore
        )

    def is_ready(self) -> bool:
        return self._session is not None


_live = _LiveSession()
_started = False
_start_lock = threading.Lock()


def _ensure_started(player=None):
    global _started
    with _start_lock:
        if not _started:
            _live.start(player=player)
            _started = True
        elif player is not None:
            _live._player = player


def screen_process(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None,
) -> bool:
    user_text = (
        parameters or {}).get("text") or (
        parameters or {}).get(
            "user_text",
        "")
    user_text = (user_text or "").strip()
    if not user_text:
        print("[ScreenProcess] ⚠️ No user_text provided.")
        return False

    angle = (parameters or {}).get("angle", "screen").lower().strip()
    print(f"[ScreenProcess] angle={angle!r}  text={user_text!r}")

    _ensure_started(player=player)

    try:
        if angle == "camera":
            image_bytes = _capture_camera()
            mime_type = "image/jpeg"
            print("[ScreenProcess] 📷 Camera captured")
        else:
            image_bytes = _capture_screenshot()
            mime_type = "image/jpeg" if _PIL_OK else "image/png"
            print("[ScreenProcess] 🖥️ Screen captured")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ScreenProcess] ❌ Capture error: {e}")
        return False

    print(f"[ScreenProcess] 📦 {len(image_bytes)} bytes → sending")
    _live.analyze(image_bytes, mime_type, user_text)
    return True


def warmup_session(player=None):
    """
    Optional: pre-warm the session.
    Do NOT call from main.py — causes double session issue.
    Only use when testing screen_processor.py standalone.
    """
    try:
        _ensure_started(player=player)
    except Exception as e:
        print(f"[ScreenProcess] ⚠️ Warmup error: {e}")


if __name__ == "__main__":
    print("[TEST] screen_processor.py v8 — image-only session")
    print("=" * 50)
    mode = input(
        "screen / camera (default: screen): ").strip().lower() or "screen"
    request = input("Question (Enter for default): ").strip(
    ) or "What do you see? Be brief."

    t0 = time.perf_counter()
    warmup_session()
    print(f"Session ready — {time.perf_counter() - t0:.2f}s\n")

    t1 = time.perf_counter()
    result = screen_process({"angle": mode, "text": request}, player=None)
    print(f"Sent — {time.perf_counter() - t1:.3f}s | audio incoming...")
    time.sleep(8)
    print(f"\n{'✅' if result else '❌'}")
