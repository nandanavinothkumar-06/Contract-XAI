"""
Flask Blueprint defining REST API endpoints for Collaborative Lawyer Review Workbench.

Enforces:
1. Server-side role and tenant access boundaries on all review endpoints.
2. Advocate verification gates on assignment (AdvocateStatus.VERIFIED).
3. Client privacy: internal lawyer notes, undisclosed findings, and other clients' contracts are never exposed.
4. Independent lawyer decisions and authoring of findings.
5. Evidence retrieval grounded in authoritative Indian statutes.
6. Revision proposals preserving immutable original documents.
7. Completion prerequisites and statutory disclaimers.
"""

import json
from flask import Blueprint, request, jsonify, g

from src.auth.rbac import (
    require_auth, require_roles, require_verified_advocate, AccessController
)
from src.persistence.database import get_db_session
from src.persistence.models import (
    UserRole, AccountStatus, AdvocateStatus,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility, RevisionStatus
)
from src.review.service import ReviewService, MANDATORY_REVIEW_DISCLAIMER
from src.review.evidence import ClauseEvidenceRetriever, SCORE_SEMANTICS_DISCLAIMER

review_bp = Blueprint("review", __name__, url_prefix="/api/review")

# Singleton evidence retriever instance
_evidence_retriever = None

def get_evidence_retriever() -> ClauseEvidenceRetriever:
    global _evidence_retriever
    if _evidence_retriever is None:
        _evidence_retriever = ClauseEvidenceRetriever()
    return _evidence_retriever


# =============================================================================
# 1. REVIEW QUEUE & INITIATION
# =============================================================================

@review_bp.route("/queue", methods=["GET"])
@require_auth
def get_review_queue():
    """
    Returns role-tailored review queue.
    - CLIENT: contracts and reviews owned by user.
    - LAWYER: reviews assigned to this lawyer.
    - SUPERVISING_LAWYER: all reviews (assigned, unassigned, completed).
    - AUDITOR: compliance overview.
    """
    user = g.current_user
    status_filter = request.args.get("status")

    with get_db_session() as sess:
        service = ReviewService(sess)
        reviews = service.repo.list_reviews(user=user, status_filter=status_filter)

        queue_items = []
        for r in reviews:
            doc = r.document
            lawyer = r.assigned_lawyer
            owner = doc.owner if doc else None

            item = {
                "review_id": r.id,
                "document_id": r.document_id,
                "document_version": r.document_version,
                "status": r.status,
                "filename": doc.sanitized_filename if doc else "Unknown",
                "document_format": doc.document_format if doc else "UNKNOWN",
                "submitted_at": doc.created_at.isoformat() if doc else None,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "assigned_lawyer": {
                    "id": lawyer.id,
                    "name": lawyer.full_name,
                    "email": lawyer.email,
                    "advocate_status": lawyer.advocate_status
                } if lawyer else None,
                "owner": {
                    "id": owner.id,
                    "name": owner.full_name,
                    "email": owner.email
                } if owner and user.role in (UserRole.SUPERVISING_LAWYER.value, UserRole.LAWYER.value) else None
            }

            if user.role != UserRole.AUDITOR.value and doc:
                item["page_count"] = doc.page_count
                item["char_count"] = doc.char_count
                item["extraction_method"] = doc.extraction_method

            queue_items.append(item)

        return jsonify({
            "count": len(queue_items),
            "user_role": user.role,
            "reviews": queue_items
        }), 200


@review_bp.route("/initiate/<document_id>", methods=["POST"])
@require_auth
def initiate_review(document_id: str):
    """
    Initiates or retrieves an existing review record for an ingested contract.
    """
    user = g.current_user
    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            review = service.initiate_review(document_id, actor_user=user)
            return jsonify({
                "message": "Review initialized successfully.",
                "review_id": review.id,
                "document_id": review.document_id,
                "status": review.status,
                "version": review.document_version
            }), 201
        except PermissionError as pe:
            return jsonify({"error": str(pe), "status_code": 403}), 403
        except ValueError as ve:
            return jsonify({"error": str(ve), "status_code": 404}), 404


