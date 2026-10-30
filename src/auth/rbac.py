"""
Role-Based Access Control (RBAC) and authorization primitives.
Enforces deny-by-default permissions, tenant isolation, and advocate verification gates.
"""

import datetime
import hashlib
from functools import wraps
from typing import List, Callable, Optional, Any
from flask import request, jsonify, g

from src.auth.config import AuthConfig
from src.auth.token import TokenManager
from src.persistence.database import get_db_session
from src.persistence.repository import DocumentRepository
from src.persistence.models import UserRecord, DocumentRecord, UserRole, AccountStatus, AdvocateStatus

class AuthorizationError(Exception):
    def __init__(self, message: str = "Access forbidden: insufficient permissions.", status_code: int = 403):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class AuthenticationError(Exception):
    def __init__(self, message: str = "Authentication required.", status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class AccessController:
    """Core programmatic authorization policy evaluator."""

    @staticmethod
    def can_access_contract(
        user: UserRecord,
        document: DocumentRecord,
        require_full_content: bool = True
    ) -> bool:
        """
        Evaluates whether user has permission to access the target contract.
        - CLIENT: only contracts where document.owner_id == user.id
        - LAWYER: only contracts where document.assigned_lawyer_id == user.id AND advocate_status == VERIFIED
        - SUPERVISING_LAWYER: access to contracts for review and supervision
        - AUDITOR: allowed for metadata inspection only (require_full_content=False); denied for raw text
        """
        if not user or not document:
            return False
            
        if user.account_status != AccountStatus.ACTIVE.value:
            return False

        role = user.role

        if role == UserRole.SUPERVISING_LAWYER.value:
            return True

        if role == UserRole.CLIENT.value:
            return document.owner_id == user.id

        if role == UserRole.LAWYER.value:
            if user.advocate_status != AdvocateStatus.VERIFIED.value:
                return False
            return document.assigned_lawyer_id == user.id

        if role == UserRole.AUDITOR.value:
            # Auditors can view audit logs and metadata, but never raw contract contents
            return not require_full_content

        return False

    @staticmethod
    def can_perform_lawyer_operations(user: UserRecord) -> bool:
        """True only if user is a verified advocate or supervising lawyer."""
        if not user or user.account_status != AccountStatus.ACTIVE.value:
            return False
        if user.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            return False
        return user.advocate_status == AdvocateStatus.VERIFIED.value

    @staticmethod
    def can_perform_supervisory_operations(user: UserRecord) -> bool:
        """True only for Supervising Lawyers."""
        if not user or user.account_status != AccountStatus.ACTIVE.value:
            return False
        return user.role == UserRole.SUPERVISING_LAWYER.value

    @staticmethod
    def can_access_audit_logs(user: UserRecord) -> bool:
        """True for Auditors and Supervising Lawyers."""
        if not user or user.account_status != AccountStatus.ACTIVE.value:
            return False
        return user.role in (UserRole.AUDITOR.value, UserRole.SUPERVISING_LAWYER.value)


# =========================================================================
# FLASK ROUTE DECORATORS & MIDDLEWARE
# =========================================================================

def extract_current_user_from_request(token_manager: Optional[TokenManager] = None) -> Optional[UserRecord]:
    """
    Extracts authenticated user from Authorization header (Bearer token) or session cookie.
    Validates token signature, database-backed persistent session state (SHA-256 token hash),
    session expiration, sliding activity window, and current database account status.
    """
    cfg = AuthConfig()
    tm = token_manager or TokenManager(config=cfg)
    token = None
    
    # 1. Bearer header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        
    # 2. Session cookie fallback
    if not token:
        token = request.cookies.get(cfg.session_cookie_name)

    if not token:
        return None

    payload = tm.decode_and_validate_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id:
        return None

    token_hash = hashlib.sha256(jti.encode("utf-8")).hexdigest() if jti else None

    # Retrieve fresh user record and validate persistent session from database
    with get_db_session() as sess:
        repo = DocumentRepository(sess)

        # Check persistent session registry if token_hash exists
        if token_hash:
            session_rec = repo.get_session_by_token_hash(token_hash)
            if session_rec:
                if session_rec.is_revoked:
                    return None
                    
                now = datetime.datetime.now(datetime.timezone.utc)
                exp = session_rec.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=datetime.timezone.utc)
                if exp <= now:
                    repo.revoke_session_by_hash(token_hash, reason="EXPIRED")
                    return None
                    
                # Sliding activity update: if more than 60s elapsed since last activity
                last_act = session_rec.last_activity_at or session_rec.created_at
                if last_act.tzinfo is None:
                    last_act = last_act.replace(tzinfo=datetime.timezone.utc)
                if (now - last_act).total_seconds() > 60:
                    repo.update_session_activity(token_hash, now)

        user = repo.get_user_by_id(user_id)
        if user and user.account_status == AccountStatus.ACTIVE.value:
            # Detach user representation for request context
            return UserRecord(
                id=user.id,
                email=user.email,
                role=user.role,
                account_status=user.account_status,
                advocate_status=user.advocate_status,
                full_name=user.full_name,
                bar_enrolment_id=user.bar_enrolment_id,
                state_bar_council=user.state_bar_council,
                year_of_enrolment=user.year_of_enrolment
            )
        elif user and user.account_status != AccountStatus.ACTIVE.value:
            # User account is suspended or deactivated; revoke session immediately
            if token_hash:
                repo.revoke_session_by_hash(token_hash, reason="ACCOUNT_SUSPENDED")

    return None

def require_auth(fn: Callable) -> Callable:
    """Decorator enforcing that the caller is authenticated."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = extract_current_user_from_request()
        if not user:
            return jsonify({"error": "Authentication required", "status_code": 401}), 401
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper

def require_roles(*allowed_roles) -> Callable:
    """Decorator enforcing that the caller possesses one of the allowed roles."""
    role_values = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            role_values.extend([x.value if hasattr(x, "value") else str(x) for x in r])
        else:
            role_values.append(r.value if hasattr(r, "value") else str(r))

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = extract_current_user_from_request()
            if not user:
                return jsonify({"error": "Authentication required", "status_code": 401}), 401
            if user.role not in role_values:
                return jsonify({
                    "error": "Forbidden: user role does not possess required privilege.",
                    "status_code": 403
                }), 403
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_verified_advocate(fn: Callable) -> Callable:
    """Decorator enforcing that the caller is a VERIFIED lawyer or supervising lawyer."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = extract_current_user_from_request()
        if not user:
            return jsonify({"error": "Authentication required", "status_code": 401}), 401
        if not AccessController.can_perform_lawyer_operations(user):
            return jsonify({
                "error": "Forbidden: advocate verification required for this operation.",
                "status_code": 403
            }), 403
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper

def require_contract_access(require_full_content: bool = True) -> Callable:
    """Decorator verifying that current user has explicit permission to access the requested contract."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = extract_current_user_from_request()
            if not user:
                return jsonify({"error": "Authentication required", "status_code": 401}), 401
                
            document_id = kwargs.get("document_id") or kwargs.get("doc_id")
            if not document_id:
                return jsonify({"error": "Document identifier missing", "status_code": 400}), 400

            with get_db_session() as sess:
                repo = DocumentRepository(sess)
                doc = repo.get_document_by_id(document_id)
                if not doc:
                    return jsonify({"error": "Document not found", "status_code": 404}), 404

                has_access = AccessController.can_access_contract(
                    user, doc, require_full_content=require_full_content
                )
                if not has_access:
                    return jsonify({
                        "error": "Forbidden: you do not have permission to access this contract.",
                        "status_code": 403
                    }), 403

            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
