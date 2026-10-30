"""
Blinded Annotation Service for CONTRACTRISK-XAI Strategy A Evaluation.

Coordinates schema validation, deterministic SHA-256 digest computation,
authoritative server-side metadata injection, independent submission storage,
locking immutability, peer blinding firewalls, and adjudication gating with
continuous cryptographic audit hash chaining.
"""

import os
import json
import uuid
import hashlib
import datetime
from typing import Dict, Any, Optional, Tuple, List
import jsonschema

from sqlalchemy.orm import Session

from src.persistence.models import (
    UserRecord, UserRole, AccountStatus, AdvocateStatus,
    BlindedAnnotationRecord, BlindedAdjudicationRecord,
    AnnotationStage, AdjudicationStatus, AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.audit.schema import AuditEvent
from src.audit.events import calculate_event_hash
from src.audit.provenance import EventType, ActorType
from src.annotation.firewall import PresentationFirewall, BlindingViolationError
from src.annotation.candidate_registry import CandidateRegistry


SCHEMA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "docs",
        "schemas",
        "candidate_finding_annotation.schema.json"
    )
)

_CACHED_SCHEMA: Optional[Dict[str, Any]] = None
_CACHED_VALIDATOR: Optional[jsonschema.Draft7Validator] = None


def get_annotation_schema() -> Dict[str, Any]:
    """Loads and caches the Draft-07 CandidateFindingAnnotationRecord JSON schema."""
    global _CACHED_SCHEMA
    if _CACHED_SCHEMA is None:
        if not os.path.exists(SCHEMA_PATH):
            raise FileNotFoundError(f"Annotation JSON schema not found at {SCHEMA_PATH}")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            _CACHED_SCHEMA = json.load(f)
    return _CACHED_SCHEMA


def get_schema_validator() -> jsonschema.Draft7Validator:
    """Returns a cached Draft7Validator instance."""
    global _CACHED_VALIDATOR
    if _CACHED_VALIDATOR is None:
        schema = get_annotation_schema()
        _CACHED_VALIDATOR = jsonschema.Draft7Validator(schema)
    return _CACHED_VALIDATOR


