"""
Authentication and Role-Based Access Control package exports.
"""

from src.auth.config import AuthConfig
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.service import AuthService
from src.auth.rbac import (
    AccessController,
    AuthorizationError,
    AuthenticationError,
    extract_current_user_from_request,
    require_auth,
    require_roles,
    require_verified_advocate,
    require_contract_access
)

__all__ = [
    "AuthConfig",
    "PasswordManager",
    "TokenManager",
    "AuthService",
    "AccessController",
    "AuthorizationError",
    "AuthenticationError",
    "extract_current_user_from_request",
    "require_auth",
    "require_roles",
    "require_verified_advocate",
    "require_contract_access",
]
