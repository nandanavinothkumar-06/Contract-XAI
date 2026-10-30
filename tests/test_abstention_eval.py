"""
Synthetic Unit Tests for Abstention Evaluation Metric Harness.

Tests verify:
1. Input validation: Duplicate candidate IDs, missing labels, empty sets.
2. Unsupported Finding Rate (UFR): WITHHOLD fraction among evaluable retained findings.
3. Zero retained candidates: UFR must return None (UNDEFINED), NEVER 0.0.
4. Safety Discrepancies: HUMAN_REVIEW_REQUIRED reference candidates retained by policy are reported separately.
5. Useful-Finding Coverage (UFC): REVIEW_REQUIRED candidates do NOT count as automatically retained.
6. Retention Rate (RR), Human-Review Workload (HRW), and Unassessable Rate (UR).
7. Unnecessary Abstention Rate (UAR) breakdown: withheld vs human review.
8. Stale-Evidence Acceptance Rate (SEAR): Stale vs Unknown vs Consistent document versions.
9. Coverage Matching Diagnostics: Matched (|UFC_A - UFC_B| <= 0.02) vs Unmatched (|UFC_A - UFC_B| > 0.02).
10. Deterministic tie breaking: SortKey = (-confidence, candidate_id) independent of outcomes.

NOTE: All tests use synthetic test vectors and fixtures. They do NOT evaluate real-world models.
"""

import pytest
from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    CandidateOrigin,
    VersionConsistencyStatus,
)
from src.evaluation.abstention_eval import (
    ReferenceDecision,
    PolicyAction,
    evaluate_policy,
    compare_policies_at_matched_coverage,
    sort_candidates_by_confidence,
    validate_evaluation_inputs,
    preflight_partition_check,
)


def create_synthetic_candidate(
    cid: str,
    contract_id: str = "doc-001",
    version: int = 1,
    conf: float = 0.80,
    version_status: VersionConsistencyStatus = VersionConsistencyStatus.CONSISTENT,
) -> CandidateFindingRecord:
    """Helper creating synthetic candidate record for testing."""
    return CandidateFindingRecord(
        candidate_finding_id=cid,
        contract_id=contract_id,
        contract_version=version,
        document_content_hash="sha256hash",
        clause_id=f"clause-{cid}",
        clause_text=f"Clause text for {cid}",
        prediction_category="INDEMNIFICATION",
        raw_model_label="0",
        model_id="mock-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=conf,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        version_consistency_status=version_status,
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
    )


def test_input_validation_detects_duplicates_and_missing_labels():
    """Verify input validation catches duplicates, missing reference annotations, and missing policy actions."""
    c1 = create_synthetic_candidate("c-01")
    c1_dup = create_synthetic_candidate("c-01") # Duplicate ID

    # 1. Empty dataset
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_evaluation_inputs([], {}, {})

    # 2. Duplicate candidate ID
    with pytest.raises(ValueError, match="Duplicate candidate_finding_id"):
        validate_evaluation_inputs([c1, c1_dup], {"c-01": ReferenceDecision.RETAIN}, {"c-01": PolicyAction.ACCEPT})

    # 3. Missing reference annotation
    with pytest.raises(ValueError, match="Missing reference annotations"):
        validate_evaluation_inputs([c1], {}, {"c-01": PolicyAction.ACCEPT})

    # 4. Missing policy decision
    with pytest.raises(ValueError, match="Missing policy decisions"):
        validate_evaluation_inputs([c1], {"c-01": ReferenceDecision.RETAIN}, {})


