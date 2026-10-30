"""
Cross-Site Request Forgery (CSRF) protection module.
Implements OWASP Double-Submit Cookie pattern with custom request headers (X-CSRF-Token)
and Origin/Referer verification for cookie-authenticated browser sessions.
"""

import hmac
import secrets
from urllib.parse import urlparse
from typing import Tuple, Optional, Set
from flask import Request, current_app

from src.auth.config import AuthConfig

# Endpoints where initial credentials or tokens are established prior to session creation
CSRF_EXEMPT_PATHS: Set[str] = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/csrf",
    "/api/health"
}

def generate_csrf_token() -> str:
    """Generates a cryptographically secure 64-character hex CSRF token."""
    return secrets.token_hex(32)

def is_safe_method(method: str) -> bool:
    """Returns True for read-only HTTP methods per RFC 7231."""
    return method.upper() in ("GET", "HEAD", "OPTIONS", "TRACE")

def validate_origin(request: Request) -> bool:
    """
    Verifies that Origin or Referer header matches the request host.
    Protects against DNS rebinding and cross-origin fetch attacks.
    """
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlparse(origin)
        expected_host = request.host.split(":")[0]
        actual_host = parsed.netloc.split(":")[0]
        if actual_host != expected_host:
            # Allow localhost / 127.0.0.1 equivalence in local dev
            if {expected_host, actual_host} <= {"localhost", "127.0.0.1"}:
                return True
            return False
        return True

    referer = request.headers.get("Referer")
    if referer:
        parsed = urlparse(referer)
        expected_host = request.host.split(":")[0]
        actual_host = parsed.netloc.split(":")[0]
        if actual_host != expected_host:
            if {expected_host, actual_host} <= {"localhost", "127.0.0.1"}:
                return True
            return False
        return True

    # Neither Origin nor Referer provided: allow for same-origin HTTP/1.0 or programmatic requests
    return True

def validate_csrf_request(request: Request, config: Optional[AuthConfig] = None) -> Tuple[bool, Optional[str]]:
    """
    Validates CSRF tokens for state-changing requests authenticated via session cookie.
    Bearer-token API requests are exempt as custom headers cannot be set cross-origin without CORS.
    Returns: (is_valid: bool, error_message: Optional[str])
    """
    cfg = config or AuthConfig()

    # 1. Read-only methods are safe from CSRF
    if is_safe_method(request.method):
        return True, None

    # 2. Exempt public / auth setup paths
    if request.path in CSRF_EXEMPT_PATHS:
        return True, None

    # 3. Check for Bearer token authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Non-browser API client using explicit Bearer token header is exempt
        return True, None

    # 4. If session cookie is not present, request will be rejected downstream by @require_auth
    session_cookie = request.cookies.get(cfg.session_cookie_name)
    if not session_cookie:
        return True, None

    # 5. Cookie-authenticated state-changing request: CSRF validation is MANDATORY
    if not validate_origin(request):
        return False, "Cross-origin request rejected: Origin or Referer does not match application host."

    # Extract header token
    header_token = request.headers.get(cfg.csrf_header_name) or request.headers.get("X-XSRF-Token")
    if not header_token or not header_token.strip():
        return False, f"Missing CSRF token in header '{cfg.csrf_header_name}'."

    # Extract cookie token
    cookie_token = request.cookies.get(cfg.csrf_cookie_name)
    if not cookie_token or not cookie_token.strip():
        return False, f"Missing CSRF token cookie '{cfg.csrf_cookie_name}'."

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(header_token.strip(), cookie_token.strip()):
        return False, "CSRF token mismatch: submitted header does not match secure session cookie."

    return True, None
