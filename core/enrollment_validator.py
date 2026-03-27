# pyre-ignore-all-errors
"""
Enrollment Validator - Quality checks and scoring for enrollment samples

Validates that enrollment samples meet quality standards:
- Resolution and clarity (Laplacian variance)
- Content diversity (all same person)
- Pose distribution (proper angle coverage)
- Confidence consistency
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class QualityMetrics:
    """Quality score for a single enrollment sample"""
    blur_score: float  # Laplacian variance (higher = sharper)
    lighting_score: float  # Histogram std (higher = good contrast)
    confidence_score: float  # Face detection confidence
    face_area_ratio: float  # Relative face size in frame
    passed: bool  # Overall pass/fail


class EnrollmentValidator:
    """Validate enrollment sample quality"""

    # Quality thresholds
    MIN_BLUR_SCORE = 100  # Laplacian variance
    MIN_LIGHTING_SCORE = 30  # Histogram std
    MIN_CONFIDENCE = 0.88  # Face detection confidence
    MIN_FACE_AREA_RATIO = 0.15  # 15% of frame should be face
    MAX_FACE_AREA_RATIO = 0.90  # Don't fill entire frame

    # Pose thresholds (degrees)
    REQUIRED_YAW_RANGE = 10  # Left/right variation
    REQUIRED_PITCH_RANGE = 8  # Up/down variation
    REQUIRED_ROLL_RANGE = 5  # Tilt variation

    def validate_sample(
        self,
        frame: np.ndarray,
        face_landmarks,
        detection_confidence: float,
    ) -> QualityMetrics:
        """
        Check quality of a single enrollment frame.

        Args:
            frame: BGR frame from camera
            face_landmarks: MediaPipe face landmarks
            detection_confidence: Detection confidence (0-1)

        Returns:
            QualityMetrics object
        """
        h, w = frame.shape[:2]

        # 1. Blur detection (Laplacian variance)
        blur_score = float(cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())

        # 2. Lighting quality (histogram std)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        lighting_score = float(np.std(hist))

        # 3. Face area
        if face_landmarks:
            xs = [lm.x for lm in face_landmarks]
            ys = [lm.y for lm in face_landmarks]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            face_area = (x_max - x_min) * (y_max - y_min)
            frame_area = 1.0  # Normalized coords
            face_area_ratio = face_area
        else:
            face_area_ratio = 0.0

        # 4. Check all thresholds
        passed = (
            blur_score >= self.MIN_BLUR_SCORE
            and lighting_score >= self.MIN_LIGHTING_SCORE
            and detection_confidence >= self.MIN_CONFIDENCE
            and self.MIN_FACE_AREA_RATIO <= face_area_ratio <= self.MAX_FACE_AREA_RATIO
        )

        return QualityMetrics(
            blur_score=round(blur_score, 2),
            lighting_score=round(lighting_score, 2),
            confidence_score=round(detection_confidence, 4),
            face_area_ratio=round(face_area_ratio, 4),
            passed=passed,
        )

    def check_pose_diversity(self, head_poses: List[Tuple[float, float, float]]) -> Dict:
        """
        Check if enrolled poses have sufficient variation.

        Args:
            head_poses: List of (yaw, pitch, roll) tuples in degrees

        Returns:
            Diversity report dict
        """
        if len(head_poses) < 3:
            return {
                "valid": False,
                "reason": f"Need at least 3 poses, got {len(head_poses)}",
            }

        yaws = [p[0] for p in head_poses]
        pitches = [p[1] for p in head_poses]
        rolls = [p[2] for p in head_poses]

        yaw_range = max(yaws) - min(yaws)
        pitch_range = max(pitches) - min(pitches)
        roll_range = max(rolls) - min(rolls)

        valid = (
            yaw_range >= self.REQUIRED_YAW_RANGE
            and pitch_range >= self.REQUIRED_PITCH_RANGE
            and roll_range >= self.REQUIRED_ROLL_RANGE
        )

        return {
            "valid": valid,
            "yaw_range": round(yaw_range, 1),
            "pitch_range": round(pitch_range, 1),
            "roll_range": round(roll_range, 1),
            "required_yaw": self.REQUIRED_YAW_RANGE,
            "required_pitch": self.REQUIRED_PITCH_RANGE,
            "required_roll": self.REQUIRED_ROLL_RANGE,
        }

    def check_inter_sample_consistency(
        self,
        scores: List[float],
        min_consistency: float = 0.85,
    ) -> Dict:
        """
        Check that all samples are from the same person (inter-sample similarity).

        Args:
            scores: List of similarity scores between consecutive samples
            min_consistency: Minimum mean similarity required

        Returns:
            Consistency report dict
        """
        if not scores:
            return {"valid": False, "reason": "No scores to check"}

        mean_consistency = float(np.mean(scores))
        min_score = float(np.min(scores))
        std_dev = float(np.std(scores))

        valid = mean_consistency >= min_consistency

        return {
            "valid": valid,
            "mean_consistency": round(mean_consistency, 4),
            "min_score": round(min_score, 4),
            "std_deviation": round(std_dev, 4),
            "required_minimum": min_consistency,
            "outliers": sum(1 for s in scores if s < (mean_consistency - 2 * std_dev)),
        }

    def compute_enrollment_quality_score(
        self,
        samples_passed: int,
        total_samples: int,
        consistency_score: float,
        pose_diversity_valid: bool,
        mean_blur: float,
        mean_confidence: float,
    ) -> Dict:
        """
        Compute overall enrollment quality score (composite).

        Args:
            samples_passed: Number of samples passing quality gate
            total_samples: Total samples captured
            consistency_score: Inter-sample consistency (0-1)
            pose_diversity_valid: Pose diversity check passed
            mean_blur: Average Laplacian variance
            mean_confidence: Average detection confidence

        Returns:
            Overall enrollment quality report
        """
        # Weighted factors
        sample_pass_rate = samples_passed / total_samples if total_samples > 0 else 0
        blur_normalized = min(mean_blur / 300, 1.0)  # Normalize to 0-1
        confidence_normalized = mean_confidence

        # Weighted average: 40% pass rate, 30% consistency, 15% blur, 10% confidence, 5% pose
        score = (
            0.40 * sample_pass_rate
            + 0.30 * consistency_score
            + 0.15 * blur_normalized
            + 0.10 * confidence_normalized
            + (0.05 if pose_diversity_valid else 0)
        )

        grade = "PASS" if score >= 0.80 else "BORDERLINE" if score >= 0.65 else "FAIL"

        return {
            "overall_score": round(score, 4),
            "grade": grade,
            "sample_pass_rate": round(sample_pass_rate, 2),
            "consistency_contribution": round(consistency_score, 4),
            "blur_quality": round(blur_normalized, 4),
            "confidence_quality": round(confidence_normalized, 4),
            "pose_diversity": pose_diversity_valid,
        }

    def generate_enrollment_report(self, metrics: Dict) -> str:
        """
        Generate human-readable enrollment report.

        Args:
            metrics: Collected metrics dict

        Returns:
            Formatted report string
        """
        report = "\n" + "=" * 60 + "\n"
        report += "📋 ENROLLMENT QUALITY REPORT\n"
        report += "=" * 60 + "\n\n"

        report += f"Samples Captured: {metrics['total']}/{metrics['expected']}\n"
        report += f"Samples Passed Quality: {metrics['passed']}\n"
        report += f"Pass Rate: {metrics['pass_rate']:.1%}\n\n"

        report += f"Average Blur Score: {metrics['avg_blur']:.1f}\n"
        report += f"Average Confidence: {metrics['avg_confidence']:.3f}\n"
        report += f"Consistency Score: {metrics['consistency']:.3f}\n\n"

        report += f"Pose Diversity: {metrics['pose_valid']}\n"
        report += f"Overall Quality Score: {metrics['overall']:.3f}\n"
        report += f"Recommendation: {metrics['recommendation']}\n\n"

        report += "=" * 60 + "\n"

        return report
