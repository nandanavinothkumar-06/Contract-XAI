"""
Synthetic Unit Tests for Candidate Finding Generation and Deduplication.

Tests verify:
1. Correct candidate record construction from supported model outputs.
2. Missing model provenance.
3. Missing or uncalibrated confidence semantics.
4. Unsupported mapping from the model label space.
5. Stable and deterministic candidate identifiers.
6. Document-version mismatch detection (CONSISTENT vs STALE vs UNKNOWN).
7. Duplicate candidate identifiers detection.
8. Deduplication key and duplicate log preservation of distinct categories.
9. Strict client disclosure isolation (is_disclosed_to_client == False).

NOTE: All tests use synthetic vectors and fixtures. They do NOT represent real-world model accuracy.
"""

import json
import pytest
from unittest.mock import MagicMock
from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    CandidateOrigin,
    VersionConsistencyStatus,
    LabelMappingStatus,
)
from src.candidates.pipeline import (
    CandidateGenerationPipeline,
    generate_deterministic_finding_id,
    VALID_INDIAN_RISK_CATEGORIES,
)
from src.candidates.deduplication import (
    compute_deduplication_key,
    deduplicate_candidates,
    normalize_finding_text,
)
from src.candidates.alternative_validator import ContractConfiguration


class MockModelConfig:
    def __init__(self, mode="multilabel", threshold=0.5):
        self.model_checkpoint = "nlpaueb/legal-bert-base-uncased"
        self.model_name = "legal-bert"
        self.model_family = "Legal-BERT"
        self.task_type = "CLASSIFICATION"
        self.classification_mode = mode
        self.multilabel_threshold = threshold


class MockModelWrapper:
    def __init__(self, mode="multilabel", threshold=0.5):
        self.config = MockModelConfig(mode=mode, threshold=threshold)

    def is_available(self):
        return True


@pytest.fixture
def sample_clauses():
    return [
        {
            "clause_id": "clause-001",
            "text": "The Contractor shall indemnify and hold harmless the Company from any loss.",
        },
        {
            "clause_id": "clause-002",
            "text": "Neither party shall be liable for indirect or consequential damages.",
        },
    ]


def test_deterministic_finding_id_stability():
    """Verify that identical inputs produce identical finding IDs and differing inputs differ."""
    id1 = generate_deterministic_finding_id(
        contract_id="doc-123",
        contract_version=1,
        clause_id="clause-01",
        prediction_category="INDEMNIFICATION",
        raw_model_label="indemnifications",
        model_id="legal-bert",
    )
    id2 = generate_deterministic_finding_id(
        contract_id="doc-123",
        contract_version=1,
        clause_id="clause-01",
        prediction_category="INDEMNIFICATION",
        raw_model_label="indemnifications",
        model_id="legal-bert",
    )
    id3 = generate_deterministic_finding_id(
        contract_id="doc-123",
        contract_version=2, # different version
        clause_id="clause-01",
        prediction_category="INDEMNIFICATION",
        raw_model_label="indemnifications",
        model_id="legal-bert",
    )
    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 36 # Standard formatted length


def test_candidate_generation_with_explicit_label_mapping(sample_clauses):
    """Test candidate construction when model labels are mapped to Indian risk categories."""
    pipeline = CandidateGenerationPipeline(
        model_wrapper=None,
        label_mapper={"0": "INDEMNIFICATION", "1": "LIMITATION_OF_LIABILITY"},
    )
    clauses = [
        {
            "clause_id": "clause-001",
            "text": sample_clauses[0]["text"],
            "candidate_predictions": [
                {"raw_label": "0", "confidence": 0.88, "confidence_semantics": "MULTILABEL_SIGMOID_SCORE"}
            ],
        }
    ]

    candidates, duplicates = pipeline.generate_candidates_for_clauses(
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="abc123sha256",
        clauses=clauses,
        is_synthetic_fixture=True,
    )

    assert len(candidates) == 1
    assert len(duplicates) == 0
    c = candidates[0]
    assert c.prediction_category == "INDEMNIFICATION"
    assert c.raw_model_label == "0"
    assert c.label_mapping_status == LabelMappingStatus.MAPPED
    assert c.confidence_value == 0.88
    assert c.confidence_semantics == ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE
    assert c.confidence_is_calibrated is False # Raw score must NOT be marked calibrated
    assert "UNCALIBRATED_RAW_SCORE" in c.missing_capabilities
    assert c.is_disclosed_to_client is False # Client disclosure isolation
    assert c.candidate_finding_text is None # No fabricated text description


