"""
Synthetic Unit Tests for Executable Evidence-Aware Abstention Policy.

Verifies:
A. Stale document version cannot be accepted (WITHHOLD).
B. Unknown document version is never silently treated as current (REVIEW_REQUIRED).
C. PARTIALLY_VERIFIED statutory source with discrepancies is routed to review.
D. TRACEABLE evidence does not automatically cause ACCEPT.
E. Insufficient evidence follows action rule (HIGH severity -> REVIEW_REQUIRED; LOW/MED -> WITHHOLD).
F. Non-statutory commercial risk is not rejected solely due to absent statutory passages (ACCEPT).
G. High-severity case requiring review is routed according to decision table when explicitly supplied.
H. Missing required input fails safely in Tier 1.
I. Uncalibrated confidence remains explicitly uncalibrated.
J. Documented confidence threshold (0.5) is enforced without silent modifications.
K. Primary reason code strictly respects five-tier precedence.
L. Additional applicable reason codes are retained.
M. Repeated evaluation produces identical results (determinism).
N. Original candidate object remains unchanged (immutability).
O. Policy output never enables client disclosure (is_disclosed_to_client == False).
P. Missing prediction correctness labels are not treated as correct or incorrect.
Q. Unsupported label mappings do not become accepted Indian legal classifications.
R. Unrecognized evidence statuses fail safely in Tier 1.
S. Malformed inputs and batch operations follow existing conventions.
T. Every action has a documented reason code.

NOTE: All tests use synthetic CandidateFindingRecord fixtures only.
They do NOT test real-world legal contracts or model accuracy.
"""

import pytest
from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    VersionConsistencyStatus,
    LabelMappingStatus,
    CandidateOrigin,
)
from src.evaluation.abstention_eval import PolicyAction
from src.abstention.evidence_policy import (
    EvidenceAwarePolicy,
    EvidenceAwarePolicyConfig,
    EvidencePolicyReasonCode,
    EvidencePolicyDecision,
)