def test_ufr_with_zero_retained_candidates_returns_none_never_zero():
    """
    CRITICAL INVARIANT:
    When zero candidates are retained by a policy, UFR is mathematically UNDEFINED.
    It must return None, NEVER 0.0 (which would falsely imply zero errors).
    """
    c1 = create_synthetic_candidate("c-01", conf=0.40)
    c2 = create_synthetic_candidate("c-02", conf=0.30)
    candidates = [c1, c2]

    # Policy withholds all candidates
    policy_decisions = {
        "c-01": PolicyAction.WITHHOLD,
        "c-02": PolicyAction.WITHHOLD,
    }
    reference_annotations = {
        "c-01": ReferenceDecision.RETAIN,
        "c-02": ReferenceDecision.WITHHOLD,
    }

    summary = evaluate_policy("policy-strict", candidates, reference_annotations, policy_decisions)
    assert summary.retained_count == 0
    assert summary.evaluable_retained_count == 0
    assert summary.ufr is None # MUST BE NONE (UNDEFINED), NOT 0.0
    assert summary.retention_rate == 0.0


def test_ufr_and_ufc_with_mixed_reference_decisions():
    """Verify correct computation of UFR, UFC, and separate reporting of safety discrepancies."""
    # 4 candidates:
    # c1: Ground truth RETAIN -> Policy ACCEPT (Correct retention)
    # c2: Ground truth WITHHOLD -> Policy ACCEPT (Unsupported finding)
    # c3: Ground truth HUMAN_REVIEW_REQUIRED -> Policy ACCEPT (Safety discrepancy!)
    # c4: Ground truth RETAIN -> Policy WITHHOLD (Unnecessary abstention)
    c1 = create_synthetic_candidate("c-01", conf=0.90)
    c2 = create_synthetic_candidate("c-02", conf=0.85)
    c3 = create_synthetic_candidate("c-03", conf=0.80)
    c4 = create_synthetic_candidate("c-04", conf=0.60)
    candidates = [c1, c2, c3, c4]

    policy_decisions = {
        "c-01": PolicyAction.ACCEPT,
        "c-02": PolicyAction.ACCEPT,
        "c-03": PolicyAction.ACCEPT,
        "c-04": PolicyAction.WITHHOLD,
    }
    reference_annotations = {
        "c-01": ReferenceDecision.RETAIN,
        "c-02": ReferenceDecision.WITHHOLD,
        "c-03": ReferenceDecision.HUMAN_REVIEW_REQUIRED,
        "c-04": ReferenceDecision.RETAIN,
    }

    summary = evaluate_policy("policy-test", candidates, reference_annotations, policy_decisions)

    # Evaluable retained count: c1, c2, c3 = 3
    assert summary.evaluable_retained_count == 3
    assert summary.unsupported_finding_count == 1 # Only c2 is WITHHOLD
    # UFR = 1 / 3 = 0.3333...
    assert pytest.approx(summary.ufr, 0.001) == 1.0 / 3.0

    # Safety discrepancy: c3 is HUMAN_REVIEW_REQUIRED retained automatically
    assert summary.human_review_discrepancy_count == 1
    assert pytest.approx(summary.human_review_discrepancy_rate, 0.001) == 1.0 / 3.0

    # Useful Finding Coverage (UFC):
    # Total reference retainable: c1, c4 = 2
    # Retained useful: c1 = 1
    # UFC = 1 / 2 = 0.50
    assert summary.total_reference_retainable == 2
    assert summary.retained_useful_count == 1
    assert summary.ufc == 0.50

    # Unnecessary Abstention Rate (UAR):
    # c4 was reference RETAIN but withheld: 1 out of 4 evaluable candidates
    assert summary.uar_withheld_count == 1
    assert summary.uar_withheld_rate == 0.25


