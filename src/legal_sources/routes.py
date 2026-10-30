"""
Flask REST API Endpoints for Authoritative Indian Legal Sources and Retrieval.

Provides authenticated endpoints for legal source retrieval, contract clause matching,
and role-restricted administrative endpoints for corpus ingestion and verification.
"""

import json
import uuid
import datetime
from flask import Blueprint, request, jsonify, g
from src.auth.rbac import require_auth, require_roles
from src.persistence.models import UserRole, AuditEventRecord
from src.legal_sources.schema import LegalSourceQuery, RetrievedLegalEvidence
from src.legal_sources.config import LegalSourceRetrievalConfig
from src.legal_sources.retriever import LegalSourceRetriever
from src.legal_sources.matcher import ContractStatuteMatcher
from src.legal_sources.registry import get_authoritative_indian_corpus, LegalSourceRegistry
from src.legal_sources.provenance import VerificationStatus
from src.persistence.database import get_db
from src.persistence.repository import DocumentRepository
from src.audit.schema import AuditEvent
from src.audit.events import calculate_event_hash
from src.audit.provenance import EventType, ActorType
from src.legal_sources.verification import LegalSourceVerificationWorkflow
from src.legal_sources.coverage import LegalCoverageModel
from src.legal_sources.acquisition import GazetteArtifactAcquisitionManager
from src.legal_sources.extraction import StatutoryTextExtractor
from src.legal_sources.comparison import StatutoryComparisonEngine

def log_audit_trail_event(repo: DocumentRepository, event_type: EventType, actor_type: ActorType, payload: dict, document_id: str = None):
    last_rec = (
        repo.session.query(AuditEventRecord)
        .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc())
        .first()
    )
    prev_hash = last_rec.event_hash if last_rec else None

    evt = AuditEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        source_document_id=document_id,
        actor_type=actor_type,
        event_payload=payload,
        previous_event_hash=prev_hash
    )
    evt.event_hash = calculate_event_hash(evt)
    return repo.record_audit_event(evt)


legal_bp = Blueprint("legal", __name__)

# Singleton corpus instances
_corpus_registry = None
_corpus_index = None
_corpus_retriever = None
_corpus_matcher = None

def get_corpus_services():
    global _corpus_registry, _corpus_index, _corpus_retriever, _corpus_matcher
    if _corpus_registry is None or _corpus_index is None:
        _corpus_registry, _corpus_index = get_authoritative_indian_corpus()
        config = LegalSourceRetrievalConfig(retrieval_method="BM25", verified_only=True)
        _corpus_retriever = LegalSourceRetriever(_corpus_registry, _corpus_index, config)
        _corpus_matcher = ContractStatuteMatcher(_corpus_retriever)
    return _corpus_registry, _corpus_index, _corpus_retriever, _corpus_matcher


@legal_bp.route("/api/legal/sources", methods=["GET"])
def list_sources():
    """
    Returns list of authoritative Indian legal sources and their currentness/verification status.
    """
    registry, _, _, _ = get_corpus_services()
    sources = registry.get_all_sources()
    return jsonify({
        "status": "success",
        "count": len(sources),
        "corpus_type": "CURATED_COMMERCIAL_STATUTORY_EXTRACTS",
        "corpus_disclosure": (
            "The statutory corpus is limited to curated extracts of selected commercial provisions from "
            "six Indian central statutes. It does not constitute complete Acts, official gazette publications, "
            "or an exhaustive search of Indian law. Independent advocate review of legal applicability is mandatory."
        ),
        "sources": [s.model_dump() for s in sources]
    }), 200


@legal_bp.route("/api/legal/sources/<source_id>", methods=["GET"])
def get_source_details(source_id: str):
    """
    Returns detailed source metadata and indexed section identifiers.
    """
    registry, index, _, _ = get_corpus_services()
    source = registry.get_source(source_id)
    if not source:
        return jsonify({"status": "error", "message": f"Legal source '{source_id}' not found"}), 404

    # Collect sections for this source
    sections = []
    for pid, p in index.passages.items():
        if p.source_id == source_id:
            sections.append({
                "passage_id": p.passage_id,
                "section_identifier": p.section_identifier,
                "heading": p.heading,
                "citation_string": p.citation_string,
                "commencement_status": p.commencement_status.value if p.commencement_status else None
            })

    return jsonify({
        "status": "success",
        "source": source.model_dump(),
        "sections_count": len(sections),
        "sections": sections
    }), 200


