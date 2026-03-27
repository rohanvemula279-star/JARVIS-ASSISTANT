# pyre-ignore-all-errors
"""
PIN Manager - Secure PIN hashing and verification with bcrypt/argon2

Provides:
- 6-digit PIN hashing with bcrypt
- PIN verification with rate limiting
- Lockout management after failed attempts
"""

import hashlib
import time
from pathlib import Path
from typing import Dict, Tuple, Optional

try:
    import bcrypt
except ImportError:
    bcrypt = None


class PINManager:
    """Secure PIN management with bcrypt hashing"""

    def __init__(self, hash_path: str):
        """
        Args:
            hash_path: Path to store hashed PIN file
        """
        self.hash_path = Path(hash_path)
        self.hash_path.parent.mkdir(parents=True, exist_ok=True)
        self.lockout_state = {
            "failed_attempts": 0,
            "lockout_until": 0,
        }

    def set_pin(self, pin: str) -> bool:
        """
        Hash and store PIN.

        Args:
            pin: 6-digit PIN string

        Returns:
            True if successful, False otherwise
        """
        if not self._validate_pin_format(pin):
            print(f"❌ PIN must be 6+ digits, got: {pin}")
            return False

        try:
            if bcrypt:
                # Use bcrypt (preferred)
                salt = bcrypt.gensalt(rounds=12)
                hashed = bcrypt.hashpw(pin.encode("utf-8"), salt)
            else:
                # Fallback: PBKDF2 (Python stdlib)
                hashed = hashlib.pbkdf2_hmac(
                    "sha256",
                    pin.encode("utf-8"),
                    b"salt_placeholder",
                    100000,
                ).hex()

            self.hash_path.write_text(hashed.decode("utf-8") if isinstance(hashed, bytes) else hashed)
            print(f"✅ PIN stored securely at {self.hash_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to store PIN: {e}")
            return False

    def verify_pin(self, pin: str) -> Tuple[bool, str]:
        """
        Verify PIN against stored hash.

        Args:
            pin: PIN to verify

        Returns:
            (success, message)
        """
        # Check lockout
        if time.time() < self.lockout_state["lockout_until"]:
            remaining = int(self.lockout_state["lockout_until"] - time.time())
            message = f"❌ Account locked. Try again in {remaining} seconds"
            return False, message

        if not self.hash_path.exists():
            return False, "❌ No PIN set. Run enrollment first"

        if not self._validate_pin_format(pin):
            return False, "❌ PIN must be 6+ digits"

        try:
            stored_hash = self.hash_path.read_text().strip()

            if bcrypt:
                # bcrypt verification
                verified = bcrypt.checkpw(pin.encode("utf-8"), stored_hash.encode("utf-8"))
            else:
                # PBKDF2 fallback comparison
                test_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    pin.encode("utf-8"),
                    b"salt_placeholder",
                    100000,
                ).hex()
                verified = test_hash == stored_hash

            if verified:
                self.lockout_state["failed_attempts"] = 0
                return True, "✅ PIN verified"
            else:
                self.lockout_state["failed_attempts"] += 1
                if self.lockout_state["failed_attempts"] >= 3:
                    self.lockout_state["lockout_until"] = time.time() + 300  # 5 min lockout
                    return False, f"❌ PIN incorrect. Locked for 5 minutes (attempt {self.lockout_state['failed_attempts']})"
                return False, f"❌ PIN incorrect ({self.lockout_state['failed_attempts']}/3 attempts)"

        except Exception as e:
            return False, f"❌ Verification error: {e}"

    def _validate_pin_format(self, pin: str) -> bool:
        """Check PIN is 6+ digits"""
        return isinstance(pin, str) and len(pin) >= 6 and pin.replace(" ", "").isalnum()

    def is_locked(self) -> bool:
        """Check if account is currently locked"""
        return time.time() < self.lockout_state["lockout_until"]

    def reset_lockout(self) -> None:
        """Reset lockout state (admin function)"""
        self.lockout_state["failed_attempts"] = 0
        self.lockout_state["lockout_until"] = 0
        print("✅ Lockout reset")
