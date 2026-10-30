"""
Candidate Generation Pipeline for CONTRACTRISK-XAI.

Provides a reproducible, defensive pipeline interface connecting contract-text
snapshots and segmented clauses to model inference and statutory evidence retrieval.
Enforces strict provenance, deterministic identification, label-space validation,
uncalibrated confidence disclosures, and client disclosure isolation.
"""

import hashlib
from typing import List, Dict, Any, Optional, Tuple, Callable, Union, Set
from datetime import datetime, timezone

from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    CandidateOrigin,
    VersionConsistencyStatus,
    LabelMappingStatus,
    DuplicateFindingEntry,
)
from src.candidates.deduplication import deduplicate_candidates
from src.candidates.alternative_validator import ContractConfiguration


# Standard Indian commercial risk categories documented in CONTRACTRISK-XAI
VALID_INDIAN_RISK_CATEGORIES = {
    "INDEMNIFICATION",
    "LIMITATION_OF_LIABILITY",
    "TERMINATION_CONVENIENCE",
    "NON_COMPETE_RESTRAINT",
    "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "PRICE_ADJUSTMENT",
    "GOVERNING_LAW_DISPUTE",
    "CONFIDENTIALITY_UNILATERAL",
    "SEVERABILITY_RESTRAINT",
}


def generate_deterministic_finding_id(
    contract_id: str,
    contract_version: int,
    clause_id: str,
    prediction_category: str,
    raw_model_label: str,
    model_id: str,
) -> str:
    """
    Computes a deterministic SHA-256 finding identifier formatted as a standard UUID-like string.
    Ensures identical inputs and model outputs always receive an identical identifier.
    """
    hasher = hashlib.sha256()
    payload = f"{contract_id}:{contract_version}:{clause_id}:{prediction_category}:{raw_model_label}:{model_id}"
    hasher.update(payload.encode("utf-8"))
    hex_digest = hasher.hexdigest()
    # Format as standard 8-4-4-4-12 hex UUID string
    return f"{hex_digest[:8]}-{hex_digest[8:12]}-{hex_digest[12:16]}-{hex_digest[16:20]}-{hex_digest[20:32]}"


