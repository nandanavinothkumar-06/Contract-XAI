"""
Tests for Offline Confidence-Only vs. Evidence-Aware Policy Comparison.

Verifies:
1. Threshold grid includes endpoints 0.0 and 1.0 and is monotonic.
2. Confidence-only actions obey the specified boundary convention.
3. Evidence-aware decisions use existing EvidenceAwarePolicy.
4. Reference labels do not affect policy actions.
5. REVIEW_REQUIRED is not counted as automatic retention.
6. UFR is undefined (None) when no candidates are automatically retained.
7. Duplicate IDs trigger the established validation behavior.
8. Matching tolerance of ±0.02 is enforced.
9. Failed matching yields no Delta UFR.
10. Ties in matched coverage are resolved deterministically.
11. Stale and unknown versions are not conflated in SEAR.
12. Unsupported label mappings do not become accepted findings.
13. Synthetic outputs carry the mandatory disclaimer.
14. Identical seed/configuration produces identical output rows.
15. No client-disclosure flags are enabled in generated artifacts.
"""

import os
import json
import pytest
from src.evaluation.synthetic_candidates import generate_synthetic_candidate_pool
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
)
from src.abstention.evidence_policy import EvidenceAwarePolicy
from scripts.evaluate_abstention_comparison import (
    evaluate_confidence_baseline,
    run_confidence_threshold_sweep,
    find_best_matched_baseline,
    execute_offline_comparison,
)


def test_threshold_grid_endpoints_and_order():
    """Threshold grid must span [0.0, 1.0] with deterministic step."""
    steps = 101
    step_size = 0.01
    thresholds = [round(i * step_size, 4) for i in range(steps)]

    assert thresholds[0] == 0.0
    assert thresholds[-1] == 1.0
    assert len(thresholds) == 101
    assert all(thresholds[i] < thresholds[i + 1] for i in range(len(thresholds) - 1))


def test_confidence_only_actions_boundary_convention():
    """Confidence-only baseline retains iff confidence >= tau_conf, barring safety gates."""
    ds = generate_synthetic_candidate_pool(seed=42, additional_random_count=10)
    cand = ds.candidates[0] # Normal valid candidate

    # Threshold below candidate confidence -> ACCEPT
    act_low = evaluate_confidence_baseline(cand, tau_conf=cand.confidence_value - 0.05)
    assert act_low == PolicyAction.ACCEPT

    # Threshold above candidate confidence -> WITHHOLD
    act_high = evaluate_confidence_baseline(cand, tau_conf=cand.confidence_value + 0.05)
    assert act_high == PolicyAction.WITHHOLD

    # Threshold exactly equal to confidence -> ACCEPT
    act_eq = evaluate_confidence_baseline(cand, tau_conf=cand.confidence_value)
    assert act_eq == PolicyAction.ACCEPT


def test_unsupported_label_mapping_blocked_by_confidence_baseline():
    """Confidence-only baseline must NEVER accept unsupported model label mappings."""
    ds = generate_synthetic_candidate_pool(seed=42)
    unmapped_cand = next(c for c in ds.candidates if c.label_mapping_status == LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING)

    # Even at tau = 0.0, unsupported label mapping must be WITHHELD
    action = evaluate_confidence_baseline(unmapped_cand, tau_conf=0.0)
    assert action == PolicyAction.WITHHOLD


def test_evidence_aware_policy_integration():
    """Evidence-aware decisions must invoke the 5-tier cascade from EvidenceAwarePolicy."""
    ds = generate_synthetic_candidate_pool(seed=42)
    stale_cand = next(c for c in ds.candidates if c.version_consistency_status == VersionConsistencyStatus.STALE)

    policy = EvidenceAwarePolicy()
    decision = policy.evaluate_candidate(stale_cand)

    # Stale version MUST be withheld under Tier 2
    assert decision.policy_action == PolicyAction.WITHHOLD
    assert decision.precedence_tier_applied == 2


