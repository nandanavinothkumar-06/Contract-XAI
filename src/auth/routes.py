"""
Flask blueprint defining REST API endpoints for authentication, advocate verification,
and role-based contract/audit access control.
"""

from flask import Blueprint, request, jsonify, g
from src.auth.config import AuthConfig
from src.auth.service import AuthService
from src.auth.token import TokenManager
from src.auth.csrf import generate_csrf_token
from src.auth.rbac import (
    require_auth, require_roles, require_verified_advocate,
    require_contract_access, AccessController
)
from src.persistence.database import get_db_session
from src.persistence.repository import DocumentRepository
from src.persistence.models import UserRole, AdvocateStatus, AccountStatus

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name", "")
    role_str = data.get("role", UserRole.CLIENT.value)
    
    # Optional advocate registration fields
    bar_enrolment_id = data.get("bar_enrolment_id")
    state_bar_council = data.get("state_bar_council")
    year_of_enrolment = data.get("year_of_enrolment")
    
    try:
        role = UserRole(role_str)
    except ValueError:
        return jsonify({"error": f"Invalid role '{role_str}'", "status_code": 400}), 400

    with get_db_session() as sess:
        auth_service = AuthService(sess)
        try:
            user = auth_service.register_user(
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                bar_enrolment_id=bar_enrolment_id,
                state_bar_council=state_bar_council,
                year_of_enrolment=year_of_enrolment
            )
            return jsonify({
                "message": "User registered successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "advocate_status": user.advocate_status,
                    "full_name": user.full_name
                }
            }), 201
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 400}), 400
        except Exception as e:
            return jsonify({"error": "Registration failed due to an internal error.", "status_code": 500}), 500

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")
    remember_me = bool(data.get("remember_me", False))
    
    if not email or not password:
        return jsonify({"error": "Email and password are required.", "status_code": 400}), 400

    ip_address = request.remote_addr
    user_agent = request.headers.get("User-Agent", "")

    with get_db_session() as sess:
        auth_service = AuthService(sess)
        user, token, err = auth_service.authenticate_user(
            email=email,
            password=password,
            remember_me=remember_me,
            ip_address=ip_address,
            user_agent=user_agent
        )
        if err or not user:
            return jsonify({"error": err or "Invalid credentials", "status_code": 401}), 401

        cfg = auth_service.config
        csrf_token = generate_csrf_token()

        max_age = (cfg.remember_me_days * 86400) if remember_me else (cfg.access_token_expire_minutes * 60)

        resp = jsonify({
            "message": "Authentication successful",
            "access_token": token,
            "token_type": "Bearer",
            "csrf_token": csrf_token,
            "remember_me": remember_me,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "advocate_status": user.advocate_status,
                "full_name": user.full_name
            }
        })
        
        # Set HttpOnly session cookie
        resp.set_cookie(
            cfg.session_cookie_name,
            token,
            httponly=cfg.cookie_httponly,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
            path=cfg.cookie_path,
            max_age=max_age
        )

        # Set readable CSRF cookie for Double-Submit pattern
        resp.set_cookie(
            cfg.csrf_cookie_name,
            csrf_token,
            httponly=False,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
            path=cfg.cookie_path,
            max_age=max_age
        )
        return resp, 200

@auth_bp.route("/api/auth/logout", methods=["POST"])
@require_auth
def logout():
    cfg = AuthConfig()
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else request.cookies.get(cfg.session_cookie_name)
    
    user_id = getattr(g.get("current_user", None), "id", None)
    if token:
        with get_db_session() as sess:
            auth_service = AuthService(sess)
            auth_service.logout_user(token, user_id=user_id)
        
    resp = jsonify({"message": "Successfully logged out."})
    resp.delete_cookie(cfg.session_cookie_name, path=cfg.cookie_path)
    resp.delete_cookie(cfg.csrf_cookie_name, path=cfg.cookie_path)
    return resp, 200

@auth_bp.route("/api/auth/csrf", methods=["GET"])
def get_csrf():
    """Generates and sets a fresh CSRF token."""
    cfg = AuthConfig()
    csrf_token = generate_csrf_token()
    resp = jsonify({"csrf_token": csrf_token})
    resp.set_cookie(
        cfg.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,
        path=cfg.cookie_path
    )
    return resp, 200

@auth_bp.route("/api/auth/me", methods=["GET"])
@require_auth
def get_current_user_profile():
    cfg = AuthConfig()
    user = g.current_user
    csrf_token = request.cookies.get(cfg.csrf_cookie_name)
    needs_cookie = False
    if not csrf_token:
        csrf_token = generate_csrf_token()
        needs_cookie = True

    resp = jsonify({
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "account_status": user.account_status,
        "advocate_status": user.advocate_status,
        "full_name": user.full_name,
        "bar_enrolment_id": user.bar_enrolment_id,
        "state_bar_council": user.state_bar_council,
        "year_of_enrolment": user.year_of_enrolment,
        "csrf_token": csrf_token
    })
    if needs_cookie:
        resp.set_cookie(
            cfg.csrf_cookie_name,
            csrf_token,
            httponly=False,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
            path=cfg.cookie_path
        )
    return resp, 200

