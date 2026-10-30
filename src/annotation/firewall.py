"""
Server-Side Presentation Firewall for Blinded Legal Annotation.

Enforces strict server-side field-visibility boundaries to eliminate cognitive
anchoring, confirmation bias, and circular policy leakage during independent legal
evaluation of contract-risk findings (Strategy A).

All filtering uses explicit allowlists. Stripping occurs at the backend API layer
before response serialization, ensuring unpermitted fields never reach the client.
"""

import json
from typing import Dict, Any, List, Optional
from src.persistence.models import AnnotationStage


class BlindingViolationError(PermissionError):
    """Raised when an unauthorized actor attempts to access blinded fields or unreleased peer submissions."""
    def __init__(self, message: str = "Access denied by presentation firewall: blinded field requested."):
        super().__init__(message)
        self.message = message


class PresentationFirewall:
    """
    Core security firewall enforcing field-level visibility controls for annotators
    and adjudicators.
    """

    # Strictly forbidden model / policy fields that must NEVER appear in an annotator's or adjudicator's view
    PROHIBITED_MODEL_POLICY_FIELDS = {
        "model_id", "model_identifier", "model_name", "model_version", "model_task",
        "raw_model_label", "confidence_value", "candidate_confidence", "confidence_semantics",
        "confidence_is_calibrated", "score", "raw_logit", "probability", "ai_confidence_score",
        "evidence_quality_status", "bm25_score", "retrieval_rank", "ranking_score",
        "baseline_policy_decision", "evidence_aware_policy_decision", "policy_action",
        "is_retained", "decision_code", "threshold", "identification"
    }

    # Explicit allowlist for generic candidate finding presentation to an authorized annotator
    GENERIC_CANDIDATE_ALLOWLIST = {
        "candidate_finding_id",
        "contract_id",
        "contract_version",
        "document_content_hash",
        "clause_id",
        "clause_text",
        "prediction_category",
        "candidate_finding_text",
        "is_synthetic_fixture",
        "retrieved_passages"
    }

    # Explicit allowlist for individual statutory passage items shown to annotators
    PASSAGE_ALLOWLIST = {
        "passage_id",
        "statute_id",
        "statute_title",
        "section_number",
        "section_title",
        "section_heading",
        "passage_text",
        "source_repository",
        "source_sha256",
        "commencement_status"
    }

    # Explicit allowlists for human evaluative components permitted in adjudication
    HUMAN_EVALUATIVE_FIELD_ALLOWLISTS = {
        "prediction_assessment": {"status", "rationale", "identified_risk_severity"},
        "evidence_support": {"status", "rationale", "passages"},
        "evidence_sufficiency": {"status", "rationale"},
        "source_status": {"status", "source_repository", "provenance_classification", "source_sha256", "notes"},
        "source_applicability": {"currentness_status", "applicability_status", "rationale"},
        "version_consistency": {"status", "finding_contract_version", "active_contract_version", "text_hash_matches", "version_mismatch_details"},
        "final_reference_decision": {"reference_action", "decision_rationale", "confidence_in_decision", "failure_category_if_withhold"},
        "epistemic_firewall_attestation": {
            "rule_traceable_not_treated_as_correct",
            "rule_bm25_not_treated_as_ground_truth_sufficiency",
            "rule_checksum_not_treated_as_official_authenticity",
            "rule_authenticity_not_treated_as_applicability",
            "rule_policy_output_not_treated_as_reference_decision"
        },
        "annotation_provenance": {
            "annotator_code",
            "annotator_qualification",
            "annotation_phase",
            "blinding_conditions",
            "disagreement_flag",
            "created_at",
            "adjudication_timestamp",
            "notes"
        }
    }

    PRIMITIVE_EVALUATIVE_FIELDS = {
        "schema_version",
        "annotation_id",
        "is_synthetic_fixture"
    }

    @classmethod
    def sanitize_passage(cls, passage: Dict[str, Any]) -> Dict[str, Any]:
        """Filters a statutory passage record through the PASSAGE_ALLOWLIST."""
        if not isinstance(passage, dict):
            return {}
        return {k: passage[k] for k in cls.PASSAGE_ALLOWLIST if k in passage}

    @classmethod
    def sanitize_evaluative_payload(cls, payload_input: Any) -> Dict[str, Any]:
        """
        Parses and strictly sanitizes an annotation payload before presenting to
        annotators, adjudicators, or supervisors.

        Enforces explicit allowlists for human evaluative judgments and rationales.
        Completely strips model identifiers, confidence scores, logits, retrieval ranks,
        system statuses, and authoritative identification metadata.
        Safely handles malformed JSON without bypassing the firewall.
        """
        if not payload_input:
            return {}

        payload_data = payload_input
        if isinstance(payload_input, str):
            try:
                payload_data = json.loads(payload_input)
            except Exception:
                # Malformed JSON safely produces an empty dictionary
                return {}

        if not isinstance(payload_data, dict):
            return {}

        sanitized: Dict[str, Any] = {}

        # 1. Primitives
        for prim in cls.PRIMITIVE_EVALUATIVE_FIELDS:
            if prim in payload_data:
                sanitized[prim] = payload_data[prim]

        # 2. Section allowlists
        for sec, allowed_keys in cls.HUMAN_EVALUATIVE_FIELD_ALLOWLISTS.items():
            if sec in payload_data and isinstance(payload_data[sec], dict):
                sec_dict = {}
                raw_sec = payload_data[sec]
                for sub_k in allowed_keys:
                    if sub_k in raw_sec:
                        val = raw_sec[sub_k]
                        if isinstance(val, dict):
                            sec_dict[sub_k] = {
                                vk: vv for vk, vv in val.items()
                                if vk not in cls.PROHIBITED_MODEL_POLICY_FIELDS
                            }
                        else:
                            sec_dict[sub_k] = val
                sanitized[sec] = sec_dict

        return sanitized

    @classmethod
    def filter_candidate_for_annotator(
        cls,
        candidate_data: Dict[str, Any],
        stage: str = AnnotationStage.FULL_RECORD.value
    ) -> Dict[str, Any]:
        """
        Filters a candidate finding record for presentation to an authorized annotator.
        Applies explicit allowlists and stage-specific projections.
        Rejects invalid or unrecognized stages with ValueError.
        """
        if not isinstance(candidate_data, dict):
            return {}

        allowed_stages = {s.value for s in AnnotationStage}
        if stage not in allowed_stages:
            raise ValueError(
                f"Invalid or unrecognized annotation stage: '{stage}'. "
                f"Allowed stages are: {sorted(list(allowed_stages))}."
            )

        # 1. Stage-specific views
        if stage == AnnotationStage.STAGE_1_PREDICTION.value:
            # Stage 1: Prediction Correctness
            # Visible: clause_text, candidate_finding_text, prediction_category, candidate_finding_id, clause_id
            # Strictly hidden: model_identifier, candidate_confidence, policy decisions, retrieved passages
            return {
                "candidate_finding_id": candidate_data.get("candidate_finding_id"),
                "clause_id": candidate_data.get("clause_id"),
                "clause_text": candidate_data.get("clause_text"),
                "candidate_finding_text": candidate_data.get("candidate_finding_text"),
                "prediction_category": candidate_data.get("prediction_category"),
                "stage": stage
            }

        elif stage == AnnotationStage.STAGE_2_SUPPORT.value:
            # Stage 2: Evidence Support
            # Visible: clause_text, candidate_finding_text, cited passages text (sanitized), section title
            # Strictly hidden: BM25 scores, evidence_quality_status, model confidence, policy decisions
            raw_passages = candidate_data.get("retrieved_passages") or []
            sanitized_passages = [cls.sanitize_passage(p) for p in raw_passages]
            return {
                "candidate_finding_id": candidate_data.get("candidate_finding_id"),
                "clause_id": candidate_data.get("clause_id"),
                "clause_text": candidate_data.get("clause_text"),
                "candidate_finding_text": candidate_data.get("candidate_finding_text"),
                "retrieved_passages": sanitized_passages,
                "stage": stage
            }

        elif stage == AnnotationStage.STAGE_3_SUFFICIENCY.value:
            # Stage 3: Evidence Sufficiency
            # Visible: clause_text, candidate_finding_text, totality of retrieved passages
            # Strictly hidden: BM25 scores, evidence_quality_status, model confidence, policy decisions
            raw_passages = candidate_data.get("retrieved_passages") or []
            sanitized_passages = [cls.sanitize_passage(p) for p in raw_passages]
            return {
                "candidate_finding_id": candidate_data.get("candidate_finding_id"),
                "clause_id": candidate_data.get("clause_id"),
                "clause_text": candidate_data.get("clause_text"),
                "candidate_finding_text": candidate_data.get("candidate_finding_text"),
                "prediction_category": candidate_data.get("prediction_category"),
                "retrieved_passages": sanitized_passages,
                "stage": stage
            }

        elif stage == AnnotationStage.STAGE_4_SOURCE.value:
            # Stage 4: Source Status
            # Visible: statute title, section number, source_sha256, source_repository, commencement_status
            # Strictly hidden: model prediction text, candidate finding, confidence score, policy decisions
            raw_passages = candidate_data.get("retrieved_passages") or []
            source_items = []
            for p in raw_passages:
                source_items.append({
                    "statute_id": p.get("statute_id"),
                    "statute_title": p.get("statute_title"),
                    "section_number": p.get("section_number"),
                    "source_repository": p.get("source_repository"),
                    "source_sha256": p.get("source_sha256"),
                    "commencement_status": p.get("commencement_status")
                })
            return {
                "candidate_finding_id": candidate_data.get("candidate_finding_id"),
                "sources": source_items,
                "stage": stage
            }

        elif stage == AnnotationStage.STAGE_5_VERSION.value:
            # Stage 5: Version Consistency
            # Visible: active clause text, finding clause text, version numbers, text SHA-256
            # Strictly hidden: model confidence scores, policy recommendations
            return {
                "candidate_finding_id": candidate_data.get("candidate_finding_id"),
                "contract_id": candidate_data.get("contract_id"),
                "contract_version": candidate_data.get("contract_version"),
                "document_content_hash": candidate_data.get("document_content_hash"),
                "clause_id": candidate_data.get("clause_id"),
                "clause_text": candidate_data.get("clause_text"),
                "stage": stage
            }

        elif stage == AnnotationStage.STAGE_6_DISPOSITION.value:
            # Stage 6: Final Reference Decision
            # Visible: clause_text, candidate_finding_text, prediction_category, sanitized passages
            # Strictly hidden: baseline policy decision, evidence-aware policy decision, model confidence
            raw_passages = candidate_data.get("retrieved_passages") or []
            sanitized_passages = [cls.sanitize_passage(p) for p in raw_passages]
            return {
                "candidate_finding_id": candidate_data.get("candidate_finding_id"),
                "clause_id": candidate_data.get("clause_id"),
                "clause_text": candidate_data.get("clause_text"),
                "candidate_finding_text": candidate_data.get("candidate_finding_text"),
                "prediction_category": candidate_data.get("prediction_category"),
                "retrieved_passages": sanitized_passages,
                "stage": stage
            }

        elif stage in (AnnotationStage.STAGE_7_PEER_INDEPENDENT.value, AnnotationStage.STAGE_8_ADJUDICATION.value, AnnotationStage.FULL_RECORD.value):
            return cls._filter_generic_candidate(candidate_data)

        raise ValueError(f"Unhandled valid stage: '{stage}'.")

    @classmethod
    def _filter_generic_candidate(cls, candidate_data: Dict[str, Any]) -> Dict[str, Any]:
        """Projects candidate data through the GENERIC_CANDIDATE_ALLOWLIST."""
        sanitized = {}
        for key in cls.GENERIC_CANDIDATE_ALLOWLIST:
            if key in candidate_data:
                if key == "retrieved_passages":
                    raw_passages = candidate_data.get(key) or []
                    sanitized[key] = [cls.sanitize_passage(p) for p in raw_passages]
                else:
                    sanitized[key] = candidate_data[key]
        return sanitized

    @classmethod
    def filter_submission_for_annotator(
        cls,
        submission_data: Dict[str, Any],
        requester_user_id: str,
        both_submissions_locked: bool = False
    ) -> Dict[str, Any]:
        """
        Enforces access control and blinding on an annotation submission:
        - If requester is the author: returns sanitized evaluative submission.
        - If requester is a peer annotator:
            * If both submissions are locked: allows viewing peer evaluative submission.
            * If NOT both locked: strictly raises BlindingViolationError.
        - NEVER forwards raw payload_json.
        """
        author_id = submission_data.get("annotator_id")
        if requester_user_id != author_id and not both_submissions_locked:
            raise BlindingViolationError(
                "Access forbidden: Peer submissions remain strictly blinded until all required "
                "independent annotator submissions are locked."
            )

        raw_payload = submission_data.get("payload_json") or submission_data.get("evaluative_payload") or {}
        sanitized_eval = cls.sanitize_evaluative_payload(raw_payload)

        clean_sub = {k: v for k, v in submission_data.items() if k != "payload_json"}
        clean_sub["evaluative_payload"] = sanitized_eval
        return clean_sub

    @classmethod
    def filter_adjudication_dossier(
        cls,
        candidate_data: Dict[str, Any],
        submission_1_data: Optional[Dict[str, Any]],
        submission_2_data: Optional[Dict[str, Any]],
        both_locked: bool
    ) -> Dict[str, Any]:
        """
        Prepares the adjudication dossier for Senior Counsel / Supervising Lawyer:
        - REQUIRES both submissions to be locked.
        - Provides Annotator 1 ratings & rationale, Annotator 2 ratings & rationale,
          clause text, finding text, statutory extracts.
        - STRICTLY EXCLUDES model confidence, logits, baseline and evidence-aware policy decisions.
        - NEVER forwards raw payload_json.
        """
        if not both_locked or not submission_1_data or not submission_2_data:
            raise BlindingViolationError(
                "Adjudication gate closed: Adjudication requires both independent primary annotator "
                "submissions to be validated and locked."
            )

        sanitized_cand = cls.filter_candidate_for_annotator(candidate_data, stage=AnnotationStage.STAGE_8_ADJUDICATION.value)

        ADJUDICATION_SUBMISSION_ALLOWLIST = {
            "id", "annotator_id", "stage", "version", "is_locked", "submitted_at", "locked_at",
            "payload_sha256", "reference_action", "evaluative_payload"
        }

        def _format_sub(sub_data: Dict[str, Any]) -> Dict[str, Any]:
            raw_payload = sub_data.get("payload_json") or sub_data.get("evaluative_payload") or {}
            eval_payload = cls.sanitize_evaluative_payload(raw_payload)
            out = {}
            for k in ADJUDICATION_SUBMISSION_ALLOWLIST:
                if k == "evaluative_payload":
                    out["evaluative_payload"] = eval_payload
                elif k in sub_data and k != "payload_json":
                    out[k] = sub_data[k]
            return out

        sub1_view = _format_sub(submission_1_data)
        sub2_view = _format_sub(submission_2_data)

        return {
            "candidate": sanitized_cand,
            "submission_1": sub1_view,
            "submission_2": sub2_view,
            "adjudication_status": "READY_FOR_ADJUDICATION"
        }