def canonical_json_dumps(obj: Any) -> str:
    """
    Serializes an object to deterministic canonical JSON:
    Sorted keys, compact separators, UTF-8 encoded without extra whitespace.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_payload_sha256(payload: Dict[str, Any]) -> str:
    """Computes SHA-256 digest from deterministic canonical JSON representation."""
    canonical_str = canonical_json_dumps(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class BlindedAnnotationService:
    """
    Service managing blinded legal annotation submissions and adjudication lifecycle.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repo = DocumentRepository(session)

    def _record_audit_event(
        self,
        event_type: EventType,
        source_document_id: Optional[str] = None,
        clause_id: Optional[str] = None,
        actor_type: ActorType = ActorType.REVIEWER,
        actor_reference: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Records a hash-chained audit record in the database."""
        last_db_event = (
            self.session.query(AuditEventRecord)
            .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc())
            .first()
        )
        previous_hash = last_db_event.event_hash if last_db_event else None

        evt = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            source_document_id=source_document_id,
            clause_id=clause_id,
            review_id=None,
            actor_type=actor_type,
            actor_reference=actor_reference,
            module_name="src.annotation.service",
            module_version="1.0.0",
            previous_event_hash=previous_hash,
            event_payload=payload or {}
        )
        evt.event_hash = calculate_event_hash(evt)
        self.repo.record_audit_event(evt)
        return evt

    def validate_payload(self, payload: Dict[str, Any], stage: str = AnnotationStage.FULL_RECORD.value) -> Tuple[bool, Optional[str]]:
        """
        Validates an annotation payload dictionary against the Draft-07 JSON schema.
        Returns: (is_valid: bool, error_message: Optional[str])
        """
        if not isinstance(payload, dict):
            return False, "Payload must be a JSON object dictionary."

        # For FULL_RECORD, run strict Draft-07 schema validation
        if stage in (AnnotationStage.FULL_RECORD.value, AnnotationStage.STAGE_7_PEER_INDEPENDENT.value):
            validator = get_schema_validator()
            errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
            if errors:
                first_err = errors[0]
                path_str = " -> ".join([str(p) for p in first_err.path]) if first_err.path else "root"
                return False, f"Schema validation failed at '{path_str}': {first_err.message}"

        # Additional stage-specific sanity checks
        if "final_reference_decision" in payload:
            decision = payload["final_reference_decision"]
            if isinstance(decision, dict) and "reference_action" in decision:
                valid_actions = {"RETAIN", "WITHHOLD", "HUMAN_REVIEW_REQUIRED", "NOT_ASSESSABLE"}
                if decision["reference_action"] not in valid_actions:
                    return False, f"Invalid reference_action '{decision['reference_action']}'"

        return True, None

    def submit_annotation(
        self,
        candidate_finding_id: str,
        contract_id: Optional[str],
        clause_id: Optional[str],
        annotator_user: UserRecord,
        payload: Dict[str, Any],
        stage: str = AnnotationStage.FULL_RECORD.value,
        is_synthetic_fixture: bool = False
    ) -> BlindedAnnotationRecord:
        """
        Submits a new draft or initial independent annotation record.
        
        Security Invariants:
        1. Validates annotator credentials (active account, enrolled advocate).
        2. Obtains authoritative candidate identification and model provenance metadata
           from the server-side CandidateRegistry.
        3. Never trusts client-supplied model_identifier, model_version, confidence_value,
           contract_id, or clause_id.
        4. Rejects submission explicitly if trusted candidate record cannot be resolved.
        5. Injects trusted identification metadata server-side before final Draft-07 schema
           validation and canonical SHA-256 digest computation.
        """
        if not annotator_user or annotator_user.account_status != AccountStatus.ACTIVE.value:
            raise PermissionError("Authentication and active account required.")

        # Annotators must be verified advocates or supervising lawyers
        if annotator_user.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            raise PermissionError("Only enrolled advocates or supervising lawyers may submit annotations.")

        if annotator_user.role == UserRole.LAWYER.value and annotator_user.advocate_status != AdvocateStatus.VERIFIED.value:
            raise PermissionError("Advocate verification required to submit legal annotations.")

        # Resolve authoritative candidate finding from trusted server-side store
        candidate = CandidateRegistry.resolve(candidate_finding_id, session=self.session)
        if not candidate:
            raise ValueError(
                f"Candidate finding '{candidate_finding_id}' cannot be resolved from trusted candidate source. "
                "Submissions for unverified candidate findings are strictly rejected."
            )

        # Authoritative metadata from server
        auth_contract_id = candidate["contract_id"]
        auth_clause_id = candidate["clause_id"]
        auth_is_synthetic = bool(candidate.get("is_synthetic_fixture", is_synthetic_fixture))

        trusted_identification = {
            "contract_id": auth_contract_id,
            "contract_cluster_id": candidate.get("contract_cluster_id", f"CLUSTER-{auth_contract_id}"),
            "contract_version": int(candidate.get("contract_version", 1)),
            "clause_id": auth_clause_id,
            "clause_text": candidate["clause_text"],
            "candidate_finding_id": candidate["candidate_finding_id"],
            "candidate_finding_text": candidate.get("candidate_finding_text", candidate["clause_text"]),
            "prediction_category": candidate["prediction_category"],
            "model_identifier": candidate.get("model_id") or candidate.get("model_identifier", "nlpaueb/legal-bert-base-uncased"),
            "model_version": candidate.get("model_version", "1.0.0"),
            "candidate_confidence": candidate.get("candidate_confidence") or {
                "score": float(candidate.get("confidence_value", 0.5)),
                "metric_type": "SIGMOID_PROBABILITY",
                "is_calibrated": False
            }
        }

        # Build synthesized authoritative payload:
        # Client supplies evaluative fields; server supplies authoritative identification and provenance
        synthesized_payload = dict(payload)
        synthesized_payload["identification"] = trusted_identification
        synthesized_payload["is_synthetic_fixture"] = auth_is_synthetic
        synthesized_payload["schema_version"] = "1.0.0"
        if not synthesized_payload.get("annotation_id"):
            synthesized_payload["annotation_id"] = str(uuid.uuid4())

        # Validate against schema
        is_valid, err_msg = self.validate_payload(synthesized_payload, stage=stage)
        if not is_valid:
            raise ValueError(f"Invalid annotation payload: {err_msg}")

        # Compute deterministic digest on authoritative synthesized payload
        payload_sha256 = compute_payload_sha256(synthesized_payload)
        payload_str = canonical_json_dumps(synthesized_payload)

        # Extract reference action if available
        reference_action = None
        if isinstance(synthesized_payload.get("final_reference_decision"), dict):
            reference_action = synthesized_payload["final_reference_decision"].get("reference_action")

        record = self.repo.create_blinded_annotation(
            candidate_finding_id=candidate["candidate_finding_id"],
            contract_id=auth_contract_id,
            clause_id=auth_clause_id,
            annotator_id=annotator_user.id,
            payload_json=payload_str,
            payload_sha256=payload_sha256,
            stage=stage,
            reference_action=reference_action,
            is_synthetic_fixture=auth_is_synthetic,
            version=1
        )

        # Record audit event
        self._record_audit_event(
            event_type=EventType.ANNOTATION_SUBMITTED,
            source_document_id=auth_contract_id,
            clause_id=auth_clause_id,
            actor_type=ActorType.REVIEWER,
            actor_reference=annotator_user.email,
            payload={
                "annotation_id": record.id,
                "candidate_finding_id": candidate["candidate_finding_id"],
                "stage": stage,
                "version": record.version,
                "payload_sha256": payload_sha256,
                "reference_action": reference_action
            }
        )

        return record

    def lock_annotation(
        self,
        annotation_id: str,
        annotator_user: UserRecord
    ) -> BlindedAnnotationRecord:
        """
        Locks a submitted annotation after strict validation.
        Transitions the record to immutable state and checks peer release conditions.
        """
        if not annotator_user or annotator_user.account_status != AccountStatus.ACTIVE.value:
            raise PermissionError("Authentication required.")

        record = self.repo.get_blinded_annotation_by_id(annotation_id)
        if not record:
            raise ValueError(f"Annotation record {annotation_id} not found.")

        if record.annotator_id != annotator_user.id:
            self._record_audit_event(
                event_type=EventType.ANNOTATION_ACCESS_DENIED,
                source_document_id=record.contract_id,
                clause_id=record.clause_id,
                actor_type=ActorType.REVIEWER,
                actor_reference=annotator_user.email,
                payload={"action": "LOCK_ATTEMPT_UNAUTHORIZED", "target_annotation_id": annotation_id}
            )
            raise PermissionError("Forbidden: cannot lock an annotation authored by another user.")

        if record.is_locked:
            raise ValueError("Annotation is already locked.")

        # Re-validate payload against Draft-07 schema before locking
        try:
            payload = json.loads(record.payload_json)
        except Exception:
            raise ValueError("Corrupted annotation payload JSON.")

        is_valid, err_msg = self.validate_payload(payload, stage=record.stage)
        if not is_valid:
            raise ValueError(f"Cannot lock invalid annotation: {err_msg}")

        # Verify digest consistency
        expected_digest = compute_payload_sha256(payload)
        if expected_digest != record.payload_sha256:
            raise ValueError("Payload integrity mismatch: SHA-256 digest does not match current payload.")

        # Lock record
        locked_record = self.repo.lock_blinded_annotation(annotation_id, annotator_user.id)

        # Audit event
        self._record_audit_event(
            event_type=EventType.ANNOTATION_LOCKED,
            source_document_id=record.contract_id,
            clause_id=record.clause_id,
            actor_type=ActorType.REVIEWER,
            actor_reference=annotator_user.email,
            payload={
                "annotation_id": locked_record.id,
                "candidate_finding_id": locked_record.candidate_finding_id,
                "stage": locked_record.stage,
                "version": locked_record.version,
                "payload_sha256": locked_record.payload_sha256,
                "locked_at": locked_record.locked_at.isoformat() if locked_record.locked_at else None
            }
        )

        # Evaluate Adjudication Readiness & Peer Status
        self._evaluate_adjudication_lifecycle(locked_record)

        return locked_record

    def _evaluate_adjudication_lifecycle(self, locked_record: BlindedAnnotationRecord):
        """
        Checks whether two independent locked annotations exist for this candidate.
        If both are locked:
        - Links submissions into BlindedAdjudicationRecord.
        - Evaluates consensus (matching reference_action) vs divergence.
        """
        all_active = self.repo.get_blinded_annotations_for_candidate(
            locked_record.candidate_finding_id,
            stage=locked_record.stage,
            only_active=True
        )

        locked_submissions = [a for a in all_active if a.is_locked]
        # Group by distinct annotator_id
        by_annotator = {}
        for s in locked_submissions:
            if s.annotator_id not in by_annotator:
                by_annotator[s.annotator_id] = s

        if len(by_annotator) >= 2:
            annotator_ids = list(by_annotator.keys())[:2]
            sub1 = by_annotator[annotator_ids[0]]
            sub2 = by_annotator[annotator_ids[1]]

            adj = self.repo.get_or_create_adjudication(
                candidate_finding_id=locked_record.candidate_finding_id,
                contract_id=locked_record.contract_id,
                clause_id=locked_record.clause_id
            )
            adj.annotator_1_submission_id = sub1.id
            adj.annotator_2_submission_id = sub2.id

            if sub1.reference_action and sub2.reference_action and sub1.reference_action == sub2.reference_action:
                adj.status = AdjudicationStatus.CONSENSUS_REACHED.value
                adj.final_disposition = sub1.reference_action
            else:
                adj.status = AdjudicationStatus.READY_FOR_ADJUDICATION.value

            self._record_audit_event(
                event_type=EventType.ADJUDICATION_INITIATED,
                source_document_id=locked_record.contract_id,
                clause_id=locked_record.clause_id,
                actor_type=ActorType.SYSTEM,
                payload={
                    "candidate_finding_id": locked_record.candidate_finding_id,
                    "adjudication_id": adj.id,
                    "status": adj.status,
                    "submission_1_id": sub1.id,
                    "submission_2_id": sub2.id,
                    "consensus": adj.status == AdjudicationStatus.CONSENSUS_REACHED.value
                }
            )
            self.session.flush()

    def get_submission_for_user(
        self,
        annotation_id: str,
        requester_user: UserRecord
    ) -> Dict[str, Any]:
        """
        Retrieves an annotation submission while strictly enforcing role authorization and blinding rules:
        - CLIENT role callers are strictly rejected with PermissionError.
        - User must possess LAWYER, SUPERVISING_LAWYER, or AUDITOR role.
        - Enrolled advocate verification required for LAWYER.
        - Authors can access their own submissions.
        - Peers can access peer submissions ONLY if both required submissions are locked.
        - Unlocked peer access raises BlindingViolationError.
        - Stored payload_json is never forwarded in raw form; sanitized evaluative payload is returned.
        """
        if not requester_user or requester_user.account_status != AccountStatus.ACTIVE.value:
            raise PermissionError("Authentication required.")

        # Explicit role check: Reject CLIENT role callers immediately
        if requester_user.role == UserRole.CLIENT.value:
            raise PermissionError(
                "Access forbidden: Clients are strictly prohibited from inspecting internal annotation submissions."
            )

        if requester_user.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value, UserRole.AUDITOR.value):
            raise PermissionError("Access forbidden: User role does not possess required privilege.")

        if requester_user.role == UserRole.LAWYER.value and requester_user.advocate_status != AdvocateStatus.VERIFIED.value:
            raise PermissionError("Access forbidden: Enrolled advocate verification required to inspect legal annotations.")

        record = self.repo.get_blinded_annotation_by_id(annotation_id)
        if not record:
            raise ValueError(f"Annotation {annotation_id} not found.")

        # Check if both submissions are locked for this candidate
        all_active = self.repo.get_blinded_annotations_for_candidate(
            record.candidate_finding_id,
            stage=record.stage,
            only_active=True
        )
        locked_by_distinct_annotators = {a.annotator_id for a in all_active if a.is_locked}
        both_locked = len(locked_by_distinct_annotators) >= 2

        # Sanitize evaluative payload: NEVER expose raw payload_json to caller
        sanitized_eval = PresentationFirewall.sanitize_evaluative_payload(record.payload_json)

        submission_dict = {
            "id": record.id,
            "candidate_finding_id": record.candidate_finding_id,
            "contract_id": record.contract_id,
            "clause_id": record.clause_id,
            "annotator_id": record.annotator_id,
            "stage": record.stage,
            "version": record.version,
            "is_locked": record.is_locked,
            "reference_action": record.reference_action,
            "payload_sha256": record.payload_sha256,
            "evaluative_payload": sanitized_eval,
            "submitted_at": record.submitted_at.isoformat() if record.submitted_at else None,
            "locked_at": record.locked_at.isoformat() if record.locked_at else None
        }

        try:
            return PresentationFirewall.filter_submission_for_annotator(
                submission_data=submission_dict,
                requester_user_id=requester_user.id,
                both_submissions_locked=both_locked
            )
        except BlindingViolationError as bve:
            self._record_audit_event(
                event_type=EventType.BLINDING_VIOLATION_BLOCKED,
                source_document_id=record.contract_id,
                clause_id=record.clause_id,
                actor_type=ActorType.REVIEWER,
                actor_reference=requester_user.email,
                payload={
                    "attempted_access": "PEER_SUBMISSION",
                    "target_annotation_id": annotation_id,
                    "reason": str(bve)
                }
            )
            raise

    def get_adjudication_dossier(
        self,
        candidate_finding_id: str,
        candidate_data: Dict[str, Any],
        requester_user: UserRecord
    ) -> Dict[str, Any]:
        """
        Retrieves the adjudication dossier for Senior Counsel.
        Strictly requires both primary annotator submissions to be locked.
        Never forwards raw payload_json; parses and sanitizes evaluative fields.
        """
        if not requester_user or requester_user.account_status != AccountStatus.ACTIVE.value:
            raise PermissionError("Authentication required.")

        if requester_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: only Supervising Lawyers may access adjudication dossiers.")

        all_active = self.repo.get_blinded_annotations_for_candidate(
            candidate_finding_id,
            stage=AnnotationStage.FULL_RECORD.value,
            only_active=True
        )
        locked = [a for a in all_active if a.is_locked]
        by_annotator = {a.annotator_id: a for a in locked}

        both_locked = len(by_annotator) >= 2
        sub_list = list(by_annotator.values())

        def _make_sub_dict(sub_record: BlindedAnnotationRecord) -> Dict[str, Any]:
            sanitized_eval = PresentationFirewall.sanitize_evaluative_payload(sub_record.payload_json)
            return {
                "id": sub_record.id,
                "annotator_id": sub_record.annotator_id,
                "stage": sub_record.stage,
                "version": sub_record.version,
                "is_locked": sub_record.is_locked,
                "payload_sha256": sub_record.payload_sha256,
                "reference_action": sub_record.reference_action,
                "evaluative_payload": sanitized_eval,
                "submitted_at": sub_record.submitted_at.isoformat() if sub_record.submitted_at else None,
                "locked_at": sub_record.locked_at.isoformat() if sub_record.locked_at else None
            }

        sub1_dict = _make_sub_dict(sub_list[0]) if len(sub_list) >= 1 else None
        sub2_dict = _make_sub_dict(sub_list[1]) if len(sub_list) >= 2 else None

        try:
            return PresentationFirewall.filter_adjudication_dossier(
                candidate_data=candidate_data,
                submission_1_data=sub1_dict,
                submission_2_data=sub2_dict,
                both_locked=both_locked
            )
        except BlindingViolationError as bve:
            self._record_audit_event(
                event_type=EventType.ANNOTATION_ACCESS_DENIED,
                source_document_id=candidate_data.get("contract_id"),
                clause_id=candidate_data.get("clause_id"),
                actor_type=ActorType.REVIEWER,
                actor_reference=requester_user.email,
                payload={
                    "attempted_access": "PREMATURE_ADJUDICATION_DOSSIER",
                    "candidate_finding_id": candidate_finding_id,
                    "reason": str(bve)
                }
            )
            raise

    def record_adjudication(
        self,
        candidate_finding_id: str,
        adjudicator_user: UserRecord,
        final_disposition: str,
        rationale: str,
        adjudication_payload: Optional[Dict[str, Any]] = None
    ) -> BlindedAdjudicationRecord:
        """
        Records the final binding adjudication decision by Senior Counsel.
        """
        if not adjudicator_user or adjudicator_user.account_status != AccountStatus.ACTIVE.value:
            raise PermissionError("Authentication required.")

        if adjudicator_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: only Supervising Lawyers may record adjudication decisions.")

        valid_dispositions = {"RETAIN", "WITHHOLD", "HUMAN_REVIEW_REQUIRED", "NOT_ASSESSABLE"}
        if final_disposition not in valid_dispositions:
            raise ValueError(f"Invalid final_disposition '{final_disposition}'.")

        if not rationale or len(rationale.strip()) < 10:
            raise ValueError("Detailed adjudicator rationale (minimum 10 characters) is mandatory.")

        payload_to_store = adjudication_payload or {
            "candidate_finding_id": candidate_finding_id,
            "final_disposition": final_disposition,
            "rationale": rationale,
            "adjudicator_id": adjudicator_user.id
        }
        payload_str = canonical_json_dumps(payload_to_store)
        payload_sha256 = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        adj = self.repo.record_adjudication(
            candidate_finding_id=candidate_finding_id,
            adjudicator_id=adjudicator_user.id,
            final_disposition=final_disposition,
            adjudicator_rationale=rationale,
            adjudication_payload_json=payload_str,
            payload_sha256=payload_sha256
        )

        self._record_audit_event(
            event_type=EventType.ADJUDICATION_RECORDED,
            source_document_id=adj.contract_id,
            clause_id=adj.clause_id,
            actor_type=ActorType.REVIEWER,
            actor_reference=adjudicator_user.email,
            payload={
                "adjudication_id": adj.id,
                "candidate_finding_id": candidate_finding_id,
                "final_disposition": final_disposition,
                "payload_sha256": payload_sha256
            }
        )

        return adj