@review_bp.route("/upload", methods=["POST"])
@require_roles(UserRole.CLIENT, UserRole.LAWYER, UserRole.SUPERVISING_LAWYER)
def upload_contract():
    """
    Uploads a new contract document (PDF, DOCX, TXT), runs the ingestion pipeline,
    and initiates a review workflow owned by the current user within a single transactional unit.
    """
    user = g.current_user
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Key 'file' is required.", "status_code": 400}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename provided.", "status_code": 400}), 400

    file_bytes = file.read()
    if not file_bytes:
        return jsonify({"error": "Uploaded file is empty.", "status_code": 400}), 400

    from src.ingestion.pipeline import IngestionPipeline

    with get_db_session() as sess:
        pipeline = IngestionPipeline()
        result = pipeline.ingest_document(
            file_bytes=file_bytes,
            original_filename=file.filename,
            owner_id=user.id,
            session=sess
        )

        if result.status.value == "FAILED" or result.errors:
            sess.rollback()
            return jsonify({
                "error": "Document ingestion failed: " + "; ".join(result.errors),
                "status_code": 400
            }), 400

        service = ReviewService(sess)
        try:
            review = service.initiate_review(result.document_id, actor_user=user)

            # Trigger core NLP screening pipeline across segmented clauses
            findings_count = 0
            try:
                from src.review.screening import get_contract_screening_service
                screening_service = get_contract_screening_service()
                screening_res = screening_service.screen_review(review.id, sess)
                findings_count = screening_res.get("findings_count", 0)
            except Exception as se:
                import logging
                logging.getLogger("contractrisk.nlp_screening").error(f"NLP screening failed on upload: {se}")

            sess.commit()
            return jsonify({
                "message": "Contract uploaded, review initiated, and NLP screening executed successfully.",
                "document_id": result.document_id,
                "review_id": review.id,
                "filename": file.filename,
                "status": review.status,
                "segments_count": result.segment_count,
                "findings_count": findings_count
            }), 201
        except Exception as e:
            sess.rollback()
            return jsonify({"error": str(e), "status_code": 500}), 500


@review_bp.route("/<review_id>/screen", methods=["POST"])
@require_auth
def trigger_nlp_screening(review_id: str):
    """
    Executes or re-executes the core NLP pipeline across all segmented clauses of an ingested review:
    LegalBERT inference -> Risk prediction -> Gradient x Input explainability ->
    BM25 statutory retrieval -> Evidence-aware abstention -> Review findings persistence.
    """
    user = g.current_user
    with get_db_session() as sess:
        service = ReviewService(sess)
        review = service.repo.get_review_by_id(review_id)
        if not review:
            return jsonify({"error": "Review not found", "status_code": 404}), 404
        if not service.can_user_access_review(user, review, require_full_content=True):
            return jsonify({"error": "Forbidden", "status_code": 403}), 403

        from src.review.screening import get_contract_screening_service
        screening_service = get_contract_screening_service()
        screening_res = screening_service.screen_review(review.id, sess)
        sess.commit()

        return jsonify({
            "message": "Core NLP screening pipeline executed successfully.",
            "review_id": review_id,
            "segments_screened": screening_res.get("segments_screened", 0),
            "findings_count": screening_res.get("findings_count", 0),
            "findings": screening_res.get("findings", [])
        }), 200


# =============================================================================
# 2. REVIEW WORKSPACE & DETAILS
# =============================================================================