def create_synthetic_candidate(
    cid: str = "cand-001",
    contract_id: str = "doc-001",
    version: int = 1,
    clause_id: str = "clause-01",
    clause_text: str = "The Contractor shall indemnify and hold harmless the Company.",
    category: str = "INDEMNIFICATION",
    raw_label: str = "0",
    confidence: float = 0.85,
    ev_status: str = "TRACEABLE",
    passages: list = None,
    version_status: VersionConsistencyStatus = VersionConsistencyStatus.CONSISTENT,
    mapping_status: LabelMappingStatus = LabelMappingStatus.MAPPED,
    missing_caps: list = None,
    provenance: dict = None,
) -> CandidateFindingRecord:
    """Helper creating synthetic candidate record for testing."""
    return CandidateFindingRecord(
        candidate_finding_id=cid,
        contract_id=contract_id,
        contract_version=version,
        document_content_hash="abc123sha256",
        clause_id=clause_id,
        clause_text=clause_text,
        prediction_category=category,
        raw_model_label=raw_label,
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=confidence,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status=ev_status,
        retrieved_passages=passages or [
            {
                "statute_id": "IN_ACT_1872_09",
                "section_number": "124",
                "passage_text": "A contract by which one party promises to save the other from loss...",
                "legal_status": "IN_FORCE_CONFIRMED",
                "currentness_status": "IN_FORCE_CONFIRMED",
                "verification_status": "PARTIALLY_VERIFIED",
                "warnings": [],
            }
        ],
        version_consistency_status=version_status,
        label_mapping_status=mapping_status,
        missing_capabilities=missing_caps or ["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance=provenance or {},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )


# =========================================================================
# TEST A: Stale document version cannot be accepted
# =========================================================================
def test_a_stale_document_version_withheld():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(version_status=VersionConsistencyStatus.STALE)

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.WITHHOLD
    assert decision.primary_reason_code == EvidencePolicyReasonCode.STALE_DOCUMENT_VERSION
    assert decision.precedence_tier_applied == 2


# =========================================================================
# TEST B: Unknown document version is never silently treated as current
# =========================================================================
def test_b_unknown_document_version_routes_to_review():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(version_status=VersionConsistencyStatus.UNKNOWN)

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.REVIEW_REQUIRED
    assert decision.primary_reason_code == EvidencePolicyReasonCode.UNKNOWN_DOCUMENT_VERSION
    assert decision.precedence_tier_applied == 3


# =========================================================================
# TEST C: PARTIALLY_VERIFIED source with discrepancies is routed to review
# =========================================================================
def test_c_partially_verified_source_with_text_difference():
    policy = EvidenceAwarePolicy()
    passages_with_notes = [
        {
            "statute_id": "IN_ACT_2000_21",
            "section_number": "43A",
            "passage_text": "Compensation for failure to protect data [Note: SPDI Rules 2011]...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "warnings": ["TEXT_DIFFERENCE: Researcher editorial note added"],
            "has_text_difference": True,
        }
    ]
    cand = create_synthetic_candidate(passages=passages_with_notes)

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.REVIEW_REQUIRED
    assert decision.primary_reason_code == EvidencePolicyReasonCode.STATUTORY_TEXT_DIFFERENCE
    assert decision.precedence_tier_applied == 3


# =========================================================================
# TEST D: TRACEABLE evidence does not automatically cause ACCEPT
# =========================================================================
def test_d_traceable_evidence_does_not_force_accept_if_below_threshold():
    policy = EvidenceAwarePolicy()
    # TRACEABLE evidence, but confidence is below configured 0.5 threshold
    cand = create_synthetic_candidate(ev_status="TRACEABLE", confidence=0.35)

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.WITHHOLD
    assert decision.primary_reason_code == EvidencePolicyReasonCode.BELOW_CONFIDENCE_THRESHOLD
    assert decision.precedence_tier_applied == 4


# =========================================================================
# TEST E: Insufficient evidence follows action rule (HIGH -> REVIEW, LOW -> WITHHOLD)
# =========================================================================
def test_e_insufficient_evidence_action_rule_by_severity():
    policy = EvidenceAwarePolicy()

    # Case 1: High severity -> REVIEW_REQUIRED
    cand_high = create_synthetic_candidate(
        ev_status="INSUFFICIENT",
        provenance={"identified_risk_severity": "HIGH"}
    )
    dec_high = policy.evaluate_candidate(cand_high)
    assert dec_high.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_high.primary_reason_code == EvidencePolicyReasonCode.HIGH_SEVERITY_INSUFFICIENT_EVIDENCE
    assert dec_high.precedence_tier_applied == 3

    # Case 2: Low/Medium severity -> WITHHOLD
    cand_low = create_synthetic_candidate(
        ev_status="INSUFFICIENT",
        provenance={"identified_risk_severity": "LOW"}
    )
    dec_low = policy.evaluate_candidate(cand_low)
    assert dec_low.policy_action == PolicyAction.WITHHOLD
    assert dec_low.primary_reason_code == EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE
    assert dec_low.precedence_tier_applied == 4


# =========================================================================
# TEST F: Non-statutory commercial risk not rejected solely due to absent statutory passage
# =========================================================================
def test_f_non_statutory_commercial_risk_accepted_without_statute():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(
        category="PRICE_ADJUSTMENT",
        ev_status="NO_MATCHING_EVIDENCE",
        passages=[],
        confidence=0.88,
    )

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.ACCEPT
    assert decision.primary_reason_code == EvidencePolicyReasonCode.VALID_NON_STATUTORY_COMMERCIAL_FINDING
    assert decision.precedence_tier_applied == 5


# =========================================================================
# TEST G: High-severity case requiring review routed when explicitly supplied
# =========================================================================
def test_g_high_severity_missing_statutory_match_routed():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(
        category="INDEMNIFICATION",
        ev_status="NO_MATCHING_EVIDENCE",
        passages=[],
    )

    decision = policy.evaluate_candidate(cand, explicit_severity="HIGH")
    assert decision.policy_action == PolicyAction.REVIEW_REQUIRED
    assert decision.primary_reason_code == EvidencePolicyReasonCode.HIGH_SEVERITY_MISSING_STATUTORY_MATCH
    assert decision.precedence_tier_applied == 3


# =========================================================================
# TEST H: Missing required input fails safely in Tier 1
# =========================================================================
def test_h_missing_required_input_fails_safely():
    policy = EvidenceAwarePolicy()

    # Empty clause text
    cand_empty_text = create_synthetic_candidate(clause_text="   ")
    dec_text = policy.evaluate_candidate(cand_empty_text)
    assert dec_text.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_text.primary_reason_code == EvidencePolicyReasonCode.EMPTY_CLAUSE_TEXT
    assert dec_text.precedence_tier_applied == 1

    # Missing required candidate identifier
    cand_missing_id = create_synthetic_candidate(cid="")
    dec_id = policy.evaluate_candidate(cand_missing_id)
    assert dec_id.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_id.primary_reason_code == EvidencePolicyReasonCode.MISSING_REQUIRED_IDENTIFIER
    assert dec_id.precedence_tier_applied == 1


# =========================================================================
# TEST I: Uncalibrated confidence remains explicitly uncalibrated
# =========================================================================
def test_i_uncalibrated_confidence_preserved():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(confidence=0.92)

    decision = policy.evaluate_candidate(cand)
    assert decision.confidence_is_calibrated is False
    assert decision.confidence_semantics == ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE
    assert "UNCALIBRATED_RAW_SCORE" in decision.missing_capabilities


# =========================================================================
# TEST J: Documented confidence threshold (0.5) enforced
# =========================================================================
def test_j_configured_confidence_threshold_enforced():
    policy = EvidenceAwarePolicy()
    assert policy.config.confidence_threshold == 0.5

    # Exactly at 0.5 -> Accepted
    cand_border = create_synthetic_candidate(confidence=0.50)
    dec_border = policy.evaluate_candidate(cand_border)
    assert dec_border.policy_action == PolicyAction.ACCEPT

    # 0.499 -> Withheld
    cand_below = create_synthetic_candidate(confidence=0.499)
    dec_below = policy.evaluate_candidate(cand_below)
    assert dec_below.policy_action == PolicyAction.WITHHOLD
    assert dec_below.primary_reason_code == EvidencePolicyReasonCode.BELOW_CONFIDENCE_THRESHOLD


# =========================================================================
# TEST K: Primary reason code strictly respects five-tier precedence
# =========================================================================
def test_k_five_tier_precedence_conflict_resolution():
    policy = EvidenceAwarePolicy()

    # Conflict 1: Stale version (Tier 2) + High severity nuance (Tier 3)
    # Tier 2 MUST PREVAIL over Tier 3
    cand_stale_high = create_synthetic_candidate(
        version_status=VersionConsistencyStatus.STALE,
        ev_status="INSUFFICIENT",
        provenance={"identified_risk_severity": "HIGH"}
    )
    dec_k1 = policy.evaluate_candidate(cand_stale_high)
    assert dec_k1.policy_action == PolicyAction.WITHHOLD
    assert dec_k1.precedence_tier_applied == 2
    assert dec_k1.primary_reason_code == EvidencePolicyReasonCode.STALE_DOCUMENT_VERSION

    # Conflict 2: High severity nuance (Tier 3) + Low confidence (Tier 4)
    # Tier 3 MUST PREVAIL over Tier 4
    cand_high_low_conf = create_synthetic_candidate(
        confidence=0.30, # Tier 4
        ev_status="INSUFFICIENT", # Tier 3 when high severity
        provenance={"identified_risk_severity": "HIGH"}
    )
    dec_k2 = policy.evaluate_candidate(cand_high_low_conf)
    assert dec_k2.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_k2.precedence_tier_applied == 3
    assert dec_k2.primary_reason_code == EvidencePolicyReasonCode.HIGH_SEVERITY_INSUFFICIENT_EVIDENCE


# =========================================================================
# TEST L: Additional applicable reason codes are retained
# =========================================================================
def test_l_additional_applicable_reason_codes_retained():
    policy = EvidenceAwarePolicy()
    # Candidate has multiple Tier 2 issues: Stale version AND Repealed statute
    passages_repealed = [
        {
            "statute_id": "IN_ACT_1872_09",
            "section_number": "76",
            "legal_status": "REPEALED",
            "currentness_status": "REPEALED",
        }
    ]
    cand = create_synthetic_candidate(
        version_status=VersionConsistencyStatus.STALE,
        passages=passages_repealed,
    )

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.WITHHOLD
    assert decision.precedence_tier_applied == 2
    assert decision.primary_reason_code == EvidencePolicyReasonCode.MULTIPLE_FATAL_FAILURES
    assert EvidencePolicyReasonCode.STALE_DOCUMENT_VERSION in decision.all_applicable_reason_codes
    assert EvidencePolicyReasonCode.INAPPLICABLE_OR_SUPERSEDED_STATUTE in decision.all_applicable_reason_codes


# =========================================================================
# TEST M: Repeated evaluation produces identical results (determinism)
# =========================================================================
def test_m_deterministic_repeatable_evaluation():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate()

    dec1 = policy.evaluate_candidate(cand)
    dec2 = policy.evaluate_candidate(cand)

    assert dec1.policy_action == dec2.policy_action
    assert dec1.primary_reason_code == dec2.primary_reason_code
    assert dec1.all_applicable_reason_codes == dec2.all_applicable_reason_codes
    assert dec1.precedence_tier_applied == dec2.precedence_tier_applied


# =========================================================================
# TEST N: Original candidate object remains unchanged (immutability)
# =========================================================================
def test_n_candidate_immutability():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate()
    original_dict = cand.model_dump()

    _ = policy.evaluate_candidate(cand)
    after_dict = cand.model_dump()

    assert original_dict == after_dict


# =========================================================================
# TEST O: Policy output never enables client disclosure
# =========================================================================
def test_o_client_disclosure_isolation():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate()

    decision = policy.evaluate_candidate(cand)
    assert decision.is_disclosed_to_client is False

    eval_record = decision.to_evaluation_record()
    assert eval_record.decision_metadata.get("is_disclosed_to_client") is False


# =========================================================================
# TEST P: Missing prediction correctness label not treated as correct or incorrect
# =========================================================================
def test_p_missing_reference_label_unbiased():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate()

    # When reference_label is None (operational mode)
    dec = policy.evaluate_candidate(cand, reference_label=None)
    assert dec.policy_action == PolicyAction.ACCEPT
    assert EvidencePolicyReasonCode.INCORRECT_PREDICTION not in dec.all_applicable_reason_codes


# =========================================================================
# TEST Q: Unsupported label mappings do not become accepted Indian legal categories
# =========================================================================
def test_q_unsupported_label_mapping_routes_to_review():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(
        category="UNMAPPED_us_sec_item_402",
        mapping_status=LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING,
    )

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.REVIEW_REQUIRED
    assert decision.primary_reason_code == EvidencePolicyReasonCode.UNSUPPORTED_LABEL_MAPPING
    assert decision.precedence_tier_applied == 3


# =========================================================================
# TEST R: Unrecognized evidence statuses fail safely in Tier 1
# =========================================================================
def test_r_unrecognized_evidence_status_fails_safely():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate(ev_status="CORRUPTED_CUSTOM_STATUS_123")

    decision = policy.evaluate_candidate(cand)
    assert decision.policy_action == PolicyAction.REVIEW_REQUIRED
    assert decision.primary_reason_code == EvidencePolicyReasonCode.UNRECOGNIZED_EVIDENCE_STATUS
    assert decision.precedence_tier_applied == 1


# =========================================================================
# TEST S: Batch operations and evaluation harness compatibility
# =========================================================================
def test_s_batch_evaluation_and_harness_dict_conversion():
    policy = EvidenceAwarePolicy()
    cand1 = create_synthetic_candidate(cid="cand-01")
    cand2 = create_synthetic_candidate(cid="cand-02", version_status=VersionConsistencyStatus.STALE)

    decisions = policy.evaluate_candidates([cand1, cand2])
    assert len(decisions) == 2

    dec_dict = policy.to_policy_decisions_dict(decisions)
    assert dec_dict["cand-01"] == PolicyAction.ACCEPT
    assert dec_dict["cand-02"] == PolicyAction.WITHHOLD


# =========================================================================
# TEST T: Every action has a documented reason code
# =========================================================================
def test_t_every_action_has_documented_reason_code():
    policy = EvidenceAwarePolicy()
    cand = create_synthetic_candidate()

    decision = policy.evaluate_candidate(cand)
    assert isinstance(decision.primary_reason_code, EvidencePolicyReasonCode)
    assert decision.primary_reason_code.value in [r.value for r in EvidencePolicyReasonCode]
    assert len(decision.all_applicable_reason_codes) >= 1