@legal_bp.route("/api/legal/retrieve", methods=["POST"])
@require_auth
def retrieve_passages():
    """
    Retrieves relevant statutory passages for a query.
    Requires authenticated user session.
    """
    data = request.get_json() or {}
    query_text = data.get("query_text", "")
    top_k = data.get("requested_top_k", 5)
    exact_section = data.get("exact_section_filter")
    retrieval_method = data.get("retrieval_method", "BM25")

    if not query_text and not exact_section:
        return jsonify({"status": "error", "message": "query_text or exact_section_filter required"}), 400

    registry, index, _, _ = get_corpus_services()
    config = LegalSourceRetrievalConfig(retrieval_method=retrieval_method, top_k=top_k)
    retriever = LegalSourceRetriever(registry, index, config)

    query = LegalSourceQuery(
        query_id=data.get("query_id", "web_query"),
        query_text=query_text,
        country="IN",
        requested_top_k=top_k,
        exact_section_filter=exact_section,
        created_at="2026-10-15T00:00:00Z"
    )

    results = retriever.retrieve(query)

    # Record audit event
    user = getattr(g, "current_user", None)
    with get_db() as db:
        repo = DocumentRepository(db)
        log_audit_trail_event(
            repo=repo,
            event_type=EventType.LEGAL_SOURCE_RETRIEVED,
            actor_type=ActorType.USER if user else ActorType.SYSTEM,
            payload={
                "user_id": user.id if user else None,
                "query_text_len": len(query_text),
                "exact_section_filter": exact_section,
                "retrieved_count": len(results),
                "top_score": results[0].similarity_score if results else 0.0
            }
        )

    return jsonify({
        "status": "success",
        "count": len(results),
        "results": [r.model_dump() for r in results]
    }), 200


@legal_bp.route("/api/legal/match", methods=["POST"])
@require_auth
def match_clause():
    """
    Matches a contract clause against verified Indian statutory evidence.
    Applies strict confidence gates and abstention policy.
    """
    data = request.get_json() or {}
    clause_text = data.get("clause_text", "")
    clause_id = data.get("clause_id")
    exact_section = data.get("exact_section_filter")

    if not clause_text:
        return jsonify({"status": "error", "message": "clause_text is required"}), 400

    _, _, _, matcher = get_corpus_services()
    evidence = matcher.match_clause(
        clause_text=clause_text,
        clause_id=clause_id,
        exact_section_filter=exact_section
    )

    # Record audit event
    user = getattr(g, "current_user", None)
    with get_db() as db:
        repo = DocumentRepository(db)
        log_audit_trail_event(
            repo=repo,
            event_type=EventType.LEGAL_SOURCE_RETRIEVED,
            actor_type=ActorType.USER if user else ActorType.SYSTEM,
            payload={
                "user_id": user.id if user else None,
                "clause_id": clause_id,
                "match_status": evidence.status,
                "abstention_reason": evidence.abstention_reason.value if evidence.abstention_reason else None,
                "passages_count": len(evidence.passages)
            }
        )

    return jsonify({
        "status": "success",
        "evidence": evidence.model_dump()
    }), 200


