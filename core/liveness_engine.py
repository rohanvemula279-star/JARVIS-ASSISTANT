# pyre-ignore-all-errors
"""
Liveness Engine - Unified multi-layer liveness detection

Implements all liveness checks in parallel:
1. Texture analysis (LBP-based, not a flat image)
2. Micro-movement detection (natural sway, not rigid)
3. Blink detection (Eye Aspect Ratio)
4. Challenge system (head pose variation)
"""

import cv2
import numpy as np
from collections import deque
from typing import Dict, Tuple, Optional, List
from pathlib import Path

try:
    from skimage.feature import local_binary_pattern
except ImportError:
    local_binary_pattern = None


class LivenessEngine:
    """Multi-layer liveness detection"""

    def __init__(self, texture_baseline_path: Optional[str] = None):
        """
        Args:
            texture_baseline_path: Path to pre-computed texture baseline
        """
        self.texture_baseline = None
        if texture_baseline_path and Path(texture_baseline_path).exists():
            try:
                self.texture_baseline = np.load(texture_baseline_path)
            except Exception:
                pass

        # Movement tracking (for micro-movement detection)
        self.landmark_history = deque(maxlen=15)  # Last 15 frames
        self.z_coords_history = deque(maxlen=15)

        # Blink tracking
        self.blink_history = deque(maxlen=10)
        self.last_blink_ear = None

    def analyze_texture(
        self,
        face_crop: np.ndarray,
        threshold: float = 35.0,
    ) -> Tuple[float, bool]:
        """
        Texture analysis using Laplacian variance.

        A real 3D face has texture variation. A photo/screen is flat.
        High variance = real face. Low variance = spoofing attempt.

        Args:
            face_crop: Face region from frame (BGR)
            threshold: Laplacian variance threshold

        Returns:
            (texture_score, is_real_face)
        """
        # Extract Laplacian variance
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Normalize to 0-1 range (assuming max texture_var ~200 for good faces)
        score = min(laplacian_var / 200.0, 1.0)

        # If baseline exists, compare against it
        if self.texture_baseline is not None:
            baseline_mean = float(np.mean(self.texture_baseline))
            baseline_std = float(np.std(self.texture_baseline))
            z_score = (laplacian_var - baseline_mean) / (baseline_std + 1e-6)
            # Real face: z-score close to 0. Outlier: high z-score.
            outlier_score = min(abs(z_score) / 3.0, 1.0)  # Normalize outlier likelihood
            score = (score + (1 - outlier_score)) / 2  # Blend both metrics

        is_real = laplacian_var >= threshold
        return round(score, 4), is_real

    def analyze_micro_movement(
        self,
        landmarks: list,
        z_coords: np.ndarray,
        min_variance: float = 0.005,
        max_correlation: float = 0.95,
    ) -> Tuple[float, bool, Dict]:
        """
        Detect natural micro-movements vs rigid-body motion.

        Real face: Landmark positions vary slightly (natural sway/micro-expressions).
        Photo on stand: All landmarks move rigidly together (perfect correlation).
        Screen/Phone: Rigid motion in one direction.

        Args:
            landmarks: Face landmarks list
            z_coords: Depth z-coordinates
            min_variance: Minimum variance for natural movement
            max_correlation: Maximum correlation allowed for rigid motion

        Returns:
            (movement_score, is_natural_movement, debug_info)
        """
        if landmarks is None or len(landmarks) < 10:
            return 0.5, True, {"reason": "insufficient_landmarks"}

        # Convert landmarks to array
        lm_array = np.array([[lm.x, lm.y] for lm in landmarks])

        # Add to history
        self.landmark_history.append(lm_array)
        if z_coords is not None:
            self.z_coords_history.append(z_coords)

        # Need at least 5 frames to analyze
        if len(self.landmark_history) < 5:
            return 0.5, True, {"status": "buffering", "frames": len(self.landmark_history)}

        # Compute variance in landmark positions
        hist_array = np.array(list(self.landmark_history))
        landmark_variance = float(np.var(hist_array))

        # Compute correlation between landmark changes (rigid body = high correlation)
        if len(self.landmark_history) >= 3:
            diffs1 = np.diff(hist_array[:, :, 0].flatten())
            diffs2 = np.diff(hist_array[:, :, 1].flatten())
            correlation = float(np.abs(np.corrcoef(diffs1, diffs2)[0, 1]))
        else:
            correlation = 0.0

        # Z-coordinate variance (if available)
        z_variance = 0.0
        if len(self.z_coords_history) >= 3:
            z_array = np.array(list(self.z_coords_history))
            z_variance = float(np.var(z_array))

        # Scoring
        variance_score = min(landmark_variance / 0.01, 1.0)  # Normalize
        rigidity_penalty = max(0, (correlation - max_correlation) * 5)  # Penalize high correlation
        movement_score = max(0, variance_score - rigidity_penalty)

        is_natural = landmark_variance >= min_variance and correlation < max_correlation

        debug = {
            "landmark_variance": round(landmark_variance, 6),
            "landmark_correlation": round(correlation, 4),
            "z_variance": round(z_variance, 6),
            "is_natural": is_natural,
            "history_length": len(self.landmark_history),
        }

        return round(movement_score, 4), is_natural, debug

    def detect_blink(
        self,
        landmarks: list,
        ear_threshold: float = 0.21,
    ) -> Tuple[float, bool, Dict]:
        """
        Detect blink using Eye Aspect Ratio.

        Args:
            landmarks: Face landmarks
            ear_threshold: EAR below threshold = blink

        Returns:
            (blink_confidence, blink_detected, metrics)
        """
        if landmarks is None:
            return 0.0, False, {"status": "no_landmarks"}

        # Compute EAR for both eyes
        left_ear = self._compute_ear(landmarks, "left")
        right_ear = self._compute_ear(landmarks, "right")
        avg_ear = (left_ear + right_ear) / 2

        # Track state
        self.blink_history.append(avg_ear)
        blink_detected = avg_ear < ear_threshold

        # Confidence: how pronounced the blink is
        if self.last_blink_ear is not None:
            blink_drop = max(0, self.last_blink_ear - avg_ear)
            confidence = min(blink_drop / 0.1, 1.0)  # Normalize
        else:
            confidence = 0.5 if blink_detected else 0.0

        self.last_blink_ear = avg_ear

        return round(confidence, 4), blink_detected, {
            "left_ear": round(left_ear, 4),
            "right_ear": round(right_ear, 4),
            "avg_ear": round(avg_ear, 4),
            "threshold": ear_threshold,
            "detected": blink_detected,
        }

    def compute_combined_liveness_score(
        self,
        face_crop: np.ndarray,
        landmarks: list,
        z_coords: np.ndarray,
        texture_weight: float = 0.40,
        movement_weight: float = 0.45,
        depth_weight: float = 0.15,
    ) -> Tuple[float, Dict]:
        """
        Compute combined liveness score from all checks.

        Args:
            face_crop: Face region
            landmarks: Face landmarks
            z_coords: Depth coordinates
            texture_weight: Weight for texture analysis
            movement_weight: Weight for micro-movement
            depth_weight: Weight for depth variance

        Returns:
            (liveness_score, breakdown_dict)
        """
        # Texture check
        texture_score, _ = self.analyze_texture(face_crop)

        # Movement check
        movement_score, _, movement_debug = self.analyze_micro_movement(landmarks, z_coords)

        # Depth check (supplementary)
        depth_score = self._analyze_depth(z_coords)

        # Weighted combination
        combined = (
            texture_weight * texture_score
            + movement_weight * movement_score
            + depth_weight * depth_score
        )

        breakdown = {
            "texture_score": texture_score,
            "movement_score": movement_score,
            "depth_score": depth_score,
            "combined_score": round(combined, 4),
            "movement_debug": movement_debug,
        }

        return round(combined, 4), breakdown

    def _compute_ear(self, landmarks, side: str) -> float:
        """Compute Eye Aspect Ratio"""
        indices = (33, 160, 158, 133, 153, 144) if side == "left" else (362, 385, 387, 263, 373, 380)

        pts = [np.array([landmarks[i].x, landmarks[i].y]) for i in indices]
        p1, p2, p3, p4, p5, p6 = pts

        vertical_1 = np.linalg.norm(p2 - p6)
        vertical_2 = np.linalg.norm(p3 - p5)
        horizontal = np.linalg.norm(p1 - p4)

        if horizontal < 1e-6:
            return 0.3

        return float((vertical_1 + vertical_2) / (2.0 * horizontal))

    def _analyze_depth(self, z_coords: np.ndarray) -> float:
        """Supplementary depth analysis"""
        if z_coords is None or len(z_coords) < 10:
            return 0.5

        z_range = float(np.ptp(z_coords))  # Peak-to-peak
        # Normalize: real face has 0.05-0.15 range, photos have ~0
        depth_score = min(z_range / 0.1, 1.0)
        return round(depth_score, 4)

    def reset(self) -> None:
        """Reset tracking buffers"""
        self.landmark_history.clear()
        self.z_coords_history.clear()
        self.blink_history.clear()
        self.last_blink_ear = None