def test_ufc_does_not_count_review_required_as_automatically_retained():
    """
    CRITICAL INVARIANT:
    Candidates routed to REVIEW_REQUIRED must NOT be counted as automatically retained
    in Useful-Finding Coverage (UFC). They represent human workload, not AI retention.
    """
    c1 = create_synthetic_candidate("c-01")
    c2 = create_synthetic_candidate("c-02")
    candidates = [c1, c2]

    # Both are genuinely retainable risks:
    reference_annotations = {
        "c-01": ReferenceDecision.RETAIN,
        "c-02": ReferenceDecision.RETAIN,
    }
    # Policy routes c1 to review, withholds c2
    policy_decisions = {
        "c-01": PolicyAction.REVIEW_REQUIRED,
        "c-02": PolicyAction.WITHHOLD,
    }

    summary = evaluate_policy("policy-human-loop", candidates, reference_annotations, policy_decisions)
    assert summary.retained_count == 0
    assert summary.retained_useful_count == 0
    assert summary.ufc == 0.0 # NOT 0.50! Routed to review does not count as automated retention
    assert summary.routed_to_review_count == 1
    assert summary.hrw_rate == 0.50
    assert summary.uar_human_review_count == 1
    assert summary.uar_human_review_rate == 0.50


def test_not_assessable_candidates_excluded_from_ufr_and_ufc():
    """Verify NOT_ASSESSABLE cases are excluded from evaluable denominators but tracked in UR."""
    c1 = create_synthetic_candidate("c-01") # Corrupt text
    c2 = create_synthetic_candidate("c-02") # Normal text
    candidates = [c1, c2]

    reference_annotations = {
        "c-01": ReferenceDecision.NOT_ASSESSABLE,
        "c-02": ReferenceDecision.RETAIN,
    }
    policy_decisions = {
        "c-01": PolicyAction.ACCEPT,
        "c-02": PolicyAction.ACCEPT,
    }

    summary = evaluate_policy("policy-unassessable", candidates, reference_annotations, policy_decisions)
    assert summary.total_candidates == 2
    assert summary.unassessable_candidates == 1
    assert summary.evaluable_candidates == 1
    assert summary.unassessable_rate == 0.50

    # c1 is excluded from evaluable retained denominator
    assert summary.evaluable_retained_count == 1
    assert summary.unsupported_finding_count == 0
    assert summary.ufr == 0.0
    assert summary.ufc == 1.0


def test_sear_tracks_stale_and_unknown_contract_versions():
    """Verify SEAR distinguishes explicitly STALE versions from UNKNOWN and CONSISTENT versions."""
    c1 = create_synthetic_candidate("c-01", version_status=VersionConsistencyStatus.CONSISTENT)
    c2 = create_synthetic_candidate("c-02", version_status=VersionConsistencyStatus.STALE)
    c3 = create_synthetic_candidate("c-03", version_status=VersionConsistencyStatus.UNKNOWN)
    candidates = [c1, c2, c3]

    policy_decisions = {
        "c-01": PolicyAction.ACCEPT,
        "c-02": PolicyAction.ACCEPT,
        "c-03": PolicyAction.ACCEPT,
    }
    reference_annotations = {
        "c-01": ReferenceDecision.RETAIN,
        "c-02": ReferenceDecision.RETAIN,
        "c-03": ReferenceDecision.RETAIN,
    }

    summary = evaluate_policy("policy-stale", candidates, reference_annotations, policy_decisions)
    assert summary.retained_count == 3
    assert summary.sear_stale_count == 1
    assert pytest.approx(summary.sear_stale_rate, 0.001) == 1.0 / 3.0
    assert summary.sear_unknown_count == 1
    assert pytest.approx(summary.sear_unknown_rate, 0.001) == 1.0 / 3.0


