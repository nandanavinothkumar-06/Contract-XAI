import sys
sys.path.insert(0, '.')
import json
import os
from typing import Dict, Tuple, Optional, Any

from src.models.legalbert import LegalBertWrapper
from src.models.config import LegalBertConfig
from src.models.prediction import predict
from src.evidence.extractor import EvidenceExtractor
from src.review.evidence import ClauseEvidenceRetriever
from src.abstention.evidence_policy import EvidenceAwarePolicy, EvidenceAwarePolicyConfig, PolicyAction
from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    LabelMappingStatus,
    VersionConsistencyStatus,
    CandidateOrigin,
)
from src.candidates.pipeline import generate_deterministic_finding_id, VALID_INDIAN_RISK_CATEGORIES

# Exact canonical LEDGAR taxonomy mapping verified against label_mapping.json
CANONICAL_LEDGAR_TAXONOMY_MAP = {
    # 1. GOVERNING_LAW_DISPUTE
    "governing laws": "GOVERNING_LAW_DISPUTE",
    "governing law: jurisdiction": "GOVERNING_LAW_DISPUTE",
    "submission to jurisdiction": "GOVERNING_LAW_DISPUTE",
    "jurisdiction": "GOVERNING_LAW_DISPUTE",
    "applicable law": "GOVERNING_LAW_DISPUTE",
    "choice of law": "GOVERNING_LAW_DISPUTE",

    # 2. INDEMNIFICATION
    "indemnity": "INDEMNIFICATION",
    "indemnification - general": "INDEMNIFICATION",
    "indemnification": "INDEMNIFICATION",
    "indemnifications": "INDEMNIFICATION",
    "additional indemnification": "INDEMNIFICATION",
    "additional indemnity": "INDEMNIFICATION",

    # 3. LIMITATION_OF_LIABILITY
    "limitation of liability": "LIMITATION_OF_LIABILITY",
    "limitation on liability": "LIMITATION_OF_LIABILITY",
    "limitations of liability": "LIMITATION_OF_LIABILITY",
    "limitations on liability": "LIMITATION_OF_LIABILITY",
    "limitation of consequential damages": "LIMITATION_OF_LIABILITY",
    "limitation of damages": "LIMITATION_OF_LIABILITY",
    "limits of liability": "LIMITATION_OF_LIABILITY",
    "liability limitations": "LIMITATION_OF_LIABILITY",

    # 4. CONFIDENTIALITY_UNILATERAL
    "confidentiality": "CONFIDENTIALITY_UNILATERAL",
    "confidential information": "CONFIDENTIALITY_UNILATERAL",
    "confidential terms": "CONFIDENTIALITY_UNILATERAL",
    "confidential": "CONFIDENTIALITY_UNILATERAL",
    "confidential agreement": "CONFIDENTIALITY_UNILATERAL",
    "confidentiality agreements": "CONFIDENTIALITY_UNILATERAL",

    # 5. TERMINATION_CONVENIENCE
    "termination for convenience": "TERMINATION_CONVENIENCE",
    "termination": "TERMINATION_CONVENIENCE",
    "termination by company": "TERMINATION_CONVENIENCE",
    "termination by company without cause": "TERMINATION_CONVENIENCE",
    "terminations": "TERMINATION_CONVENIENCE",

    # 6. ARBITRATION_EXCLUSIVE_JURISDICTION
    "arbitration": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "arbitration procedures": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "arbitration of disputes": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "arbitration agreements": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "agreement to arbitrate": "ARBITRATION_EXCLUSIVE_JURISDICTION",

    # 7. SEVERABILITY_RESTRAINT
    "severability": "SEVERABILITY_RESTRAINT",
    "severability clause": "SEVERABILITY_RESTRAINT",
    "severability of provisions": "SEVERABILITY_RESTRAINT",

    # 8. NON_COMPETE_RESTRAINT
    "non-compete agreements": "NON_COMPETE_RESTRAINT",
    "non-competition agreements": "NON_COMPETE_RESTRAINT",
    "non-competition covenants": "NON_COMPETE_RESTRAINT",
}

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"
with open(f"{model_dir}/label_mapping.json", "r") as f:
    lm = json.load(f)
l2i = lm.get("label2id", {})

mapping = {}
for name, cat in CANONICAL_LEDGAR_TAXONOMY_MAP.items():
    if name in l2i:
        mapping[int(l2i[name])] = (cat, name)

config = LegalBertConfig(
    model_name="ledgar-legalbert-frozen",
    model_family="legal-bert",
    model_checkpoint=model_dir,
    tokenizer_name=model_dir,
    num_labels=len(l2i),
    classification_mode="multilabel",
    multilabel_threshold=0.04
)
wrapper = LegalBertWrapper(config)
evidence_extractor = EvidenceExtractor(wrapper, method="GradientXInput")
evidence_retriever = ClauseEvidenceRetriever()
abstention_policy = EvidenceAwarePolicy(config=EvidenceAwarePolicyConfig(confidence_threshold=0.04))