@legal_bp.route("/api/legal/sources/ingest", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER.value)
def admin_ingest_source():
    """
    Admin-only endpoint for ingesting new statutory source snapshots.
    Restricted to SUPERVISING_LAWYER.
    """
    data = request.get_json() or {}
    manifest_path = data.get("manifest_path", "data/legal_sources/corpus_manifest.json")
    
    from src.legal_sources.ingestion import StatutoryIngestionEngine
    engine = StatutoryIngestionEngine()
    user = getattr(g, "current_user", None)
    try:
        sources, passages = engine.ingest_corpus_from_manifest(manifest_path=manifest_path)
    except Exception as e:
        with get_db() as db:
            repo = DocumentRepository(db)
            log_audit_trail_event(
                repo=repo,
                event_type=EventType.SECURITY_ALERT,
                actor_type=ActorType.ADMIN,
                payload={
                    "admin_id": user.id if user else None,
                    "operation": "LEGAL_SOURCE_INGEST_FAILED",
                    "error": str(e),
                    "manifest_path": manifest_path
                }
            )
        return jsonify({"status": "error", "message": str(e)}), 400

    registry, index, _, _ = get_corpus_services()
    for s in sources:
        registry.register_source(s)
    index.index_passages(passages)

    with get_db() as db:
        repo = DocumentRepository(db)
        log_audit_trail_event(
            repo=repo,
            event_type=EventType.LEGAL_SOURCE_INGESTED,
            actor_type=ActorType.ADMIN,
            payload={
                "admin_id": user.id if user else None,
                "sources_ingested": len(sources),
                "passages_ingested": len(passages),
                "manifest_path": manifest_path
            }
        )

    return jsonify({
        "status": "success",
        "message": f"Successfully ingested {len(sources)} sources and {len(passages)} passages",
        "sources_count": len(sources),
        "passages_count": len(passages)
    }), 200


@legal_bp.route("/api/legal/sources/<source_id>/verify", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER.value)
def admin_verify_source(source_id: str):
    """
    Admin-only endpoint to update verification status of a legal source.
    Restricted to SUPERVISING_LAWYER.
    """
    user = getattr(g, "current_user", None)
    reviewer_id = user.id if user else "ADMIN"
    data = request.get_json() or {}
    new_status_str = data.get("verification_status")

    if not new_status_str or new_status_str not in VerificationStatus.__members__:
        with get_db() as db:
            repo = DocumentRepository(db)
            log_audit_trail_event(
                repo=repo,
                event_type=EventType.SECURITY_ALERT,
                actor_type=ActorType.ADMIN,
                payload={
                    "admin_id": reviewer_id,
                    "source_id": source_id,
                    "operation": "LEGAL_SOURCE_VERIFY_INVALID_STATUS",
                    "invalid_status": new_status_str
                }
            )
        return jsonify({"status": "error", "message": f"Invalid verification_status '{new_status_str}'"}), 400

    new_status = VerificationStatus(new_status_str)
    registry, _, _, _ = get_corpus_services()

    success = registry.update_verification_status(source_id, new_status, reviewer_id=reviewer_id)
    if not success:
        with get_db() as db:
            repo = DocumentRepository(db)
            log_audit_trail_event(
                repo=repo,
                event_type=EventType.SECURITY_ALERT,
                actor_type=ActorType.ADMIN,
                payload={
                    "admin_id": reviewer_id,
                    "source_id": source_id,
                    "operation": "LEGAL_SOURCE_VERIFY_SOURCE_NOT_FOUND"
                }
            )
        return jsonify({"status": "error", "message": f"Source '{source_id}' not found"}), 404

    with get_db() as db:
        repo = DocumentRepository(db)
        log_audit_trail_event(
            repo=repo,
            event_type=EventType.LEGAL_SOURCE_VERIFIED,
            actor_type=ActorType.ADMIN,
            payload={
                "admin_id": reviewer_id,
                "source_id": source_id,
                "new_verification_status": new_status.value,
                "notes": data.get("notes")
            }
        )

    return jsonify({
        "status": "success",
        "source_id": source_id,
        "verification_status": new_status.value,
        "reviewer_id": reviewer_id
    }), 200


@legal_bp.route("/api/legal/verify", methods=["GET", "POST"])
def verify_corpus_status():
    """
    Runs the repeatable source-verification workflow and returns an auditable verification report.
    Supports optional check_network=true parameter.
    """
    check_net = request.args.get("check_network", "false").lower() == "true"
    if request.is_json and request.get_json():
        check_net = request.get_json().get("check_network", check_net)

    workflow = LegalSourceVerificationWorkflow()
    report = workflow.run_verification(check_network=check_net)

    return jsonify({
        "status": "success",
        "verification_report": report
    }), 200


@legal_bp.route("/api/legal/coverage", methods=["GET"])
def get_corpus_coverage():
    """
    Returns granular legal coverage report for the Indian statutory corpus.
    Distinguishes Categories A through F (Task 039).
    """
    model = LegalCoverageModel()
    report = model.generate_coverage_report()

    return jsonify({
        "status": "success",
        "coverage_report": report
    }), 200