@auth_bp.route("/api/auth/password/change", methods=["POST"])
@require_auth
def change_password_endpoint():
    """Changes user password and cascades revocation across all active sessions."""
    cfg = AuthConfig()
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "Both old_password and new_password are required.", "status_code": 400}), 400

    with get_db_session() as sess:
        auth_service = AuthService(sess)
        try:
            success, err = auth_service.change_password(
                user_id=g.current_user.id,
                old_password=old_password,
                new_password=new_password
            )
            if not success:
                return jsonify({"error": err or "Password change failed.", "status_code": 400}), 400

            resp = jsonify({
                "message": "Password changed successfully. All active sessions have been invalidated.",
                "status_code": 200
            })
            resp.delete_cookie(cfg.session_cookie_name, path=cfg.cookie_path)
            resp.delete_cookie(cfg.csrf_cookie_name, path=cfg.cookie_path)
            return resp, 200
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 400}), 400
        except Exception as e:
            return jsonify({"error": "Password change failed.", "status_code": 500}), 500

# =========================================================================
# ADVOCATE VERIFICATION ENDPOINTS
# =========================================================================

@auth_bp.route("/api/advocate/verify/submit", methods=["POST"])
@require_auth
def submit_verification():
    user = g.current_user
    data = request.get_json(silent=True) or {}
    
    bar_id = data.get("bar_enrolment_id")
    state_council = data.get("state_bar_council")
    year = data.get("year_of_enrolment")
    notes = data.get("evidence_notes")
    
    with get_db_session() as sess:
        auth_service = AuthService(sess)
        try:
            req = auth_service.submit_advocate_verification(
                applicant=user,
                bar_enrolment_id=bar_id,
                state_bar_council=state_council,
                year_of_enrolment=year,
                evidence_notes=notes
            )
            return jsonify({
                "message": "Advocate verification request submitted.",
                "request_id": req.id,
                "status": req.status
            }), 202
        except (PermissionError, ValueError) as e:
            return jsonify({"error": str(e), "status_code": 400}), 400

@auth_bp.route("/api/advocate/verify/decide", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER)
def decide_verification():
    reviewer = g.current_user
    data = request.get_json(silent=True) or {}
    
    request_id = data.get("request_id")
    decision_str = data.get("decision")
    rationale = data.get("rationale")
    
    try:
        decision = AdvocateStatus(decision_str)
    except ValueError:
        return jsonify({"error": f"Invalid decision '{decision_str}'", "status_code": 400}), 400

    with get_db_session() as sess:
        auth_service = AuthService(sess)
        try:
            updated_req = auth_service.decide_advocate_verification(
                reviewer=reviewer,
                request_id=request_id,
                decision=decision,
                rationale=rationale
            )
            return jsonify({
                "message": "Verification decision recorded successfully.",
                "request_id": updated_req.id,
                "applicant_id": updated_req.user_id,
                "status": updated_req.status,
                "decided_at": updated_req.decided_at.isoformat() if updated_req.decided_at else None
            }), 200
        except (PermissionError, ValueError) as e:
            return jsonify({"error": str(e), "status_code": 403 if isinstance(e, PermissionError) else 400}), 403 if isinstance(e, PermissionError) else 400

# =========================================================================
# RBAC PROTECTED CONTRACT & AUDIT ACCESS
# =========================================================================

@auth_bp.route("/api/contracts/<document_id>", methods=["GET"])
@require_contract_access(require_full_content=True)
def get_contract_details(document_id: str):
    """
    Retrieves contract details and extracted text.
    Enforces that CLIENTs access only their owned documents,
    and LAWYERs access only assigned documents.
    """
    user = g.current_user
    with get_db_session() as sess:
        repo = DocumentRepository(sess)
        doc = repo.get_document_by_id(document_id)
        if not doc:
            return jsonify({"error": "Document not found", "status_code": 404}), 404

        snapshot = doc.text_snapshots[0] if doc.text_snapshots else None
        return jsonify({
            "document_id": doc.id,
            "filename": doc.sanitized_filename,
            "status": doc.status,
            "char_count": doc.char_count,
            "page_count": doc.page_count,
            "raw_text": snapshot.raw_text if snapshot else "",
            "segments_count": len(doc.segments)
        }), 200

@auth_bp.route("/api/audit/logs", methods=["GET"])
@require_roles(UserRole.AUDITOR, UserRole.SUPERVISING_LAWYER)
def get_audit_logs():
    """
    Returns audit trail records for compliance inspection.
    CLIENT and ordinary LAWYER roles are denied.
    """
    with get_db_session() as sess:
        from src.persistence.models import AuditEventRecord
        events = sess.query(AuditEventRecord).order_by(AuditEventRecord.created_at.desc()).limit(100).all()
        return jsonify({
            "count": len(events),
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "actor_type": e.actor_type,
                    "event_hash": e.event_hash
                } for e in events
            ]
        }), 200