def test_unsupported_model_label_space_fails_defensively(sample_clauses):
    """STRICT INVARIANT: Pipeline must NOT invent a fake mapping for unsupported label spaces."""
    pipeline = CandidateGenerationPipeline(
        model_wrapper=None,
        label_mapper={}, # No mapping supplied
    )
    clauses = [
        {
            "clause_id": "clause-001",
            "text": sample_clauses[0]["text"],
            "candidate_predictions": [
                {"raw_label": "us_sec_item_402_executive_compensation", "confidence": 0.92}
            ],
        }
    ]

    candidates, _ = pipeline.generate_candidates_for_clauses(
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash001",
        clauses=clauses,
    )

    assert len(candidates) == 1
    c = candidates[0]
    assert c.label_mapping_status == LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING
    assert c.prediction_category == "UNMAPPED_us_sec_item_402_executive_compensation"
    assert any("UNSUPPORTED_MODEL_LABEL_SPACE" in cap for cap in c.missing_capabilities)


def test_missing_model_provenance_records_capability_blocker(sample_clauses):
    """When no model or predictions exist, pipeline must record missing capabilities."""
    pipeline = CandidateGenerationPipeline(model_wrapper=None)
    candidates, _ = pipeline.generate_candidates_for_clauses(
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash001",
        clauses=sample_clauses,
    )

    assert len(candidates) == 2
    for c in candidates:
        assert c.model_id == "unknown-model"
        assert "MODEL_UNAVAILABLE" in c.missing_capabilities
        assert c.confidence_semantics == ConfidenceSemantics.UNSPECIFIED


def test_document_version_consistency_states(sample_clauses):
    """Test active version matching: CONSISTENT vs STALE vs UNKNOWN."""
    # 1. Version matches active -> CONSISTENT
    pipeline_consistent = CandidateGenerationPipeline(active_version_resolver=lambda doc_id: 2)
    candidates_c, _ = pipeline_consistent.generate_candidates_for_clauses(
        contract_id="doc-001",
        contract_version=2,
        document_content_hash="hash_v2",
        clauses=[sample_clauses[0]],
    )
    assert candidates_c[0].version_consistency_status == VersionConsistencyStatus.CONSISTENT

    # 2. Version superseded -> STALE
    candidates_s, _ = pipeline_consistent.generate_candidates_for_clauses(
        contract_id="doc-001",
        contract_version=1, # Superseded by v2
        document_content_hash="hash_v1",
        clauses=[sample_clauses[0]],
    )
    assert candidates_s[0].version_consistency_status == VersionConsistencyStatus.STALE

    # 3. No resolver -> UNKNOWN
    pipeline_unknown = CandidateGenerationPipeline(active_version_resolver=None)
    candidates_u, _ = pipeline_unknown.generate_candidates_for_clauses(
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash_v1",
        clauses=[sample_clauses[0]],
    )
    assert candidates_u[0].version_consistency_status == VersionConsistencyStatus.UNKNOWN


def test_deduplication_preserves_distinct_risk_categories():
    """Verify distinct risk categories on the same clause are preserved, while identical keys are collapsed."""
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-001",
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash",
        clause_id="clause-10",
        clause_text="Contractor shall indemnify Company and limit liability to fees.",
        prediction_category="INDEMNIFICATION",
        raw_model_label="0",
        model_id="bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
    )
    # Distinct category on same clause: MUST BE PRESERVED
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-002",
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash",
        clause_id="clause-10",
        clause_text="Contractor shall indemnify Company and limit liability to fees.",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="1",
        model_id="bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.78,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
    )
    # Duplicate inference of c1: MUST BE COLLAPSED
    c3 = CandidateFindingRecord(
        candidate_finding_id="cand-003",
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash",
        clause_id="clause-10",
        clause_text="Contractor shall indemnify Company and limit liability to fees.",
        prediction_category="INDEMNIFICATION",
        raw_model_label="0",
        model_id="bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
    )

    canonical, dup_log = deduplicate_candidates([c1, c2, c3])
    assert len(canonical) == 2
    assert canonical[0].candidate_finding_id == "cand-001"
    assert canonical[1].candidate_finding_id == "cand-002"

    assert len(dup_log) == 1
    assert dup_log[0].canonical_finding_id == "cand-001"
    assert dup_log[0].duplicate_finding_id == "cand-003"


