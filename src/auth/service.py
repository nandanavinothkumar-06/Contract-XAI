"""
Core Authentication and Advocate Verification Service.
Enforces email normalization, Argon2id password hashing, generic login failures,
self-promotion prevention, advocate verification state transitions, and audit trail integration.
"""

import re
import uuid
import datetime
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session

import json
import hashlib
import jwt
from src.auth.config import AuthConfig
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.csrf import generate_csrf_token
from src.persistence.models import (
    UserRecord, AdvocateVerificationRecord, UserRole, AccountStatus, AdvocateStatus, AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.audit.logger import AuditLogger
from src.audit.store import AuditStore
from src.audit.schema import AuditEvent
from src.audit.provenance import EventType, ActorType

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class AuthService:
    def __init__(
        self,
        session: Session,
        config: Optional[AuthConfig] = None,
        audit_logger: Optional[AuditLogger] = None
    ):
        self.session = session
        self.config = config or AuthConfig()
        self.repo = DocumentRepository(session)
        self.password_manager = PasswordManager(self.config)
        self.token_manager = TokenManager(self.config)
        
        # Audit logger integration
        self.audit_logger = audit_logger or AuditLogger(AuditStore())
        self.last_created_session = None
        self.last_csrf_token = None

    def _normalize_email(self, email: str) -> str:
        if not email or not isinstance(email, str):
            raise ValueError("Email must be a valid non-empty string.")
        normalized = email.strip().lower()
        if not EMAIL_REGEX.match(normalized):
            raise ValueError(f"Invalid email address format: '{email}'")
        return normalized

    def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.CLIENT,
        bar_enrolment_id: Optional[str] = None,
        state_bar_council: Optional[str] = None,
        year_of_enrolment: Optional[int] = None,
        actor_user: Optional[UserRecord] = None
    ) -> UserRecord:
        """
        Registers a new user account with strict privilege escalation prevention.
        - Ordinary registration allows CLIENT or LAWYER.
        - Registering as LAWYER automatically sets advocate_status = PENDING_VERIFICATION.
        - Registering as SUPERVISING_LAWYER or AUDITOR requires an existing SUPERVISING_LAWYER actor.
        """
        norm_email = self._normalize_email(email)
        
        # Check duplicate normalized email
        existing = self.repo.get_user_by_email(norm_email)
        if existing:
            raise ValueError(f"An account with email '{norm_email}' already exists.")

        # Self-promotion prevention: privileged roles cannot be self-assigned
        target_role = role.value if hasattr(role, "value") else str(role)
        privileged_roles = (UserRole.SUPERVISING_LAWYER.value, UserRole.AUDITOR.value)
        
        if target_role in privileged_roles:
            if not actor_user or actor_user.role != UserRole.SUPERVISING_LAWYER.value:
                raise PermissionError(
                    f"Self-promotion to privileged role '{target_role}' is prohibited. "
                    "Privileged roles must be provisioned by a Supervising Lawyer."
                )

        # Validate advocate prerequisites
        advocate_status = AdvocateStatus.NOT_APPLICABLE
        if target_role == UserRole.LAWYER.value:
            if not bar_enrolment_id or not bar_enrolment_id.strip():
                raise ValueError("Bar enrolment ID is mandatory for advocate registration.")
            if not state_bar_council or not state_bar_council.strip():
                raise ValueError("State Bar Council name is mandatory for advocate registration.")
            if not year_of_enrolment or year_of_enrolment < 1950 or year_of_enrolment > 2030:
                raise ValueError("Valid year of enrolment is mandatory for advocate registration.")
            # Unverified advocate by default
            advocate_status = AdvocateStatus.PENDING_VERIFICATION

        # Hash password via Argon2id
        password_hash = self.password_manager.hash_password(password)

        user_id = str(uuid.uuid4())
        user = self.repo.create_user(
            user_id=user_id,
            email=norm_email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            account_status=AccountStatus.ACTIVE,
            advocate_status=advocate_status,
            bar_enrolment_id=bar_enrolment_id,
            state_bar_council=state_bar_council,
            year_of_enrolment=year_of_enrolment
        )

        # If registered as advocate, persist initial verification request
        if target_role == UserRole.LAWYER.value:
            req_id = str(uuid.uuid4())
            self.repo.create_advocate_verification_request(
                request_id=req_id,
                user_id=user_id,
                bar_enrolment_id=bar_enrolment_id,
                state_bar_council=state_bar_council,
                year_of_enrolment=year_of_enrolment,
                evidence_notes="Initial submission at registration"
            )

        # Audit Event
        evt = self.audit_logger.log_event(
            event_type=EventType.USER_REGISTERED,
            actor_type=ActorType.USER,
            actor_reference=user_id,
            event_payload={
                "user_id": user_id,
                "role": target_role,
                "advocate_status": advocate_status.value
            }
        )
        self.repo.record_audit_event(evt)

        return user

    def authenticate_user(
        self,
        email: str,
        password: str,
        remember_me: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[Optional[UserRecord], Optional[str], Optional[str]]:
        """
        Authenticates user with constant-time password verification, creates persistent session,
        and returns generic error responses.
        Returns: (user, token, error_message)
        """
        try:
            norm_email = self._normalize_email(email)
        except ValueError:
            return None, None, "Invalid email or password."

        user = self.repo.get_user_by_email(norm_email)
        
        # Constant-time dummy verification if user doesn't exist to prevent timing attacks
        if not user:
            # Run dummy verification to match timing
            self.password_manager.verify_password("dummy_password", "$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy")
            self._log_auth_event(EventType.LOGIN_FAILED, email=norm_email, reason="USER_NOT_FOUND")
            return None, None, "Invalid email or password."

        # Verify password
        is_valid = self.password_manager.verify_password(password, user.password_hash)
        if not is_valid:
            self._log_auth_event(EventType.LOGIN_FAILED, user_id=user.id, reason="PASSWORD_MISMATCH")
            return None, None, "Invalid email or password."

        # Check account status
        if user.account_status != AccountStatus.ACTIVE.value:
            self._log_auth_event(EventType.LOGIN_FAILED, user_id=user.id, reason="ACCOUNT_SUSPENDED")
            return None, None, "Account is suspended. Please contact platform compliance."

        # Transparently upgrade hash parameters if necessary
        if self.password_manager.needs_rehash(user.password_hash):
            user.password_hash = self.password_manager.hash_password(password)
            self.session.flush()

        # Calculate session lifetime
        now = datetime.datetime.now(datetime.timezone.utc)
        if remember_me:
            duration_minutes = self.config.remember_me_days * 24 * 60
        else:
            duration_minutes = self.config.access_token_expire_minutes
        expires_at = now + datetime.timedelta(minutes=duration_minutes)

        # Generate JWT bearer token
        token = self.token_manager.generate_token(user, expires_delta_minutes=duration_minutes)

        # Extract jti and persist session in database registry
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                audience=self.token_manager.AUDIENCE,
                options={"verify_exp": False}
            )
            jti = payload.get("jti") or str(uuid.uuid4())
        except Exception:
            jti = str(uuid.uuid4())

        session_token_hash = hashlib.sha256(jti.encode("utf-8")).hexdigest()
        session_id = str(uuid.uuid4())
        session_rec = self.repo.create_session(
            session_id=session_id,
            user_id=user.id,
            session_token_hash=session_token_hash,
            expires_at=expires_at,
            remember_me=remember_me,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.last_created_session = session_rec
        self.last_csrf_token = generate_csrf_token()

        # Audit events
        self._log_auth_event(
            EventType.SESSION_CREATED,
            user_id=user.id,
            reason=f"SESSION_PERSISTED:{session_id[:8]}"
        )
        self._log_auth_event(EventType.LOGIN_SUCCESS, user_id=user.id)
        return user, token, None

    def logout_user(self, token: str, user_id: Optional[str] = None) -> bool:
        """Revokes persistent database session and bearer token, logging audit event."""
        # 1. Invalidate in-memory TokenManager
        revoked = self.token_manager.revoke_token(token)

        # 2. Invalidate persistent session in database
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                audience=self.token_manager.AUDIENCE,
                options={"verify_exp": False}
            )
            jti = payload.get("jti")
            if jti:
                token_hash = hashlib.sha256(jti.encode("utf-8")).hexdigest()
                self.repo.revoke_session_by_hash(token_hash, reason="LOGOUT")
        except Exception:
            pass

        # 3. Audit logging
        if user_id:
            self._log_auth_event(EventType.SESSION_REVOKED, user_id=user_id, reason="EXPLICIT_LOGOUT")
            self._log_auth_event(EventType.LOGOUT, user_id=user_id)
        return True

    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Changes user password after verifying current credentials.
        Revokes all existing persistent sessions to prevent session hijacking.
        """
        user = self.repo.get_user_by_id(user_id)
        if not user:
            return False, "User not found."

        if not self.password_manager.verify_password(old_password, user.password_hash):
            return False, "Current password does not match."

        if len(new_password) < self.config.min_password_length or len(new_password) > self.config.max_password_length:
            return False, f"Password must be between {self.config.min_password_length} and {self.config.max_password_length} characters."

        user.password_hash = self.password_manager.hash_password(new_password)
        user.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # Cascade revocation of all active sessions
        revoked_count = self.repo.revoke_all_user_sessions(user_id, reason="PASSWORD_CHANGED")
        self.session.flush()

        self._log_auth_event(
            EventType.SESSION_REVOKED,
            user_id=user_id,
            reason=f"ALL_SESSIONS_REVOKED_ON_PASSWORD_CHANGE:{revoked_count}"
        )
        return True, None

    def suspend_user_account(
        self,
        admin_user: UserRecord,
        user_id: str,
        reason: str = "COMPLIANCE_SUSPENSION"
    ) -> UserRecord:
        """
        Suspends an account and revokes all active sessions. Requires SUPERVISING_LAWYER.
        """
        if admin_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Only Supervising Lawyers can suspend accounts.")

        user = self.repo.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")

        user.account_status = AccountStatus.SUSPENDED.value
        user.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # Invalidate all active sessions immediately
        self.repo.revoke_all_user_sessions(user_id, reason="ACCOUNT_SUSPENDED")
        self.session.flush()

        self._log_auth_event(
            EventType.ACCOUNT_SUSPENDED,
            user_id=user_id,
            reason=reason
        )
        return user


    # =========================================================================
    # ADVOCATE VERIFICATION WORKFLOW
    # =========================================================================

    def submit_advocate_verification(
        self,
        applicant: UserRecord,
        bar_enrolment_id: str,
        state_bar_council: str,
        year_of_enrolment: int,
        evidence_notes: Optional[str] = None
    ) -> AdvocateVerificationRecord:
        """
        Submits advocate enrolment details for verification.
        Applicant must be in LAWYER role.
        """
        if applicant.role != UserRole.LAWYER.value:
            raise PermissionError("Only users with LAWYER role can submit advocate verification.")
            
        if not bar_enrolment_id or not bar_enrolment_id.strip():
            raise ValueError("Bar enrolment ID cannot be empty.")
            
        req_id = str(uuid.uuid4())
        req = self.repo.create_advocate_verification_request(
            request_id=req_id,
            user_id=applicant.id,
            bar_enrolment_id=bar_enrolment_id,
            state_bar_council=state_bar_council,
            year_of_enrolment=year_of_enrolment,
            evidence_notes=evidence_notes
        )

        evt = self.audit_logger.log_event(
            event_type=EventType.ADVOCATE_VERIFICATION_SUBMITTED,
            actor_type=ActorType.USER,
            actor_reference=applicant.id,
            event_payload={
                "request_id": req_id,
                "bar_enrolment_id": bar_enrolment_id,
                "state_bar_council": state_bar_council
            }
        )
        self.repo.record_audit_event(evt)
        return req

    def decide_advocate_verification(
        self,
        reviewer: UserRecord,
        request_id: str,
        decision: AdvocateStatus,
        rationale: str
    ) -> AdvocateVerificationRecord:
        """
        Applies an authorized decision (VERIFIED or REJECTED) on a pending advocate verification.
        Enforces:
        1. Reviewer must have SUPERVISING_LAWYER role.
        2. Reviewer cannot verify themselves (self-verification prevention).
        3. Decision must be VERIFIED, REJECTED, or SUSPENDED.
        4. Validates state transition from PENDING_VERIFICATION.
        """
        if reviewer.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Only a Supervising Lawyer can review advocate verifications.")

        req = self.repo.get_advocate_verification_by_id(request_id)
        if not req:
            raise ValueError(f"Verification request '{request_id}' not found.")

        # Self-verification prevention
        if req.user_id == reviewer.id:
            raise PermissionError("Self-verification is prohibited. Reviewer cannot verify their own application.")

        # State transition validation
        allowed_decisions = (AdvocateStatus.VERIFIED, AdvocateStatus.REJECTED, AdvocateStatus.SUSPENDED)
        if decision not in allowed_decisions:
            raise ValueError(f"Invalid verification decision '{decision}'. Allowed: {allowed_decisions}")

        if req.status != AdvocateStatus.PENDING_VERIFICATION.value and decision == AdvocateStatus.VERIFIED:
            raise ValueError(f"Cannot verify request in status '{req.status}' (must be PENDING_VERIFICATION).")

        if not rationale or not rationale.strip():
            raise ValueError("A formal decision rationale is mandatory for advocate verification decisions.")

        updated_req = self.repo.decide_advocate_verification(
            request_id=request_id,
            reviewer_id=reviewer.id,
            decision=decision,
            rationale=rationale.strip()
        )

        # Audit Event
        self._ensure_audit_store_hydrated()
        evt = self.audit_logger.log_event(
            event_type=EventType.ADVOCATE_VERIFICATION_DECIDED,
            actor_type=ActorType.ADMIN,
            actor_reference=reviewer.id,
            event_payload={
                "request_id": request_id,
                "applicant_id": req.user_id,
                "decision": decision.value,
                "rationale": rationale.strip()
            }
        )
        self.repo.record_audit_event(evt)

        return updated_req

    def _ensure_audit_store_hydrated(self):
        """Ensures that the in-memory audit store is chained to the tip of the database audit log."""
        if hasattr(self.audit_logger, "store") and self.audit_logger.store.get_last_event() is None:
            last_rec = (
                self.session.query(AuditEventRecord)
                .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc())
                .first()
            )
            if last_rec:
                ae = AuditEvent(
                    event_id=last_rec.event_id,
                    event_type=EventType(last_rec.event_type),
                    timestamp=last_rec.timestamp,
                    source_document_id=last_rec.document_id,
                    actor_type=ActorType(last_rec.actor_type),
                    event_payload=json.loads(last_rec.payload_json) if last_rec.payload_json else {},
                    previous_event_hash=last_rec.previous_event_hash
                )
                ae.event_hash = last_rec.event_hash
                self.audit_logger.store.append(ae)

    def _log_auth_event(
        self,
        event_type: EventType,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Helper to record security audit events without logging sensitive credentials."""
        self._ensure_audit_store_hydrated()
        payload = {}
        if reason:
            payload["reason"] = reason
            
        evt = self.audit_logger.log_event(
            event_type=event_type,
            actor_type=ActorType.USER if user_id else ActorType.SYSTEM,
            actor_reference=user_id or "ANONYMOUS",
            event_payload=payload
        )
        self.repo.record_audit_event(evt)