clauses = [
    ("Governing Law", "This Agreement shall be governed by the laws of India. The courts of New Delhi shall have exclusive jurisdiction."),
    ("Indemnification", "The Contractor shall indemnify and hold harmless the Client against third-party claims, liabilities, damages, and reasonable expenses."),
    ("Limitation of Liability", "Neither party shall be liable for indirect or consequential damages, except where otherwise provided in this Agreement."),
    ("Confidentiality", "Each party shall protect confidential information received from the other party and shall not disclose it without authorization.")
]

print("=== VERIFYING REFINED SCREENING LOGIC ===")
for title, text in clauses:
    preds, probs, truncs = predict(wrapper, [text])
    prob_vec = probs[0]

    mapped_indices = list(mapping.keys())
    passing_candidates = [
        (idx, float(prob_vec[idx]), mapping[idx][0], mapping[idx][1])
        for idx in mapped_indices
        if float(prob_vec[idx]) >= 0.04
    ]

    if passing_candidates:
        passing_candidates.sort(key=lambda x: x[1], reverse=True)
        best_orig_idx, best_prob, pred_category, raw_label_name = passing_candidates[0]
        threshold_met = True
    else:
        sub_probs = prob_vec[mapped_indices]
        best_sub_idx = int(sub_probs.argmax())
        best_orig_idx = mapped_indices[best_sub_idx]
        best_prob = float(prob_vec[best_orig_idx])
        pred_category, raw_label_name = mapping[best_orig_idx]
        threshold_met = False

    # Evidence retrieval
    statutory_evidence_dict = evidence_retriever.retrieve_evidence_for_clause(
        clause_text=text,
        clause_id=f"seg_{title.lower().replace(' ', '_')}",
        source_document_id="doc_1",
        top_k=3,
        document_version_mismatch=False
    )
    eq_status = statutory_evidence_dict.get("evidence_quality_status", "NO_MATCHING_EVIDENCE")

    finding_id = generate_deterministic_finding_id(
        contract_id="doc_1",
        contract_version=1,
        clause_id=f"seg_{title.lower().replace(' ', '_')}",
        prediction_category=pred_category if threshold_met else "NO_ACTIONABLE_RISK",
        raw_model_label=str(best_orig_idx),
        model_id="nlpaueb/legal-bert-base-uncased",
    )

    missing_caps = ["UNCALIBRATED_RAW_SCORE"]
    if not threshold_met:
        missing_caps.append("BELOW_OPERATING_THRESHOLD")

    candidate = CandidateFindingRecord(
        candidate_finding_id=finding_id,
        contract_id="doc_1",
        contract_version=1,
        document_content_hash="content_hash",
        clause_id=f"seg_{title.lower().replace(' ', '_')}",
        clause_text=text,
        prediction_category=pred_category,
        raw_model_label=str(best_orig_idx),
        confidence_value=best_prob,
        confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
        confidence_is_calibrated=False,
        version_consistency_status=VersionConsistencyStatus.CONSISTENT,
        evidence_quality_status=eq_status,
        retrieved_passages=statutory_evidence_dict.get("passages", []),
        label_mapping_status=LabelMappingStatus.MAPPED,
        missing_capabilities=missing_caps,
        model_id="nlpaueb/legal-bert-base-uncased",
        model_version="1.0.0",
        model_task="MULTI_LABEL_PROVISION_CLASSIFICATION",
        origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
        is_disclosed_to_client=False,
    )

    policy_decision = abstention_policy.evaluate_candidate(candidate)
    is_withheld = (policy_decision.policy_action.value == "WITHHOLD")
    displayed_risk_label = "NO_ACTIONABLE_RISK" if is_withheld else pred_category

    # Attribution: Only compute if confirmed
    attribution_dict = None
    if not is_withheld:
        ev_result = evidence_extractor.extract(
            source_text=text,
            target_label_id=best_orig_idx,
            target_label_str=pred_category,
            top_k=3,
            document_id="doc_1",
            clause_id=f"seg_{title.lower().replace(' ', '_')}",
        )
        attribution_dict = {"spans": len(ev_result.evidence_spans)}

    print(f"\n[{title}]")
    print(f"  Threshold Met: {threshold_met}")
    print(f"  Displayed Risk Label: {displayed_risk_label}")
    print(f"  Best Prob: {best_prob:.4f} (Candidate: {raw_label_name})")
    print(f"  Policy Action: {policy_decision.policy_action.value} [{policy_decision.primary_reason_code.value}]")
    print(f"  Attribution Spans: {attribution_dict['spans'] if attribution_dict else 'None (Withheld)'}")
    print(f"  Statutory Quality: {eq_status}")
