# pyre-ignore-all-errors
"""
Session Manager - Track session trust tiers and timing for progressive unlocking

Implements tiered unlock requirements based on time since last unlock:
- Tier 0 (< 30s): Instant re-unlock (face only)
- Tier 1 (30s-5m): Quick unlock (1 blink)
- Tier 2 (5m-4h): Standard unlock (2 blinks)
- Tier 3 (>4h): Full challenge required
"""

import time
import json
from pathlib import Path
from typing import Dict, Literal
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class SessionTrust:
    """Tracks session security state"""
    last_unlock_time: float
    unlock_count: int
    failed_attempts: int
    last_challenge_time: float
    current_tier: int


class SessionManager:
    """Manage session trust and unlock tiers"""

    def __init__(self, session_file: str):
        """
        Args:
            session_file: Path to persist session state
        """
        self.session_file = Path(session_file)
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

        # Tier thresholds (seconds)
        self.TIER_WINDOWS = {
            0: 30,        # Instant relock (< 30s)
            1: 300,       # Quick unlock (30s - 5m)
            2: 14400,     # Standard (5m - 4h)
            3: float("inf"),  # Full challenge (> 4h)
        }

        # Tier requirements
        self.TIER_REQUIREMENTS = {
            0: {"blinks": 0, "challenge": False, "texture_check": False, "description": "Instant relock"},
            1: {"blinks": 1, "challenge": False, "texture_check": True, "description": "Quick unlock"},
            2: {"blinks": 2, "challenge": False, "texture_check": True, "description": "Standard unlock"},
            3: {"blinks": 2, "challenge": True, "texture_check": True, "description": "Full challenge"},
        }

        self.session = self._load_session()

    def _load_session(self) -> SessionTrust:
        """Load session from file or create new"""
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text())
                return SessionTrust(**data)
            except Exception:
                pass

        return SessionTrust(
            last_unlock_time=0,
            unlock_count=0,
            failed_attempts=0,
            last_challenge_time=0,
            current_tier=3,
        )

    def _save_session(self) -> None:
        """Persist session to file"""
        self.session_file.write_text(json.dumps(asdict(self.session), indent=2))

    def get_unlock_tier(self) -> Tuple[int, Dict]:
        """
        Determine current unlock tier based on time since last unlock.

        Returns:
            (tier_number, requirements_dict)
        """
        now = time.time()
        elapsed = now - self.session.last_unlock_time

        # Determine tier
        tier = 3
        for t, threshold in self.TIER_WINDOWS.items():
            if elapsed < threshold:
                tier = t
                break

        self.session.current_tier = tier
        return tier, self.TIER_REQUIREMENTS[tier]

    def record_success(self) -> None:
        """Record successful unlock"""
        self.session.last_unlock_time = time.time()
        self.session.unlock_count += 1
        self.session.failed_attempts = 0
        self._save_session()

    def record_challenge_success(self) -> None:
        """Record successful challenge"""
        self.session.last_challenge_time = time.time()
        self.session.last_unlock_time = time.time()
        self.session.unlock_count += 1
        self.session.failed_attempts = 0
        self._save_session()

    def record_failure(self) -> None:
        """Record failed unlock attempt"""
        self.session.failed_attempts += 1
        self._save_session()

    def get_session_summary(self) -> Dict:
        """Get human-readable session info"""
        tier, reqs = self.get_unlock_tier()
        elapsed = time.time() - self.session.last_unlock_time

        return {
            "current_tier": tier,
            "tier_name": reqs["description"],
            "seconds_since_last_unlock": int(elapsed),
            "total_unlocks_session": self.session.unlock_count,
            "failed_attempts": self.session.failed_attempts,
            "requirements": reqs,
            "last_unlock": datetime.fromtimestamp(self.session.last_unlock_time).isoformat(),
        }

    def reset_session(self) -> None:
        """Reset session (logout)"""
        self.session = SessionTrust(
            last_unlock_time=0,
            unlock_count=0,
            failed_attempts=0,
            last_challenge_time=0,
            current_tier=3,
        )
        self._save_session()
        print("✅ Session reset - next unlock requires full authentication")

    def should_trigger_challenge(
        self,
        match_score: float,
        texture_score: float,
        recent_failure: bool,
        unusual_lighting: bool,
    ) -> Tuple[bool, str]:
        """
        Determine if challenge should be triggered based on conditions.

        Args:
            match_score: Face match confidence (0-1)
            texture_score: Liveness texture check (0-1)
            recent_failure: True if unlock failed in last 5 minutes
            unusual_lighting: True if lighting conditions are poor

        Returns:
            (should_challenge, reason)
        """
        tier, _ = self.get_unlock_tier()

        # Tier 3 always challenges
        if tier == 3:
            return True, "Long absence (>4h) - full challenge required"

        # Borderline scores trigger challenge
        if match_score < 0.75 and match_score > 0.65:
            return True, f"Borderline match score ({match_score:.2f})"

        if texture_score < 0.75 and texture_score > 0.65:
            return True, f"Borderline liveness score ({texture_score:.2f})"

        # Recent failures
        if recent_failure:
            return True, "Recent failed attempt"

        # Unusual conditions
        if unusual_lighting:
            return True, "Unusual lighting detected"

        return False, ""


# Type hint
Tuple = tuple