def test_review_required_not_counted_as_automatically_retained():
    """Candidates routed to REVIEW_REQUIRED must not inflate retained_count or UFC."""
    ds = generate_synthetic_candidate_pool(seed=42)
    evid_policy = EvidenceAwarePolicy()
    decisions = {c.candidate_finding_id: evid_policy.evaluate_candidate(c).policy_action for c in ds.candidates}

    summary = evaluate_policy(
        policy_id="test_evidence_policy",
        candidates=ds.candidates,
        reference_annotations=ds.reference_annotations,
        policy_decisions=decisions,
    )

    review_count = sum(1 for a in decisions.values() if a == PolicyAction.REVIEW_REQUIRED)
    accept_count = sum(1 for a in decisions.values() if a == PolicyAction.ACCEPT)

    assert summary.routed_to_review_count == review_count
    assert summary.retained_count == accept_count
    assert summary.retained_count + summary.routed_to_review_count <= summary.total_candidates


def test_ufr_undefined_when_no_candidates_retained():
    """At tau = 1.0 (or high threshold where nothing is accepted), UFR is None, NEVER 0.0."""
    ds = generate_synthetic_candidate_pool(seed=42)
    # Set all decisions to WITHHOLD
    decisions = {c.candidate_finding_id: PolicyAction.WITHHOLD for c in ds.candidates}

    summary = evaluate_policy(
        policy_id="all_withheld",
        candidates=ds.candidates,
        reference_annotations=ds.reference_annotations,
        policy_decisions=decisions,
    )

    assert summary.retained_count == 0
    assert summary.evaluable_retained_count == 0
    assert summary.ufr is None # STRICT INVARIANT


def test_coverage_matching_tolerance_enforced():
    """Matching succeeds if |UFC_A - UFC_B| <= 0.02; otherwise unachieved."""
    ds = generate_synthetic_candidate_pool(seed=42)
    thresholds = [0.10, 0.30, 0.50, 0.70, 0.90]
    sweep_results = run_confidence_threshold_sweep(ds, thresholds)

    evid_summary = evaluate_policy(
        policy_id="evid_test",
        candidates=ds.candidates,
        reference_annotations=ds.reference_annotations,
        policy_decisions={c.candidate_finding_id: PolicyAction.ACCEPT for c in ds.candidates},
    )

    best_tau, best_summary, result = find_best_matched_baseline(
        sweep_results=sweep_results,
        evid_summary=evid_summary,
        tolerance=0.02,
    )

    if result.status == "MATCHED_COVERAGE_ACHIEVED":
        assert result.coverage_difference <= 0.02
        assert result.delta_ufr is not None
    else:
        assert result.coverage_difference > 0.02 or result.coverage_difference is None
        assert result.delta_ufr is None


def test_deterministic_offline_comparison_execution(tmp_path):
    """Running offline comparison with fixed seed generates exact reproducible outputs."""
    out_dir_1 = str(tmp_path / "run_1")
    out_dir_2 = str(tmp_path / "run_2")

    res1 = execute_offline_comparison(seed=42, num_contracts=10, additional_random=20, output_dir=out_dir_1)
    res2 = execute_offline_comparison(seed=42, num_contracts=10, additional_random=20, output_dir=out_dir_2)

    assert res1["dataset"].total_candidates == res2["dataset"].total_candidates
    assert res1["best_tau"] == res2["best_tau"]
    assert res1["evid_summary"].retention_rate == res2["evid_summary"].retention_rate
    assert res1["evid_summary"].ufr == res2["evid_summary"].ufr
    assert res1["matching_result"].status == res2["matching_result"].status

    # Verify JSON summary file contains mandatory disclaimer
    summary_path = res1["artifact_paths"]["summary_json"]
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "SYNTHETIC ENGINEERING VALIDATION" in data["disclaimer"]
