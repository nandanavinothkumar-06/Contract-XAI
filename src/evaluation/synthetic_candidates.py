"""
Deterministic Synthetic Candidate Dataset Generator for CONTRACTRISK-XAI.

Generates reproducible pools of synthetic CandidateFindingRecord fixtures and
ground-truth ReferenceDecision labels for offline evaluation of abstention policies.

Strict Invariants:
1. All generated data is SYNTHETIC and FICTIONAL.
2. Every record explicitly sets `is_synthetic_fixture = True` and `is_disclosed_to_client = False`.
3. Generator is 100% deterministic given a fixed random seed.
4. Candidate findings exhibit realistic structural clustering (multiple clauses per contract).
5. Explicitly constructs required research edge cases:
   - High confidence + stale document version
   - High confidence + repealed/struck down statute
   - High confidence + hallucinated assertion
   - Low confidence + traceable statutory match
   - High severity + insufficient evidence (safety net)
   - High severity + missing statutory match
   - Non-statutory commercial drafting finding without statutory citation
   - Unknown document version lineage
   - Unverified statutory source / partial extraction
   - Unsupported model label mappings
   - Unassessable candidate (empty clause text)
"""

import random
from typing import List, Dict, Tuple, Optional, Any
from pydantic import BaseModel, ConfigDict, Field

from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    VersionConsistencyStatus,
    LabelMappingStatus,
    CandidateOrigin,
)
from src.evaluation.abstention_eval import ReferenceDecision


SYNTHETIC_DATA_DISCLAIMER = (
    "SYNTHETIC ENGINEERING VALIDATION — NOT REAL-CONTRACT EVIDENCE. "
    "Fictional synthetic candidates and mock labels for software evaluation only. "
    "Does NOT represent real-world legal risk or advocate review decisions."
)

STATUTORY_CATEGORIES = [
    "INDEMNIFICATION",
    "LIMITATION_OF_LIABILITY",
    "TERMINATION_CONVENIENCE",
    "NON_COMPETE_RESTRAINT",
    "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "CONFIDENTIALITY_UNILATERAL",
    "SEVERABILITY_RESTRAINT",
]

NON_STATUTORY_CATEGORIES = [
    "PRICE_ADJUSTMENT",
    "PAYMENT_TERMS",
    "NOTICE_PERIOD",
    "COMMERCIAL_DRAFTING_AMBIGUITY",
]


class SyntheticEvaluationDataset(BaseModel):
    """Container holding a reproducible synthetic evaluation candidate pool."""
    model_config = ConfigDict(extra="forbid")

    seed: int
    total_candidates: int
    unique_contracts: int
    candidates: List[CandidateFindingRecord]
    reference_annotations: Dict[str, ReferenceDecision]
    explicit_severities: Dict[str, str] = Field(default_factory=dict)
    disclaimer: str = SYNTHETIC_DATA_DISCLAIMER
    metadata: Dict[str, Any] = Field(default_factory=dict)