@review_bp.route("/<review_id>", methods=["GET"])
@require_auth
def get_review_workspace(review_id: str):
    """
    Retrieves complete review workspace data with server-side visibility enforcement.
    Clients receive only disclosed findings and client-scoped comments.
    Unassigned lawyers are strictly denied access.
    """
    user = g.current_user
    is_client = (user.role == UserRole.CLIENT.value)
    is_auditor = (user.role == UserRole.AUDITOR.value)

    with get_db_session() as sess:
        service = ReviewService(sess)
        review = service.repo.get_review_by_id(review_id)
        if not review:
            return jsonify({"error": "Review not found", "status_code": 404}), 404

        # Access check
        if not service.can_user_access_review(user, review, require_full_content=not is_auditor):
            return jsonify({
                "error": "Forbidden: You are not authorized to access this review.",
                "status_code": 403
            }), 403

        doc = review.document
        snapshot = doc.text_snapshots[0] if doc and doc.text_snapshots else None
        lawyer = review.assigned_lawyer

        # Segments (clauses)
        segments_data = []
        if not is_auditor and doc:
            for seg in sorted(doc.segments, key=lambda s: s.sequence):
                segments_data.append({
                    "segment_id": seg.segment_id,
                    "parent_segment_id": seg.parent_segment_id,
                    "segment_type": seg.segment_type,
                    "text": seg.text,
                    "original_start": seg.original_start,
                    "original_end": seg.original_end,
                    "heading": seg.heading,
                    "sequence": seg.sequence
                })

        # Findings
        findings = service.repo.get_findings_for_review(review_id, client_view=is_client)

        # On-demand screening fallback: If an advocate/supervisor opens a review with clauses
        # that has not yet had AI screening findings generated, execute core NLP screening.
        if (
            not is_client
            and not is_auditor
            and doc
            and doc.segments
            and not any(f.finding_origin == FindingOrigin.AI_GENERATED.value for f in findings)
        ):
            try:
                from src.review.screening import get_contract_screening_service
                screening_service = get_contract_screening_service()
                screening_service.screen_review(review.id, sess)
                sess.commit()
                findings = service.repo.get_findings_for_review(review_id, client_view=is_client)
            except Exception:
                sess.rollback()

        findings_data = []
        for f in findings:
            is_stale = (f.document_version != review.document_version)
            eq_status = "STALE_EVIDENCE" if is_stale else (f.evidence_quality_status or "NO_MATCHING_EVIDENCE")
            item = {
                "id": f.id,
                "segment_id": f.segment_id,
                "document_version": f.document_version,
                "is_stale_version": is_stale,
                "finding_origin": f.finding_origin,
                "risk_label": f.risk_label,
                "ai_confidence_score": f.ai_confidence_score,
                "ai_observation": f.ai_observation,
                "evidence_quality_status": eq_status,
                "decision": f.decision,
                "lawyer_rationale": f.lawyer_rationale,
                "is_disclosed_to_client": f.is_disclosed_to_client,
                "created_at": f.created_at.isoformat(),
                "updated_at": f.updated_at.isoformat()
            }
            if f.ai_metadata_json:
                try:
                    item["ai_metadata"] = json.loads(f.ai_metadata_json)
                except Exception:
                    item["ai_metadata"] = None
            else:
                item["ai_metadata"] = {
                    "model_name": "legalbert-base-uncased",
                    "model_version": "1.0.0",
                    "calibrated_threshold": 0.04,
                    "classification_mode": "multilabel",
                    "disclaimer": "Automated model observation. Statistical output, not a legally binding determination."
                } if f.finding_origin == FindingOrigin.AI_GENERATED.value else None

            if not is_client:
                item["lawyer_notes"] = f.lawyer_notes
                item["statutory_evidence"] = json.loads(f.statutory_evidence_json) if f.statutory_evidence_json else None
                if f.model_attribution_json:
                    try:
                        item["model_attribution"] = json.loads(f.model_attribution_json)
                    except Exception:
                        item["model_attribution"] = None
                else:
                    item["model_attribution"] = None
            elif f.statutory_evidence_json:
                # Client view of verified evidence
                item["statutory_evidence"] = json.loads(f.statutory_evidence_json)
            findings_data.append(item)

        # Comments
        comments = service.repo.get_comments_for_review(review_id, client_view=is_client)
        comments_data = []
        for c in comments:
            comments_data.append({
                "id": c.id,
                "segment_id": c.segment_id,
                "finding_id": c.finding_id,
                "author_id": c.author_id,
                "author_role": c.author_role,
                "author_name": c.author_name,
                "visibility": c.visibility,
                "comment_text": c.comment_text,
                "parent_comment_id": c.parent_comment_id,
                "is_resolved": c.is_resolved,
                "created_at": c.created_at.isoformat()
            })

        # Revisions
        revisions = service.repo.get_revisions_for_document(review.document_id)
        revisions_data = [
            {
                "id": rev.id,
                "version_number": rev.version_number,
                "revision_status": rev.revision_status,
                "revised_text_sha256": rev.revised_text_sha256,
                "change_reason": rev.change_reason,
                "diff_summary": rev.diff_summary,
                "created_at": rev.created_at.isoformat()
            } for rev in revisions
        ]

        # Transitions
        transitions_data = [
            {
                "from_state": t.from_state,
                "to_state": t.to_state,
                "actor_id": t.actor_id,
                "reason": t.reason,
                "created_at": t.created_at.isoformat()
            } for t in sorted(review.transitions, key=lambda x: x.created_at)
        ]

        return jsonify({
            "review": {
                "id": review.id,
                "document_id": review.document_id,
                "version": review.document_version,
                "status": review.status,
                "assigned_lawyer": {
                    "id": lawyer.id,
                    "name": lawyer.full_name,
                    "email": lawyer.email,
                    "advocate_status": lawyer.advocate_status
                } if lawyer else None,
                "assigned_at": review.assigned_at.isoformat() if review.assigned_at else None,
                "completed_at": review.completed_at.isoformat() if review.completed_at else None,
                "completion_summary": review.completion_summary,
                "outstanding_limitations": review.outstanding_limitations,
                "unresolved_questions": review.unresolved_questions,
                "further_client_action_required": review.further_client_action_required,
                "disclaimer_text": review.disclaimer_text or MANDATORY_REVIEW_DISCLAIMER
            },
            "document": {
                "id": doc.id,
                "filename": doc.sanitized_filename,
                "file_sha256": doc.file_sha256,
                "format": doc.document_format,
                "page_count": doc.page_count,
                "char_count": doc.char_count,
                "raw_text": snapshot.raw_text if snapshot and not is_auditor else None,
                "warnings": json.loads(doc.warnings_json) if doc.warnings_json else []
            } if doc else None,
            "segments": segments_data,
            "findings": findings_data,
            "comments": comments_data,
            "revisions": revisions_data,
            "transitions": transitions_data,
            "score_disclaimer": SCORE_SEMANTICS_DISCLAIMER
        }), 200


