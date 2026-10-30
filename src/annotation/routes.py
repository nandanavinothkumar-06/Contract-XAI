"""
REST API Routes for Blinded Annotation & Independent Submission Infrastructure.
Enforces RBAC, advocate verification, presentation firewalling, and submission locking.
"""

from flask import Blueprint, request, jsonify, g
from typing import Dict, Any

from src.persistence.database import get_db_session
from src.persistence.models import UserRole, AnnotationStage
from src.auth.rbac import require_auth, require_roles, require_verified_advocate
from src.annotation.firewall import PresentationFirewall, BlindingViolationError
from src.annotation.service import BlindedAnnotationService
from src.annotation.candidate_registry import CandidateRegistry


annotation_bp = Blueprint("annotation_bp", __name__, url_prefix="/api/annotation")


@annotation_bp.route("/candidate/<candidate_id>", methods=["GET"])
@require_auth
@require_roles(UserRole.LAWYER, UserRole.SUPERVISING_LAWYER)
def get_blinded_candidate(candidate_id: str):
    """
    Returns a presentation-firewalled candidate finding record for an authorized annotator.
    Filters out model identifier, confidence values, BM25 scores, and policy recommendations.
    Validates the ?stage= query parameter to apply stage-specific field allowlists.
    Rejects invalid stages with HTTP 400.
    """
    stage = request.args.get("stage", AnnotationStage.FULL_RECORD.value)
    allowed_stages = {s.value for s in AnnotationStage}
    if stage not in allowed_stages:
        return jsonify({
            "error": f"Invalid stage '{stage}'. Allowed stages are: {sorted(list(allowed_stages))}.",
            "status_code": 400
        }), 400

    with get_db_session() as sess:
        raw_candidate = CandidateRegistry.resolve(candidate_id, session=sess)
        if not raw_candidate:
            return jsonify({
                "error": f"Candidate finding '{candidate_id}' not found.",
                "status_code": 404
            }), 404

        try:
            sanitized = PresentationFirewall.filter_candidate_for_annotator(raw_candidate, stage=stage)
            return jsonify({
                "stage": stage,
                "candidate": sanitized
            }), 200
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 400}), 400