def test_coverage_matching_protocol_within_and_outside_tolerance():
    """Verify coverage matching requires |UFC_A - UFC_B| <= 0.02 and rejects outside tolerance."""
    # Policy A: UFC = 0.80, UFR = 0.25
    # Policy B1: UFC = 0.81, UFR = 0.15 (Difference = 0.01 <= 0.02 -> MATCHED)
    # Policy B2: UFC = 0.75, UFR = 0.10 (Difference = 0.05 > 0.02 -> UNMATCHED)
    eval_a = evaluate_policy(
        "policy-a",
        [create_synthetic_candidate("c-01"), create_synthetic_candidate("c-02"), create_synthetic_candidate("c-03"), create_synthetic_candidate("c-04"), create_synthetic_candidate("c-05")],
        {"c-01": ReferenceDecision.RETAIN, "c-02": ReferenceDecision.RETAIN, "c-03": ReferenceDecision.RETAIN, "c-04": ReferenceDecision.RETAIN, "c-05": ReferenceDecision.WITHHOLD},
        {"c-01": PolicyAction.ACCEPT, "c-02": PolicyAction.ACCEPT, "c-03": PolicyAction.ACCEPT, "c-04": PolicyAction.ACCEPT, "c-05": PolicyAction.ACCEPT}, # UFC = 4/4 = 1.0, UFR = 1/5 = 0.20
    )
    # Policy B1: Identical coverage 1.0, UFR = 0.0 (no unsupported retained)
    eval_b1 = evaluate_policy(
        "policy-b1",
        [create_synthetic_candidate("c-01"), create_synthetic_candidate("c-02"), create_synthetic_candidate("c-03"), create_synthetic_candidate("c-04"), create_synthetic_candidate("c-05")],
        {"c-01": ReferenceDecision.RETAIN, "c-02": ReferenceDecision.RETAIN, "c-03": ReferenceDecision.RETAIN, "c-04": ReferenceDecision.RETAIN, "c-05": ReferenceDecision.WITHHOLD},
        {"c-01": PolicyAction.ACCEPT, "c-02": PolicyAction.ACCEPT, "c-03": PolicyAction.ACCEPT, "c-04": PolicyAction.ACCEPT, "c-05": PolicyAction.WITHHOLD}, # UFC = 4/4 = 1.0, UFR = 0/4 = 0.0
    )
    # Policy B2: Different coverage: retains only 2 out of 4 (UFC = 2/4 = 0.50)
    eval_b2 = evaluate_policy(
        "policy-b2",
        [create_synthetic_candidate("c-01"), create_synthetic_candidate("c-02"), create_synthetic_candidate("c-03"), create_synthetic_candidate("c-04"), create_synthetic_candidate("c-05")],
        {"c-01": ReferenceDecision.RETAIN, "c-02": ReferenceDecision.RETAIN, "c-03": ReferenceDecision.RETAIN, "c-04": ReferenceDecision.RETAIN, "c-05": ReferenceDecision.WITHHOLD},
        {"c-01": PolicyAction.ACCEPT, "c-02": PolicyAction.ACCEPT, "c-03": PolicyAction.WITHHOLD, "c-04": PolicyAction.WITHHOLD, "c-05": PolicyAction.WITHHOLD}, # UFC = 2/4 = 0.50
    )

    # Comparison 1: Within tolerance (0.0 <= 0.02)
    match_result = compare_policies_at_matched_coverage(eval_a, eval_b1, tolerance=0.02)
    assert match_result.status == "MATCHED_COVERAGE_ACHIEVED"
    assert match_result.coverage_difference == 0.0
    assert match_result.delta_ufr == 0.20 # UFR(A) - UFR(B) = 0.20 - 0.0 = 0.20

    # Comparison 2: Outside tolerance (0.50 > 0.02)
    unmatch_result = compare_policies_at_matched_coverage(eval_a, eval_b2, tolerance=0.02)
    assert unmatch_result.status == "MATCHED_COVERAGE_UNACHIEVED"
    assert unmatch_result.coverage_difference == 0.50
    assert unmatch_result.delta_ufr is None


def test_deterministic_confidence_tie_breaking():
    """Verify tie-breaking on confidence score is deterministic and independent of reference outcomes."""
    c1 = create_synthetic_candidate("cand-b", conf=0.75)
    c2 = create_synthetic_candidate("cand-a", conf=0.75) # Same confidence, alphabetically earlier ID
    c3 = create_synthetic_candidate("cand-c", conf=0.90) # Higher confidence

    # Sort should place c3 first (0.90), then c2 ("cand-a", 0.75), then c1 ("cand-b", 0.75)
    sorted_cands = sort_candidates_by_confidence([c1, c2, c3])
    assert [c.candidate_finding_id for c in sorted_cands] == ["cand-c", "cand-a", "cand-b"]