# =============================================================================
# 3. LAWYER ASSIGNMENT & ADVOCATE VERIFICATION
# =============================================================================

@review_bp.route("/advocates/eligible", methods=["GET"])
@review_bp.route("/eligible-lawyers", methods=["GET"])
@require_roles(UserRole.SUPERVISING_LAWYER)
def get_eligible_advocates():
    """
    Lists advocates verified and eligible for assignment.
    Supervisor access only.
    """
    with get_db_session() as sess:
        service = ReviewService(sess)
        lawyers = service.repo.get_eligible_advocates()
        return jsonify({
            "count": len(lawyers),
            "advocates": [
                {
                    "id": l.id,
                    "full_name": l.full_name,
                    "email": l.email,
                    "role": l.role,
                    "advocate_status": l.advocate_status,
                    "bar_enrolment_id": l.bar_enrolment_id,
                    "state_bar_council": l.state_bar_council,
                    "year_of_enrolment": l.year_of_enrolment,
                    "verification_method": "MANUAL_SUPERVISORY_VERIFICATION"
                } for l in lawyers
            ]
        }), 200


@review_bp.route("/<review_id>/assign", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER)
def assign_lawyer(review_id: str):
    """
    Assigns or reassigns a review to an eligible verified advocate.
    Enforces that unverified advocates cannot be assigned.
    Prevents client self-assignment.
    """
    supervisor = g.current_user
    data = request.get_json(silent=True) or {}
    lawyer_id = data.get("lawyer_id")
    rationale = data.get("rationale")

    if not lawyer_id:
        return jsonify({"error": "lawyer_id is required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            review = service.assign_review(
                review_id=review_id,
                lawyer_id=lawyer_id,
                assigning_user=supervisor,
                rationale=rationale
            )
            return jsonify({
                "message": "Review assigned successfully.",
                "review_id": review.id,
                "assigned_lawyer_id": review.assigned_lawyer_id,
                "status": review.status
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


# =============================================================================
# 4. REVIEW STATE TRANSITIONS
# =============================================================================

@review_bp.route("/<review_id>/transition", methods=["POST"])
@require_auth
def transition_review(review_id: str):
    """
    Executes a validated state transition in the review lifecycle.
    Rejects invalid transitions server-side.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    to_state = data.get("to_state")
    reason = data.get("reason")

    if not to_state:
        return jsonify({"error": "to_state is required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            review = service.transition_review_state(
                review_id=review_id,
                to_state=to_state,
                actor_user=user,
                reason=reason
            )
            return jsonify({
                "message": f"Review transitioned to '{review.status}' successfully.",
                "review_id": review.id,
                "status": review.status
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


# =============================================================================
# 5. CLAUSE FINDINGS & DECISION CONTROLS
# =============================================================================

@review_bp.route("/<review_id>/decision", methods=["POST"])
@require_verified_advocate
def record_decision(review_id: str):
    """
    Records a lawyer's evaluation decision on an AI observation.
    Requires ACCEPT_AI_OBSERVATION, CORRECT_AI_OBSERVATION, REJECT_AI_OBSERVATION,
    NEEDS_MORE_EVIDENCE, NOT_APPLICABLE_TO_REVIEW, or REQUIRES_CLIENT_CLARIFICATION.
    Mandates lawyer rationale.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    segment_id = data.get("segment_id")
    decision = data.get("decision")
    rationale = data.get("rationale")
    notes = data.get("notes")
    is_disclosed = bool(data.get("is_disclosed_to_client", False))
    evidence_json = json.dumps(data.get("statutory_evidence")) if data.get("statutory_evidence") else None
    ai_meta_json = json.dumps(data.get("ai_metadata")) if data.get("ai_metadata") else None
    model_attrib_json = json.dumps(data.get("model_attribution")) if data.get("model_attribution") else None
    eq_status = data.get("evidence_quality_status")

    if not segment_id or not decision:
        return jsonify({"error": "segment_id and decision are required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            finding = service.record_clause_decision(
                review_id=review_id,
                segment_id=segment_id,
                decision=decision,
                lawyer_rationale=rationale,
                actor_user=user,
                lawyer_notes=notes,
                is_disclosed_to_client=is_disclosed,
                statutory_evidence_json=evidence_json,
                ai_metadata_json=ai_meta_json,
                model_attribution_json=model_attrib_json,
                evidence_quality_status=eq_status
            )
            return jsonify({
                "message": "Lawyer decision recorded successfully.",
                "finding_id": finding.id,
                "segment_id": finding.segment_id,
                "decision": finding.decision,
                "evidence_quality_status": finding.evidence_quality_status,
                "is_disclosed_to_client": finding.is_disclosed_to_client
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


@review_bp.route("/<review_id>/finding/create", methods=["POST"])
@require_verified_advocate
def create_lawyer_finding(review_id: str):
    """
    Creates an independent lawyer-authored finding not generated by AI.
    Origin is strictly recorded as LAWYER_AUTHORED.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    segment_id = data.get("segment_id")
    risk_label = data.get("risk_label", "LAWYER_IDENTIFIED_RISK")
    observation = data.get("lawyer_observation")
    decision = data.get("decision", LawyerDecisionType.ACCEPT_AI_OBSERVATION.value)
    rationale = data.get("rationale")
    notes = data.get("notes")
    is_disclosed = bool(data.get("is_disclosed_to_client", False))
    evidence_json = json.dumps(data.get("statutory_evidence")) if data.get("statutory_evidence") else None
    eq_status = data.get("evidence_quality_status") or "TRACEABLE"

    if not segment_id or not observation or not rationale:
        return jsonify({"error": "segment_id, lawyer_observation, and rationale are required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            finding = service.create_lawyer_authored_finding(
                review_id=review_id,
                segment_id=segment_id,
                risk_label=risk_label,
                lawyer_observation=observation,
                decision=decision,
                lawyer_rationale=rationale,
                actor_user=user,
                lawyer_notes=notes,
                is_disclosed_to_client=is_disclosed,
                statutory_evidence_json=evidence_json,
                evidence_quality_status=eq_status
            )
            return jsonify({
                "message": "Independent lawyer finding authored successfully.",
                "finding_id": finding.id,
                "finding_origin": finding.finding_origin,
                "segment_id": finding.segment_id,
                "risk_label": finding.risk_label,
                "evidence_quality_status": finding.evidence_quality_status
            }), 201
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


# =============================================================================
# 6. EVIDENCE RETRIEVAL PANEL
# =============================================================================

@review_bp.route("/<review_id>/evidence/<segment_id>", methods=["GET"])
@require_auth
def get_clause_evidence(review_id: str, segment_id: str):
    """
    Retrieves authoritative Indian statutory passages for a specific clause.
    Returns provenance, checksums, currentness, and ranking score disclaimers.
    Checks document version staleness.
    """
    user = g.current_user
    with get_db_session() as sess:
        service = ReviewService(sess)
        review = service.repo.get_review_by_id(review_id)
        if not review:
            return jsonify({"error": "Review not found", "status_code": 404}), 404

        if not service.can_user_access_review(user, review, require_full_content=True):
            return jsonify({"error": "Forbidden", "status_code": 403}), 403

        doc = review.document
        clause = next((s for s in doc.segments if s.segment_id == segment_id), None)
        if not clause:
            return jsonify({"error": "Clause segment not found", "status_code": 404}), 404

        revisions = service.repo.get_revisions_for_document(doc.id)
        latest_version = max([r.version_number for r in revisions], default=1) if revisions else 1
        is_version_mismatch = (review.document_version < latest_version)

        retriever = get_evidence_retriever()
        evidence_data = retriever.retrieve_evidence_for_clause(
            clause_text=clause.text,
            clause_id=clause.segment_id,
            source_document_id=doc.id,
            document_version_mismatch=is_version_mismatch
        )

        return jsonify(evidence_data), 200


# =============================================================================
# 7. SCOPED COMMENTS & CLARIFICATIONS
# =============================================================================

@review_bp.route("/<review_id>/comment", methods=["POST"])
@require_auth
def add_comment(review_id: str):
    """
    Posts a comment or clarification request.
    Clients are prohibited from posting INTERNAL_LAWYER_ONLY comments.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    text = data.get("comment_text")
    visibility = data.get("visibility", CommentVisibility.INTERNAL_LAWYER_ONLY.value)
    segment_id = data.get("segment_id")
    finding_id = data.get("finding_id")
    parent_id = data.get("parent_comment_id")

    if not text:
        return jsonify({"error": "comment_text is required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            comment = service.add_comment(
                review_id=review_id,
                actor_user=user,
                comment_text=text,
                visibility=visibility,
                segment_id=segment_id,
                finding_id=finding_id,
                parent_comment_id=parent_id
            )
            return jsonify({
                "message": "Comment posted successfully.",
                "comment_id": comment.id,
                "visibility": comment.visibility,
                "created_at": comment.created_at.isoformat()
            }), 201
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


@review_bp.route("/<review_id>/comment/<comment_id>/resolve", methods=["POST"])
@require_verified_advocate
def resolve_comment(review_id: str, comment_id: str):
    """
    Resolves a comment thread or clarification request.
    Lawyer or supervisor only.
    """
    user = g.current_user
    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            comment = service.resolve_comment(comment_id=comment_id, actor_user=user)
            return jsonify({
                "message": "Comment resolved successfully.",
                "comment_id": comment.id,
                "is_resolved": comment.is_resolved
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


# =============================================================================
# 8. DOCUMENT REVISIONS & REDLINE PROPOSALS
# =============================================================================

@review_bp.route("/<review_id>/revision/propose", methods=["POST"])
@require_auth
def propose_revision(review_id: str):
    """
    Proposes a versioned revision of contract text.
    Preserves original uploaded document immutable.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    revised_text = data.get("revised_text")
    reason = data.get("change_reason")

    if not revised_text:
        return jsonify({"error": "revised_text is required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        review = service.repo.get_review_by_id(review_id)
        if not review:
            return jsonify({"error": "Review not found", "status_code": 404}), 404

        try:
            rev = service.propose_document_revision(
                document_id=review.document_id,
                review_id=review_id,
                actor_user=user,
                revised_text=revised_text,
                change_reason=reason
            )
            return jsonify({
                "message": "Document revision proposed successfully.",
                "revision_id": rev.id,
                "version_number": rev.version_number,
                "revised_text_sha256": rev.revised_text_sha256,
                "revision_status": rev.revision_status
            }), 201
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


@review_bp.route("/<review_id>/revision/<revision_id>/decide", methods=["POST"])
@require_verified_advocate
def decide_revision(review_id: str, revision_id: str):
    """
    Accepts or rejects a proposed document revision.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    rationale = data.get("rationale")

    if not decision:
        return jsonify({"error": "decision (ACCEPTED/REJECTED) is required.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            updated = service.decide_document_revision(
                revision_id=revision_id,
                decision=decision,
                actor_user=user,
                rationale=rationale
            )
            return jsonify({
                "message": f"Revision {decision.lower()} successfully.",
                "revision_id": updated.id,
                "revision_status": updated.revision_status
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


# =============================================================================
# 9. REVIEW COMPLETION & REOPENING
# =============================================================================

@review_bp.route("/<review_id>/complete", methods=["POST"])
@require_verified_advocate
def complete_review(review_id: str):
    """
    Completes review workflow after validating prerequisites:
    - Must be IN_REVIEW.
    - Assigned lawyer or supervisor only.
    - No unresolved clarification requests.
    - Mandatory statutory assessment disclaimer attached.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    summary = data.get("completion_summary")
    limitations = data.get("outstanding_limitations")
    unresolved_q = data.get("unresolved_questions")
    action_required = bool(data.get("further_client_action_required", False))

    if not summary:
        return jsonify({"error": "completion_summary is mandatory.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            completed = service.complete_review(
                review_id=review_id,
                actor_user=user,
                completion_summary=summary,
                outstanding_limitations=limitations,
                unresolved_questions=unresolved_q,
                further_client_action_required=action_required
            )
            return jsonify({
                "message": "Review completed successfully.",
                "review_id": completed.id,
                "status": completed.status,
                "completed_at": completed.completed_at.isoformat(),
                "completed_by": user.full_name,
                "disclaimer": completed.disclaimer_text
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code


@review_bp.route("/<review_id>/reopen", methods=["POST"])
@require_verified_advocate
def reopen_review(review_id: str):
    """
    Reopens a completed review with mandatory justification.
    """
    user = g.current_user
    data = request.get_json(silent=True) or {}
    reason = data.get("reason")

    if not reason:
        return jsonify({"error": "reason is required to reopen a review.", "status_code": 400}), 400

    with get_db_session() as sess:
        service = ReviewService(sess)
        try:
            reopened = service.reopen_review(
                review_id=review_id,
                actor_user=user,
                reason=reason
            )
            return jsonify({
                "message": "Review reopened successfully.",
                "review_id": reopened.id,
                "status": reopened.status
            }), 200
        except (PermissionError, ValueError) as e:
            code = 403 if isinstance(e, PermissionError) else 400
            return jsonify({"error": str(e), "status_code": code}), code
