"""
Flask Blueprint defining REST API endpoints for Task 034 Final Lawyer-Reviewed Reports and Client Feedback.

Enforces:
1. Server-side role and tenant access boundaries on all report endpoints.
2. Advocate verification gates on final report generation.
3. Client privacy: internal lawyer notes and comments are never exposed.
4. Immutable report versions and traceable superseding.
5. Structured client feedback and advocate responses.
6. Cryptographically hash-chained audit logging.
"""

import json
from flask import Blueprint, request, jsonify, g, Response

from src.auth.rbac import (
    require_auth, require_roles, require_verified_advocate, AccessController
)
from src.persistence.database import get_db_session
from src.persistence.models import (
    UserRole, AccountStatus, AdvocateStatus,
    ReportStatus, FeedbackStatus
)
from src.reporting.service import ReportService
from src.reporting.schema import (
    FeedbackSubmitRequest, FeedbackResponseRequest, FeedbackStatusUpdateRequest
)

reporting_bp = Blueprint("reporting", __name__, url_prefix="/api/reports")


# =============================================================================
# 1. REPORT GENERATION & PREVIEW
# =============================================================================

@reporting_bp.route("/generate/<review_id>", methods=["POST"])
@require_auth
@require_verified_advocate
def generate_report(review_id: str):
    """
    Generates an immutable final report for a completed review.
    Enforces review completion prerequisites, document version matching,
    and advocate assignment.
    """
    user = g.current_user
    export_pdf = request.json.get("export_pdf", True) if request.is_json else True

    with get_db_session() as sess:
        service = ReportService(sess)
        try:
            report = service.generate_final_report(
                review_id=review_id,
                actor_user=user,
                export_pdf=export_pdf
            )
            sess.commit()
            payload = json.loads(report.report_payload_json)
            return jsonify({
                "message": "Final lawyer-reviewed report generated successfully.",
                "report_id": report.id,
                "report_number": report.report_number,
                "report_version": report.report_version,
                "content_sha256": report.content_sha256,
                "pdf_sha256": report.pdf_sha256,
                "is_final": report.is_final,
                "status": report.status,
                "metadata": payload.get("metadata", {}),
                "executive_summary": payload.get("executive_summary", {})
            }), 201
        except ValueError as e:
            return jsonify({"error": str(e), "status_code": 400}), 400
        except PermissionError as e:
            return jsonify({"error": str(e), "status_code": 403}), 403
        except RuntimeError as e:
            return jsonify({"error": str(e), "status_code": 500}), 500


@reporting_bp.route("/preview/<review_id>", methods=["GET"])
@require_auth
def preview_report(review_id: str):
    """
    Returns a draft preview of the report (is_final = False).
    Clearly marked as DRAFT.
    """
    user = g.current_user

    with get_db_session() as sess:
        service = ReportService(sess)
        try:
            preview_payload = service.generate_draft_preview(
                review_id=review_id,
                actor_user=user
            )
            return jsonify({
                "preview": preview_payload,
                "notice": "DRAFT PREVIEW — NOT A FINAL LAWYER REPORT"
            }), 200
        except ValueError as e:
            return jsonify({"error": str(e), "status_code": 404}), 404
        except PermissionError as e:
            return jsonify({"error": str(e), "status_code": 403}), 403


@reporting_bp.route("/<report_id>", methods=["GET"])
@require_auth
def get_report(report_id: str):
    """
    Retrieves report details and structured findings.
    Enforces tenant isolation for CLIENT users.
    Internal lawyer notes are never exposed.
    """
    user = g.current_user

    with get_db_session() as sess:
        service = ReportService(sess)
        report = service.repo.get_report_by_id(report_id)
        if not report:
            return jsonify({"error": f"Report '{report_id}' not found.", "status_code": 404}), 404

        doc = report.document
        if user.role == UserRole.CLIENT.value:
            if doc and doc.owner_id != user.id:
                return jsonify({"error": "Forbidden: You cannot access reports for other clients' contracts.", "status_code": 403}), 403
        elif user.role == UserRole.LAWYER.value:
            if doc and doc.assigned_lawyer_id != user.id and report.generated_by_id != user.id:
                return jsonify({"error": "Forbidden: You are not assigned to this contract review.", "status_code": 403}), 403

        payload = json.loads(report.report_payload_json)
        return jsonify({
            "report_id": report.id,
            "report_number": report.report_number,
            "report_version": report.report_version,
            "status": report.status,
            "is_final": report.is_final,
            "content_sha256": report.content_sha256,
            "pdf_sha256": report.pdf_sha256,
            "payload": payload
        }), 200


