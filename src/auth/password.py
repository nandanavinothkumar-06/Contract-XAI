"""
Argon2id password hashing, verification, parameter migration, and policy validation.
Adheres to OWASP recommendations and eliminates homemade cryptography.
"""

from typing import Tuple, Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from src.auth.config import AuthConfig

class PasswordManager:
    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or AuthConfig()
        self.hasher = PasswordHasher(
            time_cost=self.config.argon2_time_cost,
            memory_cost=self.config.argon2_memory_cost,
            parallelism=self.config.argon2_parallelism,
            hash_len=self.config.argon2_hash_len,
            salt_len=self.config.argon2_salt_len
        )

    def validate_password_policy(self, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validates password against length bounds and non-empty policy.
        """
        if not password or not password.strip():
            return False, "Password cannot be empty or purely whitespace."
        if len(password) < self.config.min_password_length:
            return False, f"Password must be at least {self.config.min_password_length} characters long."
        if len(password) > self.config.max_password_length:
            return False, f"Password cannot exceed {self.config.max_password_length} characters."
        return True, None

    def hash_password(self, password: str) -> str:
        """
        Generates a salted Argon2id hash of the password.
        Never stores or logs the plaintext password.
        """
        valid, err = self.validate_password_policy(password)
        if not valid:
            raise ValueError(err)
        return self.hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verifies plaintext password against stored Argon2id hash using constant-time comparison.
        Catches verification mismatch and invalid hash exceptions safely.
        """
        if not password or not password_hash:
            return False
        try:
            return self.hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
        except Exception:
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """
        Checks whether stored hash was generated with older Argon2 parameters
        and should be upgraded upon next successful login.
        """
        try:
            return self.hasher.check_needs_rehash(password_hash)
        except Exception:
            return False
