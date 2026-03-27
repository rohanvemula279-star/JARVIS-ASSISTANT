# pyre-ignore-all-errors
"""
Face Authentication Configuration
All constants for the face auth security gate.

SECURITY NOTE: This is NOT equivalent to FaceID-grade security.
Geometric ratio matching provides deterrent-level locking suitable
for personal use. A video of the owner blinking may bypass blink
detection — this is a known limitation.
"""

import cv2  # pyre-ignore
from pathlib import Path

# Project root (two levels up from config/face_config.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ──── CAMERA ────
CAMERA_INDEX = 0
CAMERA_BACKEND = cv2.CAP_DSHOW        # Windows DirectShow; use cv2.CAP_ANY for cross-platform
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# ──── DETECTION TIMING (time-based, decoupled from FPS) ────
DETECTION_INTERVAL_MS = 150            # Run face detection every ~150ms (~6.7/sec)
IDENTITY_CHECK_INTERVAL_MS = 150       # Run identity comparison every 150ms (~6.7/sec)
PROCESS_SCALE = 0.5                    # Downscale to 50% for faster MediaPipe

# ──── MATCHING / SECURITY ────
OWNER_SIGNATURE_PATH = str(_PROJECT_ROOT / "data" / "authorized_faces" / "owner_signature.npy")
OWNER_HASH_PATH      = str(_PROJECT_ROOT / "data" / "authorized_faces" / "owner_signature.sha256")

# ──── DEEP EMBEDDING (SFace) ────
SFACE_MODEL_PATH = str(_PROJECT_ROOT / "models" / "face_recognition_sface_2021dec.onnx")
OWNER_EMBEDDING_PATH = str(_PROJECT_ROOT / "data" / "authorized_faces" / "owner_embedding.npy")
OWNER_EMBEDDING_HASH_PATH = str(_PROJECT_ROOT / "data" / "authorized_faces" / "owner_embedding.sha256")
EMBEDDING_DIM = 128                    # SFace output dimensionality
EMBEDDING_SIMILARITY_METHOD = 1        # 0=L2, 1=Cosine (use cosine)

# ──── BLINK LIVENESS ────
REQUIRE_BLINK_FOR_AUTH = False          # Require blink before granting
BLINK_EAR_THRESHOLD = 0.21             # EAR below this = blink detected
BLINK_DETECTION_WINDOW = 5.0           # Seconds to detect a blink
MIN_BLINKS_REQUIRED = 1                # Must detect at least 1 blink

# ──── AUTH TIMING ────
AUTH_TIMEOUT = 10.0                    # Max seconds for full auth attempt
COOLDOWN_AFTER_FAILURE = 3.0           # Wait time after failed attempt

# Adaptive threshold calibration (tuned for 128-dim deep embeddings)
SIMILARITY_THRESHOLD = 0.75            # Required for unlock (was 0.85)
ADAPTIVE_THRESHOLD = True              # Auto-calibrate based on enrollment samples
CALIBRATION_FILE = str(_PROJECT_ROOT / "data" / "authorized_faces" / "calibration.json")
CALIBRATION_MARGIN = 2.0               # Standard deviations below self-match mean
MIN_THRESHOLD = 0.76                   # Floor — adjusted for 0.80 main threshold
MAX_THRESHOLD = 0.95                   # Ceiling (usability maximum)

# Strict mode with rolling window (more forgiving than consecutive)
STRICT_MODE = True                     # ENABLED: Require high-quality matches
MATCH_WINDOW_SIZE = 5                  # Analyze last 5 quality frames
MATCH_WINDOW_REQUIRED = 3              # Need 3/5 matches
FRAME_QUALITY_GATE = True              # Only count high-quality frames

MAX_FAILED_ATTEMPTS = 5                # Before extended cooldown
LOCKOUT_DURATION = 1                   # Seconds (reduced from 30)
MIN_LANDMARK_CONFIDENCE = 0.75         # Lowered to 0.75 for speed



