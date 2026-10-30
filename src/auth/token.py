"""
JWT token manager: generates, decodes, validates, and revokes bearer tokens.
Enforces algorithm pinning, expiration, issuer/audience validation, and revocation checks.
"""

import uuid
import datetime
from typing import Optional, Dict, Any, Set
import jwt
from src.auth.config import AuthConfig
from src.persistence.models import UserRecord

class TokenManager:
    ISSUER = "contractrisk-xai"
    AUDIENCE = "contractrisk-client"

    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or AuthConfig()
        self.revoked_jtis: Set[str] = set()

    def generate_token(self, user: UserRecord, expires_delta_minutes: Optional[int] = None) -> str:
        """
        Generates a cryptographically signed JWT token with standard claims.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        duration = expires_delta_minutes or self.config.access_token_expire_minutes
        exp = now + datetime.timedelta(minutes=duration)
        jti = str(uuid.uuid4())

        payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "advocate_status": user.advocate_status,
            "jti": jti,
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp())
        }

        token = jwt.encode(
            payload,
            self.config.jwt_secret,
            algorithm=self.config.jwt_algorithm
        )
        return token

    def decode_and_validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decodes token and validates signature, expiration, issuer, audience, and revocation.
        Rejects unsigned or tampered tokens.
        """
        if not token:
            return None

        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                issuer=self.ISSUER,
                audience=self.AUDIENCE,
                options={"require": ["exp", "iss", "aud", "sub", "jti"]}
            )

            # Check revocation
            jti = payload.get("jti")
            if jti in self.revoked_jtis:
                return None

            return payload

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
        except Exception:
            return None

    def revoke_token(self, token: str) -> bool:
        """
        Revokes a token by adding its unique jti to the revocation registry.
        """
        try:
            # Decode without strict expiration check to allow revoking expired tokens
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                audience=self.AUDIENCE,
                options={"verify_exp": False}
            )
            jti = payload.get("jti")
            if jti:
                self.revoked_jtis.add(jti)
                return True
        except Exception:
            pass
        return False
