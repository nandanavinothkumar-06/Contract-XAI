"""
Deterministic NLP Correctness and Validation Test Suite for CONTRACTRISK-XAI.

Tests:
1. Exact taxonomy index-to-label mapping against actual saved label_mapping.json.
2. Clause-to-finding association preventing false GOVERNING_LAW_DISPUTE labels on non-governing law clauses.
3. Attribution span alignment to exact input clause text and predicted output.
4. Abstention behavior verifying empirical operating threshold \u03c4* = 0.04 and ensuring
   withheld predictions are not presented as confirmed risks.
"""

import os
import json
import pytest

from src.review.screening import (
    ContractScreeningService,
    CANONICAL_LEDGAR_TAXONOMY_MAP,
    DEFAULT_MODEL_DIR,
)
from src.candidates.pipeline import VALID_INDIAN_RISK_CATEGORIES
from src.abstention.evidence_policy import PolicyAction, EvidencePolicyReasonCode


@pytest.fixture(scope="module")
def screening_service():
    """Initializes the real screening service with the authentic local LegalBERT model."""
    return ContractScreeningService(operating_threshold=0.04)


def test_saved_taxonomy_index_mapping():
    """
    Verifies that the index-to-label mapping is constructed strictly from the model's
    actual saved taxonomy (label_mapping.json) without heuristic substring guessing.
    """
    mapping_file = os.path.join(DEFAULT_MODEL_DIR, "label_mapping.json")
    assert os.path.exists(mapping_file), f"label_mapping.json missing at {mapping_file}"

    with open(mapping_file, "r", encoding="utf-8") as f:
        taxonomy = json.load(f)

    label2id = taxonomy.get("label2id", {})
    assert len(label2id) == 12407, f"Expected 12407 taxonomy labels, got {len(label2id)}"

    # Check canonical taxonomy mapping
    assert len(CANONICAL_LEDGAR_TAXONOMY_MAP) >= 35

    svc = ContractScreeningService(operating_threshold=0.04)
    mapping = svc.label_mapping
    assert len(mapping) == len(CANONICAL_LEDGAR_TAXONOMY_MAP)

    for idx, (cat, name) in mapping.items():
        # Assert label exists in actual saved taxonomy
        assert name in label2id
        assert int(label2id[name]) == idx
        # Assert mapped category belongs to valid Indian commercial risk categories
        assert cat in VALID_INDIAN_RISK_CATEGORIES

    # Verify critical boundary labels in LEDGAR
    assert "governing laws" in label2id
    gov_idx = int(label2id["governing laws"])
    assert mapping[gov_idx] == ("GOVERNING_LAW_DISPUTE", "governing laws")

    assert "limitation on liability" in label2id
    lim_idx = int(label2id["limitation on liability"])
    assert mapping[lim_idx] == ("LIMITATION_OF_LIABILITY", "limitation on liability")

    assert "confidentiality" in label2id
    conf_idx = int(label2id["confidentiality"])
    assert mapping[conf_idx] == ("CONFIDENTIALITY_UNILATERAL", "confidentiality")

    assert "indemnifications" in label2id
    ind_idx = int(label2id["indemnifications"])
    assert mapping[ind_idx] == ("INDEMNIFICATION", "indemnifications")


