"""
Tests for Deterministic Synthetic Candidate Dataset Generator.

Verifies:
1. Fixed seed produces 100% reproducible candidate pools.
2. All candidate IDs are strictly unique.
3. Multiple clauses belong to the same contract (clustering).
4. Required edge cases are guaranteed to occur.
5. All synthetic fixtures carry is_synthetic_fixture = True and is_disclosed_to_client = False.
6. Synthetic disclaimer is present on all datasets.
"""

import pytest
from src.evaluation.synthetic_candidates import (
    generate_synthetic_candidate_pool,
    SYNTHETIC_DATA_DISCLAIMER,
)
from src.candidates.schema import (
    VersionConsistencyStatus,
    LabelMappingStatus,
    CandidateOrigin,
)
from src.evaluation.abstention_eval import ReferenceDecision


def test_fixed_seed_reproducibility():
    """Seed 42 must generate identical candidates and reference annotations across repeated calls."""
    ds1 = generate_synthetic_candidate_pool(seed=42, additional_random_count=30)
    ds2 = generate_synthetic_candidate_pool(seed=42, additional_random_count=30)

    assert ds1.total_candidates == ds2.total_candidates
    assert ds1.unique_contracts == ds2.unique_contracts

    for c1, c2 in zip(ds1.candidates, ds2.candidates):
        assert c1.candidate_finding_id == c2.candidate_finding_id
        assert c1.contract_id == c2.contract_id
        assert c1.clause_id == c2.clause_id
        assert c1.confidence_value == c2.confidence_value
        assert c1.evidence_quality_status == c2.evidence_quality_status
        assert c1.version_consistency_status == c2.version_consistency_status
        assert c1.prediction_category == c2.prediction_category

    assert ds1.reference_annotations == ds2.reference_annotations


def test_unique_candidate_ids():
    """All generated candidate finding IDs must be unique."""
    ds = generate_synthetic_candidate_pool(seed=123, additional_random_count=50)
    ids = [c.candidate_finding_id for c in ds.candidates]
    assert len(ids) == len(set(ids))
    assert len(ids) == ds.total_candidates


def test_multiple_clauses_per_contract_clustering():
    """Multiple candidate findings must belong to the same contract ID."""
    ds = generate_synthetic_candidate_pool(seed=42, num_contracts=15, additional_random_count=40)
    assert ds.total_candidates > ds.unique_contracts

    contract_counts = {}
    for c in ds.candidates:
        contract_counts[c.contract_id] = contract_counts.get(c.contract_id, 0) + 1

    # At least some contracts must have >= 2 clauses
    clustered = [cnt for cnt in contract_counts.values() if cnt >= 2]
    assert len(clustered) >= 5


def test_required_edge_cases_guaranteed():
    """All documented research edge cases must appear in the dataset."""
    ds = generate_synthetic_candidate_pool(seed=42)

    version_statuses = {c.version_consistency_status for c in ds.candidates}
    assert VersionConsistencyStatus.CONSISTENT in version_statuses
    assert VersionConsistencyStatus.STALE in version_statuses
    assert VersionConsistencyStatus.UNKNOWN in version_statuses

    ev_statuses = {c.evidence_quality_status for c in ds.candidates}
    assert "TRACEABLE" in ev_statuses
    assert "INSUFFICIENT" in ev_statuses
    assert "PARTIAL" in ev_statuses
    assert "NO_MATCHING_EVIDENCE" in ev_statuses

    ref_decisions = set(ds.reference_annotations.values())
    assert ReferenceDecision.RETAIN in ref_decisions
    assert ReferenceDecision.WITHHOLD in ref_decisions
    assert ReferenceDecision.HUMAN_REVIEW_REQUIRED in ref_decisions
    assert ReferenceDecision.NOT_ASSESSABLE in ref_decisions

    # Verify presence of non-statutory commercial risk finding
    non_stat = [c for c in ds.candidates if c.prediction_category == "PRICE_ADJUSTMENT"]
    assert len(non_stat) >= 1
    assert non_stat[0].source_document_provenance.get("is_statutory") is False

    # Verify presence of unsupported model label mapping
    unmapped = [c for c in ds.candidates if c.label_mapping_status == LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING]
    assert len(unmapped) >= 1

    # Verify presence of unassessable candidate
    unassessable = [c for c in ds.candidates if not c.clause_text.strip()]
    assert len(unassessable) >= 1
    assert ds.reference_annotations[unassessable[0].candidate_finding_id] == ReferenceDecision.NOT_ASSESSABLE


def test_synthetic_safety_invariants_and_disclaimer():
    """All records must be marked as synthetic fixtures with client disclosure disabled."""
    ds = generate_synthetic_candidate_pool(seed=999)

    assert SYNTHETIC_DATA_DISCLAIMER in ds.disclaimer
    for c in ds.candidates:
        assert c.is_synthetic_fixture is True
        assert c.is_disclosed_to_client is False
        assert c.origin == CandidateOrigin.SYNTHETIC_TEST_FIXTURE