# =============================================================================
# STRATEGY A (STEP 5): PRE-FLIGHT PARTITION ISOLATION HOOK TESTS
# =============================================================================

def test_evaluation_preflight_partition_check_valid_splits_succeeds():
    """Valid partition splits pass pre-flight check and evaluation proceeds normally."""
    val_items = [{"template_family_id": "MACRO-FAM-DOE-PPD", "contract_id": "C-VAL-01"}]
    test_items = [{"template_family_id": "MACRO-FAM-DEA-CONCESSION", "contract_id": "C-TEST-01"}]

    c1 = create_synthetic_candidate("c-val-01")
    candidates = [c1]
    refs = {"c-val-01": ReferenceDecision.RETAIN}
    decisions = {"c-val-01": PolicyAction.ACCEPT}

    # Direct preflight check
    check_res = preflight_partition_check(validation_items=val_items, test_items=test_items)
    assert check_res is not None
    assert check_res.is_valid is True

    # Check via evaluate_policy
    summary = evaluate_policy(
        policy_id="test-valid-split-policy",
        candidates=candidates,
        reference_annotations=refs,
        policy_decisions=decisions,
        validation_items=val_items,
        test_items=test_items,
    )
    assert summary.retained_count == 1
    assert summary.ufc == 1.0


def test_evaluation_preflight_partition_check_leakage_fails_closed():
    """Detected cross-partition template family leakage fails closed with ValueError."""
    # Shared family in both splits (LEAKAGE)
    val_items = [{"template_family_id": "SHARED-FAMILY-01"}]
    test_items = [{"template_family_id": "SHARED-FAMILY-01"}]

    c1 = create_synthetic_candidate("c-01")

    with pytest.raises(ValueError, match="Cross-partition template family leakage detected"):
        evaluate_policy(
            policy_id="policy-leakage",
            candidates=[c1],
            reference_annotations={"c-01": ReferenceDecision.RETAIN},
            policy_decisions={"c-01": PolicyAction.ACCEPT},
            validation_items=val_items,
            test_items=test_items,
        )


def test_evaluation_preflight_partition_check_doe_in_test_fails_closed():
    """MACRO-FAM-DOE-PPD in Test partition violates Strategy A and fails closed with ValueError."""
    val_items = [{"template_family_id": "MACRO-FAM-NITI-BUS"}]
    test_items = [{"template_family_id": "MACRO-FAM-DOE-PPD"}]

    c1 = create_synthetic_candidate("c-01")

    with pytest.raises(ValueError, match="MACRO-FAM-DOE-PPD.*allocated to Test partition"):
        evaluate_policy(
            policy_id="policy-doe-violation",
            candidates=[c1],
            reference_annotations={"c-01": ReferenceDecision.RETAIN},
            policy_decisions={"c-01": PolicyAction.ACCEPT},
            partition_metadata={"validation_items": val_items, "test_items": test_items},
        )


def test_evaluation_preserves_behavior_when_partition_metadata_absent():
    """When partition metadata is omitted, existing evaluation behavior is fully preserved without error."""
    c1 = create_synthetic_candidate("c-01")

    # None partition metadata
    summary = evaluate_policy(
        policy_id="policy-no-partition-meta",
        candidates=[c1],
        reference_annotations={"c-01": ReferenceDecision.RETAIN},
        policy_decisions={"c-01": PolicyAction.ACCEPT},
        validation_items=None,
        test_items=None,
        partition_metadata=None,
    )
    assert summary.retained_count == 1
    assert summary.ufc == 1.0

    # Also directly in preflight_partition_check
    res = preflight_partition_check(validation_items=None, test_items=None, partition_metadata=None)
    assert res is None