# Tier 1 thresholds (instant unlock)
TIER1_MIN_CONFIDENCE = 0.80
# Tier 2 thresholds (standard unlock)
TIER2_MIN_CONFIDENCE = 0.75
# Tier 3 triggers (challenge required)
TIER3_TRIGGERS = [
    "borderline_match",
    "borderline_texture",
    "unusual_lighting",
    "recent_failure",
    "long_absence",
]
LONG_ABSENCE_HOURS = 4

# ──── PIN SECURITY ────
ENROLLMENT_PIN_HASH_PATH = str(_PROJECT_ROOT / "data" / "authorized_faces" / "enrollment_pin.sha256")
PIN_LENGTH = 6                         # Upgraded from 4 (1M combinations instead of 10K)
PIN_MAX_ATTEMPTS = 3                   # Failed attempts before lockout
PIN_LOCKOUT_SECONDS = 300              # 5 minute lockout

# ──── ENROLLMENT (REVISED) ────
# Sample distribution (27 total):
ENROLLMENT_STRAIGHT_SAMPLES = 8        # PRIMARY pose (most common unlock)
ENROLLMENT_LEFT_SAMPLES = 4            # Left turn ~15-20°
ENROLLMENT_RIGHT_SAMPLES = 4           # Right turn ~15-20°
ENROLLMENT_UP_SAMPLES = 3              # Up tilt ~10-15°
ENROLLMENT_DOWN_SAMPLES = 3            # Down tilt ~10-15°
ENROLLMENT_SMILE_SAMPLES = 3           # Expression variation (NEW)
ENROLLMENT_BLINK_SAMPLES = 3           # Blink verification (NEW)
ENROLLMENT_TOTAL_SAMPLES = 28          # Total to capture

ENROLLMENT_DELAY = 0.5                 # Seconds between captures
ENROLLMENT_MIN_CONFIDENCE = 0.90       # High-quality enrollment captures only
ENROLLMENT_MIN_YAW_RANGE = 10.0        # Degree requirement
ENROLLMENT_QUALITY_THRESHOLD = 0.80    # Overall enrollment quality score required
ENROLLMENT_MIN_PASS_RATE = 0.81        # 22/27 samples must pass quality gate

# ──── SESSION MANAGEMENT ────
SESSION_TRUST_ENABLED = True           # NEW: Progressive trust tiers
INSTANT_RELOCK_WINDOW = 30             # Seconds (Tier 0: instant re-unlock)
QUICK_UNLOCK_WINDOW = 300              # 5 minutes (Tier 1: 1 blink only)
STANDARD_UNLOCK_WINDOW = 14400         # 4 hours (Tier 2: standard checks)
SESSION_FILE = str(_PROJECT_ROOT / "data" / "authorized_faces" / "session.json")

AUTO_LOCK_TIMEOUT = 45                 # Seconds without activity → auto-lock
INTRUDER_INSTANT_LOCK = True           # Lock immediately on stranger detection

# ──── AUDIT & LOGGING ────
AUDIT_LOGGING_ENABLED = True           # NEW: Log all unlock attempts
AUDIT_LOG_DIR = str(_PROJECT_ROOT / "data" / "audit_logs")
AUDIT_RETENTION_DAYS = 90              # Auto-delete logs older than this

# ──── UI ────
SESSION_POLL_INTERVAL_MS = 2000        # UI polls session state every 2s

# ──── COLORS ────
HUD_CYAN = "#00FFFF"
HUD_GREEN = "#00FF00"
HUD_RED = "#FF3333"
HUD_YELLOW = "#FFCC00"
HUD_DIM = "#003344"
LOCK_BG = "#000000"

# ──── BACKWARD COMPATIBILITY ────
# Old variable names (for existing code like face_auth.py)
STRICT_CONSECUTIVE_REQUIRED = MATCH_WINDOW_REQUIRED  # Old name (now rolling window)
STRICT_WINDOW = MATCH_WINDOW_SIZE                     # Old name
ENROLLMENT_SAMPLES = ENROLLMENT_TOTAL_SAMPLES         # Old name

# ──── ANIMATION ────
LOCK_SCREEN_REFRESH_MS = 50            # Lock screen redraws at ~20 FPS
UNLOCK_ANIMATION_FRAMES = 30