def test_deduplication_missing_finding_text_with_distinct_raw_labels():
    """
    Regression test: Candidates with candidate_finding_text=None and distinct raw_model_labels
    must NOT collapse to the same deduplication key.
    """
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-lbl-1",
        contract_id="doc-002",
        contract_version=1,
        document_content_hash="hash_abc",
        clause_id="clause-20",
        clause_text="Each party indemnifies the other.",
        prediction_category="INDEMNIFICATION",
        raw_model_label="indemnification_direct",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.82,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-lbl-2",
        contract_id="doc-002",
        contract_version=1,
        document_content_hash="hash_abc",
        clause_id="clause-20",
        clause_text="Each party indemnifies the other.",
        prediction_category="INDEMNIFICATION",
        raw_model_label="indemnification_third_party",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.79,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    key1 = compute_deduplication_key(c1)
    key2 = compute_deduplication_key(c2)
    assert key1 != key2, f"Keys must differ for distinct raw model labels: {key1} vs {key2}"

    canonical, dup_log = deduplicate_candidates([c1, c2])
    assert len(canonical) == 2
    assert canonical[0].candidate_finding_id == "cand-lbl-1"
    assert canonical[1].candidate_finding_id == "cand-lbl-2"
    assert len(dup_log) == 0


def test_deduplication_distinct_generator_origins_preserved():
    """
    Regression test: Candidates with candidate_finding_text=None and distinct origins
    (e.g. MODEL_INFERENCE_BATCH vs LAWYER_WORKBENCH_CREATION) must NOT collapse.
    """
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-orig-1",
        contract_id="doc-003",
        contract_version=1,
        document_content_hash="hash_xyz",
        clause_id="clause-30",
        clause_text="Liability is capped at contract value.",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="limitation_of_liability",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.88,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-orig-2",
        contract_id="doc-003",
        contract_version=1,
        document_content_hash="hash_xyz",
        clause_id="clause-30",
        clause_text="Liability is capped at contract value.",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="limitation_of_liability",
        candidate_finding_text=None,
        model_id="lawyer-reviewed",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=1.0,
        confidence_semantics=ConfidenceSemantics.HEURISTIC_SCORE,
        origin=CandidateOrigin.LAWYER_CREATED,
    )

    key1 = compute_deduplication_key(c1)
    key2 = compute_deduplication_key(c2)
    assert key1 != key2, f"Keys must differ for distinct origins: {key1} vs {key2}"

    canonical, dup_log = deduplicate_candidates([c1, c2])
    assert len(canonical) == 2
    assert canonical[0].candidate_finding_id == "cand-orig-1"
    assert canonical[1].candidate_finding_id == "cand-orig-2"
    assert len(dup_log) == 0