def generate_synthetic_candidate_pool(
    seed: int = 42,
    num_contracts: int = 15,
    clauses_per_contract: int = 4,
    additional_random_count: int = 40,
) -> SyntheticEvaluationDataset:
    """
    Constructs a deterministic synthetic candidate dataset containing both
    curated edge cases and seeded variations.

    Args:
        seed: Random seed for deterministic reproducibility.
        num_contracts: Number of distinct synthetic contract document clusters.
        clauses_per_contract: Number of clause segments per synthetic contract.
        additional_random_count: Additional seeded candidate findings to generate.

    Returns:
        SyntheticEvaluationDataset containing candidates, reference annotations, and metadata.
    """
    rng = random.Random(seed)

    candidates: List[CandidateFindingRecord] = []
    reference_annotations: Dict[str, ReferenceDecision] = []
    ref_dict: Dict[str, ReferenceDecision] = {}
    severity_dict: Dict[str, str] = {}

    finding_counter = 0

    def _next_id() -> str:
        nonlocal finding_counter
        finding_counter += 1
        return f"synth-cand-{seed}-{finding_counter:04d}"

    # =========================================================================
    # PART 1: DETERMINISTIC CURATED RESEARCH EDGE CASES
    # =========================================================================

    # Edge Case 1: Grounded Statutory Finding (Ideal Retainable)
    cid_1 = _next_id()
    c1 = CandidateFindingRecord(
        candidate_finding_id=cid_1,
        contract_id="synth-doc-001",
        contract_version=1,
        document_content_hash="sha256-doc-001-v1",
        clause_id="clause-indemnity-01",
        clause_text="Vendor shall indemnify Customer against all third-party IP infringement claims.",
        prediction_category="INDEMNIFICATION",
        raw_model_label="0",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.88,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="TRACEABLE",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "124",
            "passage_text": "A contract by which one party promises to save the other from loss caused to him...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "MEDIUM", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c1)
    ref_dict[cid_1] = ReferenceDecision.RETAIN
    severity_dict[cid_1] = "MEDIUM"

    # Edge Case 2: Valid Non-Statutory Commercial Drafting Finding
    cid_2 = _next_id()
    c2 = CandidateFindingRecord(
        candidate_finding_id=cid_2,
        contract_id="synth-doc-001",
        contract_version=1,
        document_content_hash="sha256-doc-001-v1",
        clause_id="clause-price-02",
        clause_text="Fees shall increase annually based on the published Consumer Price Index plus 5%.",
        prediction_category="PRICE_ADJUSTMENT",
        raw_model_label="1",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.85,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="NO_MATCHING_EVIDENCE",
        retrieved_passages=[],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "LOW", "is_statutory": False},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c2)
    ref_dict[cid_2] = ReferenceDecision.RETAIN
    severity_dict[cid_2] = "LOW"

    # Edge Case 3: High Confidence Model Hallucination on Stale Document Version
    cid_3 = _next_id()
    c3 = CandidateFindingRecord(
        candidate_finding_id=cid_3,
        contract_id="synth-doc-002",
        contract_version=1,
        document_content_hash="sha256-doc-002-v1",
        clause_id="clause-superseded-01",
        clause_text="[Superseded Draft Text] Either party may terminate immediately without cause.",
        prediction_category="TERMINATION_CONVENIENCE",
        raw_model_label="2",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.96,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="TRACEABLE",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "39",
            "passage_text": "Effect of refusal of party to perform promise wholly...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=VersionConsistencyStatus.STALE, # Fatal Defect!
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "HIGH", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c3)
    ref_dict[cid_3] = ReferenceDecision.WITHHOLD
    severity_dict[cid_3] = "HIGH"

    # Edge Case 4: High Confidence Citing Repealed / Inapplicable Statute
    cid_4 = _next_id()
    c4 = CandidateFindingRecord(
        candidate_finding_id=cid_4,
        contract_id="synth-doc-002",
        contract_version=2,
        document_content_hash="sha256-doc-002-v2",
        clause_id="clause-goods-02",
        clause_text="Title to equipment shall pass upon delivery at the port of destination.",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="3",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.93,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="SOURCE_UNVERIFIED",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "76",
            "passage_text": "[Repealed by Sale of Goods Act 1930] 'Goods' defined.",
            "legal_status": "REPEALED",
            "currentness_status": "REPEALED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": ["REPEALED_PROVISION"],
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "MEDIUM", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c4)
    ref_dict[cid_4] = ReferenceDecision.WITHHOLD
    severity_dict[cid_4] = "MEDIUM"

    # Edge Case 5: Spurious Model Hallucination on Non-Damages Clause
    cid_5 = _next_id()
    c5 = CandidateFindingRecord(
        candidate_finding_id=cid_5,
        contract_id="synth-doc-003",
        contract_version=1,
        document_content_hash="sha256-doc-003-v1",
        clause_id="clause-notices-01",
        clause_text="All notices shall be sent by registered post or courier to the registered address.",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="3",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.91,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="INSUFFICIENT",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "73",
            "passage_text": "Compensation for loss or damage caused by breach of contract...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "LOW", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c5)
    ref_dict[cid_5] = ReferenceDecision.WITHHOLD
    severity_dict[cid_5] = "LOW"

    # Edge Case 6: High Severity Risk with Incomplete Statutory Evidence (Safety Net Trigger)
    cid_6 = _next_id()
    c6 = CandidateFindingRecord(
        candidate_finding_id=cid_6,
        contract_id="synth-doc-003",
        contract_version=1,
        document_content_hash="sha256-doc-003-v1",
        clause_id="clause-covenant-02",
        clause_text="Employee shall not engage in any competitive commercial activity in India for 3 years.",
        prediction_category="NON_COMPETE_RESTRAINT",
        raw_model_label="4",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.82,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="INSUFFICIENT", # Incomplete extract
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "27",
            "passage_text": "Agreement in restraint of trade, void [Excerpt omits goodwill exception]...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": ["INCOMPLETE_PROVISION_EXTRACT"],
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "HIGH", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c6)
    ref_dict[cid_6] = ReferenceDecision.HUMAN_REVIEW_REQUIRED
    severity_dict[cid_6] = "HIGH"

    # Edge Case 7: High Severity Risk Missing Statutory Match
    cid_7 = _next_id()
    c7 = CandidateFindingRecord(
        candidate_finding_id=cid_7,
        contract_id="synth-doc-004",
        contract_version=1,
        document_content_hash="sha256-doc-004-v1",
        clause_id="clause-arbitration-01",
        clause_text="All disputes shall be referred exclusively to private mediation with no right of legal appeal.",
        prediction_category="ARBITRATION_EXCLUSIVE_JURISDICTION",
        raw_model_label="5",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.79,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="NO_MATCHING_EVIDENCE",
        retrieved_passages=[],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "HIGH", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c7)
    ref_dict[cid_7] = ReferenceDecision.HUMAN_REVIEW_REQUIRED
    severity_dict[cid_7] = "HIGH"

    # Edge Case 8: Cited Provision with Text Difference / Editorial Note
    cid_8 = _next_id()
    c8 = CandidateFindingRecord(
        candidate_finding_id=cid_8,
        contract_id="synth-doc-004",
        contract_version=1,
        document_content_hash="sha256-doc-004-v1",
        clause_id="clause-privacy-02",
        clause_text="Vendor shall implement industry standard security practices for sensitive personal data.",
        prediction_category="CONFIDENTIALITY_UNILATERAL",
        raw_model_label="6",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.76,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="PARTIAL",
        retrieved_passages=[{
            "statute_id": "IN_ACT_2000_21",
            "section_number": "43A",
            "passage_text": "Compensation for failure to protect data [Note: Subject to SPDI Rules 2011]...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": ["TEXT_DIFFERENCE: Researcher editorial note added"],
            "has_text_difference": True,
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "MEDIUM", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c8)
    ref_dict[cid_8] = ReferenceDecision.HUMAN_REVIEW_REQUIRED
    severity_dict[cid_8] = "MEDIUM"

    # Edge Case 9: Default Rule with Permitted Contractual Override
    cid_9 = _next_id()
    c9 = CandidateFindingRecord(
        candidate_finding_id=cid_9,
        contract_id="synth-doc-005",
        contract_version=1,
        document_content_hash="sha256-doc-005-v1",
        clause_id="clause-notice-override-01",
        clause_text="Parties agree that termination notice of 7 days shall override any statutory default period.",
        prediction_category="TERMINATION_CONVENIENCE",
        raw_model_label="2",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.84,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="TRACEABLE",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "39",
            "passage_text": "Effect of refusal of party to perform promise wholly...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={
            "identified_risk_severity": "MEDIUM",
            "contractual_override_permitted": True,
            "is_statutory": True,
        },
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c9)
    ref_dict[cid_9] = ReferenceDecision.HUMAN_REVIEW_REQUIRED
    severity_dict[cid_9] = "MEDIUM"

    # Edge Case 10: Unknown Document Version Lineage
    cid_10 = _next_id()
    c10 = CandidateFindingRecord(
        candidate_finding_id=cid_10,
        contract_id="synth-doc-005",
        contract_version=1,
        document_content_hash="sha256-doc-005-v1",
        clause_id="clause-unknown-v-02",
        clause_text="Neither party shall assign its rights under this Agreement without prior written consent.",
        prediction_category="SEVERABILITY_RESTRAINT",
        raw_model_label="7",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.78,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="TRACEABLE",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "24",
            "passage_text": "Agreements void, if considerations and objects unlawful in part...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=VersionConsistencyStatus.UNKNOWN,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "MEDIUM", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c10)
    ref_dict[cid_10] = ReferenceDecision.HUMAN_REVIEW_REQUIRED
    severity_dict[cid_10] = "MEDIUM"

    # Edge Case 11: Unsupported Model Label Space
    cid_11 = _next_id()
    c11 = CandidateFindingRecord(
        candidate_finding_id=cid_11,
        contract_id="synth-doc-006",
        contract_version=1,
        document_content_hash="sha256-doc-006-v1",
        clause_id="clause-sec-item-01",
        clause_text="Executive compensation disclosures shall conform to SEC Regulation S-K Item 402.",
        prediction_category="UNMAPPED_sec_item_402",
        raw_model_label="sec_item_402",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.86,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="NO_MATCHING_EVIDENCE",
        retrieved_passages=[],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE", "UNSUPPORTED_MODEL_LABEL_SPACE"],
        source_document_provenance={"identified_risk_severity": "LOW", "is_statutory": False},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c11)
    ref_dict[cid_11] = ReferenceDecision.WITHHOLD
    severity_dict[cid_11] = "LOW"

    # Edge Case 12: Low Confidence but Genuinely Traceable Evidence (Threshold Boundary)
    cid_12 = _next_id()
    c12 = CandidateFindingRecord(
        candidate_finding_id=cid_12,
        contract_id="synth-doc-006",
        contract_version=1,
        document_content_hash="sha256-doc-006-v1",
        clause_id="clause-low-conf-02",
        clause_text="In no event shall aggregate liability exceed total fees paid in the prior 12 months.",
        prediction_category="LIMITATION_OF_LIABILITY",
        raw_model_label="3",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.35, # Low confidence
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="TRACEABLE",
        retrieved_passages=[{
            "statute_id": "IN_ACT_1872_09",
            "section_number": "73",
            "passage_text": "Compensation for loss or damage caused by breach of contract...",
            "legal_status": "IN_FORCE_CONFIRMED",
            "currentness_status": "IN_FORCE_CONFIRMED",
            "verification_status": "PARTIALLY_VERIFIED",
            "warnings": [],
        }],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "MEDIUM", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c12)
    ref_dict[cid_12] = ReferenceDecision.RETAIN # True finding, but low confidence model score
    severity_dict[cid_12] = "MEDIUM"

    # Edge Case 13: Unassessable / Corrupt Clause Text
    cid_13 = _next_id()
    c13 = CandidateFindingRecord(
        candidate_finding_id=cid_13,
        contract_id="synth-doc-007",
        contract_version=1,
        document_content_hash="sha256-doc-007-v1",
        clause_id="clause-corrupt-01",
        clause_text="   ", # Blank text
        prediction_category="INDEMNIFICATION",
        raw_model_label="0",
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="CLASSIFICATION",
        confidence_value=0.60,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        evidence_quality_status="INSUFFICIENT",
        retrieved_passages=[],
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
        source_document_provenance={"identified_risk_severity": "NOT_APPLICABLE", "is_statutory": True},
        origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
        is_synthetic_fixture=True,
        is_disclosed_to_client=False,
    )
    candidates.append(c13)
    ref_dict[cid_13] = ReferenceDecision.NOT_ASSESSABLE
    severity_dict[cid_13] = "NOT_APPLICABLE"

    # =========================================================================
    # PART 2: SEEDED STATISTICAL CLUSTER GENERATION
    # =========================================================================

    for i in range(additional_random_count):
        cid = _next_id()
        contract_num = (i % (num_contracts - 7)) + 8
        contract_id = f"synth-doc-{contract_num:03d}"
        clause_id = f"clause-gen-{(i % clauses_per_contract) + 1:02d}"

        # Choose category type
        is_statutory = rng.random() > 0.3
        if is_statutory:
            category = rng.choice(STATUTORY_CATEGORIES)
        else:
            category = rng.choice(NON_STATUTORY_CATEGORIES)

        # Seeded continuous confidence in [0.10, 0.98]
        confidence = round(rng.uniform(0.10, 0.98), 4)

        # Version status distribution: mostly CONSISTENT, some STALE, few UNKNOWN
        v_rand = rng.random()
        if v_rand < 0.80:
            version_status = VersionConsistencyStatus.CONSISTENT
        elif v_rand < 0.95:
            version_status = VersionConsistencyStatus.STALE
        else:
            version_status = VersionConsistencyStatus.UNKNOWN

        # Evidence quality status distribution
        if not is_statutory:
            ev_status = "NO_MATCHING_EVIDENCE"
            passages = []
        else:
            e_rand = rng.random()
            if e_rand < 0.50:
                ev_status = "TRACEABLE"
                passages = [{
                    "statute_id": "IN_ACT_1872_09",
                    "section_number": str(rng.randint(10, 130)),
                    "passage_text": f"Statutory provision text excerpt for {category}...",
                    "legal_status": "IN_FORCE_CONFIRMED",
                    "currentness_status": "IN_FORCE_CONFIRMED",
                    "verification_status": "PARTIALLY_VERIFIED",
                    "warnings": [],
                }]
            elif e_rand < 0.75:
                ev_status = "INSUFFICIENT"
                passages = []
            elif e_rand < 0.90:
                ev_status = "PARTIAL"
                passages = [{
                    "statute_id": "IN_ACT_2000_21",
                    "section_number": "N/A",
                    "passage_text": "Partial extract lacking subsection...",
                    "legal_status": "IN_FORCE_CONFIRMED",
                    "currentness_status": "IN_FORCE_CONFIRMED",
                    "verification_status": "PARTIALLY_VERIFIED",
                    "warnings": [],
                }]
            else:
                ev_status = "NO_MATCHING_EVIDENCE"
                passages = []

        # Severity
        s_rand = rng.random()
        severity = "HIGH" if s_rand < 0.25 else ("MEDIUM" if s_rand < 0.70 else "LOW")

        # Ground-truth reference label generation based on synthetic ground truth
        # (independent from policy outcomes)
        if version_status == VersionConsistencyStatus.STALE:
            ref_decision = ReferenceDecision.WITHHOLD
        elif severity == "HIGH" and ev_status in ("INSUFFICIENT", "NO_MATCHING_EVIDENCE") and is_statutory:
            ref_decision = ReferenceDecision.HUMAN_REVIEW_REQUIRED
        elif ev_status == "TRACEABLE" and version_status == VersionConsistencyStatus.CONSISTENT:
            # 80% genuine retainable, 20% spurious model false assertion
            ref_decision = ReferenceDecision.RETAIN if rng.random() < 0.80 else ReferenceDecision.WITHHOLD
        elif not is_statutory and version_status == VersionConsistencyStatus.CONSISTENT:
            ref_decision = ReferenceDecision.RETAIN if rng.random() < 0.75 else ReferenceDecision.WITHHOLD
        else:
            ref_decision = ReferenceDecision.WITHHOLD

        cand = CandidateFindingRecord(
            candidate_finding_id=cid,
            contract_id=contract_id,
            contract_version=1,
            document_content_hash=f"sha256-{contract_id}-v1",
            clause_id=clause_id,
            clause_text=f"Synthetic commercial contract clause text for {category} ({clause_id}).",
            prediction_category=category,
            raw_model_label=str(rng.randint(0, 15)),
            model_id="nlpaueb/legal-bert-base-uncased",
            model_version="1.0.0",
            model_task="CLASSIFICATION",
            confidence_value=confidence,
            confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
            confidence_is_calibrated=False,
            evidence_quality_status=ev_status,
            retrieved_passages=passages,
            version_consistency_status=version_status,
            label_mapping_status=LabelMappingStatus.MAPPED,
            missing_capabilities=["UNCALIBRATED_RAW_SCORE"],
            source_document_provenance={"identified_risk_severity": severity, "is_statutory": is_statutory},
            origin=CandidateOrigin.SYNTHETIC_TEST_FIXTURE,
            is_synthetic_fixture=True,
            is_disclosed_to_client=False,
        )
        candidates.append(cand)
        ref_dict[cid] = ref_decision
        severity_dict[cid] = severity

    # Compute unique contract count
    unique_contracts = len(set(c.contract_id for c in candidates))

    return SyntheticEvaluationDataset(
        seed=seed,
        total_candidates=len(candidates),
        unique_contracts=unique_contracts,
        candidates=candidates,
        reference_annotations=ref_dict,
        explicit_severities=severity_dict,
        disclaimer=SYNTHETIC_DATA_DISCLAIMER,
        metadata={
            "curated_edge_cases": 13,
            "additional_seeded_candidates": additional_random_count,
            "statutory_categories": STATUTORY_CATEGORIES,
            "non_statutory_categories": NON_STATUTORY_CATEGORIES,
        }
    )


PERTURBED_DATA_DISCLAIMER = (
    "SYNTHETIC ENGINEERING VALIDATION (PERTURBED METADATA FIXTURE) — NOT REAL-CONTRACT EVIDENCE. "
    "Fictional synthetic candidates with controlled reference-label perturbations to evaluate "
    "policy robustness under imperfect metadata and decoupled reference decisions. "
    "Does NOT represent real-world legal risk or advocate review decisions."
)


def generate_perturbed_candidate_pool(
    seed: int = 42,
    num_contracts: int = 15,
    clauses_per_contract: int = 4,
    additional_random_count: int = 45,
    perturbation_rate: float = 0.20,
) -> SyntheticEvaluationDataset:
    """
    Constructs a deterministic synthetic evaluation pool with controlled perturbations
    that decouple reference decisions from the strict rule-matching heuristics of the
    baseline generator.

    Addresses synthetic-label circularity by testing policy sensitivity to:
    1. Human-annotator disagreement on retainability (marking traceable findings as REVIEW or WITHHOLD).
    2. Over-optimistic retrieval (statute retrieved as TRACEABLE, but legal expert marks WITHHOLD).
    3. Latent drafting ambiguity in non-statutory commercial provisions.

    Invariants:
    - Fixed seed ensures 100% determinism.
    - Contract-cluster structure is preserved.
    - Reference labels remain strictly unavailable to operational policy evaluation.
    - Explicitly labeled as a synthetic engineering stress fixture.
    """
    # 1. Generate base dataset
    base = generate_synthetic_candidate_pool(
        seed=seed,
        num_contracts=num_contracts,
        clauses_per_contract=clauses_per_contract,
        additional_random_count=additional_random_count,
    )

    # 2. Deterministic perturbation RNG
    rng = random.Random(seed + 9999)
    perturbed_refs: Dict[str, ReferenceDecision] = {}
    perturbed_severities: Dict[str, str] = dict(base.explicit_severities)
    perturbation_records: List[Dict[str, Any]] = []

    for cand in base.candidates:
        cid = cand.candidate_finding_id
        original_ref = base.reference_annotations[cid]

        # Check if candidate is unassessable - preserve unassessable integrity
        if original_ref == ReferenceDecision.NOT_ASSESSABLE or not cand.clause_text.strip():
            perturbed_refs[cid] = ReferenceDecision.NOT_ASSESSABLE
            continue

        if rng.random() < perturbation_rate:
            # Apply controlled perturbation to reference label
            if original_ref == ReferenceDecision.RETAIN:
                if rng.random() < 0.50:
                    new_ref = ReferenceDecision.HUMAN_REVIEW_REQUIRED
                    reason = "Annotator identified latent contractual ambiguity not captured by lexical retrieval."
                else:
                    new_ref = ReferenceDecision.WITHHOLD
                    reason = "Annotator ruled statutory match legally inapplicable to transaction context."
            elif original_ref == ReferenceDecision.WITHHOLD:
                if rng.random() < 0.50:
                    new_ref = ReferenceDecision.RETAIN
                    reason = "Commercial custom validates finding despite absence of central statutory section."
                else:
                    new_ref = ReferenceDecision.HUMAN_REVIEW_REQUIRED
                    reason = "Complex factual determination requires advocate consultation."
            else:  # HUMAN_REVIEW_REQUIRED
                new_ref = ReferenceDecision.WITHHOLD
                reason = "Advocate preliminary assessment ruled risk de minimis."

            perturbed_refs[cid] = new_ref
            perturbation_records.append({
                "candidate_finding_id": cid,
                "original_reference": original_ref.value,
                "perturbed_reference": new_ref.value,
                "rationale": reason,
            })
        else:
            perturbed_refs[cid] = original_ref

    return SyntheticEvaluationDataset(
        seed=seed,
        total_candidates=base.total_candidates,
        unique_contracts=base.unique_contracts,
        candidates=base.candidates,
        reference_annotations=perturbed_refs,
        explicit_severities=perturbed_severities,
        disclaimer=PERTURBED_DATA_DISCLAIMER,
        metadata={
            "base_seed": seed,
            "perturbation_rate": perturbation_rate,
            "perturbed_candidates_count": len(perturbation_records),
            "perturbations": perturbation_records,
            "curated_edge_cases": base.metadata.get("curated_edge_cases", 13),
            "additional_seeded_candidates": additional_random_count,
        }
    )
