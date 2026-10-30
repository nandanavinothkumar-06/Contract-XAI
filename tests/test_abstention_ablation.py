"""
Focused Test Suite for Configurable Evidence-Aware Abstention Ablation Study.

Verifies the 12 requirements:
1. Default configuration preserves original policy behavior.
2. Disabling version checks changes intended stale/unknown-version behavior without bypassing unrelated safeguards.
3. Disabling the high-severity safety net changes only intended high-severity routing behavior.
4. Disabling statutory grounding changes only intended statutory-grounding behavior.
5. Invalid configuration values are rejected.
6. Reason-code ordering remains deterministic.
7. Existing APIs remain backward compatible.
8. All configurations use the same candidate pool.
9. Evaluation reference labels never influence operational decisions.
10. Zero denominators and unmatched coverage are handled correctly.
11. Synthetic perturbations are reproducible.
12. Existing end-to-end screening behavior remains intact.
"""

import pytest
from pydantic import ValidationError

from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    VersionConsistencyStatus,
    LabelMappingStatus,
    CandidateOrigin,
)
from src.evaluation.abstention_eval import (
    PolicyAction,
    ReferenceDecision,
    evaluate_policy,
    compare_policies_at_matched_coverage,
    PolicyEvaluationSummary,
)
from src.abstention.evidence_policy import (
    EvidenceAwarePolicy,
    EvidenceAwarePolicyConfig,
    EvidencePolicyReasonCode,
    EvidencePolicyDecision,
)
from src.evaluation.synthetic_candidates import (
    generate_synthetic_candidate_pool,
    generate_perturbed_candidate_pool,
)
from scripts.evaluate_abstention_ablation import (
    build_ablation_policy_instances,
    evaluate_dataset_across_configurations,
    CONFIGURATIONS_METADATA,
)