def test_clause_to_finding_association_and_no_false_governing_law(screening_service):
    """
    Verifies that clauses involving confidentiality and limitation of liability
    are NOT assigned GOVERNING_LAW_DISPUTE as confirmed risks.
    """
    confidentiality_clause = (
        "Each party shall protect confidential information received from the other party "
        "and shall not disclose it to any third party without prior authorization."
    )
    limitation_clause = (
        "Neither party shall be liable for indirect, incidental, or consequential damages, "
        "except where otherwise provided in this Agreement."
    )
    governing_law_clause = (
        "This Agreement shall be governed by the substantive laws of India. "
        "The courts of New Delhi shall have exclusive jurisdiction."
    )

    # 1. Governing Law Clause
    res_gov = screening_service.screen_clause(
        clause_text=governing_law_clause,
        clause_id="seg_gov_01",
        document_id="doc_test_nlp",
    )
    assert res_gov is not None
    assert res_gov["risk_label"] == "GOVERNING_LAW_DISPUTE"
    assert res_gov["policy_action"] == PolicyAction.ACCEPT.value
    assert float(res_gov["ai_confidence_score"]) >= 0.04

    # 2. Confidentiality Clause must NOT be presented as GOVERNING_LAW_DISPUTE
    res_conf = screening_service.screen_clause(
        clause_text=confidentiality_clause,
        clause_id="seg_conf_01",
        document_id="doc_test_nlp",
    )
    assert res_conf is not None
    assert res_conf["risk_label"] != "GOVERNING_LAW_DISPUTE"
    assert res_conf["risk_label"] in ("NO_ACTIONABLE_RISK", "CONFIDENTIALITY_UNILATERAL")

    # 3. Limitation of Liability Clause must NOT be presented as GOVERNING_LAW_DISPUTE
    res_lim = screening_service.screen_clause(
        clause_text=limitation_clause,
        clause_id="seg_lim_01",
        document_id="doc_test_nlp",
    )
    assert res_lim is not None
    assert res_lim["risk_label"] != "GOVERNING_LAW_DISPUTE"
    assert res_lim["risk_label"] in ("NO_ACTIONABLE_RISK", "LIMITATION_OF_LIABILITY")


def test_abstention_behavior_and_withheld_predictions_presentation(screening_service):
    """
    Verifies that abstention uses the empirical operating threshold \u03c4* = 0.04 and
    that withheld predictions are presented as NO_ACTIONABLE_RISK, not as confirmed risks.
    """
    below_thresh_clause = (
        "Each party shall protect confidential information received from the other party "
        "and shall not disclose it without authorization."
    )
    res = screening_service.screen_clause(
        clause_text=below_thresh_clause,
        clause_id="seg_withheld_01",
        document_id="doc_test_abstention",
    )
    assert res is not None

    meta = json.loads(res["ai_metadata_json"])
    assert meta["calibrated_threshold"] == 0.04
    score = float(res["ai_confidence_score"])

    # If score is below operating threshold, policy action must be WITHHOLD
    if score < 0.04:
        assert res["policy_action"] == PolicyAction.WITHHOLD.value
        assert res["risk_label"] == "NO_ACTIONABLE_RISK"
        assert "Below Operating Threshold" in res["ai_observation"]
        assert meta["policy_action"] == PolicyAction.WITHHOLD.value
        assert meta["policy_tier_applied"] in (3, 4)
    else:
        assert res["policy_action"] == PolicyAction.ACCEPT.value


def test_attribution_span_alignment_and_clause_correspondence(screening_service):
    """
    Verifies that attribution spans correspond to the exact input clause and predicted output,
    and that withheld predictions do not attach misleading explanation spans.
    """
    governing_law_clause = (
        "This Agreement shall be governed by the laws of India. "
        "The courts of New Delhi shall have exclusive jurisdiction."
    )
    res = screening_service.screen_clause(
        clause_text=governing_law_clause,
        clause_id="seg_gov_align",
        document_id="doc_test_align",
    )
    assert res is not None
    assert res["policy_action"] == PolicyAction.ACCEPT.value
    assert res["model_attribution_json"] is not None

    attr = json.loads(res["model_attribution_json"])
    assert attr["method"] == "GradientXInput"
    assert attr["target_label"] == res["risk_label"]
    assert len(attr["attributed_spans"]) > 0

    # Verify character offsets match exact input clause substring
    for span in attr["attributed_spans"]:
        start = span["source_start"]
        end = span["source_end"]
        expected_text = governing_law_clause[start:end]
        assert span["text"] == expected_text, (
            f"Span text mismatch: expected {repr(expected_text)}, got {repr(span['text'])}"
        )

    # Verify withheld clause receives no attribution spans
    withheld_clause = (
        "Each party shall protect confidential information received from the other party "
        "and shall not disclose it without authorization."
    )
    res_withheld = screening_service.screen_clause(
        clause_text=withheld_clause,
        clause_id="seg_withheld_attr",
        document_id="doc_test_align",
    )
    assert res_withheld is not None
    if res_withheld["policy_action"] == PolicyAction.WITHHOLD.value:
        assert res_withheld["model_attribution_json"] is None
