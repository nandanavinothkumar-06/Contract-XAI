"""
Executable Evidence-Aware Abstention Policy for CONTRACTRISK-XAI.

Implements the formal five-tier hierarchical decision cascade documented in
`docs/annotation_guidelines_abstention.md` for evaluating candidate contract risk
findings. Connects model confidence, statutory evidence sufficiency, source
provenance, and document-version consistency into a deterministic, testable policy.

Strict Invariants:
1. Operational decisions (ACCEPT, WITHHOLD, REVIEW_REQUIRED) are deterministic and reproducible.
2. Five-tier precedence order is strictly enforced:
   Tier 1 (Assessability) -> Tier 2 (Fatal Defects) -> Tier 3 (High-Severity / Nuance)
   -> Tier 4 (Evidentiary Deficiencies) -> Tier 5 (Fully Grounded Retention).
3. Primary reason code strictly follows the highest-precedence tier.
4. All applicable reason codes are preserved in `all_applicable_reason_codes`.
5. Non-statutory commercial drafting risks are not rejected solely due to absent statutory passages.
6. High confidence is never treated as legal validity or calibrated probability.
7. Uncalibrated confidence scores remain explicitly flagged as uncalibrated.
8. ACCEPT does not constitute proof of legal correctness or authorization for client disclosure.
9. All policy outputs strictly maintain `is_disclosed_to_client = False`.
10. The original CandidateFindingRecord is never mutated.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict

from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    VersionConsistencyStatus,
    LabelMappingStatus,
)
from src.evaluation.abstention_eval import (
    PolicyAction,
    PolicyDecisionRecord,
)


class EvidencePolicyReasonCode(str, Enum):
    """
    Standardized, deterministic reason codes capturing the justification for each policy action.
    Organized by hierarchical precedence tier.
    """
    # ---------------------------------------------------------
    # Tier 1: Input Assessability (Priority 1)
    # ---------------------------------------------------------
    INPUT_UNASSESSABLE = "INPUT_UNASSESSABLE"
    MISSING_REQUIRED_IDENTIFIER = "MISSING_REQUIRED_IDENTIFIER"
    EMPTY_CLAUSE_TEXT = "EMPTY_CLAUSE_TEXT"
    INVALID_VERSION_INFORMATION = "INVALID_VERSION_INFORMATION"
    UNRECOGNIZED_EVIDENCE_STATUS = "UNRECOGNIZED_EVIDENCE_STATUS"

    # ---------------------------------------------------------
    # Tier 2: Fatal Defects (Priority 2)
    # ---------------------------------------------------------
    STALE_DOCUMENT_VERSION = "STALE_DOCUMENT_VERSION"
    INAPPLICABLE_OR_SUPERSEDED_STATUTE = "INAPPLICABLE_OR_SUPERSEDED_STATUTE"
    INCORRECT_PREDICTION = "INCORRECT_PREDICTION"
    MULTIPLE_FATAL_FAILURES = "MULTIPLE_FATAL_FAILURES"

    # ---------------------------------------------------------
    # Tier 3: High-Severity Safety Net & Legal Nuance (Priority 3)
    # ---------------------------------------------------------
    HIGH_SEVERITY_UNSUPPORTED_EVIDENCE = "HIGH_SEVERITY_UNSUPPORTED_EVIDENCE"
    HIGH_SEVERITY_INSUFFICIENT_EVIDENCE = "HIGH_SEVERITY_INSUFFICIENT_EVIDENCE"
    HIGH_SEVERITY_MISSING_STATUTORY_MATCH = "HIGH_SEVERITY_MISSING_STATUTORY_MATCH"
    STATUTORY_TEXT_DIFFERENCE = "STATUTORY_TEXT_DIFFERENCE"
    CONTRACTUAL_OVERRIDE_PERMITTED = "CONTRACTUAL_OVERRIDE_PERMITTED"
    PARTIALLY_CORRECT_PREDICTION = "PARTIALLY_CORRECT_PREDICTION"
    UNCLEAR_CONTRACT_TEXT = "UNCLEAR_CONTRACT_TEXT"
    UNKNOWN_DOCUMENT_VERSION = "UNKNOWN_DOCUMENT_VERSION"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE"
    UNSUPPORTED_LABEL_MAPPING = "UNSUPPORTED_LABEL_MAPPING"

    # ---------------------------------------------------------
    # Tier 4: Low/Medium Evidentiary Deficiencies (Priority 4)
    # ---------------------------------------------------------
    UNSUPPORTED_FINDING = "UNSUPPORTED_FINDING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_MATCHING_EVIDENCE = "NO_MATCHING_EVIDENCE"
    BELOW_CONFIDENCE_THRESHOLD = "BELOW_CONFIDENCE_THRESHOLD"

    # ---------------------------------------------------------
    # Tier 5: Fully Grounded Retention (Priority 5)
    # ---------------------------------------------------------
    GROUNDED_STATUTORY_FINDING = "GROUNDED_STATUTORY_FINDING"
    VALID_NON_STATUTORY_COMMERCIAL_FINDING = "VALID_NON_STATUTORY_COMMERCIAL_FINDING"


# Precedence tier ranking lookup (Lower number = higher precedence)
REASON_TIER_PRIORITY: Dict[EvidencePolicyReasonCode, int] = {
    # Tier 1
    EvidencePolicyReasonCode.INPUT_UNASSESSABLE: 1,
    EvidencePolicyReasonCode.MISSING_REQUIRED_IDENTIFIER: 1,
    EvidencePolicyReasonCode.EMPTY_CLAUSE_TEXT: 1,
    EvidencePolicyReasonCode.INVALID_VERSION_INFORMATION: 1,
    EvidencePolicyReasonCode.UNRECOGNIZED_EVIDENCE_STATUS: 1,

    # Tier 2
    EvidencePolicyReasonCode.STALE_DOCUMENT_VERSION: 2,
    EvidencePolicyReasonCode.INAPPLICABLE_OR_SUPERSEDED_STATUTE: 2,
    EvidencePolicyReasonCode.INCORRECT_PREDICTION: 2,
    EvidencePolicyReasonCode.MULTIPLE_FATAL_FAILURES: 2,

    # Tier 3
    EvidencePolicyReasonCode.HIGH_SEVERITY_UNSUPPORTED_EVIDENCE: 3,
    EvidencePolicyReasonCode.HIGH_SEVERITY_INSUFFICIENT_EVIDENCE: 3,
    EvidencePolicyReasonCode.HIGH_SEVERITY_MISSING_STATUTORY_MATCH: 3,
    EvidencePolicyReasonCode.STATUTORY_TEXT_DIFFERENCE: 3,
    EvidencePolicyReasonCode.CONTRACTUAL_OVERRIDE_PERMITTED: 3,
    EvidencePolicyReasonCode.PARTIALLY_CORRECT_PREDICTION: 3,
    EvidencePolicyReasonCode.UNCLEAR_CONTRACT_TEXT: 3,
    EvidencePolicyReasonCode.UNKNOWN_DOCUMENT_VERSION: 3,
    EvidencePolicyReasonCode.SOURCE_UNVERIFIED: 3,
    EvidencePolicyReasonCode.PARTIAL_EVIDENCE: 3,
    EvidencePolicyReasonCode.UNSUPPORTED_LABEL_MAPPING: 3,

    # Tier 4
    EvidencePolicyReasonCode.UNSUPPORTED_FINDING: 4,
    EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE: 4,
    EvidencePolicyReasonCode.NO_MATCHING_EVIDENCE: 4,
    EvidencePolicyReasonCode.BELOW_CONFIDENCE_THRESHOLD: 4,

    # Tier 5
    EvidencePolicyReasonCode.GROUNDED_STATUTORY_FINDING: 5,
    EvidencePolicyReasonCode.VALID_NON_STATUTORY_COMMERCIAL_FINDING: 5,
}

VALID_EVIDENCE_QUALITY_STATUSES = {
    "TRACEABLE",
    "PARTIAL",
    "INSUFFICIENT",
    "SOURCE_UNVERIFIED",
    "STALE_EVIDENCE",
    "NO_MATCHING_EVIDENCE",
}

DEFAULT_NON_STATUTORY_CATEGORIES = {
    "PRICE_ADJUSTMENT",
    "PAYMENT_TERMS",
    "NOTICE_PERIOD",
    "COMMERCIAL_DRAFTING_AMBIGUITY",
}


class EvidenceAwarePolicyConfig(BaseModel):
    """Configuration parameters for the evidence-aware abstention policy."""
    model_config = ConfigDict(extra="forbid")

    policy_id: str = "evidence_aware_policy_v1"
    policy_version: str = "1.0.0"
    # Documented baseline threshold: 0.5 matches LegalBertConfig.multilabel_threshold
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum continuous confidence score for candidate acceptance."
    )
    non_statutory_categories: Set[str] = Field(
        default_factory=lambda: set(DEFAULT_NON_STATUTORY_CATEGORIES),
        description="Set of risk categories recognized as contractual/commercial drafting issues not requiring external statutory grounding."
    )
    enable_version_consistency: bool = Field(
        default=True,
        description="Whether to enforce document version consistency (Tier 2 stale and Tier 3 unknown checks)."
    )
    enable_high_severity_safety_net: bool = Field(
        default=True,
        description="Whether to route high-severity risks with defective statutory evidence to advocate review in Tier 3."
    )
    enable_statutory_grounding: bool = Field(
        default=True,
        description="Whether to require TRACEABLE statutory evidence for statutory risk findings in Tier 4 and Tier 5."
    )


class EvidencePolicyDecision(BaseModel):
    """Structured decision output produced by the evidence-aware policy for a candidate finding."""
    model_config = ConfigDict(extra="forbid")

    candidate_finding_id: str
    policy_id: str
    policy_action: PolicyAction
    primary_reason_code: EvidencePolicyReasonCode
    all_applicable_reason_codes: List[EvidencePolicyReasonCode]
    precedence_tier_applied: int = Field(ge=1, le=5)
    evidence_quality_status: Optional[str] = None
    version_consistency_status: VersionConsistencyStatus
    confidence_value: float
    confidence_semantics: ConfidenceSemantics
    confidence_is_calibrated: bool
    missing_capabilities: List[str]
    policy_version: str
    decision_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_disclosed_to_client: bool = Field(
        default=False,
        description="STRICT INVARIANT: Policy decisions MUST remain undisclosed to clients."
    )
    decision_metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_evaluation_record(self) -> PolicyDecisionRecord:
        """
        Converts this decision to the standard PolicyDecisionRecord consumable
        by the evaluation harness in src/evaluation/abstention_eval.py.
        """
        return PolicyDecisionRecord(
            candidate_finding_id=self.candidate_finding_id,
            policy_id=self.policy_id,
            action=self.policy_action,
            threshold_applied=self.confidence_value,
            decision_metadata={
                "primary_reason_code": self.primary_reason_code.value,
                "all_applicable_reason_codes": [r.value for r in self.all_applicable_reason_codes],
                "precedence_tier_applied": self.precedence_tier_applied,
                "evidence_quality_status": self.evidence_quality_status,
                "version_consistency_status": self.version_consistency_status.value,
                "confidence_semantics": self.confidence_semantics.value,
                "confidence_is_calibrated": self.confidence_is_calibrated,
                "missing_capabilities": self.missing_capabilities,
                "policy_version": self.policy_version,
                "decision_timestamp": self.decision_timestamp,
                "is_disclosed_to_client": False,
                **self.decision_metadata,
            }
        )


class EvidenceAwarePolicy:
    """
    Executable implementation of the Five-Tier Precedence Cascade for evidence-aware abstention.
    Evaluates candidate findings against document versions, statutory evidence sufficiency,
    source provenance, and confidence semantics without modifying candidate records.
    """

    def __init__(self, config: Optional[EvidenceAwarePolicyConfig] = None):
        self.config = config or EvidenceAwarePolicyConfig()

    def evaluate_candidate(
        self,
        candidate: CandidateFindingRecord,
        reference_label: Optional[str] = None,
        explicit_severity: Optional[str] = None,
    ) -> EvidencePolicyDecision:
        """
        Evaluates a candidate finding under the 5-tier hierarchical cascade.

        Args:
            candidate: Immutable CandidateFindingRecord to evaluate.
            reference_label: Optional reference correctness label (e.g. 'CORRECT', 'INCORRECT',
                             'PARTIALLY_CORRECT', 'UNCLEAR') supplied strictly in evaluation contexts.
                             Never assumed or fabricated if None.
            explicit_severity: Optional severity string ('HIGH', 'MEDIUM', 'LOW').
                               Never fabricated if not supplied.

        Returns:
            EvidencePolicyDecision with deterministic action, tier, and reason codes.
        """
        reasons: List[EvidencePolicyReasonCode] = []

        # =====================================================================
        # TIER 1: INPUT ASSESSABILITY (Priority 1)
        # =====================================================================
        tier1_reasons: List[EvidencePolicyReasonCode] = []

        if not candidate.candidate_finding_id or not candidate.contract_id or not candidate.clause_id:
            tier1_reasons.append(EvidencePolicyReasonCode.MISSING_REQUIRED_IDENTIFIER)

        if not candidate.clause_text or not candidate.clause_text.strip():
            tier1_reasons.append(EvidencePolicyReasonCode.EMPTY_CLAUSE_TEXT)

        if candidate.contract_version < 1:
            tier1_reasons.append(EvidencePolicyReasonCode.INVALID_VERSION_INFORMATION)

        if candidate.evidence_quality_status is not None:
            if candidate.evidence_quality_status not in VALID_EVIDENCE_QUALITY_STATUSES:
                tier1_reasons.append(EvidencePolicyReasonCode.UNRECOGNIZED_EVIDENCE_STATUS)

        if tier1_reasons:
            sorted_t1 = self._sort_reasons_deterministically(tier1_reasons)
            primary = sorted_t1[0]
            return self._build_decision(
                candidate=candidate,
                action=PolicyAction.REVIEW_REQUIRED,
                primary_reason=primary,
                all_reasons=sorted_t1,
                tier=1,
            )

        # =====================================================================
        # TIER 2: FATAL FINDING DEFECTS (Priority 2 -> Mandatory WITHHOLD)
        # =====================================================================
        tier2_reasons: List[EvidencePolicyReasonCode] = []

        # 1. Stale document version
        if self.config.enable_version_consistency and candidate.version_consistency_status == VersionConsistencyStatus.STALE:
            tier2_reasons.append(EvidencePolicyReasonCode.STALE_DOCUMENT_VERSION)

        # 2. Inapplicable or repealed statutory sources
        for passage in candidate.retrieved_passages:
            leg_stat = str(passage.get("legal_status", "")).upper()
            curr_stat = str(passage.get("currentness_status", "")).upper()
            if leg_stat in ("REPEALED", "STRUCK_DOWN", "NOT_COMMENCED", "REPEALED_OR_SUPERSEDED") or \
               curr_stat in ("REPEALED", "JUDICIALLY_INVALIDATED"):
                tier2_reasons.append(EvidencePolicyReasonCode.INAPPLICABLE_OR_SUPERSEDED_STATUTE)
                break

        # 3. Known incorrect prediction in evaluation contexts
        if reference_label is not None:
            norm_ref = reference_label.strip().upper()
            if norm_ref in ("INCORRECT", "HALLUCINATED"):
                tier2_reasons.append(EvidencePolicyReasonCode.INCORRECT_PREDICTION)

        # If fatal defects exist, Tier 2 MUST govern regardless of lower-tier nuance
        if tier2_reasons:
            sorted_t2 = self._sort_reasons_deterministically(tier2_reasons)
            primary = (
                EvidencePolicyReasonCode.MULTIPLE_FATAL_FAILURES
                if len(sorted_t2) > 1
                else sorted_t2[0]
            )
            return self._build_decision(
                candidate=candidate,
                action=PolicyAction.WITHHOLD,
                primary_reason=primary,
                all_reasons=sorted_t2,
                tier=2,
            )

        # =====================================================================
        # TIER 3: HIGH-SEVERITY SAFETY NET & LEGAL NUANCE (Priority 3 -> REVIEW_REQUIRED)
        # =====================================================================
        tier3_reasons: List[EvidencePolicyReasonCode] = []

        # Extract severity only if explicitly supplied
        sev = explicit_severity or candidate.source_document_provenance.get("identified_risk_severity") or \
              candidate.source_document_provenance.get("severity")
        is_high_severity = (str(sev).strip().upper() == "HIGH") if sev else False

        # High-severity safety net: High risk with defective evidence must be reviewed by advocate
        if self.config.enable_high_severity_safety_net and is_high_severity:
            if candidate.evidence_quality_status == "INSUFFICIENT":
                tier3_reasons.append(EvidencePolicyReasonCode.HIGH_SEVERITY_INSUFFICIENT_EVIDENCE)
            elif candidate.evidence_quality_status == "NO_MATCHING_EVIDENCE":
                tier3_reasons.append(EvidencePolicyReasonCode.HIGH_SEVERITY_MISSING_STATUTORY_MATCH)

        # Unknown document version: never silently treated as current
        if self.config.enable_version_consistency and candidate.version_consistency_status == VersionConsistencyStatus.UNKNOWN:
            tier3_reasons.append(EvidencePolicyReasonCode.UNKNOWN_DOCUMENT_VERSION)

        # Text discrepancies or editorial annotations in cited provision
        for passage in candidate.retrieved_passages:
            warnings = passage.get("warnings", [])
            has_diff = passage.get("has_text_difference") is True
            if has_diff or any("TEXT_DIFFERENCE" in str(w) or "NOTE" in str(w).upper() for w in warnings):
                tier3_reasons.append(EvidencePolicyReasonCode.STATUTORY_TEXT_DIFFERENCE)
                break

        # Contractual override on default rule
        if candidate.source_document_provenance.get("contractual_override_permitted") is True:
            tier3_reasons.append(EvidencePolicyReasonCode.CONTRACTUAL_OVERRIDE_PERMITTED)

        # Reference-indicated partial correctness or ambiguity
        if reference_label is not None:
            norm_ref = reference_label.strip().upper()
            if norm_ref in ("PARTIALLY_CORRECT", "PARTIAL"):
                tier3_reasons.append(EvidencePolicyReasonCode.PARTIALLY_CORRECT_PREDICTION)
            elif norm_ref in ("UNCLEAR", "AMBIGUOUS"):
                tier3_reasons.append(EvidencePolicyReasonCode.UNCLEAR_CONTRACT_TEXT)

        # Source unverified or partial evidence quality
        if candidate.evidence_quality_status == "SOURCE_UNVERIFIED":
            tier3_reasons.append(EvidencePolicyReasonCode.SOURCE_UNVERIFIED)
        elif candidate.evidence_quality_status == "PARTIAL":
            tier3_reasons.append(EvidencePolicyReasonCode.PARTIAL_EVIDENCE)

        # Unsupported model label mapping (cannot be accepted as authentic Indian law)
        if candidate.label_mapping_status == LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING or \
           candidate.prediction_category.startswith("UNMAPPED_"):
            tier3_reasons.append(EvidencePolicyReasonCode.UNSUPPORTED_LABEL_MAPPING)

        if tier3_reasons:
            sorted_t3 = self._sort_reasons_deterministically(tier3_reasons)
            primary = sorted_t3[0]
            return self._build_decision(
                candidate=candidate,
                action=PolicyAction.REVIEW_REQUIRED,
                primary_reason=primary,
                all_reasons=sorted_t3,
                tier=3,
            )

        # =====================================================================
        # TIER 4: LOW/MEDIUM EVIDENTIARY DEFICIENCIES (Priority 4 -> WITHHOLD)
        # =====================================================================
        tier4_reasons: List[EvidencePolicyReasonCode] = []

        is_non_statutory = (
            candidate.prediction_category in self.config.non_statutory_categories or
            candidate.source_document_provenance.get("is_statutory") is False
        )

        # Insufficient evidence on low/medium risk (or high risk if safety net disabled)
        if self.config.enable_statutory_grounding and candidate.evidence_quality_status == "INSUFFICIENT":
            tier4_reasons.append(EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE)

        # Missing statutory evidence on statutory finding
        if self.config.enable_statutory_grounding and not is_non_statutory:
            if candidate.evidence_quality_status in ("NO_MATCHING_EVIDENCE", None):
                tier4_reasons.append(EvidencePolicyReasonCode.NO_MATCHING_EVIDENCE)

        # Below confidence threshold
        if candidate.confidence_value < self.config.confidence_threshold:
            tier4_reasons.append(EvidencePolicyReasonCode.BELOW_CONFIDENCE_THRESHOLD)

        if tier4_reasons:
            sorted_t4 = self._sort_reasons_deterministically(tier4_reasons)
            primary = sorted_t4[0]
            return self._build_decision(
                candidate=candidate,
                action=PolicyAction.WITHHOLD,
                primary_reason=primary,
                all_reasons=sorted_t4,
                tier=4,
            )

        # =====================================================================
        # TIER 5: FULLY GROUNDED RETENTION (Priority 5 -> ACCEPT)
        # =====================================================================
        tier5_reasons: List[EvidencePolicyReasonCode] = []

        if is_non_statutory:
            tier5_reasons.append(EvidencePolicyReasonCode.VALID_NON_STATUTORY_COMMERCIAL_FINDING)
        else:
            if not self.config.enable_statutory_grounding:
                tier5_reasons.append(EvidencePolicyReasonCode.GROUNDED_STATUTORY_FINDING)
            elif candidate.evidence_quality_status == "TRACEABLE":
                tier5_reasons.append(EvidencePolicyReasonCode.GROUNDED_STATUTORY_FINDING)
            else:
                # Fallback: if not TRACEABLE, cannot be accepted
                tier4_reasons.append(EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE)
                return self._build_decision(
                    candidate=candidate,
                    action=PolicyAction.WITHHOLD,
                    primary_reason=EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE,
                    all_reasons=[EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE],
                    tier=4,
                )

        sorted_t5 = self._sort_reasons_deterministically(tier5_reasons)
        return self._build_decision(
            candidate=candidate,
            action=PolicyAction.ACCEPT,
            primary_reason=sorted_t5[0],
            all_reasons=sorted_t5,
            tier=5,
        )

    def evaluate_candidates(
        self,
        candidates: List[CandidateFindingRecord],
        reference_labels: Optional[Dict[str, str]] = None,
        severities: Optional[Dict[str, str]] = None,
    ) -> List[EvidencePolicyDecision]:
        """
        Batch evaluates a list of candidate findings deterministically.
        """
        ref_dict = reference_labels or {}
        sev_dict = severities or {}
        decisions: List[EvidencePolicyDecision] = []

        for candidate in candidates:
            cid = candidate.candidate_finding_id
            ref_lbl = ref_dict.get(cid)
            sev_lbl = sev_dict.get(cid)
            decision = self.evaluate_candidate(
                candidate=candidate,
                reference_label=ref_lbl,
                explicit_severity=sev_lbl,
            )
            decisions.append(decision)

        return decisions

    def to_policy_decisions_dict(
        self,
        decisions: List[EvidencePolicyDecision],
    ) -> Dict[str, PolicyAction]:
        """
        Converts policy decisions to Dict[candidate_finding_id, PolicyAction]
        directly consumable by evaluate_policy() in src/evaluation/abstention_eval.py.
        """
        return {d.candidate_finding_id: d.policy_action for d in decisions}

    def _sort_reasons_deterministically(
        self,
        reasons: List[EvidencePolicyReasonCode]
    ) -> List[EvidencePolicyReasonCode]:
        """
        Sorts reason codes deterministically by precedence tier ascending,
        then alphabetically by reason code value.
        """
        unique_reasons = list(set(reasons))
        return sorted(
            unique_reasons,
            key=lambda r: (REASON_TIER_PRIORITY.get(r, 99), r.value)
        )

    def _build_decision(
        self,
        candidate: CandidateFindingRecord,
        action: PolicyAction,
        primary_reason: EvidencePolicyReasonCode,
        all_reasons: List[EvidencePolicyReasonCode],
        tier: int,
    ) -> EvidencePolicyDecision:
        """Constructs an immutable EvidencePolicyDecision record."""
        return EvidencePolicyDecision(
            candidate_finding_id=candidate.candidate_finding_id,
            policy_id=self.config.policy_id,
            policy_action=action,
            primary_reason_code=primary_reason,
            all_applicable_reason_codes=all_reasons,
            precedence_tier_applied=tier,
            evidence_quality_status=candidate.evidence_quality_status,
            version_consistency_status=candidate.version_consistency_status,
            confidence_value=candidate.confidence_value,
            confidence_semantics=candidate.confidence_semantics,
            confidence_is_calibrated=candidate.confidence_is_calibrated,
            missing_capabilities=list(candidate.missing_capabilities),
            policy_version=self.config.policy_version,
            is_disclosed_to_client=False, # STRICT INVARIANT
            decision_metadata={
                "prediction_category": candidate.prediction_category,
                "label_mapping_status": candidate.label_mapping_status.value,
                "enable_version_consistency": self.config.enable_version_consistency,
                "enable_high_severity_safety_net": self.config.enable_high_severity_safety_net,
                "enable_statutory_grounding": self.config.enable_statutory_grounding,
            }
        )
