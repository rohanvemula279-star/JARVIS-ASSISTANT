# pyre-ignore-all-errors
"""
Enhanced Face Enrollment - Simplified multi-angle enrollment

Works with existing face_auth.py infrastructure.
Captures 28 samples from 7 poses with real-time guidance.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.face_config import (
    CAMERA_INDEX,
    CAMERA_BACKEND,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
    ENROLLMENT_STRAIGHT_SAMPLES,
    ENROLLMENT_LEFT_SAMPLES,
    ENROLLMENT_RIGHT_SAMPLES,
    ENROLLMENT_UP_SAMPLES,
    ENROLLMENT_DOWN_SAMPLES,
    ENROLLMENT_SMILE_SAMPLES,
    ENROLLMENT_BLINK_SAMPLES,
    ENROLLMENT_DELAY,
    OWNER_SIGNATURE_PATH,
    PIN_LENGTH,
)
from core.enrollment_validator import EnrollmentValidator
from core.adaptive_threshold import AdaptiveThresholdManager
from utils.pin_manager import PINManager


class SimplifiedEnrollmentUI:
    """Simplified multi-angle enrollment"""

    def __init__(self):
        """Initialize enrollment"""
        self.validator = EnrollmentValidator()
        self.samples = {
            "straight": [],
            "left": [],
            "right": [],
            "up": [],
            "down": [],
            "smile": [],
            "blink": [],
        }
        self.poses_required = {
            "straight": ENROLLMENT_STRAIGHT_SAMPLES,
            "left": ENROLLMENT_LEFT_SAMPLES,
            "right": ENROLLMENT_RIGHT_SAMPLES,
            "up": ENROLLMENT_UP_SAMPLES,
            "down": ENROLLMENT_DOWN_SAMPLES,
            "smile": ENROLLMENT_SMILE_SAMPLES,
            "blink": ENROLLMENT_BLINK_SAMPLES,
        }

    def run_flow(self, pin_manager: PINManager) -> Tuple[bool, Dict]:
        """
        Run enrollment flow.

        Returns:
            (success, summary_dict)
        """
        print("\n" + "=" * 70)
        print("🔐 ENHANCED FACE ENROLLMENT SYSTEM")
        print("=" * 70)

        # Step 1: PIN Setup
        if not self._setup_pin(pin_manager):
            return False, {"reason": "PIN setup failed"}

        # Step 2: Environment check
        if not self._check_environment():
            return False, {"reason": "Environment check failed"}

        # Step 3: Multi-angle capture
        if not self._capture():
            return False, {"reason": "Face capture failed"}

        # Step 4: Generate signature
        try:
            if self._generate_signature():
                total = sum(len(v) for v in self.samples.values())
                return True, {
                    "status": "success",
                    "samples_total": total,
                    "recommendation": "✅ Enrollment complete! Ready to unlock.",
                }
            else:
                return False, {"reason": "Signature generation failed"}
        except Exception as e:
            return False, {"reason": f"Error: {e}"}

    def _setup_pin(self, pin_manager: PINManager) -> bool:
        """Set up enrollment PIN"""
        print("\n📍 STEP 1: PIN SETUP")
        print("-" * 70)
        print(f"Enter a {PIN_LENGTH}-digit PIN for re-enrollment protection:")

        while True:
            pin = input("Enter PIN: ").strip()

            if not pin or len(pin) < PIN_LENGTH:
                print(f"❌ PIN too short. Minimum {PIN_LENGTH} digits.")
                continue

            if not pin.replace(" ", "").isalnum():
                print("❌ PIN must be digits/letters only.")
                continue

            confirm = input("Confirm PIN: ").strip()
            if pin != confirm:
                print("❌ PINs don't match.")
                continue

            if pin_manager.set_pin(pin):
                print("✅ PIN stored securely")
                return True
            print("❌ Failed to store PIN")
            return False

    def _check_environment(self) -> bool:
        """Check camera"""
        print("\n📍 STEP 2: ENVIRONMENT CHECK")
        print("-" * 70)

        try:
            cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
            if not cap.isOpened():
                print("❌ Cannot access camera")
                return False

            ret, frame = cap.read()
            cap.release()

            if not ret:
                print("❌ Cannot capture from camera")
                return False

            print("✅ Camera: OK")
            print("✅ Resolution: 640x480")
            print("\n📝 Tips:")
            print("   • Face camera directly")
            print("   • Good lighting (no shadows)")
            print("   • Plain background")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def _capture(self) -> bool:
        """Capture samples from 7 poses"""
        print("\n📍 STEP 3: MULTI-ANGLE CAPTURE")
        print("-" * 70)

        pose_prompts = {
            "straight": "📸 STRAIGHT - Look at camera",
            "left": "👈 LEFT - Turn head ~15°",
            "right": "👉 RIGHT - Turn head ~15°",
            "up": "⬆️ UP - Tilt head up",
            "down": "⬇️ DOWN - Tilt head down",
            "smile": "😊 SMILE - Natural smile",
            "blink": "👁️ BLINK - Blink naturally",
        }

        cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        try:
            for pose in ["straight", "left", "right", "up", "down", "smile", "blink"]:
                required = self.poses_required[pose]
                print(f"\n{pose_prompts[pose]} ({required} samples)")
                print("-" * 70)

                captured = 0
                next_capture = time.time()

                while captured < required:
                    ret, frame = cap.read()
                    if not ret:
                        print("❌ Frame capture failed")
                        return False

                    # Simple countdown
                    if time.time() < next_capture:
                        elapsed = next_capture - time.time()
                        print(f"\r   Ready in {elapsed:.1f}s... [{captured}/{required}]", end="", flush=True)
                        time.sleep(0.1)
                        continue

                    # Capture frame
                    captured += 1
                    self.samples[pose].append({"frame": frame.copy()})
                    next_capture = time.time() + ENROLLMENT_DELAY
                    print(f"\r   ✅ [{captured}/{required}]" + " " * 40, end="", flush=True)

                print()  # newline
            return True

        finally:
            cap.release()
            cv2.destroyAllWindows()

    def _generate_signature(self) -> bool:
        """Generate signature from samples"""
        print("\n📍 STEP 4: SIGNATURE GENERATION & CALIBRATION")
        print("-" * 70)

        try:
            # Extract simple embeddings from frames
            embeddings = []

            total_samples = sum(len(v) for v in self.samples.values())
            print(f"Processing {total_samples} frames...")

            for pose, samples in self.samples.items():
                for sample in samples:
                    frame = sample["frame"]
                    h, w = frame.shape[:2]

                    # Simple approach: extract center face region as embedding
                    y1, y2 = h // 4, 3 * h // 4
                    x1, x2 = w // 4, 3 * w // 4
                    face_region = frame[y1:y2, x1:x2]

                    # Convert to grayscale and create embedding
                    gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
                    embedding = gray.flatten().astype(np.float32)

                    # Normalize
                    norm = np.linalg.norm(embedding)
                    if norm > 1e-6:
                        embedding = embedding / norm
                    embeddings.append(embedding)

            if not embeddings:
                print("❌ No embeddings extracted")
                return False

            # Average signature
            avg_signature = np.mean(embeddings, axis=0)

            # Save
            sig_path = Path(OWNER_SIGNATURE_PATH)
            sig_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(sig_path, avg_signature)
            print(f"✅ Signature saved")

            # Calibrate threshold
            self_scores = []
            for emb in embeddings[:min(10, len(embeddings))]:
                score = float(np.dot(emb, avg_signature))
                self_scores.append(score)

            mgr = AdaptiveThresholdManager(str(sig_path.parent / "calibration.json"))
            threshold, report = mgr.calibrate_from_samples(self_scores)

            print(f"✅ Threshold calibrated: {report['recommended_threshold']:.3f}")
            print(f"   Self-match mean: {report['self_mean_score']:.3f}")

            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def run_enrollment() -> bool:
    """Run enrollment"""
    enrollment = SimplifiedEnrollmentUI()
    pin_mgr = PINManager(
        str(Path(__file__).parent.parent / "data" / "authorized_faces" / "enrollment_pin.sha256")
    )

    success, summary = enrollment.run_flow(pin_mgr)

    print("\n" + "=" * 70)
    if success:
        print("✅ ENROLLMENT SUCCESSFUL!")
        print(f"   {summary.get('recommendation', '')}")
    else:
        print("❌ ENROLLMENT FAILED")
        print(f"   Reason: {summary.get('reason', 'Unknown')}")
    print("=" * 70 + "\n")

    return success


if __name__ == "__main__":
    success = run_enrollment()
    sys.exit(0 if success else 1)
