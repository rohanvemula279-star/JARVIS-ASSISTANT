# pyre-ignore-all-errors
"""
Adaptive Threshold Manager - Per-user threshold calibration

Learns user's self-match distribution and automatically calibrates
similarity thresholds to minimize false rejections while maintaining
security against strangers.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class CalibrationData:
    """Per-user calibration results"""
    self_match_scores: list  # Your face vs signature
    self_mean: float
    self_std: float
    threshold: float
    samples_count: int
    calibration_time: float


class AdaptiveThresholdManager:
    """Learn and maintain per-user similarity thresholds"""

    def __init__(
        self,
        calibration_file: str,
        min_threshold: float = 0.68,
        max_threshold: float = 0.82,
        margin_std_devs: float = 2.0,
    ):
        """
        Args:
            calibration_file: Path to store calibration data
            min_threshold: Floor threshold (security floor)
            max_threshold: Ceiling threshold (usability ceiling)
            margin_std_devs: How many std-devs below mean for threshold
        """
        self.calibration_file = Path(calibration_file)
        self.calibration_file.parent.mkdir(parents=True, exist_ok=True)

        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.margin_std_devs = margin_std_devs

        self.calibration = self._load_calibration()

    def _load_calibration(self) -> Optional[CalibrationData]:
        """Load existing calibration or return None"""
        if self.calibration_file.exists():
            try:
                data = json.loads(self.calibration_file.read_text())
                return CalibrationData(**data)
            except Exception:
                pass
        return None

    def _save_calibration(self) -> None:
        """Persist calibration data"""
        if self.calibration:
            self.calibration_file.write_text(
                json.dumps(asdict(self.calibration), indent=2)
            )

    def calibrate_from_samples(
        self,
        self_match_scores: list,
        stranger_scores: Optional[list] = None,
    ) -> Tuple[float, Dict]:
        """
        Calibrate threshold from enrollment/test samples.

        Args:
            self_match_scores: List of match scores (your face variants)
            stranger_scores: Optional list of non-owner scores for validation

        Returns:
            (recommended_threshold, calibration_report)
        """
        if len(self_match_scores) < 3:
            return (
                0.72,
                {
                    "status": "insufficient_samples",
                    "message": "Need at least 3 self-samples to calibrate",
                },
            )

        self_match_scores = np.array(self_match_scores, dtype=float)
        self_mean = float(np.mean(self_match_scores))
        self_std = float(np.std(self_match_scores))

        # Calculate threshold as: mean - (margin * std)
        # This catches ~95% of your variations while staying strict
        raw_threshold = self_mean - (self.margin_std_devs * self_std)
        threshold = np.clip(raw_threshold, self.min_threshold, self.max_threshold)

        # Store calibration
        self.calibration = CalibrationData(
            self_match_scores=self_match_scores.tolist(),
            self_mean=self_mean,
            self_std=self_std,
            threshold=float(threshold),
            samples_count=len(self_match_scores),
            calibration_time=time.time(),
        )
        self._save_calibration()

        report = {
            "status": "calibrated",
            "self_mean_score": round(self_mean, 4),
            "self_std_deviation": round(self_std, 4),
            "recommended_threshold": round(threshold, 4),
            "margin_std_devs": self.margin_std_devs,
            "samples_used": len(self_match_scores),
        }

        # Validate against stranger scores if provided
        if stranger_scores:
            stranger_scores = np.array(stranger_scores, dtype=float)
            stranger_max = float(np.max(stranger_scores))
            overlap = (
                "⚠️ WARNING: High stranger score, threshold may be too lenient"
                if stranger_max > threshold
                else "✅ Good separation between self and stranger"
            )
            report["stranger_validation"] = {
                "max_stranger_score": round(stranger_max, 4),
                "gap_to_threshold": round(threshold - stranger_max, 4),
                "note": overlap,
            }

        return threshold, report

    def get_current_threshold(self) -> float:
        """Get currently configured threshold (or default)"""
        if self.calibration:
            return self.calibration.threshold
        return 0.72  # Default

    def is_calibrated(self) -> bool:
        """Check if calibration data exists"""
        return self.calibration is not None

    def get_calibration_summary(self) -> Dict:
        """Get human-readable calibration info"""
        if not self.calibration:
            return {
                "status": "not_calibrated",
                "recommended_action": "Run enrollment to generate calibration data",
            }

        return {
            "status": "calibrated",
            "threshold": self.calibration.threshold,
            "self_mean": self.calibration.self_mean,
            "self_std": self.calibration.self_std,
            "samples": self.calibration.samples_count,
            "margin_std_devs": self.margin_std_devs,
            "notes": f"Threshold set {self.margin_std_devs} std-devs below your mean score",
        }

    def reset_calibration(self) -> None:
        """Reset calibration (used before re-enrollment)"""
        self.calibration = None
        if self.calibration_file.exists():
            self.calibration_file.unlink()
        print("✅ Calibration data cleared - ready for new enrollment")


# Import time at top of file
import time