@annotation_bp.route("/submit", methods=["POST"])
@require_auth
@require_roles(UserRole.LAWYER, UserRole.SUPERVISING_LAWYER)
def submit_annotation():
    """
    Submits an independent legal annotation record.
    Enforces advocate verification, validates draft payload, and records hash-chained audit event.
    Authoritative candidate identification metadata is injected server-side.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}

    candidate_finding_id = data.get("candidate_finding_id")
    payload = data.get("payload")
    stage = data.get("stage", AnnotationStage.FULL_RECORD.value)
    is_synthetic = data.get("is_synthetic_fixture", False)

    allowed_stages = {s.value for s in AnnotationStage}
    if stage not in allowed_stages:
        return jsonify({
            "error": f"Invalid stage '{stage}'. Allowed stages are: {sorted(list(allowed_stages))}.",
            "status_code": 400
        }), 400

    if not candidate_finding_id or not payload:
        return jsonify({
            "error": "Missing required fields: candidate_finding_id, payload.",
            "status_code": 400
        }), 400

    with get_db_session() as sess:
        service = BlindedAnnotationService(sess)
        try:
            record = service.submit_annotation(
                candidate_finding_id=candidate_finding_id,
                contract_id=data.get("contract_id"),
                clause_id=data.get("clause_id"),
                annotator_user=user,
                payload=payload,
                stage=stage,
                is_synthetic_fixture=is_synthetic
            )
            return jsonify({
                "message": "Annotation submitted successfully.",
                "annotation_id": record.id,
                "candidate_finding_id": record.candidate_finding_id,
                "stage": record.stage,
                "version": record.version,
                "is_locked": record.is_locked,
                "payload_sha256": record.payload_sha256,
                "submitted_at": record.submitted_at.isoformat()
            }), 201
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 400}), 400


@annotation_bp.route("/lock/<annotation_id>", methods=["POST"])
@require_auth
@require_roles(UserRole.LAWYER, UserRole.SUPERVISING_LAWYER)
def lock_annotation(annotation_id: str):
    """
    Locks an annotation submission after schema validation.
    Once locked, ordinary edit/delete operations are permanently prohibited.
    """
    user = g.current_user
    with get_db_session() as sess:
        service = BlindedAnnotationService(sess)
        try:
            locked = service.lock_annotation(annotation_id, user)
            return jsonify({
                "message": "Annotation locked successfully.",
                "annotation_id": locked.id,
                "candidate_finding_id": locked.candidate_finding_id,
                "stage": locked.stage,
                "version": locked.version,
                "is_locked": locked.is_locked,
                "payload_sha256": locked.payload_sha256,
                "locked_at": locked.locked_at.isoformat() if locked.locked_at else None
            }), 200
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 400}), 400


@annotation_bp.route("/submission/<annotation_id>", methods=["GET"])
@require_auth
@require_roles(UserRole.LAWYER, UserRole.SUPERVISING_LAWYER, UserRole.AUDITOR)
def get_submission(annotation_id: str):
    """
    Retrieves an annotation submission.
    Explicitly requires LAWYER, SUPERVISING_LAWYER, or AUDITOR role; CLIENT callers rejected with 403.
    Enforces server-side blinding: peer submissions remain strictly inaccessible
    until both independent submissions are locked.
    """
    user = g.current_user
    with get_db_session() as sess:
        service = BlindedAnnotationService(sess)
        try:
            submission = service.get_submission_for_user(annotation_id, user)
            return jsonify({"submission": submission}), 200
        except BlindingViolationError as bve:
            return jsonify({"error": str(bve), "status_code": 403}), 403
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 404}), 404


@annotation_bp.route("/adjudication/<candidate_id>", methods=["GET"])
@require_auth
@require_roles(UserRole.SUPERVISING_LAWYER)
def get_adjudication_dossier(candidate_id: str):
    """
    Retrieves the adjudication dossier for Senior Counsel.
    Access is rejected with 403 if both primary annotators have not locked their submissions.
    """
    user = g.current_user
    with get_db_session() as sess:
        candidate_data = CandidateRegistry.resolve(candidate_id, session=sess)
        if not candidate_data:
            return jsonify({
                "error": f"Candidate finding '{candidate_id}' not found.",
                "status_code": 404
            }), 404

        service = BlindedAnnotationService(sess)
        try:
            dossier = service.get_adjudication_dossier(candidate_id, candidate_data, user)
            return jsonify(dossier), 200
        except BlindingViolationError as bve:
            return jsonify({"error": str(bve), "status_code": 403}), 403
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403


@annotation_bp.route("/adjudicate/<candidate_id>", methods=["POST"])
@require_auth
@require_roles(UserRole.SUPERVISING_LAWYER)
def record_adjudication(candidate_id: str):
    """
    Records and locks final adjudication decision by Senior Counsel.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}

    final_disposition = data.get("final_disposition")
    rationale = data.get("rationale")
    payload = data.get("payload")

    if not final_disposition or not rationale:
        return jsonify({
            "error": "Missing required fields: final_disposition, rationale.",
            "status_code": 400
        }), 400

    with get_db_session() as sess:
        service = BlindedAnnotationService(sess)
        try:
            adj = service.record_adjudication(
                candidate_finding_id=candidate_id,
                adjudicator_user=user,
                final_disposition=final_disposition,
                rationale=rationale,
                adjudication_payload=payload
            )
            return jsonify({
                "message": "Adjudication recorded and locked successfully.",
                "candidate_finding_id": adj.candidate_finding_id,
                "adjudication_id": adj.id,
                "final_disposition": adj.final_disposition,
                "status": adj.status,
                "is_locked": adj.is_locked,
                "payload_sha256": adj.payload_sha256
            }), 200
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 400}), 400
