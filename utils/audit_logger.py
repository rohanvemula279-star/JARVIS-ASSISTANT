# pyre-ignore-all-errors
"""
Audit Logger - Log security events for debugging and compliance

Records all unlock attempts with detailed metrics to help tune thresholds
and detect attack patterns.
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional, Literal
from datetime import datetime


class AuditLogger:
    """Log security events"""

    def __init__(self, log_dir: str):
        """
        Args:
            log_dir: Directory to store audit logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Daily log file
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"audit_{today}.jsonl"

    def log_unlock_attempt(
        self,
        event: Literal["attempt", "success", "denied", "timeout"],
        match_score: float,
        liveness_score: float,
        tier: int,
        challenge_type: Optional[str] = None,
        duration_ms: int = 0,
        failure_reason: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Log an unlock attempt.

        Args:
            event: "attempt", "success", "denied", "timeout"
            match_score: Face match confidence (0-1)
            liveness_score: Liveness check result (0-1)
            tier: Current session tier (0-3)
            challenge_type: Type of challenge if used
            duration_ms: Time taken for unlock attempt
            failure_reason: Why it failed (if denied)
            metadata: Additional context
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "unix_time": time.time(),
            "event": event,
            "match_score": round(match_score, 4),
            "liveness_score": round(liveness_score, 4),
            "tier": tier,
            "challenge_type": challenge_type,
            "duration_ms": duration_ms,
            "failure_reason": failure_reason,
        }

        if metadata:
            entry.update(metadata)

        try:
            self.log_file.write_text(
                json.dumps(entry) + "\n",
                mode="a" if self.log_file.exists() else "w",
            )
        except Exception as e:
            print(f"⚠️  Failed to write audit log: {e}")

    def log_enrollment(
        self,
        samples_captured: int,
        samples_passed_quality: int,
        inter_sample_consistency: float,
        overall_quality_score: float,
        enrollment_duration_seconds: int,
        recommendation: str,
    ) -> None:
        """Log enrollment session"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "enrollment",
            "samples_captured": samples_captured,
            "samples_passed": samples_passed_quality,
            "consistency": round(inter_sample_consistency, 4),
            "quality_score": round(overall_quality_score, 4),
            "duration_seconds": enrollment_duration_seconds,
            "recommendation": recommendation,
        }

        try:
            self.log_file.write_text(
                json.dumps(entry) + "\n",
                mode="a" if self.log_file.exists() else "w",
            )
        except Exception as e:
            print(f"⚠️  Failed to write audit log: {e}")

    def get_statistics(self, hours: int = 24) -> Dict:
        """
        Get unlock statistics from recent logs.

        Args:
            hours: Look back this many hours

        Returns:
            Statistics dict
        """
        if not self.log_file.exists():
            return {"total": 0, "success": 0, "denied": 0, "timeout": 0}

        cutoff_time = time.time() - (hours * 3600)
        events = {"attempt": 0, "success": 0, "denied": 0, "timeout": 0}
        scores = {"match": [], "liveness": []}

        try:
            for line in self.log_file.read_text().strip().split("\n"):
                if not line:
                    continue

                entry = json.loads(line)
                if entry.get("unix_time", 0) < cutoff_time:
                    continue

                event = entry.get("event")
                if event in events:
                    events[event] += 1

                if "match_score" in entry:
                    scores["match"].append(entry["match_score"])
                if "liveness_score" in entry:
                    scores["liveness"].append(entry["liveness_score"])

        except Exception as e:
            print(f"⚠️  Error reading audit logs: {e}")

        # Compute averages
        avg_match = sum(scores["match"]) / len(scores["match"]) if scores["match"] else 0
        avg_liveness = (
            sum(scores["liveness"]) / len(scores["liveness"])
            if scores["liveness"]
            else 0
        )

        success_rate = (
            (events["success"] / (events["success"] + events["denied"]) * 100)
            if (events["success"] + events["denied"]) > 0
            else 0
        )

        return {
            "period_hours": hours,
            "total_attempts": sum(events.values()),
            "events": events,
            "success_rate_percent": round(success_rate, 1),
            "avg_match_score": round(avg_match, 4),
            "avg_liveness_score": round(avg_liveness, 4),
            "common_failure_reason": self._get_top_failures(cutoff_time),
        }

    def _get_top_failures(self, cutoff_time: float) -> Optional[str]:
        """Get most common failure reason"""
        if not self.log_file.exists():
            return None

        reasons = {}
        try:
            for line in self.log_file.read_text().strip().split("\n"):
                if not line:
                    continue

                entry = json.loads(line)
                if entry.get("unix_time", 0) < cutoff_time:
                    continue

                reason = entry.get("failure_reason")
                if reason:
                    reasons[reason] = reasons.get(reason, 0) + 1

            return max(reasons, key=reasons.get) if reasons else None
        except Exception:
            return None
