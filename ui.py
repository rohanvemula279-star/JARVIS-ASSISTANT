# pyre-ignore-all-errors
import os, json, time, math, random, threading
import tkinter as tk
from collections import deque
from PIL import Image, ImageTk, ImageDraw  # pyre-ignore
import sys
from pathlib import Path
import concurrent.futures


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE = CONFIG_DIR / "api_keys.json"

SYSTEM_NAME = "J.A.R.V.I.S"
MODEL_BADGE = "MARK XXX"

C_BG = "#000000"
C_PRI = "#00d4ff"
C_MID = "#007a99"
C_DIM = "#003344"
C_DIMMER = "#001520"
C_ACC = "#ff6600"
C_ACC2 = "#ffcc00"
C_TEXT = "#8ffcff"
C_PANEL = "#010c10"
C_GREEN = "#00ff88"
C_RED = "#ff3333"


class JarvisUI:
    def __init__(self, face_path, size=None, face_system=None, mode="NORMAL"):
        """
        Args:
            face_path: Path to JARVIS face image
            size: Unused (kept for compat)
            face_system: FaceAuthSystem instance (None = no face auth)
            mode: 'NORMAL' | 'LOCKED' | 'ENROLLMENT'
        """
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S — MARK XXX")
        self.root.resizable(False, False)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        W = min(sw, 984)
        H = min(sh, 816)
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
        self.root.configure(bg=C_BG)

        self.W = W
        self.H = H

        self.FACE_SZ = min(int(H * 0.54), 400)
        self.FCX = W // 2
        self.FCY = int(H * 0.13) + self.FACE_SZ // 2

        self.speaking = False
        self.mic_active = False
        self.scale = 1.0
        self.target_scale = 1.0
        self.halo_a = 60.0
        self.target_halo = 60.0
        self.last_t = time.time()
        self.tick = 0
        self.scan_angle = 0.0
        self.scan2_angle = 180.0
        self.rings_spin = [0.0, 120.0, 240.0]
        self.pulse_r = [0.0, self.FACE_SZ * 0.26, self.FACE_SZ * 0.52]
        self.status_text = "INITIALISING"
        self.status_blink = True

        self.typing_queue = deque()
        self.is_typing = False

        self._face_pil = None
        self._has_face = False
        self._face_scale_cache = None
        self.setup_frame = None
        self.gemini_entry = None
        self._load_face(face_path)

        self.bg = tk.Canvas(self.root, width=W, height=H, bg=C_BG, highlightthickness=0)
        self.bg.place(x=0, y=0)

        LW = int(W * 0.72)
        LH = 138
        self.log_frame = tk.Frame(
            self.root, bg=C_PANEL, highlightbackground=C_MID, highlightthickness=1
        )
        self.log_frame.place(x=(W - LW) // 2, y=H - LH - 36, width=LW, height=LH)
        self.log_text = tk.Text(
            self.log_frame,
            fg=C_TEXT,
            bg=C_PANEL,
            insertbackground=C_TEXT,
            borderwidth=0,
            wrap="word",
            font=("Courier", 10),
            padx=10,
            pady=6,
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.log_text.tag_config("you", foreground="#e8e8e8")
        self.log_text.tag_config("ai", foreground=C_PRI)
        self.log_text.tag_config("sys", foreground=C_ACC2)

        # ── Face Auth State ──
        self.face_system = face_system
        self.is_locked = mode == "LOCKED"
        self.mode = mode  # NORMAL / LOCKED / ENROLLMENT

        # Lock screen state
        self._lock_scan_y = 0
        self._lock_scan_dir = 1
        self._lock_corner_phase = 0.0
        self._lock_status_msg = "SCANNING FOR AUTHORIZED USER..."
        self._lock_status_color = C_PRI
        self._lock_denied_flash = 0
        self._circular_mask = None  # Pre-created, reuse forever
        self._camera_tk_img = None  # Keep reference to prevent GC
        self._cam_display_size = min(280, self.FACE_SZ - 20)

        # Enrollment state
        self._enroll_step = 0
        self._enroll_total = 10
        self._enroll_text = ""
        self._enroll_started = False
        self._enroll_done = False
        self._enroll_btn_id = None

        # Unlock animation
        self._unlock_anim_frame = 0
        self._unlock_animating = False

        # API key event-based synchronization (non-blocking)
        self._api_key_ready = self._api_keys_exist()
        self._api_key_event = threading.Event()
        if self._api_key_ready:
            self._api_key_event.set()

        if not self._api_key_ready and mode == "NORMAL":
            self._show_setup_ui()

        # Start appropriate mode
        if mode == "ENROLLMENT":
            self._hide_normal_ui()
            self._show_enrollment_screen()
        elif mode == "LOCKED":
            self._hide_normal_ui()
            self._show_lock_screen()
        else:
            self._animate()

        self.root.bind("<m>", lambda e: self._safe_toggle_mic())
        self.root.bind("<M>", lambda e: self._safe_toggle_mic())

        # Window close: allow even when locked
        if face_system:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        else:
            self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    def _on_close(self):
        """Clean shutdown with face system cleanup."""
        if self.face_system:
            self.face_system.stop()
        self.root.destroy()
        os._exit(0)

    def _safe_toggle_mic(self):
        """Toggle mic only if unlocked."""
        if self.is_locked:
            return
        self.toggle_mic()

    def _hide_normal_ui(self):
        """Hide normal Jarvis UI elements (log panel)."""
        self.log_frame.place_forget()

    def _show_normal_ui(self):
        """Restore normal Jarvis UI elements."""
        LW = int(self.W * 0.72)
        LH = 138
        self.log_frame.place(
            x=(self.W - LW) // 2, y=self.H - LH - 36, width=LW, height=LH
        )

    def _load_face(self, path):
        FW = self.FACE_SZ
        try:
            img = Image.open(path).convert("RGBA").resize((FW, FW), Image.LANCZOS)
            mask = Image.new("L", (FW, FW), 0)
            ImageDraw.Draw(mask).ellipse((2, 2, FW - 2, FW - 2), fill=255)
            img.putalpha(mask)
            self._face_pil = img
            self._has_face = True
        except Exception:
            self._has_face = False

    @staticmethod
    def _ac(r, g, b, a):
        f = a / 255.0
        return f"#{int(r * f):02x}{int(g * f):02x}{int(b * f):02x}"

    # ══════════════════════════════════════════
    #  LOCK SCREEN
    # ══════════════════════════════════════════

    def _show_lock_screen(self):
        """Replace Jarvis UI with face auth lock screen."""
        self.is_locked = True
        self.mode = "LOCKED"
        self._hide_normal_ui()
        self._lock_scan_y = 0
        self._lock_denied_flash = 0
        self._lock_status_msg = "SCANNING FOR AUTHORIZED USER..."
        self._lock_status_color = C_PRI

        # Pre-create circular mask for camera feed (reuse every frame)
        cam_size = min(280, self.FACE_SZ - 20)
        self._cam_display_size = cam_size
        if self._circular_mask is None:
            mask = Image.new("L", (cam_size, cam_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, cam_size - 1, cam_size - 1), fill=255)
            self._circular_mask = mask

        self._lock_screen_loop()

    def _lock_screen_loop(self):
        """Main lock screen render loop — runs every 50ms."""
        if not self.is_locked:
            return
        if self._unlock_animating:
            return

        self._draw_lock_screen()

        # Check face auth status
        if self.face_system:
            result = self.face_system.authenticate()
            self._handle_auth_result(result)

        self.root.after(50, self._lock_screen_loop)

    def _draw_lock_screen(self):
        """Render the full lock screen on canvas."""
        c = self.bg
        W, H = self.W, self.H
        c.delete("all")

        # Background grid
        for x in range(0, W, 44):
            for y in range(0, H, 44):
                c.create_rectangle(x, y, x + 1, y + 1, fill=C_DIMMER, outline="")

        # ── Header ──
        HDR = 62
        c.create_rectangle(0, 0, W, HDR, fill="#00080d", outline="")
        c.create_line(0, HDR, W, HDR, fill=C_MID, width=1)
        c.create_text(
            W // 2, 22, text=SYSTEM_NAME, fill=C_PRI, font=("Courier", 18, "bold")
        )
        c.create_text(
            W // 2,
            44,
            text="SECURITY PROTOCOL",
            fill=C_RED,
            font=("Courier", 10, "bold"),
        )
        c.create_text(
            W - 16,
            31,
            text=time.strftime("%H:%M:%S"),
            fill=C_PRI,
            font=("Courier", 14, "bold"),
            anchor="e",
        )
        c.create_text(
            16, 31, text="🔒 LOCKED", fill=C_RED, font=("Courier", 9), anchor="w"
        )

        # ── Camera feed area ──
        cam_cx = W // 2
        cam_cy = H // 2 - 40
        cam_r = self._cam_display_size // 2

        # Outer ring glow
        for i in range(3):
            r = cam_r + 15 + i * 8
            alpha = max(0, 80 - i * 25)
            c.create_oval(
                cam_cx - r,
                cam_cy - r,
                cam_cx + r,
                cam_cy + r,
                outline=self._ac(0, 212, 255, alpha),
                width=2,
            )

        # Camera feed (circular masked)
        frame = self.face_system.get_frame_rgb() if self.face_system else None
        if frame is not None:
            self._render_camera_feed(frame, cam_cx, cam_cy)
        else:
            # No camera / no frame — show placeholder
            c.create_oval(
                cam_cx - cam_r,
                cam_cy - cam_r,
                cam_cx + cam_r,
                cam_cy + cam_r,
                fill="#001520",
                outline=C_DIM,
                width=2,
            )
            c.create_text(
                cam_cx,
                cam_cy,
                text="📷 NO CAMERA",
                fill=C_DIM,
                font=("Courier", 12, "bold"),
            )

        # ── Animated face detection overlay ──
        state = self.face_system.get_state() if self.face_system else {}

        if state.get("face_detected"):
            box = state.get("face_box")
            if box:
                self._draw_face_overlay(c, box, cam_cx, cam_cy, cam_r, state, frame)

        # ── Scanning line animation ──
        self._lock_scan_y += 3 * self._lock_scan_dir
        scan_top = cam_cy - cam_r
        scan_bot = cam_cy + cam_r
        if self._lock_scan_y > (scan_bot - scan_top):
            self._lock_scan_dir = -1
        elif self._lock_scan_y < 0:
            self._lock_scan_dir = 1
        scan_y_pos = scan_top + self._lock_scan_y
        c.create_line(
            cam_cx - cam_r + 10,
            scan_y_pos,
            cam_cx + cam_r - 10,
            scan_y_pos,
            fill=self._ac(0, 255, 255, 60),
            width=1,
        )

        # ── Corner brackets ──
        self._lock_corner_phase += 0.05
        blen = 25
        pad = 5
        bracket_alpha = int(150 + 50 * math.sin(self._lock_corner_phase))
        bc = self._ac(0, 212, 255, bracket_alpha)
        hl = cam_cx - cam_r - pad
        hr = cam_cx + cam_r + pad
        ht = cam_cy - cam_r - pad
        hb = cam_cy + cam_r + pad
        for bx, by, sdx, sdy in [
            (hl, ht, 1, 1),
            (hr, ht, -1, 1),
            (hl, hb, 1, -1),
            (hr, hb, -1, -1),
        ]:
            c.create_line(bx, by, bx + sdx * blen, by, fill=bc, width=2)
            c.create_line(bx, by, bx, by + sdy * blen, fill=bc, width=2)

        # ── Status panel ──
        status_y = cam_cy + cam_r + 50

        # Denied flash effect
        if self._lock_denied_flash > 0:
            flash_alpha = min(255, self._lock_denied_flash * 8)
            c.create_rectangle(
                0, 0, W, H, fill=self._ac(255, 0, 0, flash_alpha), outline=""
            )
            self._lock_denied_flash -= 1

        # Status box
        box_w = 320
        box_h = 50
        c.create_rectangle(
            W // 2 - box_w // 2,
            status_y - box_h // 2,
            W // 2 + box_w // 2,
            status_y + box_h // 2,
            fill="#00080d",
            outline=C_DIM,
            width=1,
        )
        c.create_text(
            W // 2,
            status_y,
            text=self._lock_status_msg,
            fill=self._lock_status_color,
            font=("Courier", 10, "bold"),
        )

        # ── Confidence bar ──
        conf = state.get("confidence", 0.0)
        if conf > 0:
            bar_y = status_y + 35
            bar_w = 200
            bar_h = 4
            c.create_rectangle(
                W // 2 - bar_w // 2,
                bar_y,
                W // 2 + bar_w // 2,
                bar_y + bar_h,
                fill="#001520",
                outline="",
            )
            fill_w = int(bar_w * min(conf, 1.0))
            bar_color = C_GREEN if conf >= 0.85 else C_ACC2 if conf >= 0.7 else C_RED
            c.create_rectangle(
                W // 2 - bar_w // 2,
                bar_y,
                W // 2 - bar_w // 2 + fill_w,
                bar_y + bar_h,
                fill=bar_color,
                outline="",
            )
            c.create_text(
                W // 2 + bar_w // 2 + 30,
                bar_y + 2,
                text=f"{conf:.0%}",
                fill=C_DIM,
                font=("Courier", 8),
                anchor="w",
            )

        # Quality hint
        hint = state.get("quality_hint", "")
        if hint:
            c.create_text(
                W // 2, status_y + 75, text=hint, fill=C_ACC, font=("Courier", 9)
            )

        # ── Footer ──
        c.create_rectangle(0, H - 28, W, H, fill="#00080d", outline="")
        c.create_line(0, H - 28, W, H - 28, fill=C_DIM, width=1)
        c.create_text(
            W // 2,
            H - 14,
            fill=C_DIM,
            font=("Courier", 8),
            text="FACE AUTHENTICATION REQUIRED  ·  SECURITY LEVEL: ALPHA",
        )

    def _render_camera_feed(self, frame_rgb, cx, cy):
        """Convert numpy RGB frame → circular masked image on canvas."""
        import numpy as np  # pyre-ignore

        cam_size = self._cam_display_size
        h, w = frame_rgb.shape[:2]

        # Center-crop to square
        side = min(h, w)
        y_off = (h - side) // 2
        x_off = (w - side) // 2
        square = frame_rgb[y_off : y_off + side, x_off : x_off + side]

        # Convert to PIL, resize, apply circular mask
        pil_img = Image.fromarray(square).resize((cam_size, cam_size), Image.BILINEAR)
        pil_img = pil_img.convert("RGBA")

        # Apply pre-created circular mask
        bg = Image.new("RGBA", (cam_size, cam_size), (0, 0, 0, 0))
        bg.paste(pil_img, (0, 0), self._circular_mask)

        # Convert to Tk
        self._camera_tk_img = ImageTk.PhotoImage(bg)
        self.bg.create_image(cx, cy, image=self._camera_tk_img)

    def _draw_face_overlay(self, c, box, cam_cx, cam_cy, cam_r, state, frame):
        """Draw face detection overlay (corner brackets around detected face)."""
        # Map face box coordinates to the circular camera display area
        # box is in original frame coords; we need to scale to display
        cam_size = self._cam_display_size
        fx, fy, fw, fh = box

        # Scale factors (frame → display)
        if frame is None:
            return
        frame_h, frame_w = frame.shape[:2] if hasattr(frame, "shape") else (480, 640)
        side = min(frame_h, frame_w)
        scale = cam_size / side

        # Offset from center-crop
        x_off = (int(frame_w) - int(side)) // 2
        y_off = (int(frame_h) - int(side)) // 2

        dx = int((fx - x_off) * scale) + cam_cx - cam_size // 2
        dy = int((fy - y_off) * scale) + cam_cy - cam_size // 2
        dw = int(fw * scale)
        dh = int(fh * scale)

        # Color based on auth state
        is_owner = state.get("is_owner")
        if is_owner is True:
            color = C_GREEN
        elif is_owner is False:
            color = C_RED
        else:
            color = C_PRI  # scanning

        # Corner brackets (not full rectangle)
        blen = min(20, dw // 3, dh // 3)
        for bx, by, sdx, sdy in [
            (dx, dy, 1, 1),
            (dx + dw, dy, -1, 1),
            (dx, dy + dh, 1, -1),
            (dx + dw, dy + dh, -1, -1),
        ]:
            c.create_line(bx, by, bx + sdx * blen, by, fill=color, width=2)
            c.create_line(bx, by, bx, by + sdy * blen, fill=color, width=2)

    def _handle_auth_result(self, result):
        """Handle authentication result from face system."""
        if result == "GRANTED":
            if self._unlock_animating:
                return
            self._unlock_animating = True
            self._lock_status_msg = "✓ IDENTITY VERIFIED"
            self._lock_status_color = C_GREEN

            if self.face_system and self.face_system.cap is not None:
                self.face_system.stop_camera()

            self.root.after(800, self._unlock)  # type: ignore

        elif result == "DENIED":
            self._lock_status_msg = "YOU ARE NOT THE OWNER - GO AWAY"
            self._lock_status_color = C_RED
            self._lock_denied_flash = 0  # removed red flash frames

        elif result == "NO_FACE":
            self._lock_status_msg = "SCANNING FOR AUTHORIZED USER..."
            self._lock_status_color = C_PRI

        elif result.startswith("LOCKED_OUT"):
            remaining = result.split(":")[1] if ":" in result else "?"
            self._lock_status_msg = f"LOCKED OUT — TRY AGAIN IN {remaining}s"
            self._lock_status_color = C_RED

        elif result == "NO_CAMERA":
            self._lock_status_msg = "CAMERA UNAVAILABLE"
            self._lock_status_color = C_ACC

        elif result == "NEED_BLINK":
            self._lock_status_msg = "IDENTITY MATCHED — BLINK TO CONFIRM"
            self._lock_status_color = C_GREEN

        elif result == "LOW_QUALITY":
            self._lock_status_msg = "POOR CONDITIONS — ADJUST POSITION"
            self._lock_status_color = C_ACC2

    # ══════════════════════════════════════════
    #  UNLOCK / LOCK
    # ══════════════════════════════════════════

    def _unlock(self):
        """Transition from lock screen to full Jarvis UI."""
        self._unlock_animating = False
        self.is_locked = False
        self.mode = "NORMAL"
        self._show_normal_ui()

        # If API key isn't setup, show the setup screen now that we're unlocked
        if not self._api_key_ready:
            self._show_setup_ui()

        # Camera tracking is already stopped in _handle_auth_result

        # Start normal animation
        self.status_text = "ONLINE"
        self._animate()

    def _lock(self, reason=""):
        """Lock the UI and return to lock screen."""
        if self.is_locked:
            return
        self.is_locked = True
        self.mode = "LOCKED"

        if reason:
            print(f"[FaceAuth] 🔒 Locked: {reason}")

        if self.face_system:
            self.face_system.reset_auth()
            self.face_system.stop_camera()  # Stop camera when locked (wait for explicit 'open camera' command)

        self._hide_normal_ui()
        self._show_lock_screen()

    def _start_session_check(self):
        """Deprecated: session checking disabled due to camera shutoff on login."""
        pass

    # ══════════════════════════════════════════
    #  ENROLLMENT SCREEN
    # ══════════════════════════════════════════

    def _show_enrollment_screen(self):
        """First-time face registration UI."""
        self.mode = "ENROLLMENT"
        self._hide_normal_ui()

        # Pre-create circular mask
        cam_size = min(280, self.FACE_SZ - 20)
        self._cam_display_size = cam_size
        if self._circular_mask is None:
            mask = Image.new("L", (cam_size, cam_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, cam_size - 1, cam_size - 1), fill=255)
            self._circular_mask = mask

        self._enroll_started = False
        self._enroll_done = False
        self._enroll_step = 0
        self._enroll_text = "Position face in camera and press Begin"

        # Start camera if face system available
        if self.face_system:
            self.face_system.start_camera()

        self._enrollment_render_loop()

    def _enrollment_render_loop(self):
        """Render enrollment screen at ~20fps."""
        if self.mode != "ENROLLMENT":
            return

        c = self.bg
        W, H = self.W, self.H
        c.delete("all")

        # Background
        for x in range(0, W, 44):
            for y in range(0, H, 44):
                c.create_rectangle(x, y, x + 1, y + 1, fill=C_DIMMER, outline="")

        # Header
        HDR = 62
        c.create_rectangle(0, 0, W, HDR, fill="#00080d", outline="")
        c.create_line(0, HDR, W, HDR, fill=C_MID, width=1)
        c.create_text(
            W // 2, 22, text=SYSTEM_NAME, fill=C_PRI, font=("Courier", 18, "bold")
        )
        c.create_text(
            W // 2,
            44,
            text="FIRST-TIME SECURITY SETUP",
            fill=C_ACC2,
            font=("Courier", 10, "bold"),
        )

        # Camera feed
        cam_cx = W // 2
        cam_cy = H // 2 - 60
        cam_r = self._cam_display_size // 2

        frame = self.face_system.get_frame_rgb() if self.face_system else None
        if frame is not None:
            self._render_camera_feed(frame, cam_cx, cam_cy)
        else:
            c.create_oval(
                cam_cx - cam_r,
                cam_cy - cam_r,
                cam_cx + cam_r,
                cam_cy + cam_r,
                fill="#001520",
                outline=C_DIM,
                width=2,
            )
            c.create_text(
                cam_cx,
                cam_cy,
                text="Starting camera...",
                fill=C_DIM,
                font=("Courier", 11),
            )

        # Camera ring
        c.create_oval(
            cam_cx - cam_r - 3,
            cam_cy - cam_r - 3,
            cam_cx + cam_r + 3,
            cam_cy + cam_r + 3,
            outline=C_MID,
            width=2,
        )

        # Instruction text
        instr_y = cam_cy + cam_r + 40
        c.create_text(
            W // 2, instr_y, text=self._enroll_text, fill=C_TEXT, font=("Courier", 11)
        )

        # Progress bar
        if self._enroll_started and not self._enroll_done:
            bar_y = instr_y + 30
            bar_w = 300
            bar_h = 8
            c.create_rectangle(
                W // 2 - bar_w // 2,
                bar_y,
                W // 2 + bar_w // 2,
                bar_y + bar_h,
                fill="#001520",
                outline=C_DIM,
            )
            progress = self._enroll_step / max(self._enroll_total, 1)
            fill_w = int(bar_w * progress)
            c.create_rectangle(
                W // 2 - bar_w // 2,
                bar_y,
                W // 2 - bar_w // 2 + fill_w,
                bar_y + bar_h,
                fill=C_PRI,
                outline="",
            )
            c.create_text(
                W // 2,
                bar_y + 20,
                text=f"Step {self._enroll_step}/{self._enroll_total}",
                fill=C_DIM,
                font=("Courier", 9),
            )

        # Begin button (only before enrollment starts)
        if not self._enroll_started and not self._enroll_done:
            btn_y = instr_y + 60
            btn_w, btn_h = 200, 40
            c.create_rectangle(
                W // 2 - btn_w // 2,
                btn_y - btn_h // 2,
                W // 2 + btn_w // 2,
                btn_y + btn_h // 2,
                fill="#001520",
                outline=C_PRI,
                width=2,
                tags="enroll_btn",
            )
            c.create_text(
                W // 2,
                btn_y,
                text="▸  BEGIN REGISTRATION",
                fill=C_PRI,
                font=("Courier", 11, "bold"),
                tags="enroll_btn",
            )
            c.tag_bind("enroll_btn", "<Button-1>", lambda e: self._begin_enrollment())

        # Done message
        if self._enroll_done:
            done_y = instr_y + 40
            c.create_text(
                W // 2,
                done_y,
                text="✅ REGISTRATION COMPLETE",
                fill=C_GREEN,
                font=("Courier", 14, "bold"),
            )
            c.create_text(
                W // 2,
                done_y + 25,
                text="System will lock in 2 seconds...",
                fill=C_DIM,
                font=("Courier", 9),
            )

        # Tip text
        c.create_text(
            W // 2,
            H - 50,
            text="Wrong camera? Edit config/face_config.py → CAMERA_INDEX",
            fill=C_DIMMER,
            font=("Courier", 8),
        )

        # Footer
        c.create_rectangle(0, H - 28, W, H, fill="#00080d", outline="")
        c.create_line(0, H - 28, W, H - 28, fill=C_DIM, width=1)
        c.create_text(
            W // 2,
            H - 14,
            fill=C_DIM,
            font=("Courier", 8),
            text="FACE ENROLLMENT  ·  LOOK AT CAMERA  ·  FOLLOW PROMPTS",
        )

        self.root.after(50, self._enrollment_render_loop)

    def _begin_enrollment(self):
        """Start enrollment in background thread."""
        if self._enroll_started:
            return
        self._enroll_started = True
        self._enroll_text = "Starting enrollment..."

        def _do_enroll():
            success = self.face_system.enroll_owner(callback=self._enrollment_progress)
            if success:
                self._enroll_done = True
                self._enroll_text = "Registration complete! Set your PIN."
                # Show PIN setup dialog via main thread
                self.root.after(1000, self._prompt_pin)  # type: ignore
            else:
                self._enroll_started = False
                self._enroll_text = "Enrollment failed — try again"

        threading.Thread(target=_do_enroll, daemon=True).start()

    def _prompt_pin(self):
        """Show dialog to set enrollment security PIN."""
        top = tk.Toplevel(self.root)
        top.title("Security PIN")
        top.geometry("300x150")
        top.configure(bg="#00080d")
        top.transient(self.root)
        top.grab_set()

        # Center dialog
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 75
        top.geometry(f"+{x}+{y}")

        tk.Label(
            top,
            text="Set 4-Digit Security PIN\n(Used for re-enrollment)",
            fg=C_ACC,
            bg="#00080d",
            font=("Courier", 10),
        ).pack(pady=10)

        pin_var = tk.StringVar()
        entry = tk.Entry(
            top,
            textvariable=pin_var,
            font=("Courier", 16),
            show="*",
            justify="center",
            width=6,
        )
        entry.pack(pady=10)
        entry.focus()

        def submit(event=None):
            pin = pin_var.get().strip()
            if len(pin) >= 4 and pin.isdigit():
                self.face_system.set_enrollment_pin(pin)
                top.destroy()
                self._enroll_text = "PIN set! Locking system..."
                self.root.after(1000, self._enrollment_to_lock)  # type: ignore
            else:
                pin_var.set("")
                tk.Label(
                    top,
                    text="Invalid PIN (4 digits min)",
                    fg=C_RED,
                    bg="#00080d",
                    font=("Courier", 8),
                ).pack()

        top.bind("<Return>", submit)
        btn = tk.Button(
            top,
            text="SAVE",
            command=submit,
            bg=C_ACC2,
            fg="white",
            font=("Courier", 10, "bold"),
        )
        btn.pack(pady=5)

    def _enrollment_progress(self, step, total, instruction):
        """Callback from face_system.enroll_owner()."""
        self._enroll_step = step
        self._enroll_total = total
        self._enroll_text = instruction

    def _enrollment_to_lock(self):
        """After enrollment, transition to lock screen."""
        self.mode = "LOCKED"
        if self.face_system:
            self.face_system.load_owner()
            self.face_system.reset_auth()
        self._show_lock_screen()

    # ══════════════════════════════════════════
    #  NORMAL JARVIS UI (existing draw code)
    # ══════════════════════════════════════════

    def _animate(self):
        if self.is_locked:
            return  # lock screen has its own loop

        self.tick += 1
        t = self.tick
        now = time.time()

        if now - self.last_t > (0.14 if self.speaking else 0.55):
            if self.speaking:
                self.target_scale = random.uniform(1.05, 1.11)
                self.target_halo = random.uniform(138, 182)
            else:
                self.target_scale = random.uniform(1.001, 1.007)
                self.target_halo = random.uniform(50, 68)
            self.last_t = now

        sp = 0.35 if self.speaking else 0.16
        self.scale += (self.target_scale - self.scale) * sp
        self.halo_a += (self.target_halo - self.halo_a) * sp

        for i, spd in enumerate(
            [1.2, -0.8, 1.9] if self.speaking else [0.5, -0.3, 0.82]
        ):
            self.rings_spin[i] = (self.rings_spin[i] + spd) % 360

        self.scan_angle = (self.scan_angle + (2.8 if self.speaking else 1.2)) % 360
        self.scan2_angle = (self.scan2_angle + (-1.7 if self.speaking else -0.68)) % 360

        pspd = 3.8 if self.speaking else 1.8
        limit = self.FACE_SZ * 0.72
        new_p = [r + pspd for r in self.pulse_r if r + pspd < limit]
        if len(new_p) < 3 and random.random() < (0.06 if self.speaking else 0.022):
            new_p.append(0.0)
        self.pulse_r = new_p

        if t % 40 == 0:
            self.status_blink = not self.status_blink

        self._draw()
        self.root.after(16, self._animate)

    def _draw(self):
        c = self.bg
        W, H = self.W, self.H
        t = self.tick
        FCX = self.FCX
        FCY = self.FCY
        FW = self.FACE_SZ
        c.delete("all")

        for x in range(0, W, 44):
            for y in range(0, H, 44):
                c.create_rectangle(x, y, x + 1, y + 1, fill=C_DIMMER, outline="")

        for r in range(int(FW * 0.54), int(FW * 0.28), -22):
            frac = 1.0 - (r - FW * 0.28) / (FW * 0.26)
            ga = max(0, min(255, int(self.halo_a * 0.09 * frac)))
            gh = f"{ga:02x}"
            c.create_oval(
                FCX - r, FCY - r, FCX + r, FCY + r, outline=f"#00{gh}ff", width=2
            )

        for pr in self.pulse_r:
            pa = max(0, int(220 * (1.0 - pr / (FW * 0.72))))
            r = int(pr)
            c.create_oval(
                FCX - r,
                FCY - r,
                FCX + r,
                FCY + r,
                outline=self._ac(0, 212, 255, pa),
                width=2,
            )

        for idx, (r_frac, w_ring, arc_l, gap) in enumerate(
            [(0.47, 3, 110, 75), (0.39, 2, 75, 55), (0.31, 1, 55, 38)]
        ):
            ring_r = int(FW * r_frac)
            base_a = self.rings_spin[idx]
            a_val = max(0, min(255, int(self.halo_a * (1.0 - idx * 0.18))))
            col = self._ac(0, 212, 255, a_val)
            for s in range(360 // (arc_l + gap)):
                start = (base_a + s * (arc_l + gap)) % 360
                c.create_arc(
                    FCX - ring_r,
                    FCY - ring_r,
                    FCX + ring_r,
                    FCY + ring_r,
                    start=start,
                    extent=arc_l,
                    outline=col,
                    width=w_ring,
                    style="arc",
                )

        sr = int(FW * 0.49)
        scan_a = min(255, int(self.halo_a * 1.4))
        arc_ext = 70 if self.speaking else 42
        c.create_arc(
            FCX - sr,
            FCY - sr,
            FCX + sr,
            FCY + sr,
            start=self.scan_angle,
            extent=arc_ext,
            outline=self._ac(0, 212, 255, scan_a),
            width=3,
            style="arc",
        )
        c.create_arc(
            FCX - sr,
            FCY - sr,
            FCX + sr,
            FCY + sr,
            start=self.scan2_angle,
            extent=arc_ext,
            outline=self._ac(255, 100, 0, scan_a // 2),
            width=2,
            style="arc",
        )

        t_out = int(FW * 0.495)
        t_in = int(FW * 0.472)
        a_mk = self._ac(0, 212, 255, 155)
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 5
            c.create_line(
                FCX + t_out * math.cos(rad),
                FCY - t_out * math.sin(rad),
                FCX + inn * math.cos(rad),
                FCY - inn * math.sin(rad),
                fill=a_mk,
                width=1,
            )

        ch_r = int(FW * 0.50)
        gap = int(FW * 0.15)
        ch_a = self._ac(0, 212, 255, int(self.halo_a * 0.55))
        for x1, y1, x2, y2 in [
            (FCX - ch_r, FCY, FCX - gap, FCY),
            (FCX + gap, FCY, FCX + ch_r, FCY),
            (FCX, FCY - ch_r, FCX, FCY - gap),
            (FCX, FCY + gap, FCX, FCY + ch_r),
        ]:
            c.create_line(x1, y1, x2, y2, fill=ch_a, width=1)

        blen = 22
        bc = self._ac(0, 212, 255, 200)
        hl = FCX - FW // 2
        hr = FCX + FW // 2
        ht = FCY - FW // 2
        hb = FCY + FW // 2
        for bx, by, sdx, sdy in [
            (hl, ht, 1, 1),
            (hr, ht, -1, 1),
            (hl, hb, 1, -1),
            (hr, hb, -1, -1),
        ]:
            c.create_line(bx, by, bx + sdx * blen, by, fill=bc, width=2)
            c.create_line(bx, by, bx, by + sdy * blen, fill=bc, width=2)

        face_pil = self._face_pil  # pyre-ignore
        if self._has_face and face_pil is not None:  # pyre-ignore
            fw = int(FW * self.scale)
            if (
                self._face_scale_cache is None
                or abs(self._face_scale_cache[0] - self.scale) > 0.004
            ):  # pyre-ignore
                scaled = face_pil.resize((fw, fw), Image.BILINEAR)  # pyre-ignore
                tk_img = ImageTk.PhotoImage(scaled)
                self._face_scale_cache = (self.scale, tk_img)  # pyre-ignore
            if self._face_scale_cache is not None:
                c.create_image(FCX, FCY, image=self._face_scale_cache[1])  # pyre-ignore
        else:
            orb_r = int(FW * 0.27 * self.scale)
            for i in range(7, 0, -1):
                r2 = int(orb_r * i / 7)
                frac = i / 7
                ga = max(0, min(255, int(self.halo_a * 1.1 * frac)))
                c.create_oval(
                    FCX - r2,
                    FCY - r2,
                    FCX + r2,
                    FCY + r2,
                    fill=self._ac(0, int(65 * frac), int(120 * frac), ga),
                    outline="",
                )
            c.create_text(
                FCX,
                FCY,
                text=SYSTEM_NAME,
                fill=self._ac(0, 212, 255, min(255, int(self.halo_a * 2))),
                font=("Courier", 14, "bold"),
            )

        HDR = 62
        c.create_rectangle(0, 0, W, HDR, fill="#00080d", outline="")
        c.create_line(0, HDR, W, HDR, fill=C_MID, width=1)
        c.create_text(
            W // 2, 22, text=SYSTEM_NAME, fill=C_PRI, font=("Courier", 18, "bold")
        )
        c.create_text(
            W // 2,
            44,
            text="Just A Rather Very Intelligent System",
            fill=C_MID,
            font=("Courier", 9),
        )
        c.create_text(
            16, 31, text=MODEL_BADGE, fill=C_DIM, font=("Courier", 9), anchor="w"
        )
        c.create_text(
            W - 16,
            31,
            text=time.strftime("%H:%M:%S"),
            fill=C_PRI,
            font=("Courier", 14, "bold"),
            anchor="e",
        )

        sy = FCY + FW // 2 + 45
        if self.speaking:
            stat, sc = "● SPEAKING", C_ACC
        else:
            sym = "●" if self.status_blink else "○"
            stat, sc = f"{sym} {self.status_text}", C_PRI

        c.create_text(W // 2, sy, text=stat, fill=sc, font=("Courier", 11, "bold"))

        wy = sy + 22
        N = 32
        BH = 18
        bw = 8
        total_w = N * bw
        wx0 = (W - total_w) // 2
        for i in range(N):
            if self.speaking:
                hb = random.randint(3, BH)
                col = C_PRI if hb > BH * 0.6 else C_MID
            elif self.mic_active:
                hb = int(3 + 2 * math.sin(t * 0.08 + i * 0.55))
                col = C_DIM
            else:
                hb = 2
                col = C_DIMMER
            bx = wx0 + i * bw
            c.create_rectangle(
                bx, wy + BH - hb, bx + bw - 1, wy + BH, fill=col, outline=""
            )

        # ── Mic toggle button ──
        mic_y = wy + BH + 28
        mic_r = 18
        mic_cx = W // 2
        if self.mic_active:
            c.create_oval(
                mic_cx - mic_r,
                mic_y - mic_r,
                mic_cx + mic_r,
                mic_y + mic_r,
                fill=C_PRI,
                outline=C_PRI,
                width=2,
                tags="mic_btn",
            )
            c.create_rectangle(
                mic_cx - 4,
                mic_y - 9,
                mic_cx + 4,
                mic_y + 1,
                outline="#000000",
                fill="#000000",
                width=1,
                tags="mic_btn",
            )
            c.create_arc(
                mic_cx - 7,
                mic_y - 6,
                mic_cx + 7,
                mic_y + 6,
                start=180,
                extent=180,
                outline="#000000",
                width=2,
                style="arc",
                tags="mic_btn",
            )
            c.create_line(
                mic_cx,
                mic_y + 6,
                mic_cx,
                mic_y + 10,
                fill="#000000",
                width=2,
                tags="mic_btn",
            )
            c.create_text(
                mic_cx,
                mic_y + mic_r + 12,
                text="MIC ON",
                fill=C_PRI,
                font=("Courier", 9, "bold"),
                tags="mic_btn",
            )
        else:
            c.create_oval(
                mic_cx - mic_r,
                mic_y - mic_r,
                mic_cx + mic_r,
                mic_y + mic_r,
                fill="",
                outline=C_RED,
                width=2,
                tags="mic_btn",
            )
            c.create_rectangle(
                mic_cx - 4,
                mic_y - 9,
                mic_cx + 4,
                mic_y + 1,
                outline=C_RED,
                fill="",
                width=1,
                tags="mic_btn",
            )
            c.create_arc(
                mic_cx - 7,
                mic_y - 6,
                mic_cx + 7,
                mic_y + 6,
                start=180,
                extent=180,
                outline=C_RED,
                width=2,
                style="arc",
                tags="mic_btn",
            )
            c.create_line(
                mic_cx,
                mic_y + 6,
                mic_cx,
                mic_y + 10,
                fill=C_RED,
                width=2,
                tags="mic_btn",
            )
            c.create_line(
                mic_cx - 8,
                mic_y + 10,
                mic_cx + 8,
                mic_y - 10,
                fill=C_RED,
                width=2,
                tags="mic_btn",
            )
            c.create_text(
                mic_cx,
                mic_y + mic_r + 12,
                text="MIC OFF",
                fill=C_RED,
                font=("Courier", 9, "bold"),
                tags="mic_btn",
            )

        c.tag_bind("mic_btn", "<Button-1>", lambda e: self._safe_toggle_mic())

        c.create_rectangle(0, H - 28, W, H, fill="#00080d", outline="")
        c.create_line(0, H - 28, W, H - 28, fill=C_DIM, width=1)
        c.create_text(
            W // 2,
            H - 14,
            fill=C_DIM,
            font=("Courier", 8),
            text="ROHAN Industries  ·  CLASSIFIED  ·  MARK XXX",
        )

    # ══════════════════════════════════════════
    #  PUBLIC API (existing methods preserved)
    # ══════════════════════════════════════════

    def write_log(self, text: str):
        self.typing_queue.append(text)
        tl = text.lower()
        self.status_text = (
            "PROCESSING"
            if tl.startswith("you:")
            else "RESPONDING"
            if tl.startswith("ai:")
            else self.status_text
        )
        if not self.is_typing:
            self._start_typing()

    def _start_typing(self):
        if not self.typing_queue:
            self.is_typing = False
            if not self.speaking:
                self.status_text = "ONLINE"
            return
        self.is_typing = True
        text = self.typing_queue.popleft()
        tl = text.lower()
        tag = (
            "you" if tl.startswith("you:") else "ai" if tl.startswith("ai:") else "sys"
        )
        self.log_text.configure(state="normal")
        self._type_char(text, 0, tag)

    def _type_char(self, text, i, tag):
        if i < len(text):
            self.log_text.insert(tk.END, text[i], tag)
            self.log_text.see(tk.END)
            self.root.after(8, self._type_char, text, i + 1, tag)  # type: ignore
        else:
            self.log_text.insert(tk.END, "\n")
            self.log_text.configure(state="disabled")
            self.root.after(25, self._start_typing)  # type: ignore

    def start_speaking(self):
        if self.is_locked:
            return
        self.speaking = True
        self.status_text = "SPEAKING"

    def stop_speaking(self):
        if self.is_locked:
            return
        self.speaking = False
        self.status_text = "LISTENING" if self.mic_active else "ONLINE"

    def toggle_mic(self):
        self.mic_active = not self.mic_active
        if self.mic_active:
            self.status_text = "LISTENING"
        else:
            self.status_text = "ONLINE"

    def is_mic_active(self):
        return self.mic_active

    def _api_keys_exist(self):
        return API_FILE.exists()

    def wait_for_api_key(self):
        """Block until API key is saved (called from main thread before starting JARVIS).

        Uses threading.Event for non-blocking synchronization.
        """
        if self._api_key_ready:
            return
        # Wait with timeout to allow periodic checking and clean shutdown
        while not self._api_key_ready:
            # Wait for the event with timeout, then check again
            # This allows graceful exit if needed
            self._api_key_event.wait(timeout=0.5)

    def _show_setup_ui(self):
        self.setup_frame = tk.Frame(
            self.root, bg="#00080d", highlightbackground=C_PRI, highlightthickness=1
        )  # type: ignore
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center")  # type: ignore

        tk.Label(
            self.setup_frame,
            text="◈  INITIALISATION REQUIRED",
            fg=C_PRI,
            bg="#00080d",
            font=("Courier", 13, "bold"),
        ).pack(pady=(18, 4))
        tk.Label(
            self.setup_frame,
            text="Enter your Gemini API key to boot J.A.R.V.I.S.",
            fg=C_MID,
            bg="#00080d",
            font=("Courier", 9),
        ).pack(pady=(0, 10))

        tk.Label(
            self.setup_frame,
            text="GEMINI API KEY",
            fg=C_DIM,
            bg="#00080d",
            font=("Courier", 9),
        ).pack(pady=(8, 2))
        self.gemini_entry = tk.Entry(
            self.setup_frame,
            width=52,
            fg=C_TEXT,
            bg="#000d12",
            insertbackground=C_TEXT,
            borderwidth=0,
            font=("Courier", 10),
            show="*",
        )  # type: ignore
        self.gemini_entry.pack(pady=(0, 4))  # type: ignore

        tk.Button(
            self.setup_frame,
            text="▸  INITIALISE SYSTEMS",
            command=self._save_api_keys,
            bg=C_BG,
            fg=C_PRI,
            activebackground="#003344",
            font=("Courier", 10),
            borderwidth=0,
            pady=8,
        ).pack(pady=14)

    def _save_api_keys(self):
        gemini_entry = self.gemini_entry
        assert gemini_entry is not None
        gemini = gemini_entry.get().strip()
        if not gemini:
            return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(API_FILE, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": gemini}, f, indent=4)
        setup_frame = self.setup_frame
        assert setup_frame is not None
        setup_frame.destroy()
        self._api_key_ready = True
        self._api_key_event.set()  # Signal the event (non-blocking wakeup)
        self.status_text = "ONLINE"
        self.write_log("SYS: Systems initialised. JARVIS online.")
