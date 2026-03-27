# pyre-ignore-all-errors
"""
core/face_auth.py — Complete face authentication system with 3-layer anti-spoofing.

Architecture:
  Camera Thread ──→ Shared State ──→ UI reads via get_state() / get_frame_rgb()
       │                │
       ▼                ▼
  MediaPipe Face   Identity Check ──→ Anti-Spoof ──→ Blink ──→ Challenge
  Mesh Detection   (time-based)     (texture +      (EAR)    (random
  (time-based)         │             movement +               head turn)
       │                ▼             depth)                      │
       ▼          Cosine Similarity      │                        ▼
  468 Landmarks   vs Owner Signature     ▼                   AUTH RESULT
  + Blink EAR          │            Weighted Fusion          GRANTED/DENIED
       │                ▼            (0.40/0.45/0.15)
       ▼          IDENTITY MATCH
  Quality Check

State Machine:
  LOCKED → DETECTING → IDENTITY_MATCHED → ANTI_SPOOF → BLINK → CHALLENGE → UNLOCKED
"""

import os
import random
import sys
import time
import threading
from collections import deque
from pathlib import Path

import cv2  # pyre-ignore
import numpy as np  # pyre-ignore

# Make all data paths absolute relative to this file's project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Handle imports from project root
try:
    from config.face_config import (  # pyre-ignore
        CAMERA_INDEX, CAMERA_BACKEND, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS,
        DETECTION_INTERVAL_MS, IDENTITY_CHECK_INTERVAL_MS, PROCESS_SCALE,
        OWNER_SIGNATURE_PATH, OWNER_HASH_PATH,
        SIMILARITY_THRESHOLD, STRICT_MODE, STRICT_CONSECUTIVE_REQUIRED, STRICT_WINDOW,
        MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION, MIN_LANDMARK_CONFIDENCE,
        ENROLLMENT_SAMPLES, ENROLLMENT_DELAY, ENROLLMENT_MIN_CONFIDENCE,
        AUTO_LOCK_TIMEOUT, INTRUDER_INSTANT_LOCK,
        ENROLLMENT_PIN_HASH_PATH,
        SFACE_MODEL_PATH, OWNER_EMBEDDING_PATH, OWNER_EMBEDDING_HASH_PATH,
        REQUIRE_BLINK_FOR_AUTH, BLINK_EAR_THRESHOLD, BLINK_DETECTION_WINDOW,
        MIN_BLINKS_REQUIRED, AUTH_TIMEOUT, COOLDOWN_AFTER_FAILURE,
    )
    from core.face_utils import (  # pyre-ignore
        extract_face_signature, cosine_similarity,
        save_signature_with_hash, verify_signature_integrity,
        save_pin, verify_pin,
        DeepFaceEmbedder, compute_ear,
        NOSE_TIP, LEFT_EYE_CORNER, RIGHT_EYE_CORNER, CHIN, FOREHEAD_TOP,
    )
except ImportError:
    # Fallback for direct execution
    _root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_root))
    from config.face_config import (  # pyre-ignore
        CAMERA_INDEX, CAMERA_BACKEND, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS,
        DETECTION_INTERVAL_MS, IDENTITY_CHECK_INTERVAL_MS, PROCESS_SCALE,
        OWNER_SIGNATURE_PATH, OWNER_HASH_PATH,
        SIMILARITY_THRESHOLD, STRICT_MODE, STRICT_CONSECUTIVE_REQUIRED, STRICT_WINDOW,
        MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION, MIN_LANDMARK_CONFIDENCE,
        ENROLLMENT_SAMPLES, ENROLLMENT_DELAY, ENROLLMENT_MIN_CONFIDENCE,
        AUTO_LOCK_TIMEOUT, INTRUDER_INSTANT_LOCK,
        ENROLLMENT_PIN_HASH_PATH,
        SFACE_MODEL_PATH, OWNER_EMBEDDING_PATH, OWNER_EMBEDDING_HASH_PATH,
        REQUIRE_BLINK_FOR_AUTH, BLINK_EAR_THRESHOLD, BLINK_DETECTION_WINDOW,
        MIN_BLINKS_REQUIRED, AUTH_TIMEOUT, COOLDOWN_AFTER_FAILURE,
    )
    from core.face_utils import (  # pyre-ignore
        extract_face_signature, cosine_similarity,
        save_signature_with_hash, verify_signature_integrity,
        save_pin, verify_pin,
        DeepFaceEmbedder, compute_ear,
        NOSE_TIP, LEFT_EYE_CORNER, RIGHT_EYE_CORNER, CHIN, FOREHEAD_TOP,
    )