@legal_bp.route("/api/legal/artifacts/acquire", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER.value)
def acquire_reference_artifact():
    """
    Role-restricted endpoint to acquire an authoritative legal artifact from an official URL.
    Restricted to SUPERVISING_LAWYER. Enforces SSRF defenses and host allowlisting.
    """
    data = request.get_json() or {}
    source_id = data.get("source_id")
    pub_id = data.get("publication_id") or data.get("pub_id") or f"pub_{source_id or 'default'}"
    source_url = data.get("source_url") or data.get("url")

    if not source_id or not source_url:
        return jsonify({
            "status": "error",
            "error": "Missing required fields: 'source_id' and 'source_url' are required",
            "message": "Missing required fields: 'source_id' and 'source_url' are required"
        }), 400

    manager = GazetteArtifactAcquisitionManager()
    result = manager.acquire_from_url(
        source_id=source_id,
        publication_id=pub_id,
        source_url=source_url,
        issuing_authority=data.get("issuing_authority"),
        publication_title=data.get("publication_title"),
        publication_date=data.get("publication_date"),
        expected_format=data.get("expected_format", "PDF")
    )

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@legal_bp.route("/api/legal/artifacts/register", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER.value)
def register_manual_artifact():
    """
    Role-restricted endpoint to register an out-of-band / air-gapped reference artifact.
    Restricted to SUPERVISING_LAWYER.
    """
    data = request.get_json() or {}
    source_id = data.get("source_id")
    pub_id = data.get("publication_id")
    file_path = data.get("input_file_path")

    if not source_id or not pub_id or not file_path:
        return jsonify({
            "status": "error",
            "message": "Missing required fields: 'source_id', 'publication_id', and 'input_file_path'"
        }), 400

    manager = GazetteArtifactAcquisitionManager()
    result = manager.register_manual_artifact(
        source_id=source_id,
        publication_id=pub_id,
        input_file_path=file_path,
        issuing_authority=data.get("issuing_authority", "Government of India"),
        publication_title=data.get("publication_title"),
        publication_date=data.get("publication_date"),
        source_url=data.get("source_url"),
        advocate_reviewer_notes=data.get("notes")
    )

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@legal_bp.route("/api/legal/artifacts/extract", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER.value)
def extract_artifact_text():
    """
    Role-restricted endpoint to extract structural text from an authoritative reference artifact.
    Restricted to SUPERVISING_LAWYER.
    """
    data = request.get_json() or {}
    source_id = data.get("source_id")
    pub_id = data.get("publication_id")
    artifact_path = data.get("artifact_path")

    if not source_id or not pub_id or not artifact_path:
        return jsonify({
            "status": "error",
            "message": "Missing required fields: 'source_id', 'publication_id', and 'artifact_path'"
        }), 400

    extractor = StatutoryTextExtractor()
    result = extractor.extract_from_artifact(
        artifact_path=artifact_path,
        source_id=source_id,
        publication_id=pub_id,
        enable_ocr_fallback=data.get("enable_ocr_fallback", False)
    )

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@legal_bp.route("/api/legal/artifacts/compare", methods=["POST"])
@require_roles(UserRole.SUPERVISING_LAWYER.value)
def compare_snapshot_with_reference():
    """
    Role-restricted endpoint to execute section-by-section comparison between snapshot and reference.
    Restricted to SUPERVISING_LAWYER.
    """
    data = request.get_json() or {}
    source_id = data.get("source_id")
    snapshot_path = data.get("snapshot_file_path")
    reference_text_path = data.get("reference_text_path")

    if not source_id or not snapshot_path or not reference_text_path:
        return jsonify({
            "status": "error",
            "message": "Missing required fields: 'source_id', 'snapshot_file_path', and 'reference_text_path'"
        }), 400

    engine = StatutoryComparisonEngine()
    result = engine.compare_snapshot_with_reference(
        source_id=source_id,
        snapshot_file_path=snapshot_path,
        reference_text_path=reference_text_path,
        reference_metadata=data.get("reference_metadata")
    )

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