def test_deduplication_genuine_duplicates_collapsed():
    """
    Regression test: Exact duplicate inferences sharing identical key elements
    must collapse to a single canonical finding, logging duplicates into the audit log.
    Tests both candidate_finding_text=None and normalized text equivalences.
    """
    # Case A: candidate_finding_text=None genuine duplicate
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-dup-1",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_111",
        clause_id="clause-40",
        clause_text="Disputes shall be settled under the Arbitration and Conciliation Act 1996.",
        prediction_category="ARBITRATION_EXCLUSIVE_JURISDICTION",
        raw_model_label="arbitration",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.91,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-dup-2",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_111",
        clause_id="clause-40",
        clause_text="Disputes shall be settled under the Arbitration and Conciliation Act 1996.",
        prediction_category="ARBITRATION_EXCLUSIVE_JURISDICTION",
        raw_model_label="arbitration",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.91,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    canonical_a, dup_log_a = deduplicate_candidates([c1, c2])
    assert len(canonical_a) == 1
    assert canonical_a[0].candidate_finding_id == "cand-dup-1"
    assert len(dup_log_a) == 1
    assert dup_log_a[0].canonical_finding_id == "cand-dup-1"
    assert dup_log_a[0].duplicate_finding_id == "cand-dup-2"
    assert dup_log_a[0].deduplication_key == compute_deduplication_key(c1)

    # Case B: candidate_finding_text normalized equivalence (case & punctuation variation)
    c3 = CandidateFindingRecord(
        candidate_finding_id="cand-dup-3",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_111",
        clause_id="clause-41",
        clause_text="Governed by the laws of India.",
        prediction_category="GOVERNING_LAW_DISPUTE",
        raw_model_label="governing_law",
        candidate_finding_text="  Indian governing law applies to disputes.  ",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c4 = CandidateFindingRecord(
        candidate_finding_id="cand-dup-4",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_111",
        clause_id="clause-41",
        clause_text="Governed by the laws of India.",
        prediction_category="GOVERNING_LAW_DISPUTE",
        raw_model_label="governing_law",
        candidate_finding_text="indian governing law applies to disputes!",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    canonical_b, dup_log_b = deduplicate_candidates([c3, c4])
    assert len(canonical_b) == 1
    assert canonical_b[0].candidate_finding_id == "cand-dup-3"
    assert len(dup_log_b) == 1
    assert dup_log_b[0].canonical_finding_id == "cand-dup-3"
    assert dup_log_b[0].duplicate_finding_id == "cand-dup-4"


def test_deduplication_deterministic_behavior():
    """
    Regression test: compute_deduplication_key and deduplicate_candidates must behave
    strictly deterministically across repeated invocations.
    """
    candidate = CandidateFindingRecord(
        candidate_finding_id="cand-det-1",
        contract_id="doc-005",
        contract_version=2,
        document_content_hash="hash_222",
        clause_id="clause-50",
        clause_text="Agreement may be terminated by either party upon 30 days notice.",
        prediction_category="TERMINATION_CONVENIENCE",
        raw_model_label="termination",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.87,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    # Key determinism
    key_run1 = compute_deduplication_key(candidate)
    key_run2 = compute_deduplication_key(candidate)
    key_run3 = compute_deduplication_key(candidate)
    assert key_run1 == key_run2 == key_run3
    expected_key = json.dumps(
        [
            "doc-005",
            2,
            "clause-50",
            "TERMINATION_CONVENIENCE",
            "termination",
            "MODEL_INFERENCE_BATCH",
            None,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    assert key_run1 == expected_key

    # Deduplication determinism on candidate collection
    candidates = [candidate]
    can1, log1 = deduplicate_candidates(candidates)
    can2, log2 = deduplicate_candidates(candidates)
    assert [c.candidate_finding_id for c in can1] == [c.candidate_finding_id for c in can2]
    assert len(log1) == len(log2) == 0


def test_deduplication_colon_delimiter_no_collision():
    """
    Focused regression test: demonstrates actual failure/collision of the naive
    colon-concatenated representation, and verifies that canonical JSON serialization
    prevents false collisions when fields contain colon delimiters.
    """
    # Candidate 1: clause_id has a colon ("sec:1"), category is "INDEMNITY"
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-col-1",
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash_col",
        clause_id="sec:1",
        clause_text="Indemnification text here.",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity_clause",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.91,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    # Candidate 2: clause_id is "sec", category has a colon ("1:INDEMNITY")
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-col-2",
        contract_id="doc-001",
        contract_version=1,
        document_content_hash="hash_col",
        clause_id="sec",
        clause_text="Different clause text.",
        prediction_category="1:INDEMNITY",
        raw_model_label="indemnity_clause",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.88,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    # 1. Demonstrate actual failure of the legacy colon concatenation
    legacy_key1 = f"{c1.contract_id}:{c1.contract_version}:{c1.clause_id}:{c1.prediction_category}:{c1.raw_model_label}:{c1.origin.value}:"
    legacy_key2 = f"{c2.contract_id}:{c2.contract_version}:{c2.clause_id}:{c2.prediction_category}:{c2.raw_model_label}:{c2.origin.value}:"
    assert legacy_key1 == legacy_key2, "Legacy colon concatenation must collide to demonstrate the defect"

    # 2. Verify hardened canonical JSON serialization prevents collision
    key1 = compute_deduplication_key(c1)
    key2 = compute_deduplication_key(c2)
    assert key1 != key2, "Canonical JSON keys must be distinct despite colon in field"

    # 3. Verify deduplication preserves both candidates
    canonical, dup_log = deduplicate_candidates([c1, c2])
    assert len(canonical) == 2
    assert len(dup_log) == 0
    assert {c.candidate_finding_id for c in canonical} == {"cand-col-1", "cand-col-2"}


def test_deduplication_ambiguous_concatenation_field_boundary():
    """
    Focused regression test: demonstrates delimiter shift collision across
    prediction_category and raw_model_label in legacy representation, and
    proves canonical JSON maintains strict field boundary protection.
    """
    c3 = CandidateFindingRecord(
        candidate_finding_id="cand-bound-3",
        contract_id="doc-002",
        contract_version=1,
        document_content_hash="hash_bound",
        clause_id="clause-10",
        clause_text="Text 10",
        prediction_category="CAT",
        raw_model_label="A:B",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c4 = CandidateFindingRecord(
        candidate_finding_id="cand-bound-4",
        contract_id="doc-002",
        contract_version=1,
        document_content_hash="hash_bound",
        clause_id="clause-10",
        clause_text="Text 10",
        prediction_category="CAT:A",
        raw_model_label="B",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    # Legacy representation collided across category and raw_model_label
    legacy_key3 = f"{c3.contract_id}:{c3.contract_version}:{c3.clause_id}:{c3.prediction_category}:{c3.raw_model_label}:{c3.origin.value}:"
    legacy_key4 = f"{c4.contract_id}:{c4.contract_version}:{c4.clause_id}:{c4.prediction_category}:{c4.raw_model_label}:{c4.origin.value}:"
    assert legacy_key3 == legacy_key4

    # Canonical keys are completely distinct
    key3 = compute_deduplication_key(c3)
    key4 = compute_deduplication_key(c4)
    assert key3 != key4

    canonical, dup_log = deduplicate_candidates([c3, c4])
    assert len(canonical) == 2
    assert len(dup_log) == 0


def test_deduplication_none_versus_empty_finding_text():
    """
    Focused regression test: verify None and empty finding text are explicitly
    and consistently handled, differentiating absence of text from empty text
    while genuine duplicates (both None or both empty/whitespace) collapse properly.
    """
    # Candidate A: candidate_finding_text is None
    ca = CandidateFindingRecord(
        candidate_finding_id="cand-text-a",
        contract_id="doc-003",
        contract_version=1,
        document_content_hash="hash_txt",
        clause_id="clause-20",
        clause_text="Text 20",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="liability_cap",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.90,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    # Candidate B: candidate_finding_text is empty string ""
    cb = CandidateFindingRecord(
        candidate_finding_id="cand-text-b",
        contract_id="doc-003",
        contract_version=1,
        document_content_hash="hash_txt",
        clause_id="clause-20",
        clause_text="Text 20",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="liability_cap",
        candidate_finding_text="",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.90,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    # Candidate C: candidate_finding_text is whitespace only "   "
    cc = CandidateFindingRecord(
        candidate_finding_id="cand-text-c",
        contract_id="doc-003",
        contract_version=1,
        document_content_hash="hash_txt",
        clause_id="clause-20",
        clause_text="Text 20",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="liability_cap",
        candidate_finding_text="   ",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.90,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    key_a = compute_deduplication_key(ca)
    key_b = compute_deduplication_key(cb)
    key_c = compute_deduplication_key(cc)

    # None maps to JSON null (item 6 is None)
    parsed_a = json.loads(key_a)
    assert parsed_a[6] is None

    # Empty string maps to JSON "" (item 6 is "")
    parsed_b = json.loads(key_b)
    assert parsed_b[6] == ""

    # Whitespace normalizes to empty string (item 6 is "")
    parsed_c = json.loads(key_c)
    assert parsed_c[6] == ""

    # None and empty string produce distinct keys
    assert key_a != key_b

    # Empty string and whitespace produce identical keys
    assert key_b == key_c

    # Deduplicating [ca, cb] preserves both because absence of text != empty text
    canonical_ab, dup_log_ab = deduplicate_candidates([ca, cb])
    assert len(canonical_ab) == 2
    assert len(dup_log_ab) == 0

    # Deduplicating [cb, cc] collapses cc as a genuine duplicate of cb
    canonical_bc, dup_log_bc = deduplicate_candidates([cb, cc])
    assert len(canonical_bc) == 1
    assert canonical_bc[0].candidate_finding_id == "cand-text-b"
    assert len(dup_log_bc) == 1
    assert dup_log_bc[0].canonical_finding_id == "cand-text-b"
    assert dup_log_bc[0].duplicate_finding_id == "cand-text-c"


def test_deduplication_distinct_raw_model_labels():
    """
    Focused regression test: verify distinct raw model labels with identical
    categories and clauses produce distinct keys and are never collapsed.
    """
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-raw-1",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_raw",
        clause_id="clause-30",
        clause_text="Governing law clause.",
        prediction_category="GOVERNING_LAW_DISPUTE",
        raw_model_label="governing_law_choice",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.88,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-raw-2",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_raw",
        clause_id="clause-30",
        clause_text="Governing law clause.",
        prediction_category="GOVERNING_LAW_DISPUTE",
        raw_model_label="dispute_resolution_venue",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.82,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    key1 = compute_deduplication_key(c1)
    key2 = compute_deduplication_key(c2)
    assert key1 != key2

    canonical, dup_log = deduplicate_candidates([c1, c2])
    assert len(canonical) == 2
    assert len(dup_log) == 0


def test_deduplication_distinct_generator_origins():
    """
    Focused regression test: verify distinct generator origins with identical
    categories, raw labels, and clauses produce distinct keys and are never collapsed.
    """
    c_model = CandidateFindingRecord(
        candidate_finding_id="cand-orig-model",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_orig",
        clause_id="clause-35",
        clause_text="Indemnity clause.",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c_lawyer = CandidateFindingRecord(
        candidate_finding_id="cand-orig-lawyer",
        contract_id="doc-004",
        contract_version=1,
        document_content_hash="hash_orig",
        clause_id="clause-35",
        clause_text="Indemnity clause.",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity",
        candidate_finding_text=None,
        model_id="manual",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=1.0,
        confidence_semantics=ConfidenceSemantics.HEURISTIC_SCORE,
        origin=CandidateOrigin.LAWYER_CREATED,
    )
    key_model = compute_deduplication_key(c_model)
    key_lawyer = compute_deduplication_key(c_lawyer)
    assert key_model != key_lawyer

    canonical, dup_log = deduplicate_candidates([c_model, c_lawyer])
    assert len(canonical) == 2
    assert len(dup_log) == 0


def test_deduplication_genuine_duplicates_comprehensive():
    """
    Focused regression test: verify genuine duplicates are collapsed into
    the canonical candidate and logged with exact audit metadata across:
    1. Both having candidate_finding_text=None.
    2. Both having whitespace/empty finding text.
    3. Both having substantive finding text differing only in casing, punctuation, and whitespace.
    """
    # Case 1: Both None
    c1 = CandidateFindingRecord(
        candidate_finding_id="cand-gen-1",
        contract_id="doc-006",
        contract_version=1,
        document_content_hash="hash_gen",
        clause_id="clause-1",
        clause_text="Some text",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.9,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c2 = CandidateFindingRecord(
        candidate_finding_id="cand-gen-2",
        contract_id="doc-006",
        contract_version=1,
        document_content_hash="hash_gen",
        clause_id="clause-1",
        clause_text="Some text",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.9,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    can1, log1 = deduplicate_candidates([c1, c2])
    assert len(can1) == 1
    assert can1[0].candidate_finding_id == "cand-gen-1"
    assert len(log1) == 1
    assert log1[0].canonical_finding_id == "cand-gen-1"
    assert log1[0].duplicate_finding_id == "cand-gen-2"

    # Case 2: Substantive finding text normalization
    c3 = CandidateFindingRecord(
        candidate_finding_id="cand-gen-3",
        contract_id="doc-006",
        contract_version=1,
        document_content_hash="hash_gen",
        clause_id="clause-2",
        clause_text="Other text",
        prediction_category="NON_COMPETE",
        raw_model_label="non_compete",
        candidate_finding_text="  Restrictive Covenant Observed!  ",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.88,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c4 = CandidateFindingRecord(
        candidate_finding_id="cand-gen-4",
        contract_id="doc-006",
        contract_version=1,
        document_content_hash="hash_gen",
        clause_id="clause-2",
        clause_text="Other text",
        prediction_category="NON_COMPETE",
        raw_model_label="non_compete",
        candidate_finding_text="restrictive covenant observed",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.88,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    can2, log2 = deduplicate_candidates([c3, c4])
    assert len(can2) == 1
    assert can2[0].candidate_finding_id == "cand-gen-3"
    assert len(log2) == 1
    assert log2[0].canonical_finding_id == "cand-gen-3"
    assert log2[0].duplicate_finding_id == "cand-gen-4"


def test_deduplication_deterministic_output():
    """
    Focused regression test: verify key calculation and deduplication output
    are 100% deterministic across multiple repeated runs.
    """
    candidate = CandidateFindingRecord(
        candidate_finding_id="cand-det-test",
        contract_id="doc-det",
        contract_version=3,
        document_content_hash="hash_det",
        clause_id="clause-det-1",
        clause_text="Deterministic test clause.",
        prediction_category="CONFIDENTIALITY",
        raw_model_label="confidentiality_label",
        candidate_finding_text="Confidentiality obligation present.",
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.92,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    # 10 identical invocations produce exact byte-for-byte identical key
    keys = [compute_deduplication_key(candidate) for _ in range(10)]
    assert len(set(keys)) == 1

    # Deserializes to expected 7 elements
    parsed = json.loads(keys[0])
    assert len(parsed) == 7
    assert parsed[0] == "doc-det"
    assert parsed[1] == 3
    assert parsed[2] == "clause-det-1"
    assert parsed[3] == "CONFIDENTIALITY"
    assert parsed[4] == "confidentiality_label"
    assert parsed[5] == "MODEL_INFERENCE_BATCH"
    assert parsed[6] == "confidentiality obligation present"


def test_deduplication_ordering_and_audit_log():
    """
    Focused regression test: verify order of first-seen canonical findings is
    strictly preserved, and duplicate audit log records all required fields.
    """
    c_first = CandidateFindingRecord(
        candidate_finding_id="cand-ord-1",
        contract_id="doc-007",
        contract_version=1,
        document_content_hash="hash_ord",
        clause_id="clause-ord-1",
        clause_text="First clause.",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.95,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c_second = CandidateFindingRecord(
        candidate_finding_id="cand-ord-2",
        contract_id="doc-007",
        contract_version=1,
        document_content_hash="hash_ord",
        clause_id="clause-ord-2",
        clause_text="Second clause.",
        prediction_category="WARRANTY",
        raw_model_label="warranty",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.89,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )
    c_first_dup = CandidateFindingRecord(
        candidate_finding_id="cand-ord-3",
        contract_id="doc-007",
        contract_version=1,
        document_content_hash="hash_ord",
        clause_id="clause-ord-1",
        clause_text="First clause.",
        prediction_category="INDEMNITY",
        raw_model_label="indemnity",
        candidate_finding_text=None,
        model_id="legal-bert",
        model_version="1.0",
        model_task="CLASSIFICATION",
        confidence_value=0.91,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
    )

    canonical, dup_log = deduplicate_candidates([c_first, c_second, c_first_dup])

    # Canonical findings retain exact arrival order of distinct keys
    assert [c.candidate_finding_id for c in canonical] == ["cand-ord-1", "cand-ord-2"]

    # Audit log accurately identifies duplicate
    assert len(dup_log) == 1
    entry = dup_log[0]
    assert entry.canonical_finding_id == "cand-ord-1"
    assert entry.duplicate_finding_id == "cand-ord-3"
    assert entry.contract_id == "doc-007"
    assert entry.clause_id == "clause-ord-1"
    assert entry.prediction_category == "INDEMNITY"
    assert entry.deduplication_key == compute_deduplication_key(c_first)


# =============================================================================
# STRATEGY A (STEP 5): ACTIVE CONFIGURATION HOOK TESTS
# =============================================================================

def test_active_configuration_processes_active_and_skips_inactive(sample_clauses):
    """
    Candidate pipeline hook: When active_configuration is supplied,
    inactive alternative clauses are skipped before model inference,
    while active alternatives and standard clauses are evaluated.
    """
    pipeline = CandidateGenerationPipeline(
        model_wrapper=None,
        label_mapper={"0": "INDEMNIFICATION"},
    )

    clauses = [
        # Standard non-alternative clause
        {
            "clause_id": "GCC-01.1",
            "text": "Standard general clause text here.",
            "is_drafting_alternative": False,
            "candidate_predictions": [{"raw_label": "0", "confidence": 0.85}],
        },
        # Alternative Group: Dispute Resolution - Option A (ACTIVE)
        {
            "clause_id": "GCC-24.2#OPT-A",
            "text": "Dispute resolution via Indian Arbitration and Conciliation Act 1996.",
            "is_drafting_alternative": True,
            "alternative_group_id": "ALT-GCC-24.2-DISPUTE-RESOLUTION",
            "alternative_id": "GCC-24.2#OPT-A",
            "candidate_predictions": [{"raw_label": "0", "confidence": 0.90}],
        },
        # Alternative Group: Dispute Resolution - Option B (INACTIVE)
        {
            "clause_id": "GCC-24.2#OPT-B",
            "text": "Dispute resolution via Adjudication Council.",
            "is_drafting_alternative": True,
            "alternative_group_id": "ALT-GCC-24.2-DISPUTE-RESOLUTION",
            "alternative_id": "GCC-24.2#OPT-B",
            "candidate_predictions": [{"raw_label": "0", "confidence": 0.95}],
        },
    ]

    active_config = ContractConfiguration(
        configuration_id="CFG-001",
        contract_id="doc-cfg-test",
        document_id="DOE-GOODS-2022-GCC",
        template_family_id="MACRO-FAM-DOE-PPD",
        active_clause_ids=["GCC-01.1", "GCC-24.2#OPT-A"],
        active_alternatives={"ALT-GCC-24.2-DISPUTE-RESOLUTION": "GCC-24.2#OPT-A"},
    )

    candidates, duplicates = pipeline.generate_candidates_for_clauses(
        contract_id="doc-cfg-test",
        contract_version=1,
        document_content_hash="hash-123456",
        clauses=clauses,
        is_synthetic_fixture=True,
        active_configuration=active_config,
    )

    candidate_clause_ids = [c.clause_id for c in candidates]
    # Standard clause GCC-01.1 and active alternative GCC-24.2#OPT-A are present
    assert "GCC-01.1" in candidate_clause_ids
    assert "GCC-24.2#OPT-A" in candidate_clause_ids
    # Inactive alternative GCC-24.2#OPT-B was skipped before inference
    assert "GCC-24.2#OPT-B" not in candidate_clause_ids
    assert len(candidates) == 2


def test_active_configuration_contract_id_mismatch_fails_closed():
    """Active configuration must match contract_id or raise ValueError."""
    pipeline = CandidateGenerationPipeline()
    active_config = ContractConfiguration(
        configuration_id="CFG-001",
        contract_id="contract-mismatch",
        document_id="doc-01",
        template_family_id="FAM-01",
    )

    with pytest.raises(ValueError, match="does not match"):
        pipeline.generate_candidates_for_clauses(
            contract_id="contract-expected",
            contract_version=1,
            document_content_hash="hash-abc",
            clauses=[{"clause_id": "c1", "text": "Clause text"}],
            active_configuration=active_config,
        )


def test_active_configuration_missing_group_selection_fails_closed():
    """Configuration missing selection for an alternative group present in clauses raises ValueError."""
    pipeline = CandidateGenerationPipeline()
    active_config = ContractConfiguration(
        configuration_id="CFG-001",
        contract_id="contract-01",
        document_id="doc-01",
        template_family_id="FAM-01",
        active_alternatives={},  # Empty: missing selection for group
    )

    clauses = [
        {
            "clause_id": "c1#opt-a",
            "text": "Clause option A text",
            "alternative_group_id": "ALT-GROUP-REQUIRED",
            "is_drafting_alternative": True,
        }
    ]

    with pytest.raises(ValueError, match="missing selection for alternative group"):
        pipeline.generate_candidates_for_clauses(
            contract_id="contract-01",
            contract_version=1,
            document_content_hash="hash-abc",
            clauses=clauses,
            active_configuration=active_config,
        )


def test_active_configuration_invalid_type_fails_closed():
    """Supplying an invalid type for active_configuration raises ValueError."""
    pipeline = CandidateGenerationPipeline()

    with pytest.raises(ValueError, match="must be a ContractConfiguration or dict"):
        pipeline.generate_candidates_for_clauses(
            contract_id="contract-01",
            contract_version=1,
            document_content_hash="hash-abc",
            clauses=[{"clause_id": "c1", "text": "Clause text"}],
            active_configuration="invalid-string-config",  # type: ignore
        )


def test_active_configuration_omitted_preserves_all_clauses():
    """When active_configuration is omitted (None), existing behavior processes all clauses."""
    pipeline = CandidateGenerationPipeline(
        model_wrapper=None,
        label_mapper={"0": "INDEMNIFICATION"},
    )
    clauses = [
        {
            "clause_id": "opt-a",
            "text": "Option A text",
            "is_drafting_alternative": True,
            "alternative_group_id": "ALT-GRP-1",
            "candidate_predictions": [{"raw_label": "0", "confidence": 0.88}],
        },
        {
            "clause_id": "opt-b",
            "text": "Option B text",
            "is_drafting_alternative": True,
            "alternative_group_id": "ALT-GRP-1",
            "candidate_predictions": [{"raw_label": "0", "confidence": 0.82}],
        },
    ]

    candidates, _ = pipeline.generate_candidates_for_clauses(
        contract_id="contract-01",
        contract_version=1,
        document_content_hash="hash-abc",
        clauses=clauses,
        is_synthetic_fixture=True,
        active_configuration=None,  # OMITTED
    )

    # Both clauses are evaluated when configuration is omitted
    assert len(candidates) == 2
    c_ids = [c.clause_id for c in candidates]
    assert "opt-a" in c_ids
    assert "opt-b" in c_ids