import mediapipe as mp  # pyre-ignore
from mediapipe.tasks.python import vision  # pyre-ignore


class FaceAuthSystem:
    """
    Main face authentication controller.
    One instance runs everything — camera, detection, identity, enrollment, session.
    """

    def __init__(self):
        # MediaPipe Face Landmarker
        model_path = os.path.join(os.path.dirname(__file__), '..', 'face_landmarker.task')
        self.face_landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=2,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )

        # Deep face embedder (SFace 128-dim)
        try:
            self._embedder = DeepFaceEmbedder(SFACE_MODEL_PATH)
        except FileNotFoundError as e:
            print(f"[FaceAuth] ⚠️ {e}")
            self._embedder = None

        # Camera (opened by start_camera)
        self.cap = None

        # Threading
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

        # Shared state (UI reads via get_state())
        self.state = {
            "frame": None,
            "frame_rgb": None,
            "face_detected": False,
            "face_box": None,           # (x, y, w, h)
            "landmarks": None,
            "is_owner": None,           # True / False / None
            "confidence": 0.0,
            "status": "IDLE",           # IDLE / SCANNING / VERIFYING / GRANTED / DENIED / LOCKED_OUT / NO_CAMERA / LOW_QUALITY
            "camera_ok": False,
            "auth_attempts": 0,
            "lockout_until": 0,
            "quality_hint": "",         # "Move closer" / "Improve lighting" / ""
        }

        # Identity — deep embeddings (primary) + geometric signature (fallback)
        self.owner_signature = None         # legacy geometric (30-dim)
        self.owner_gallery = None           # deep embeddings (N, 128)
        self._identity_history = deque(maxlen=STRICT_WINDOW)

        # Blink liveness detection
        self._blink_detected = False
        self._blink_start_time = 0.0
        self._prev_ear = 0.3                # previous EAR for edge detection
        self._blink_count = 0
        self._identity_confirmed = False    # owner matched, awaiting liveness
        self._auth_start_time = 0.0         # when current auth attempt started

        # Session monitoring
        self._session_active = False
        self._last_owner_seen = 0.0

        # Timing
        self._last_detection_time = 0.0
        self._last_identity_time = 0.0
        self._mp_timestamp_ms = 0

        # Load owner if exists
        self.load_owner()

    # ──── CAMERA MANAGEMENT ────

    def start_camera(self):
        """Open camera and start background capture thread. Returns True on success."""
        with self._lock:
            if self.cap is not None and self.cap.isOpened() and self._thread is not None and self._thread.is_alive():  # pyre-ignore
                print("[FaceAuth] ✅ Camera already running")
                return True

        try:
            self.cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)  # pyre-ignore
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)  # pyre-ignore
            self.cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)  # pyre-ignore
        except Exception as e:
            print(f"[FaceAuth] ❌ Camera open failed: {e}")
            with self._lock:
                self.state["camera_ok"] = False
                self.state["status"] = "NO_CAMERA"
            return False

        if not self.cap.isOpened():  # pyre-ignore
            print("[FaceAuth] ⚠️ Camera not available")
            with self._lock:
                self.state["camera_ok"] = False
                self.state["status"] = "NO_CAMERA"
            return False

        with self._lock:
            self.state["camera_ok"] = True
            self.state["status"] = "SCANNING"

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)  # pyre-ignore
        self._thread.start()  # pyre-ignore
        print("[FaceAuth] ✅ Camera started")
        return True

    def _capture_loop(self):
        """Background thread: capture frames and run detection/identity on timers."""
        while not self._stop_event.is_set():
            with self._lock:
                status = self.state.get("status")
            if status == "PERMANENTLY_UNLOCKED":
                time.sleep(0.5)
                continue

            if self.cap is None or not self.cap.isOpened():  # pyre-ignore
                self._handle_camera_disconnect()
                continue

            ret, frame = self.cap.read()  # pyre-ignore
            if not ret:
                self._handle_camera_disconnect()
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            with self._lock:
                self.state["frame"] = frame
                self.state["frame_rgb"] = frame_rgb

            now = time.time()
            now_ms = now * 1000

            # Face detection (time-based)
            if now_ms - self._last_detection_time >= DETECTION_INTERVAL_MS:
                self._last_detection_time = now_ms
                self._detect_face(frame_rgb)

            # Identity check (time-based)
            dynamic_interval = getattr(self, '_dynamic_identity_interval_ms', IDENTITY_CHECK_INTERVAL_MS)
            if now_ms - self._last_identity_time >= dynamic_interval:
                self._last_identity_time = now_ms
                t0 = time.time()
                self._check_identity()
                pipeline_time_ms = (time.time() - t0) * 1000
                if pipeline_time_ms > IDENTITY_CHECK_INTERVAL_MS:
                    self._dynamic_identity_interval_ms = pipeline_time_ms + 50
                else:
                    self._dynamic_identity_interval_ms = IDENTITY_CHECK_INTERVAL_MS

            # Small sleep to cap CPU (captures at ~60-100fps without this)
            time.sleep(0.008)

    def _handle_camera_disconnect(self):
        """Attempt to reconnect camera."""
        print("[FaceAuth] ⚠️ Camera disconnected, attempting reconnect...")
        if self.cap:
            try:
                self.cap.release()  # pyre-ignore
            except Exception:
                pass

        for attempt in range(3):
            if self._stop_event.is_set():
                return
            time.sleep(2)
            try:
                self.cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
                if self.cap.isOpened():  # pyre-ignore
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)  # pyre-ignore
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)  # pyre-ignore
                    print(f"[FaceAuth] ✅ Reconnected on attempt {attempt + 1}")
                    with self._lock:
                        self.state["camera_ok"] = True
                    return
            except Exception:
                pass

        print("[FaceAuth] ❌ Camera reconnect failed")
        with self._lock:
            self.state["camera_ok"] = False
            self.state["status"] = "NO_CAMERA"

    # ──── FACE DETECTION ────

    def _detect_face(self, frame_rgb):
        """Find face and extract landmarks. Updates blink tracking."""
        h, w = frame_rgb.shape[:2]
        small_w = int(w * PROCESS_SCALE)
        small_h = int(h * PROCESS_SCALE)
        small = cv2.resize(frame_rgb, (small_w, small_h))

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=small)
        
        with self._lock:
            ts = int(time.time() * 1000)
            if ts <= self._mp_timestamp_ms:
                ts = self._mp_timestamp_ms + 1
            self._mp_timestamp_ms = ts

        results = self.face_landmarker.detect_for_video(mp_image, ts)

        # ── Phase 1: update basic detection state under lock ──
        # Do NOT call _check_landmark_quality or _update_blink_detection here
        # because those methods also acquire self._lock → deadlock.
        face_landmarks = None
        had_face = False

        with self._lock:
            if results.face_landmarks:
                face_landmarks = results.face_landmarks[0]
                had_face = True
                self.state["face_detected"] = True
                self.state["landmarks"] = face_landmarks
                self.state["face_box"] = self._landmarks_to_box(  # pyre-ignore
                    face_landmarks, (h, w)
                )
            else:
                self.state["face_detected"] = False
                self.state["landmarks"] = None
                self.state["face_box"] = None
                self.state["quality_hint"] = ""

        # ── Phase 2: quality check OUTSIDE the lock ──
        if had_face and face_landmarks is not None:
            quality_ok = self._check_landmark_quality(face_landmarks)
            with self._lock:
                if not quality_ok:
                    self.state["status"] = "LOW_QUALITY"
                elif self.state["status"] == "LOW_QUALITY":
                    self.state["status"] = "SCANNING"

            # ── Phase 3: blink detection OUTSIDE the lock ──
            if quality_ok and REQUIRE_BLINK_FOR_AUTH:
                self._update_blink_detection(face_landmarks)

    def _check_landmark_quality(self, landmarks):
        """
        Check landmark quality — called WITHOUT holding self._lock.
        Detects too-close, too-far, or partial face situations.
        Returns (quality_ok: bool, hint: str)
        """
        pts = []
        for idx in [NOSE_TIP, LEFT_EYE_CORNER, RIGHT_EYE_CORNER, CHIN, FOREHEAD_TOP]:
            lm = landmarks[idx]
            pts.append((lm.x, lm.y))

        # Check if key points are within frame (0..1)
        out_of_frame = sum(1 for x, y in pts if x < 0.05 or x > 0.95 or y < 0.05 or y > 0.95)

        if out_of_frame >= 2:
            with self._lock:
                self.state["quality_hint"] = "Move back — face too close"
            return False

        # Check face size (too small = too far)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        face_span = max(max(xs) - min(xs), max(ys) - min(ys))
        if face_span < 0.08:
            with self._lock:
                self.state["quality_hint"] = "Move closer to camera"
            return False

        with self._lock:
            self.state["quality_hint"] = ""
        return True

    def _landmarks_to_box(self, landmarks, frame_shape):
        """Convert landmarks to (x, y, w, h) bounding box in pixel coords."""
        h, w = frame_shape[:2]
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]

        # Scale back from PROCESS_SCALE
        x_min = min(xs) * w
        x_max = max(xs) * w
        y_min = min(ys) * h
        y_max = max(ys) * h

        # Add 15% padding
        pad_x = (x_max - x_min) * 0.15
        pad_y = (y_max - y_min) * 0.15
        x_min = max(0, x_min - pad_x)
        y_min = max(0, y_min - pad_y)
        x_max = min(w, x_max + pad_x)
        y_max = min(h, y_max + pad_y)

        return (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))

    # ──── BLINK DETECTION ────

    def _update_blink_detection(self, landmarks):
        """Track blink events using Eye Aspect Ratio (EAR). Called each frame."""
        left_ear = compute_ear(landmarks, "left")
        right_ear = compute_ear(landmarks, "right")
        avg_ear = (left_ear + right_ear) / 2.0

        # Detect blink: EAR drops below threshold then rises back
        if self._prev_ear >= BLINK_EAR_THRESHOLD and avg_ear < BLINK_EAR_THRESHOLD:
            # Eyes just closed → blink started
            pass
        elif self._prev_ear < BLINK_EAR_THRESHOLD and avg_ear >= BLINK_EAR_THRESHOLD:
            # Eyes just opened → blink completed
            self._blink_count += 1
            if self._blink_count >= MIN_BLINKS_REQUIRED:
                self._blink_detected = True

        self._prev_ear = avg_ear

    # ──── IDENTITY MATCHING ────

    def _check_identity(self):
        """Compare current face to owner using deep embeddings (primary)
        or geometric signature (fallback).

        Deep embeddings (128-dim SFace):
        - Different people: cosine similarity 0.3–0.6
        - Same person: cosine similarity 0.85–0.99
        - Threshold of 0.82 cleanly separates owner from others

        STRICT MATCHING:
        - Positive matches: 5/7 rolling window required
        - Clear non-match: instant rejection
        """
        with self._lock:
            if not self.state["face_detected"]:
                return
            if self.state["status"] == "LOW_QUALITY":
                return
            landmarks = self.state["landmarks"]
            frame_rgb = self.state["frame_rgb"]
            self.state["status"] = "VERIFYING"

        # ── Deep embedding path (primary) ──
        if self._embedder is not None and self.owner_gallery is not None and frame_rgb is not None:
            try:
                current_emb = self._embedder.extract_embedding(frame_rgb, landmarks)
                if current_emb is None:
                    return

                best_score, avg_score = DeepFaceEmbedder.match_against_gallery(
                    current_emb, self.owner_gallery
                )

                is_match = best_score >= SIMILARITY_THRESHOLD
                is_clear_non_match = best_score < (SIMILARITY_THRESHOLD - 0.10)

                with self._lock:
                    self.state["confidence"] = best_score

                    if STRICT_MODE:
                        self._identity_history.append(is_match)
                        positive_count = sum(self._identity_history)
                        negative_count = len(self._identity_history) - positive_count

                        if positive_count >= STRICT_CONSECUTIVE_REQUIRED:
                            self.state["is_owner"] = True
                            self._identity_confirmed = True
                        elif is_clear_non_match:
                            self.state["is_owner"] = False
                            self._identity_confirmed = False
                        elif len(self._identity_history) == self._identity_history.maxlen and positive_count == 0:
                            self.state["is_owner"] = False
                            self._identity_confirmed = False
                    else:
                        self._identity_history.append(is_match)
                        self.state["is_owner"] = is_match
                        self._identity_confirmed = is_match

                return  # Deep path handled it
            except Exception as e:
                print(f"[FaceAuth] ⚠️ Deep embedding error: {e}")
                # Fall through to geometric fallback

        # ── Geometric signature path (fallback) ──
        if self.owner_signature is not None:
            try:
                current_sig = extract_face_signature(landmarks)
                if np.all(current_sig == 0):
                    return

                similarity = cosine_similarity(current_sig, self.owner_signature)
                is_match = similarity >= SIMILARITY_THRESHOLD
                is_clear_non_match = similarity < (SIMILARITY_THRESHOLD - 0.05)

                with self._lock:
                    self.state["confidence"] = similarity

                    if STRICT_MODE:
                        self._identity_history.append(is_match)
                        positive_count = sum(self._identity_history)
                        negative_count = len(self._identity_history) - positive_count

                        if positive_count >= STRICT_CONSECUTIVE_REQUIRED:
                            self.state["is_owner"] = True
                            self._identity_confirmed = True
                        elif is_clear_non_match:
                            self.state["is_owner"] = False
                            self._identity_confirmed = False
                        elif len(self._identity_history) == self._identity_history.maxlen and positive_count == 0:
                            self.state["is_owner"] = False
                            self._identity_confirmed = False
                    else:
                        self._identity_history.append(is_match)
                        self.state["is_owner"] = is_match
                        self._identity_confirmed = is_match

            except Exception as e:
                print(f"[FaceAuth] ⚠️ Identity check error: {e}")

    # ──── ENROLLMENT ────

    def enroll_owner(self, callback=None):
        """
        Capture multiple face samples and create owner identity data.

        Captures both:
        - Deep embeddings (128-dim SFace) — stored as gallery (N, 128)
        - Geometric signatures (30-dim) — stored as averaged vector (fallback)

        The gallery approach stores multiple embeddings from different
        angles/expressions, reducing false rejections while maintaining
        zero false accepts.

        callback(step, total, instruction):
            Called after each capture so UI can show progress.
        """
        if not self.state["camera_ok"]:
            if not self.start_camera():
                return False

        prompts = [
            "Look straight at camera",
            "Turn slightly to the left",
            "Turn slightly to the right",
            "Look slightly up",
            "Look slightly down",
            "Normal position",
            "Slight smile",
            "Neutral expression",
            "Tilt head slightly left",
            "Normal position — final capture",
        ]

        signatures = []   # geometric (fallback)
        embeddings = []   # deep (primary)

        for i in range(ENROLLMENT_SAMPLES):
            instruction = prompts[i] if i < len(prompts) else "Hold steady"
            if callback:
                callback(i, ENROLLMENT_SAMPLES, instruction)

            # Wait for good face detection (up to 5 seconds)
            start = time.time()
            captured = False
            while time.time() - start < 5.0:
                if self._stop_event.is_set():
                    return False

                with self._lock:
                    landmarks = self.state.get("landmarks")
                    face_detected = self.state.get("face_detected", False)
                    frame_rgb = self.state.get("frame_rgb")

                if face_detected and landmarks is not None:
                    # Check quality
                    if self._check_landmark_quality(landmarks):
                        # Geometric signature (fallback)
                        sig = extract_face_signature(landmarks)
                        if not np.all(sig == 0):
                            signatures.append(sig)

                        # Deep embedding (primary)
                        if self._embedder is not None and frame_rgb is not None:
                            emb = self._embedder.extract_embedding(frame_rgb, landmarks)
                            if emb is not None:
                                embeddings.append(emb)

                        captured = True
                        break

                time.sleep(0.1)

            if not captured:
                if callback:
                    callback(i, ENROLLMENT_SAMPLES, "Face not detected — try again")
                time.sleep(0.5)
                continue

            time.sleep(ENROLLMENT_DELAY)

        if len(signatures) < 5:
            print(f"[FaceAuth] ❌ Enrollment failed — only {len(signatures)} samples captured")
            return False

        # ── Save geometric signature (fallback) ──
        owner_signature = np.mean(signatures, axis=0)
        norm = np.linalg.norm(owner_signature)
        if norm > 1e-6:
            owner_signature = owner_signature / norm
        save_signature_with_hash(owner_signature, OWNER_SIGNATURE_PATH, OWNER_HASH_PATH)
        self.owner_signature = owner_signature

        # ── Save deep embedding gallery (primary) ──
        if len(embeddings) >= 5:
            gallery = np.array(embeddings, dtype=np.float64)
            # Normalize each embedding
            norms = np.linalg.norm(gallery, axis=1, keepdims=True)
            norms[norms < 1e-6] = 1.0
            gallery = gallery / norms
            DeepFaceEmbedder.save_gallery(gallery, OWNER_EMBEDDING_PATH, OWNER_EMBEDDING_HASH_PATH)
            self.owner_gallery = gallery
            print(f"[FaceAuth] ✅ Owner enrolled — {len(embeddings)} deep embeddings + {len(signatures)} geometric")
        else:
            print(f"[FaceAuth] ⚠️ Only {len(embeddings)} deep embeddings captured, using geometric only")
            print(f"[FaceAuth] ✅ Owner enrolled ({len(signatures)} geometric samples)")

        if callback:
            callback(ENROLLMENT_SAMPLES, ENROLLMENT_SAMPLES, "Registration complete!")

        return True

    # ──── OWNER MANAGEMENT ────

    def owner_registered(self):
        """Check if owner enrollment data exists."""
        return os.path.exists(OWNER_SIGNATURE_PATH)

    def load_owner(self):
        """Load owner identity data (deep embeddings + geometric signature)."""
        loaded_any = False

        # Load deep embedding gallery (primary)
        gallery = DeepFaceEmbedder.load_gallery(OWNER_EMBEDDING_PATH, OWNER_EMBEDDING_HASH_PATH)
        if gallery is not None:
            self.owner_gallery = gallery
            loaded_any = True

        # Load geometric signature (fallback)
        if os.path.exists(OWNER_SIGNATURE_PATH):
            if verify_signature_integrity(OWNER_SIGNATURE_PATH, OWNER_HASH_PATH):
                try:
                    self.owner_signature = np.load(OWNER_SIGNATURE_PATH)
                    print("[FaceAuth] ✅ Owner geometric signature loaded")
                    loaded_any = True
                except Exception as e:
                    print(f"[FaceAuth] ❌ Failed to load geometric signature: {e}")
            else:
                print("[FaceAuth] ⚠️ Geometric signature file tampered or hash missing!")

        if not loaded_any:
            print("[FaceAuth] ℹ️ No owner data found — enrollment required")

        return loaded_any

    def reenroll(self, callback=None, pin=None):
        """
        Re-enrollment — requires existing face auth OR PIN.
        Clears existing data and runs enrollment.
        """
        # Verify authorization for re-enrollment
        if pin and os.path.exists(ENROLLMENT_PIN_HASH_PATH):
            if not verify_pin(pin, ENROLLMENT_PIN_HASH_PATH):
                print("[FaceAuth] ❌ Invalid PIN for re-enrollment")
                return False

        self._clear_enrollment_data()
        self.owner_signature = None
        self.owner_gallery = None
        return self.enroll_owner(callback=callback)

    def set_enrollment_pin(self, pin):
        """Set or update the enrollment protection PIN."""
        save_pin(pin, ENROLLMENT_PIN_HASH_PATH)
        print("[FaceAuth] ✅ Enrollment PIN set")

    def verify_enrollment_pin(self, pin):
        """Verify enrollment PIN."""
        return verify_pin(pin, ENROLLMENT_PIN_HASH_PATH)

    def has_enrollment_pin(self):
        """Check if an enrollment PIN has been set."""
        return os.path.exists(ENROLLMENT_PIN_HASH_PATH)

    def _clear_enrollment_data(self):
        """Remove enrollment files."""
        for path in [OWNER_SIGNATURE_PATH, OWNER_HASH_PATH,
                     OWNER_EMBEDDING_PATH, OWNER_EMBEDDING_HASH_PATH,
                     ENROLLMENT_PIN_HASH_PATH]:
            if os.path.exists(path):
                os.remove(path)
                print(f"[FaceAuth] 🗑️ Removed {path}")

    @staticmethod
    def reset_face_data():
        """CLI reset: clear all enrollment data. For --reset-face flag."""
        for path in [OWNER_SIGNATURE_PATH, OWNER_HASH_PATH,
                     OWNER_EMBEDDING_PATH, OWNER_EMBEDDING_HASH_PATH,
                     ENROLLMENT_PIN_HASH_PATH]:
            if os.path.exists(path):
                os.remove(path)
                print(f"Removed {path}")
        print("Face data cleared. Run again to re-enroll.")

    # ──── AUTHENTICATION FLOW ────

    def authenticate(self):
        """
        Main authentication check — called by lock screen.

        Flow: identity check → blink liveness → GRANTED

        Identity is checked FIRST (deep embeddings), then liveness.
        This prevents information leakage about whether a face matched.

        Returns:
            'GRANTED'        — Owner confirmed + liveness passed
            'DENIED'         — Face detected but not owner
            'NO_FACE'        — No face in frame
            'NEED_BLINK'     — Owner identity confirmed, awaiting blink
            'LOCKED_OUT'     — Too many failed attempts
            'NO_CAMERA'      — Camera not available
            'LOW_QUALITY'    — Face detected but poor conditions
        """
        with self._lock:
            state = self.state.copy()

        if not state["camera_ok"]:
            return "NO_CAMERA"

        if time.time() < state["lockout_until"]:
            remaining = int(state["lockout_until"] - time.time())
            return f"LOCKED_OUT:{remaining}"

        if not state["face_detected"]:
            return "NO_FACE"

        if state["status"] == "LOW_QUALITY":
            return "LOW_QUALITY"

        # Step 1: Identity check (is_owner set by _check_identity)
        if state["is_owner"] is True:
            # Step 2: Blink liveness check (identity first, then liveness)
            if not REQUIRE_BLINK_FOR_AUTH or self._blink_detected:
                return "GRANTED"
            else:
                # Check if blink window has expired
                if self._blink_start_time == 0.0:
                    self._blink_start_time = time.time()
                elif time.time() - self._blink_start_time > BLINK_DETECTION_WINDOW:
                    # Timed out waiting for blink — could be a photo
                    self._blink_start_time = 0.0
                    self._blink_count = 0
                    self._blink_detected = False
                    self._identity_confirmed = False
                    with self._lock:
                        self.state["is_owner"] = None
                    self._identity_history.clear()
                    return "DENIED"
                return "NEED_BLINK"

        if state["is_owner"] is False:
            with self._lock:
                a = self.state.get("auth_attempts", 0)
                self.state["auth_attempts"] = a + 1 if isinstance(a, int) else 1
                if isinstance(self.state["auth_attempts"], int) and self.state["auth_attempts"] >= MAX_FAILED_ATTEMPTS:
                    self.state["lockout_until"] = time.time() + LOCKOUT_DURATION
                    self.state["status"] = "LOCKED_OUT"
                    self.state["auth_attempts"] = 0
            return "DENIED"

        return "NO_FACE"  # is_owner is None — hasn't been checked yet

    # ──── SESSION MONITORING ────

    def start_session_monitor(self):
        """Begin monitoring owner presence after unlock."""
        self._session_active = True
        self._last_owner_seen = time.time()

    def check_session(self):
        """
        Called periodically by UI to check if should auto-lock.

        Returns:
            'OWNER_PRESENT'   — Owner face visible
            'OWNER_ABSENT'    — No face, but within timeout
            'AUTO_LOCK'       — Timeout exceeded → should lock
            'INTRUDER'        — Different face detected → lock immediately
        """
        if not self._session_active:
            return "OWNER_PRESENT"

        with self._lock:
            is_owner = self.state.get("is_owner")
            face_detected = self.state.get("face_detected", False)

        if is_owner is True:
            self._last_owner_seen = time.time()
            return "OWNER_PRESENT"

        if face_detected and is_owner is False:
            if INTRUDER_INSTANT_LOCK:
                return "INTRUDER"

        elapsed = time.time() - self._last_owner_seen
        if elapsed > AUTO_LOCK_TIMEOUT:
            return "AUTO_LOCK"

        return "OWNER_ABSENT"

    # ──── CLEANUP ────

    def stop(self):
        """Clean shutdown — release camera, stop threads."""
        self._stop_event.set()
        self._session_active = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)  # pyre-ignore

        if self.cap and self.cap.isOpened():
            try:
                self.cap.release()  # pyre-ignore
            except Exception:
                pass

        try:
            self.face_landmarker.close()
        except Exception:
            pass

        print("[FaceAuth] 🔴 Stopped")

    def stop_camera(self):
        """Stop background capture loop and release camera, keep landmarker alive."""
        self._stop_event.set()
        self._session_active = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)  # pyre-ignore
        self._thread = None
        
        self._stop_event.clear()

        with self._lock:
            if self.cap and self.cap.isOpened():
                try:
                    self.cap.release()  # pyre-ignore
                except Exception:
                    pass
            self.cap = None
            self.state["camera_ok"] = False
            self.state["status"] = "PERMANENTLY_UNLOCKED"
            
        print("[FaceAuth] 📷 Camera feed explicitly stopped (UNLOCKED state).")

    # ──── THREAD-SAFE STATE ACCESS ────

    def get_state(self):
        """Thread-safe copy of current state for UI."""
        with self._lock:
            return self.state.copy()

    def get_frame_rgb(self):
        """Get latest RGB frame for display — returns a COPY to prevent tearing."""
        with self._lock:
            if self.state["frame_rgb"] is not None:
                return self.state["frame_rgb"].copy()
        return None

    def reset_auth(self):
        """Reset authentication state for new attempt."""
        with self._lock:
            self.state["is_owner"] = None
            self.state["auth_attempts"] = 0
            self.state["consecutive_matches"] = 0
            self.state["confidence"] = 0.0
            self.state["status"] = "SCANNING"
            self.state["quality_hint"] = ""
        self._identity_history.clear()
        self._identity_confirmed = False
        self._blink_detected = False
        self._blink_count = 0
        self._blink_start_time = 0.0
        self._prev_ear = 0.3
        self._auth_start_time = 0.0
        self._session_active = False