class CandidateGenerationPipeline:
    """
    Reproducible candidate-generation pipeline for contract risk findings.
    
    Adheres strictly to the following architectural invariants:
    1. Does NOT fabricate finding descriptions if the model only produces class labels.
    2. Does NOT treat sigmoid, softmax, or heuristic scores as interchangeable.
    3. Explicitly flags uncalibrated model scores (confidence_is_calibrated = False).
    4. Halts or marks UNSUPPORTED_LABEL_MAPPING if model label space cannot be defensibly mapped.
    5. Isolates candidate generation from client disclosure (is_disclosed_to_client = False).
    """

    def __init__(
        self,
        model_wrapper: Optional[Any] = None,
        label_mapper: Optional[Dict[str, str]] = None,
        evidence_retriever: Optional[Any] = None,
        active_version_resolver: Optional[Callable[[str], Optional[int]]] = None,
    ):
        """
        Args:
            model_wrapper: LegalBertWrapper or duck-typed inference object with predict() method.
            label_mapper: Explicit mapping dictionary from raw model labels/indices to valid Indian risk categories.
            evidence_retriever: ClauseEvidenceRetriever or callable returning statutory evidence dictionary.
            active_version_resolver: Optional callable (contract_id) -> active_version_int.
        """
        self.model_wrapper = model_wrapper
        self.label_mapper = label_mapper or {}
        self.evidence_retriever = evidence_retriever
        self.active_version_resolver = active_version_resolver

    def generate_candidates_for_clauses(
        self,
        contract_id: str,
        contract_version: int,
        document_content_hash: str,
        clauses: List[Dict[str, Any]],
        source_document_provenance: Optional[Dict[str, Any]] = None,
        origin: CandidateOrigin = CandidateOrigin.MODEL_INFERENCE_BATCH,
        is_synthetic_fixture: bool = False,
        active_configuration: Optional[Union[ContractConfiguration, Dict[str, Any]]] = None,
    ) -> Tuple[List[CandidateFindingRecord], List[DuplicateFindingEntry]]:
        """
        Executes candidate generation across a list of segmented clauses.
        
        Args:
            contract_id: Identifier of the contract document.
            contract_version: Monotonically increasing version integer.
            document_content_hash: SHA-256 digest of contract text snapshot.
            clauses: List of clause dictionaries containing 'clause_id' and 'text'.
            source_document_provenance: Optional provenance dictionary.
            origin: Finding origin enum.
            is_synthetic_fixture: Flag indicating whether this run is a synthetic test fixture.
            active_configuration: Optional ContractConfiguration or dict defining active clauses/alternatives.
                                  When supplied, validates configuration and skips inactive alternative
                                  clauses before model inference.
            
        Returns:
            Tuple of (canonical_candidates, duplicate_entries).
        """
        provenance = source_document_provenance or {}
        raw_candidates: List[CandidateFindingRecord] = []

        # Validate active configuration if supplied
        active_config: Optional[ContractConfiguration] = None
        if active_configuration is not None:
            if isinstance(active_configuration, dict):
                try:
                    active_config = ContractConfiguration(**active_configuration)
                except Exception as e:
                    raise ValueError(f"Invalid active_configuration: {e}") from e
            elif isinstance(active_configuration, ContractConfiguration):
                active_config = active_configuration
            else:
                raise ValueError(
                    f"active_configuration must be a ContractConfiguration or dict, got {type(active_configuration).__name__}"
                )

            # Contract ID alignment check
            if active_config.contract_id != contract_id:
                raise ValueError(
                    f"Configuration contract_id '{active_config.contract_id}' does not match "
                    f"contract_id '{contract_id}'"
                )

            # Validate alternative groups present in clauses against active configuration
            groups_in_clauses: Dict[str, Set[str]] = {}
            for c in clauses:
                g_id = c.get("alternative_group_id")
                if g_id:
                    c_alt_id = str(c.get("alternative_id") or c.get("clause_id") or c.get("segment_id") or "")
                    groups_in_clauses.setdefault(g_id, set()).add(c_alt_id)

            for g_id, option_ids in groups_in_clauses.items():
                if g_id not in active_config.active_alternatives:
                    raise ValueError(
                        f"Active configuration missing selection for alternative group '{g_id}' "
                        f"present in contract clauses."
                    )
                selected_alt = active_config.active_alternatives[g_id]
                if option_ids and selected_alt not in option_ids:
                    raise ValueError(
                        f"Active configuration selected alternative '{selected_alt}' for group '{g_id}', "
                        f"which is not among available clause options: {sorted(list(option_ids))}"
                    )

        # Determine version consistency status against active document revision
        version_status = VersionConsistencyStatus.UNKNOWN
        if self.active_version_resolver:
            try:
                active_v = self.active_version_resolver(contract_id)
                if active_v is not None:
                    if contract_version == active_v:
                        version_status = VersionConsistencyStatus.CONSISTENT
                    else:
                        version_status = VersionConsistencyStatus.STALE
            except Exception:
                version_status = VersionConsistencyStatus.UNKNOWN

        # Model provenance metadata
        model_id = "unknown-model"
        model_version = "unknown-version"
        model_task = "CLASSIFICATION"
        classification_mode = "multilabel"
        model_available = False

        if self.model_wrapper and hasattr(self.model_wrapper, "config"):
            cfg = self.model_wrapper.config
            model_id = getattr(cfg, "model_checkpoint", getattr(cfg, "model_name", "legal-bert"))
            model_version = getattr(cfg, "model_family", "1.0.0")
            model_task = getattr(cfg, "task_type", "CLASSIFICATION")
            classification_mode = getattr(cfg, "classification_mode", "multilabel")
            if hasattr(self.model_wrapper, "is_available"):
                model_available = self.model_wrapper.is_available()
            else:
                model_available = True

        for clause in clauses:
            clause_id = str(clause.get("clause_id") or clause.get("segment_id") or "unknown-clause")
            clause_text = str(clause.get("text") or clause.get("clause_text") or "")

            if not clause_text.strip():
                continue

            # When active_configuration is supplied, skip inactive alternative clauses before inference
            if active_config is not None:
                is_alt = clause.get("is_drafting_alternative", False) or bool(clause.get("alternative_group_id"))
                group_id = clause.get("alternative_group_id")
                alt_id = str(clause.get("alternative_id") or clause_id)

                if is_alt:
                    if group_id and group_id in active_config.active_alternatives:
                        active_alt = active_config.active_alternatives[group_id]
                        if alt_id != active_alt and clause_id != active_alt:
                            # Inactive alternative: skip before model inference
                            continue
                    elif active_config.active_clause_ids:
                        if clause_id not in active_config.active_clause_ids and alt_id not in active_config.active_clause_ids:
                            # Inactive alternative: skip before model inference
                            continue

            # 1. Statutory Retrieval & Evidence Quality Assessment
            ev_status = None
            passages = []
            if self.evidence_retriever:
                try:
                    ev_data = self.evidence_retriever.retrieve_evidence_for_clause(
                        clause_text=clause_text,
                        clause_id=clause_id,
                        source_document_id=contract_id,
                        document_version_mismatch=(version_status == VersionConsistencyStatus.STALE),
                    )
                    ev_status = ev_data.get("evidence_quality_status")
                    passages = ev_data.get("passages", [])
                except Exception:
                    ev_status = "EVIDENCE_RETRIEVAL_FAILED"
                    passages = []

            # 2. Model Prediction
            inferred_predictions: List[Tuple[str, float, ConfidenceSemantics, List[str]]] = []

            if self.model_wrapper and model_available:
                try:
                    from src.models.prediction import predict
                    preds, probs, truncs = predict(self.model_wrapper, [clause_text])
                    prob_vector = probs[0]
                    is_truncated = bool(truncs[0]) if len(truncs) > 0 else False

                    missing_caps = []
                    if is_truncated:
                        missing_caps.append("INPUT_TRUNCATED")

                    if classification_mode == "multilabel":
                        sem = ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE
                        for idx, p_val in enumerate(prob_vector):
                            float_val = float(p_val)
                            # Threshold check or retain all positive assertions
                            threshold = getattr(self.model_wrapper.config, "multilabel_threshold", 0.5)
                            if float_val >= threshold:
                                inferred_predictions.append((str(idx), float_val, sem, missing_caps))
                    else:
                        sem = ConfidenceSemantics.MULTICLASS_SOFTMAX_SCORE
                        top_idx = int(preds[0])
                        float_val = float(prob_vector[top_idx])
                        inferred_predictions.append((str(top_idx), float_val, sem, missing_caps))
                except Exception as e:
                    # Model inference failed; record explicit capability blocker
                    inferred_predictions.append(("PREDICTION_FAILED", 0.0, ConfidenceSemantics.UNSPECIFIED, [f"INFERENCE_ERROR: {str(e)}"]))
            else:
                # Reusable path: Check if candidate predictions were passed directly in clause dictionary (e.g. from benchmark dataset or offline batch)
                provided_preds = clause.get("candidate_predictions")
                if provided_preds:
                    for p in provided_preds:
                        raw_lbl = str(p.get("raw_label", "unknown"))
                        conf = float(p.get("confidence", 0.0))
                        sem_str = p.get("confidence_semantics", ConfidenceSemantics.UNSPECIFIED.value)
                        try:
                            sem = ConfidenceSemantics(sem_str)
                        except ValueError:
                            sem = ConfidenceSemantics.UNSPECIFIED
                        inferred_predictions.append((raw_lbl, conf, sem, p.get("missing_capabilities", [])))
                else:
                    inferred_predictions.append(("NO_MODEL_AVAILABLE", 0.0, ConfidenceSemantics.UNSPECIFIED, ["MODEL_UNAVAILABLE"]))

            # 3. Construct Candidate Records with Defensive Label Mapping
            for raw_lbl, conf_val, sem_type, missing_caps in inferred_predictions:
                current_missing_caps = list(missing_caps)
                # Check for calibration limitation
                current_missing_caps.append("UNCALIBRATED_RAW_SCORE")

                # Validate Label Mapping to Indian Commercial Risk Categories
                mapping_status = LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING
                if raw_lbl in self.label_mapper:
                    mapped_cat = self.label_mapper[raw_lbl]
                    if mapped_cat in VALID_INDIAN_RISK_CATEGORIES:
                        pred_category = mapped_cat
                        mapping_status = LabelMappingStatus.MAPPED
                    else:
                        pred_category = f"UNSUPPORTED_MAPPING_{mapped_cat}"
                        mapping_status = LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING
                        current_missing_caps.append("INVALID_TARGET_CATEGORY")
                elif raw_lbl in VALID_INDIAN_RISK_CATEGORIES:
                    pred_category = raw_lbl
                    mapping_status = LabelMappingStatus.EXACT_MATCH
                else:
                    # STRICT REQUIREMENT: Do NOT invent a fake mapping for unsupported label spaces!
                    pred_category = f"UNMAPPED_{raw_lbl}"
                    mapping_status = LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING
                    current_missing_caps.append(f"UNSUPPORTED_MODEL_LABEL_SPACE: '{raw_lbl}'")

                # Compute deterministic candidate finding ID
                cand_id = generate_deterministic_finding_id(
                    contract_id=contract_id,
                    contract_version=contract_version,
                    clause_id=clause_id,
                    prediction_category=pred_category,
                    raw_model_label=raw_lbl,
                    model_id=model_id,
                )

                candidate = CandidateFindingRecord(
                    candidate_finding_id=cand_id,
                    contract_id=contract_id,
                    contract_version=contract_version,
                    document_content_hash=document_content_hash,
                    clause_id=clause_id,
                    clause_text=clause_text,
                    prediction_category=pred_category,
                    raw_model_label=raw_lbl,
                    candidate_finding_text=None, # Never fabricate explanatory text if model produces only class label
                    model_id=model_id,
                    model_version=model_version,
                    model_task=model_task,
                    confidence_value=conf_val,
                    confidence_semantics=sem_type,
                    confidence_is_calibrated=False, # Raw model scores are NOT calibrated probabilities
                    prediction_timestamp=datetime.now(timezone.utc).isoformat(),
                    source_document_provenance=provenance,
                    evidence_quality_status=ev_status,
                    retrieved_passages=passages,
                    version_consistency_status=version_status,
                    label_mapping_status=mapping_status,
                    missing_capabilities=sorted(list(set(current_missing_caps))),
                    origin=origin,
                    is_synthetic_fixture=is_synthetic_fixture,
                    is_disclosed_to_client=False, # STRICT INVARIANT: Isolated from client disclosure
                )
                raw_candidates.append(candidate)

        # 4. Apply Deduplication Protocol
        canonical_candidates, duplicate_log = deduplicate_candidates(raw_candidates)
        return canonical_candidates, duplicate_log