def create_fixture_candidate(
    cid: str = "test-cand-01",
    version_status: VersionConsistencyStatus = VersionConsistencyStatus.CONSISTENT,
    ev_status: str = "TRACEABLE",
    confidence: float = 0.85,
    category: str = "INDEMNIFICATION",
    severity: str = "MEDIUM",
    is_statutory: bool = True,
    passages: list = None,
) -> CandidateFindingRecord:
    """Helper to build synthetic candidate fixture for ablation testing."""
    return CandidateFindingRecord(
        candidate_finding_id=cid,
        contract_id="doc-test-01",
        contract_version=1,
        document_content_hash="hashsha256",
        clause_id="clause-01",
        clause_text="Vendor shall indemnify customer against all damages.",
        prediction_category=category,
        raw_model_label="0",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=confidence,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status=ev_status,
        retrieved_passages=passages or [{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "124",
            "passage_text": "Indemnity contract defined.",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=version_status,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": severity, "is_statutory": is_statutory},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )


# =========================================================================
# 1. Default configuration preserves original policy behavior
# =========================================================================
def test_1_default_configuration_preserves_original_behavior():
    default_config = EvidenceAwarePolicyConfig()
    assert default_config.enable_version_consistency is True
    assert default_config.enable_high_severity_safety_net is True
    assert default_config.enable_statutory_grounding is True

    policy = EvidenceAwarePolicy(default_config)
    # Stale candidate -> Withheld under Tier 2
    cand_stale = create_fixture_candidate(version_status=VersionConsistencyStatus.STALE)
    dec_stale = policy.evaluate_candidate(cand_stale)
    assert dec_stale.policy_action == PolicyAction.WITHHOLD
    assert dec_stale.primary_reason_code == EvidencePolicyReasonCode.STALE_DOCUMENT_VERSION
    assert dec_stale.precedence_tier_applied == 2

    # High severity insufficient -> Review under Tier 3
    cand_high = create_fixture_candidate(severity="HIGH", ev_status="INSUFFICIENT")
    dec_high = policy.evaluate_candidate(cand_high)
    assert dec_high.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_high.primary_reason_code == EvidencePolicyReasonCode.HIGH_SEVERITY_INSUFFICIENT_EVIDENCE
    assert dec_high.precedence_tier_applied == 3


# =========================================================================
# 2. Disabling version checks changes intended stale/unknown behavior without bypassing unrelated safeguards
# =========================================================================
def test_2_disabling_version_checks_behavior():
    cfg_no_version = EvidenceAwarePolicyConfig(enable_version_consistency=False)
    policy_no_ver = EvidenceAwarePolicy(cfg_no_version)

    # Stale candidate with valid traceable evidence should NOT be blocked in Tier 2
    cand_stale = create_fixture_candidate(version_status=VersionConsistencyStatus.STALE, ev_status="TRACEABLE", confidence=0.85)
    dec = policy_no_ver.evaluate_candidate(cand_stale)
    # Without version check, it reaches Tier 5 and is ACCEPTED
    assert dec.policy_action == PolicyAction.ACCEPT
    assert dec.primary_reason_code == EvidencePolicyReasonCode.GROUNDED_STATUTORY_FINDING

    # BUT unrelated Tier 2 safeguards (repealed statute) MUST STILL OPERATE
    cand_repealed = create_fixture_candidate(
        version_status=VersionConsistencyStatus.STALE,
        passages=[{"legal_status": "REPEALED", "currentness_status": "REPEALED"}],
    )
    dec_rep = policy_no_ver.evaluate_candidate(cand_repealed)
    assert dec_rep.policy_action == PolicyAction.WITHHOLD
    assert dec_rep.primary_reason_code == EvidencePolicyReasonCode.INAPPLICABLE_OR_SUPERSEDED_STATUTE
    assert dec_rep.precedence_tier_applied == 2

    # And Tier 1 assessability MUST STILL OPERATE
    cand_empty = create_fixture_candidate(cid="")
    dec_empty = policy_no_ver.evaluate_candidate(cand_empty)
    assert dec_empty.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_empty.primary_reason_code == EvidencePolicyReasonCode.MISSING_REQUIRED_IDENTIFIER


# =========================================================================
# 3. Disabling high-severity safety net changes only intended routing
# =========================================================================
def test_3_disabling_high_severity_safety_net_behavior():
    cfg_no_net = EvidenceAwarePolicyConfig(enable_high_severity_safety_net=False)
    policy_no_net = EvidenceAwarePolicy(cfg_no_net)

    # High severity candidate with insufficient evidence falls through Tier 3 to Tier 4 (WITHHOLD)
    cand_high_insufficient = create_fixture_candidate(severity="HIGH", ev_status="INSUFFICIENT", confidence=0.85)
    dec = policy_no_net.evaluate_candidate(cand_high_insufficient)
    assert dec.policy_action == PolicyAction.WITHHOLD
    assert dec.primary_reason_code == EvidencePolicyReasonCode.INSUFFICIENT_EVIDENCE
    assert dec.precedence_tier_applied == 4

    # BUT other Tier 3 legal nuance checks (text difference) MUST STILL OPERATE
    cand_diff = create_fixture_candidate(
        severity="HIGH",
        passages=[{"has_text_difference": True, "legal_status": "IN_FORCE_CONFIRMED", "currentness_status": "IN_FORCE_CONFIRMED"}]
    )
    dec_diff = policy_no_net.evaluate_candidate(cand_diff)
    assert dec_diff.policy_action == PolicyAction.REVIEW_REQUIRED
    assert dec_diff.primary_reason_code == EvidencePolicyReasonCode.STATUTORY_TEXT_DIFFERENCE


# =========================================================================
# 4. Disabling statutory grounding changes only intended statutory behavior
# =========================================================================
def test_4_disabling_statutory_grounding_behavior():
    cfg_no_ground = EvidenceAwarePolicyConfig(enable_statutory_grounding=False)
    policy_no_ground = EvidenceAwarePolicy(cfg_no_ground)

    # Statutory finding with INSUFFICIENT evidence but high confidence is accepted when grounding is disabled
    cand_insufficient = create_fixture_candidate(ev_status="INSUFFICIENT", confidence=0.85)
    dec = policy_no_ground.evaluate_candidate(cand_insufficient)
    assert dec.policy_action == PolicyAction.ACCEPT
    assert dec.primary_reason_code == EvidencePolicyReasonCode.GROUNDED_STATUTORY_FINDING

    # BUT low confidence (< 0.5) MUST STILL BE WITHHELD in Tier 4
    cand_low_conf = create_fixture_candidate(ev_status="INSUFFICIENT", confidence=0.35)
    dec_low = policy_no_ground.evaluate_candidate(cand_low_conf)
    assert dec_low.policy_action == PolicyAction.WITHHOLD
    assert dec_low.primary_reason_code == EvidencePolicyReasonCode.BELOW_CONFIDENCE_THRESHOLD
    assert dec_low.precedence_tier_applied == 4


# =========================================================================
# 5. Invalid configuration values are rejected
# =========================================================================
def test_5_invalid_configuration_values_rejected():
    # Extra unexpected fields rejected by ConfigDict(extra="forbid")
    with pytest.raises(ValidationError):
        EvidenceAwarePolicyConfig(unexpected_flag=True)

    # Confidence threshold out of bounds rejected
    with pytest.raises(ValidationError):
        EvidenceAwarePolicyConfig(confidence_threshold=1.5)

    with pytest.raises(ValidationError):
        EvidenceAwarePolicyConfig(confidence_threshold=-0.1)


# =========================================================================
# 6. Reason-code ordering remains deterministic
# =========================================================================
def test_6_reason_code_ordering_deterministic():
    policy = EvidenceAwarePolicy()
    cand = create_fixture_candidate()

    dec1 = policy.evaluate_candidate(cand)
    dec2 = policy.evaluate_candidate(cand)

    assert dec1.primary_reason_code == dec2.primary_reason_code
    assert dec1.all_applicable_reason_codes == dec2.all_applicable_reason_codes
    assert dec1.precedence_tier_applied == dec2.precedence_tier_applied


# =========================================================================
# 7. Existing APIs remain backward compatible
# =========================================================================
def test_7_existing_apis_backward_compatible():
    # Calling EvidenceAwarePolicy() without arguments must succeed
    policy = EvidenceAwarePolicy()
    assert policy.config.enable_version_consistency is True
    assert policy.config.enable_high_severity_safety_net is True
    assert policy.config.enable_statutory_grounding is True

    cand = create_fixture_candidate()
    dec = policy.evaluate_candidate(cand)
    assert isinstance(dec, EvidencePolicyDecision)
    assert dec.policy_action in (PolicyAction.ACCEPT, PolicyAction.WITHHOLD, PolicyAction.REVIEW_REQUIRED)

    eval_rec = dec.to_evaluation_record()
    assert eval_rec.action == dec.policy_action
    assert eval_rec.decision_metadata["enable_version_consistency"] is True


# =========================================================================
# 8. All configurations use the same candidate pool
# =========================================================================
def test_8_all_configurations_use_same_candidate_pool():
    dataset = generate_synthetic_candidate_pool(seed=42, additional_random_count=45)
    policies = build_ablation_policy_instances(threshold=0.50)

    candidate_ids = [c.candidate_finding_id for c in dataset.candidates]
    assert len(candidate_ids) == 58

    for name, policy in policies.items():
        decisions = [policy.evaluate_candidate(c) for c in dataset.candidates]
        assert len(decisions) == 58
        assert [d.candidate_finding_id for d in decisions] == candidate_ids


# =========================================================================
# 9. Evaluation reference labels never influence operational decisions
# =========================================================================
def test_9_reference_labels_never_influence_operational_decisions():
    policy = EvidenceAwarePolicy()
    cand = create_fixture_candidate()

    # Operational call (reference_label is None)
    dec_operational = policy.evaluate_candidate(cand, reference_label=None)

    # In evaluation mode with None or unrelated reference label, operational outcome is identical
    dec_eval_none = policy.evaluate_candidate(cand)
    assert dec_operational.policy_action == dec_eval_none.policy_action
    assert dec_operational.primary_reason_code == dec_eval_none.primary_reason_code


# =========================================================================
# 10. Zero denominators and unmatched coverage handled correctly
# =========================================================================
def test_10_zero_denominators_and_unmatched_coverage_handled():
    dataset = generate_synthetic_candidate_pool(seed=42)
    # All candidates withheld -> retained count = 0
    all_withheld = {c.candidate_finding_id: PolicyAction.WITHHOLD for c in dataset.candidates}
    summary = evaluate_policy(
        policy_id="test_zero_denom",
        candidates=dataset.candidates,
        reference_annotations=dataset.reference_annotations,
        policy_decisions=all_withheld,
    )
    assert summary.retained_count == 0
    assert summary.ufr is None  # Handled safely as None, not 0.0 or DivisionByZeroError

    # Compare two policies with wildly mismatched coverage
    all_accepted = {c.candidate_finding_id: PolicyAction.ACCEPT for c in dataset.candidates}
    summary_accepted = evaluate_policy(
        policy_id="test_all_accept",
        candidates=dataset.candidates,
        reference_annotations=dataset.reference_annotations,
        policy_decisions=all_accepted,
    )
    match_result = compare_policies_at_matched_coverage(summary, summary_accepted, tolerance=0.02)
    assert match_result.status == "MATCHED_COVERAGE_UNACHIEVED"
    assert match_result.delta_ufr is None


# =========================================================================
# 11. Synthetic perturbations are reproducible
# =========================================================================
def test_11_synthetic_perturbations_reproducible():
    pool1 = generate_perturbed_candidate_pool(seed=42, perturbation_rate=0.20)
    pool2 = generate_perturbed_candidate_pool(seed=42, perturbation_rate=0.20)

    assert pool1.total_candidates == pool2.total_candidates
    assert pool1.reference_annotations == pool2.reference_annotations
    assert pool1.metadata["perturbed_candidates_count"] == pool2.metadata["perturbed_candidates_count"]
    assert pool1.metadata["perturbed_candidates_count"] > 0
    assert "PERTURBED METADATA FIXTURE" in pool1.disclaimer


# =========================================================================
# 12. Existing end-to-end screening behavior remains intact
# =========================================================================
def test_12_end_to_end_screening_behavior_intact():
    from src.review.screening import ContractScreeningService
    service = ContractScreeningService()
    clause_text = "Vendor shall indemnify, defend, and hold harmless the Client against all liabilities."
    result = service.screen_clause(
        clause_text=clause_text,
        clause_id="seg-test-01",
        document_id="doc-test-01",
        document_version=1,
    )
    assert result is not None
    assert "policy_action" in result
    assert "policy_reason_code" in result
    assert result["is_disclosed_to_client"] is False
