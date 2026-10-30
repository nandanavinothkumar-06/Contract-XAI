"""
Authentication and session security configuration.
"""

import os
from dataclasses import dataclass, field

@dataclass
class AuthConfig:
    # Signing secret for JWT and session tokens (must be overridden in production)
    jwt_secret: str = field(
        default_factory=lambda: os.getenv("CONTRACTRISK_JWT_SECRET", "dev_insecure_secret_change_in_production_32bytes_min!")
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    remember_me_days: int = 14
    session_idle_timeout_minutes: int = 30
    
    # Password policy constraints
    min_password_length: int = 8
    max_password_length: int = 128
    
    # Session / Cookie configuration
    session_cookie_name: str = "contractrisk_session"
    csrf_cookie_name: str = "contractrisk_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = field(
        default_factory=lambda: os.getenv("CONTRACTRISK_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
    )
    cookie_httponly: bool = True
    cookie_samesite: str = "Lax"
    cookie_path: str = "/"
    
    # Environment enforcement
    is_production: bool = field(
        default_factory=lambda: os.getenv("FLASK_ENV", "development").lower() == "production" or os.getenv("CONTRACTRISK_ENV", "development").lower() == "production"
    )

    # Argon2id parameters (standard OWASP recommended profile)
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536  # 64 MB
    argon2_parallelism: int = 4
    argon2_hash_len: int = 32
    argon2_salt_len: int = 16

    def __post_init__(self):
        """Fails safely if required security settings or signing secrets are missing in production."""
        if self.is_production:
            if "dev_insecure_secret" in self.jwt_secret or len(self.jwt_secret) < 32:
                raise ValueError(
                    "Production security failure: CONTRACTRISK_JWT_SECRET must be configured with a strong key (at least 32 characters)."
                )
            if not self.cookie_secure:
                raise ValueError(
                    "Production security failure: CONTRACTRISK_COOKIE_SECURE must be enabled in production environments."
                )