@reporting_bp.route("/<report_id>/pdf", methods=["GET"])
@require_auth
def download_pdf(report_id: str):
    """
    Downloads client-facing publication-quality PDF report.
    Enforces tenant boundaries and records audit download event.
    """
    user = g.current_user

    with get_db_session() as sess:
        service = ReportService(sess)
        try:
            pdf_bytes, filename = service.download_report_pdf(report_id=report_id, actor_user=user)
            return Response(
                pdf_bytes,
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": len(pdf_bytes)
                }
            )
        except ValueError as e:
            return jsonify({"error": str(e), "status_code": 404}), 404
        except PermissionError as e:
            return jsonify({"error": str(e), "status_code": 403}), 403


@reporting_bp.route("/document/<document_id>", methods=["GET"])
@require_auth
def get_reports_for_document(document_id: str):
    """
    Returns report history (active and superseded) for a given document.
    """
    user = g.current_user

    with get_db_session() as sess:
        service = ReportService(sess)
        doc = service.repo.get_document_by_id(document_id)
        if not doc:
            return jsonify({"error": "Document not found.", "status_code": 404}), 404

        if user.role == UserRole.CLIENT.value:
            if doc.owner_id != user.id:
                return jsonify({"error": "Forbidden: You cannot access reports for other clients' contracts.", "status_code": 403}), 403
        elif user.role == UserRole.LAWYER.value:
            if doc.assigned_lawyer_id != user.id:
                return jsonify({"error": "Forbidden: You are not assigned to this contract.", "status_code": 403}), 403

        reports = service.repo.get_reports_for_document(document_id)
        items = []
        for r in reports:
            items.append({
                "report_id": r.id,
                "report_number": r.report_number,
                "report_version": r.report_version,
                "document_version": r.document_version,
                "status": r.status,
                "is_final": r.is_final,
                "generated_at": r.generated_at.isoformat(),
                "content_sha256": r.content_sha256,
                "pdf_sha256": r.pdf_sha256,
                "superseded_at": r.superseded_at.isoformat() if r.superseded_at else None,
                "superseded_by_id": r.superseded_by_id,
                "supersession_reason": r.supersession_reason
            })
        return jsonify({"reports": items}), 200


@reporting_bp.route("/client/queue", methods=["GET"])
@require_auth
def get_client_reports():
    """
    Returns list of finalized reports accessible to the logged-in client.
    """
    user = g.current_user
    if user.role != UserRole.CLIENT.value:
        return jsonify({"error": "This queue is dedicated to client users.", "status_code": 403}), 403

    with get_db_session() as sess:
        service = ReportService(sess)
        docs = sess.query(service.repo.session.query(service.repo.DocumentRecord).filter(
            service.repo.DocumentRecord.owner_id == user.id
        ).subquery())

        reports = (
            sess.query(service.repo.FinalReportRecord)
            .join(service.repo.DocumentRecord, service.repo.FinalReportRecord.document_id == service.repo.DocumentRecord.id)
            .filter(
                service.repo.DocumentRecord.owner_id == user.id,
                service.repo.FinalReportRecord.is_final == True
            )
            .order_by(service.repo.FinalReportRecord.generated_at.desc())
            .all()
        )

        items = []
        for r in reports:
            doc = r.document
            lawyer = r.review.assigned_lawyer if r.review else None
            items.append({
                "report_id": r.id,
                "report_number": r.report_number,
                "report_version": r.report_version,
                "document_id": r.document_id,
                "document_version": r.document_version,
                "filename": doc.original_filename if doc else "Contract",
                "lawyer_name": lawyer.full_name if lawyer else "Assigned Advocate",
                "status": r.status,
                "generated_at": r.generated_at.isoformat(),
                "content_sha256": r.content_sha256,
                "pdf_available": bool(r.pdf_storage_path)
            })
        return jsonify({"reports": items}), 200


# =============================================================================
# 2. CLIENT FEEDBACK WORKFLOW
# =============================================================================

@reporting_bp.route("/<report_id>/feedback", methods=["POST"])
@require_auth
def submit_feedback(report_id: str):
    """
    Submits structured client feedback against a specific final report version.
    Validates ratings (1 to 5) and tenant boundaries.
    """
    user = g.current_user
    data = request.get_json() or {}

    try:
        feedback_req = FeedbackSubmitRequest(**data)
    except Exception as e:
        return jsonify({"error": f"Invalid feedback payload: {str(e)}", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReportService(sess)
        try:
            feedback = service.submit_client_feedback(
                report_id=report_id,
                client_user=user,
                feedback_data=feedback_req
            )
            sess.commit()
            return jsonify({
                "message": "Client feedback submitted successfully.",
                "feedback_id": feedback.id,
                "report_id": feedback.report_id,
                "status": feedback.status,
                "submitted_at": feedback.submitted_at.isoformat()
            }), 201
        except ValueError as e:
            return jsonify({"error": str(e), "status_code": 400}), 400
        except PermissionError as e:
            return jsonify({"error": str(e), "status_code": 403}), 403


@reporting_bp.route("/<report_id>/feedback", methods=["GET"])
@require_auth
def get_report_feedback(report_id: str):
    """
    Retrieves feedback associated with a report.
    - CLIENT: only views their own submitted feedback and client-visible responses.
    - LAWYER/SUPERVISOR: views all feedback and responses for the report.
    """
    user = g.current_user

    with get_db_session() as sess:
        service = ReportService(sess)
        report = service.repo.get_report_by_id(report_id)
        if not report:
            return jsonify({"error": "Report not found.", "status_code": 404}), 404

        doc = report.document
        all_feedback = service.repo.get_feedback_for_report(report_id)
        if user.role == UserRole.CLIENT.value:
            if doc and doc.owner_id != user.id:
                return jsonify({"error": "Forbidden: You cannot access feedback for other clients' reports.", "status_code": 403}), 403
            feedbacks = [fb for fb in all_feedback if fb.client_id == user.id]
        else:
            feedbacks = all_feedback

        items = []
        for fb in feedbacks:
            client = fb.client
            # Filter responses for clients
            responses_data = []
            for resp in fb.responses:
                if user.role == UserRole.CLIENT.value and not resp.is_client_visible:
                    continue
                responder = resp.responder
                responses_data.append({
                    "response_id": resp.id,
                    "responder_name": responder.full_name if responder else "Advocate",
                    "responder_role": resp.responder_role,
                    "response_text": resp.response_text,
                    "is_client_visible": resp.is_client_visible,
                    "internal_notes": resp.internal_notes if user.role != UserRole.CLIENT.value else None,
                    "created_at": resp.created_at.isoformat()
                })

            items.append({
                "feedback_id": fb.id,
                "report_id": fb.report_id,
                "client_id": fb.client_id,
                "client_name": client.full_name if client else "Client",
                "overall_satisfaction": fb.overall_satisfaction,
                "clarity_rating": fb.clarity_rating,
                "usefulness_rating": fb.usefulness_rating,
                "needs_clarification": fb.needs_clarification,
                "follow_up_requested": fb.follow_up_requested,
                "client_comments": fb.client_comments,
                "status": fb.status,
                "submitted_at": fb.submitted_at.isoformat(),
                "responses": responses_data
            })

        return jsonify({"feedback": items}), 200


@reporting_bp.route("/feedback/<feedback_id>/respond", methods=["POST"])
@require_auth
@require_verified_advocate
def respond_feedback(feedback_id: str):
    """
    Records an advocate response to client feedback.
    Maintains client-visible vs internal notes separation.
    """
    user = g.current_user
    data = request.get_json() or {}

    try:
        resp_req = FeedbackResponseRequest(**data)
    except Exception as e:
        return jsonify({"error": f"Invalid response payload: {str(e)}", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReportService(sess)
        try:
            resp = service.respond_to_feedback(
                feedback_id=feedback_id,
                actor_user=user,
                response_data=resp_req
            )
            sess.commit()
            return jsonify({
                "message": "Feedback response recorded successfully.",
                "response_id": resp.id,
                "feedback_id": resp.feedback_id,
                "is_client_visible": resp.is_client_visible,
                "created_at": resp.created_at.isoformat()
            }), 201
        except ValueError as e:
            return jsonify({"error": str(e), "status_code": 404}), 404
        except PermissionError as e:
            return jsonify({"error": str(e), "status_code": 403}), 403


@reporting_bp.route("/feedback/<feedback_id>/status", methods=["POST"])
@require_auth
@require_verified_advocate
def update_feedback_status(feedback_id: str):
    """
    Updates the status of client feedback (ACKNOWLEDGED, CLOSED, etc.).
    """
    user = g.current_user
    data = request.get_json() or {}

    try:
        status_req = FeedbackStatusUpdateRequest(**data)
    except Exception as e:
        return jsonify({"error": f"Invalid status payload: {str(e)}", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReportService(sess)
        try:
            updated = service.update_feedback_status(
                feedback_id=feedback_id,
                actor_user=user,
                new_status=status_req.status
            )
            sess.commit()
            return jsonify({
                "message": f"Feedback status updated to {updated.status}.",
                "feedback_id": updated.id,
                "new_status": updated.status,
                "updated_at": updated.updated_at.isoformat()
            }), 200
        except ValueError as e:
            return jsonify({"error": str(e), "status_code": 400}), 400
        except PermissionError as e:
            return jsonify({"error": str(e), "status_code": 403}), 403
