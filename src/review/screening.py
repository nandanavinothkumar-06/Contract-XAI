"""
Core NLP Contract Screening Service for CONTRACTRISK-XAI.

Orchestrates the complete end-to-end NLP workflow:
Contract upload / Ingested text
  → Text extraction snapshot
  → Preprocessing
  → Clause segmentation
  → LegalBERT tokenization and inference (authentic local checkpoint)
  → Risk-label prediction (mapped to Indian commercial risk categories)
  → Gradient x Input explainability (character-offset aligned token saliency)
  → BM25 statutory retrieval (Okapi BM25 across 6 Indian commercial statutes)
  → Evidence-aware abstention (5-tier hierarchical decision cascade)
  → Reviewable prediction output (persisted into database clause findings).
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from src.models.config import LegalBertConfig
from src.models.legalbert import LegalBertWrapper
from src.models.prediction import predict
from src.evidence.extractor import EvidenceExtractor
from src.evidence.schema import EvidenceResult
from src.review.evidence import ClauseEvidenceRetriever
from src.abstention.evidence_policy import (
    EvidenceAwarePolicy,
    EvidenceAwarePolicyConfig,
    EvidencePolicyReasonCode,
    PolicyAction,
)
from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    LabelMappingStatus,
    VersionConsistencyStatus,
    CandidateOrigin,
)
from src.candidates.pipeline import (
    generate_deterministic_finding_id,
    VALID_INDIAN_RISK_CATEGORIES,
)
from src.review.service import ReviewService
from src.persistence.models import (
    DocumentRecord,
    SegmentRecord,
    ReviewRecord,
    ClauseFindingRecord,
    EvidenceQualityStatus,
)

logger = logging.getLogger("contractrisk.nlp_screening")

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_MODEL_DIR = os.path.join(
    WORKSPACE_ROOT, "results", "models", "ledgar_frozen_subset_fresh", "final_model"
)

# Canonical LEDGAR taxonomy mapping verified against results/models/ledgar_frozen_subset_fresh/final_model/label_mapping.json
# Maps exact saved LEDGAR labels to standard Indian commercial risk categories without heuristic name guessing.
CANONICAL_LEDGAR_TAXONOMY_MAP: Dict[str, str] = {
    # 1. GOVERNING_LAW_DISPUTE
    "governing laws": "GOVERNING_LAW_DISPUTE",
    "governing law: jurisdiction": "GOVERNING_LAW_DISPUTE",
    "submission to jurisdiction": "GOVERNING_LAW_DISPUTE",

    # 2. INDEMNIFICATION
    "indemnity": "INDEMNIFICATION",
    "indemnification - general": "INDEMNIFICATION",
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


class ContractScreeningService:
    """
    Executes the end-to-end NLP screening pipeline across segmented contract clauses.
    Ensures that uploaded text reaches actual model inference without substituting
    static demo findings, and links predictions, Gradient x Input explanations,
    BM25 retrieved provisions, and abstention decisions to the exact input clauses.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        model_wrapper: Optional[LegalBertWrapper] = None,
        operating_threshold: float = 0.04,
    ):
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        self.operating_threshold = operating_threshold

        # 1. Model Wrapper Initialization
        if model_wrapper is not None:
            self.model_wrapper = model_wrapper
        else:
            self.model_wrapper = self._init_model_wrapper(self.model_dir, self.operating_threshold)

        # 2. Gradient x Input Explainability Extractor
        self.evidence_extractor = EvidenceExtractor(self.model_wrapper, method="GradientXInput")

        # 3. BM25 Statutory Evidence Retriever (6 Indian Central Commercial Acts)
        self.evidence_retriever = ClauseEvidenceRetriever()

        # 4. Evidence-Aware Abstention Policy (5-Tier Cascade with Calibrated Operating Threshold)
        policy_cfg = EvidenceAwarePolicyConfig(confidence_threshold=self.operating_threshold)
        self.abstention_policy = EvidenceAwarePolicy(config=policy_cfg)

        # 5. Build Label Mapper from model label metadata to Indian commercial risk categories
        self.label_mapping = self._build_label_mapping(self.model_dir)

    def _init_model_wrapper(self, model_dir: str, threshold: float) -> LegalBertWrapper:
        """Initializes LegalBertWrapper using the local verified checkpoint."""
        config_path = os.path.join(model_dir, "config.json")
        num_labels = 12407
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    num_labels = len(cfg_data.get("id2label", {})) or 12407
            except Exception as e:
                logger.warning(f"Could not load config.json for num_labels: {e}")

        config = LegalBertConfig(
            model_name="ledgar-legalbert-frozen",
            model_family="legal-bert",
            model_checkpoint=model_dir,
            tokenizer_name=model_dir,
            num_labels=num_labels,
            classification_mode="multilabel",
            multilabel_threshold=threshold,
        )
        return LegalBertWrapper(config)

    def _build_label_mapping(self, model_dir: str) -> Dict[int, Tuple[str, str]]:
        """
        Maps model output indices to standard Indian commercial risk categories
        verified against the model's actual saved taxonomy in label_mapping.json.
        Does not infer labels from arbitrary substring matching or names.
        """
        mapping_file = os.path.join(model_dir, "label_mapping.json")
        mapping: Dict[int, Tuple[str, str]] = {}
        if not os.path.exists(mapping_file):
            logger.warning(f"label_mapping.json not found at {mapping_file}")
            return mapping

        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                lm = json.load(f)
            l2i = lm.get("label2id", {})
            for name, category in CANONICAL_LEDGAR_TAXONOMY_MAP.items():
                if name in l2i:
                    idx_int = int(l2i[name])
                    mapping[idx_int] = (category, name)
        except Exception as e:
            logger.error(f"Error loading label_mapping.json: {e}")

        return mapping

    def screen_clause(
        self,
        clause_text: str,
        clause_id: str,
        document_id: str,
        document_version: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes real NLP inference, explainability, retrieval, and abstention for a single clause.
        """
        cleaned_text = clause_text.strip()
        if len(cleaned_text) < 10:
            return None

        # -------------------------------------------------------------
        # 1. LegalBERT Tokenization & Inference
        # -------------------------------------------------------------
        best_orig_idx = 0
        best_prob = 0.0
        pred_category = "UNMAPPED_LEGAL_RISK"
        raw_label_name = "unknown"
        threshold_met = False

        if self.model_wrapper and self.model_wrapper.is_available():
            preds, probs, truncs = predict(self.model_wrapper, [cleaned_text])
            prob_vec = probs[0]

            mapped_indices = list(self.label_mapping.keys())
            if mapped_indices:
                # First check if any mapped category meets or exceeds operating threshold
                passing_candidates = [
                    (idx, float(prob_vec[idx]), self.label_mapping[idx][0], self.label_mapping[idx][1])
                    for idx in mapped_indices
                    if float(prob_vec[idx]) >= self.operating_threshold
                ]
                if passing_candidates:
                    passing_candidates.sort(key=lambda x: x[1], reverse=True)
                    best_orig_idx, best_prob, pred_category, raw_label_name = passing_candidates[0]
                    threshold_met = True
                else:
                    # No mapped category passed threshold; select highest for diagnostic / abstention logging
                    sub_probs = prob_vec[mapped_indices]
                    best_sub_idx = int(sub_probs.argmax())
                    best_orig_idx = mapped_indices[best_sub_idx]
                    best_prob = float(prob_vec[best_orig_idx])
                    pred_category, raw_label_name = self.label_mapping[best_orig_idx]
                    threshold_met = False
            else:
                best_orig_idx = int(prob_vec.argmax())
                best_prob = float(prob_vec[best_orig_idx])
                pred_category = f"LABEL_{best_orig_idx}"
                raw_label_name = str(best_orig_idx)
                threshold_met = best_prob >= self.operating_threshold

        # -------------------------------------------------------------
        # 2. BM25 Statutory Evidence Retrieval
        # -------------------------------------------------------------
        statutory_evidence_dict = self.evidence_retriever.retrieve_evidence_for_clause(
            clause_text=cleaned_text,
            clause_id=clause_id,
            source_document_id=document_id,
            top_k=3,
            document_version_mismatch=False,
        )
        eq_status = statutory_evidence_dict.get(
            "evidence_quality_status", EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value
        )

        # -------------------------------------------------------------
        # 3. Evidence-Aware Abstention Policy Evaluation (5 Tiers)
        # -------------------------------------------------------------
        missing_capabilities = ["UNCALIBRATED_RAW_SCORE"]
        if not threshold_met:
            missing_capabilities.append("BELOW_OPERATING_THRESHOLD")

        candidate_category = pred_category if threshold_met else "NO_ACTIONABLE_RISK"

        finding_id = generate_deterministic_finding_id(
            contract_id=document_id,
            contract_version=document_version,
            clause_id=clause_id,
            prediction_category=candidate_category,
            raw_model_label=str(best_orig_idx),
            model_id="nlpaueb/legal-bert-base-uncased",
        )

        candidate = CandidateFindingRecord(
            candidate_finding_id=finding_id,
            contract_id=document_id,
            contract_version=document_version,
            document_content_hash="content_hash",
            clause_id=clause_id,
            clause_text=cleaned_text,
            prediction_category=pred_category,
            raw_model_label=str(best_orig_idx),
            confidence_value=best_prob,
            confidence_semantics=ConfidenceSemantics.MULTILABEL_SIGMOID_SCORE,
            confidence_is_calibrated=False,
            version_consistency_status=VersionConsistencyStatus.CONSISTENT,
            evidence_quality_status=eq_status,
            retrieved_passages=statutory_evidence_dict.get("passages", []),
            label_mapping_status=(
                LabelMappingStatus.MAPPED
                if pred_category in VALID_INDIAN_RISK_CATEGORIES
                else LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING
            ),
            missing_capabilities=missing_capabilities,
            model_id="nlpaueb/legal-bert-base-uncased",
            model_version="1.0.0",
            model_task="MULTI_LABEL_PROVISION_CLASSIFICATION",
            origin=CandidateOrigin.MODEL_INFERENCE_BATCH,
            is_disclosed_to_client=False,
        )

        policy_decision = self.abstention_policy.evaluate_candidate(candidate)
        is_withheld = (policy_decision.policy_action == PolicyAction.WITHHOLD)
        displayed_risk_label = "NO_ACTIONABLE_RISK" if is_withheld else pred_category

        # -------------------------------------------------------------
        # 4. Gradient x Input Explainability Extraction (Only for Accepted Risks)
        # -------------------------------------------------------------
        model_attribution_dict: Optional[Dict[str, Any]] = None
        if not is_withheld and self.evidence_extractor and self.evidence_extractor.is_available():
            ev_result: EvidenceResult = self.evidence_extractor.extract(
                source_text=cleaned_text,
                target_label_id=best_orig_idx,
                target_label_str=pred_category,
                top_k=3,
                document_id=document_id,
                clause_id=clause_id,
            )
            model_attribution_dict = {
                "method": "GradientXInput",
                "target_label": pred_category,
                "target_score": float(best_prob),
                "alignment_status": ev_result.alignment_status,
                "truncation_status": ev_result.truncation_status,
                "research_warning": (
                    "Attribution scores reflect Gradient x Input token sensitivities and may exhibit "
                    "bias toward punctuation or frequent function words. They do not constitute legal reasons or causal proof."
                ),
                "attributed_spans": [
                    {
                        "evidence_id": s.evidence_id,
                        "source_start": s.source_start,
                        "source_end": s.source_end,
                        "text": s.text,
                        "raw_score": float(s.raw_score),
                        "ranking_score": float(s.ranking_score),
                        "rank": s.rank,
                    }
                    for s in ev_result.evidence_spans
                ],
                "evidence_spans": [
                    {
                        "evidence_id": s.evidence_id,
                        "source_start": s.source_start,
                        "source_end": s.source_end,
                        "text": s.text,
                        "raw_score": float(s.raw_score),
                        "ranking_score": float(s.ranking_score),
                        "rank": s.rank,
                    }
                    for s in ev_result.evidence_spans
                ],
            }

        # -------------------------------------------------------------
        # 5. Substantive AI Observation & Metadata Assembly
        # -------------------------------------------------------------
        obs_text = (
            f"Risk Archetype: {displayed_risk_label}. "
            f"Model Sigmoid Probability: {best_prob:.4f} "
            f"(Empirical Operating Threshold \u03c4* = {self.operating_threshold:.2f}, "
            f"{'Met' if threshold_met else 'Below Operating Threshold'}). "
            f"Policy Decision: {policy_decision.policy_action.value} "
            f"[Reason: {policy_decision.primary_reason_code.value}, Tier {policy_decision.precedence_tier_applied}]. "
            f"Statutory Evidence Quality: {eq_status}."
        )

        ai_metadata_dict = {
            "model_name": "nlpaueb/legal-bert-base-uncased",
            "model_version": "1.0.0",
            "checkpoint_path": self.model_dir,
            "raw_model_label": raw_label_name,
            "raw_model_index": best_orig_idx,
            "raw_confidence": float(best_prob),
            "calibrated_threshold": self.operating_threshold,
            "classification_mode": "multilabel",
            "policy_action": policy_decision.policy_action.value,
            "policy_reason_code": policy_decision.primary_reason_code.value,
            "policy_tier_applied": policy_decision.precedence_tier_applied,
            "disclaimer": (
                "Automated model observation. Statistical output, not a legally binding determination."
            ),
        }

        return {
            "finding_id": finding_id,
            "segment_id": clause_id,
            "risk_label": displayed_risk_label,
            "ai_observation": obs_text,
            "ai_confidence_score": f"{best_prob:.4f}",
            "ai_metadata_json": json.dumps(ai_metadata_dict),
            "model_attribution_json": (
                json.dumps(model_attribution_dict) if model_attribution_dict else None
            ),
            "statutory_evidence_json": json.dumps(statutory_evidence_dict),
            "evidence_quality_status": eq_status,
            "policy_action": policy_decision.policy_action.value,
            "policy_reason_code": policy_decision.primary_reason_code.value,
            "is_disclosed_to_client": False,
        }

    def screen_review(self, review_id: str, session: Session) -> Dict[str, Any]:
        """
        Executes NLP screening across all segmented clauses of a review record,
        persisting findings into the database within the active session.
        """
        review = session.query(ReviewRecord).filter_by(id=review_id).first()
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        doc = review.document or session.query(DocumentRecord).filter_by(id=review.document_id).first()
        if not doc:
            raise ValueError(f"Document for review {review_id} not found.")

        segments = (
            session.query(SegmentRecord)
            .filter_by(document_id=doc.id)
            .order_by(SegmentRecord.sequence)
            .all()
        )

        review_service = ReviewService(session)
        created_findings: List[Dict[str, Any]] = []

        for seg in segments:
            seg_text = seg.text or ""
            if len(seg_text.strip()) < 10:
                continue

            finding_data = self.screen_clause(
                clause_text=seg_text,
                clause_id=seg.segment_id,
                document_id=doc.id,
                document_version=review.document_version,
            )
            if not finding_data:
                continue

            # Persist via ReviewService
            clause_finding = review_service.create_or_update_ai_finding(
                review_id=review.id,
                segment_id=seg.segment_id,
                risk_label=finding_data["risk_label"],
                ai_observation=finding_data["ai_observation"],
                ai_confidence_score=finding_data["ai_confidence_score"],
                ai_metadata_json=finding_data["ai_metadata_json"],
                model_attribution_json=finding_data["model_attribution_json"],
                statutory_evidence_json=finding_data["statutory_evidence_json"],
                evidence_quality_status=finding_data["evidence_quality_status"],
                is_disclosed_to_client=False,
            )

            created_findings.append({
                "finding_id": clause_finding.id,
                "segment_id": seg.segment_id,
                "risk_label": finding_data["risk_label"],
                "confidence": finding_data["ai_confidence_score"],
                "policy_action": finding_data["policy_action"],
                "policy_reason_code": finding_data["policy_reason_code"],
                "evidence_quality_status": finding_data["evidence_quality_status"],
            })

        logger.info(
            f"NLP Screening completed for Review {review_id}: Generated {len(created_findings)} findings."
        )
        return {
            "review_id": review_id,
            "document_id": doc.id,
            "segments_screened": len(segments),
            "findings_count": len(created_findings),
            "findings": created_findings,
        }


# Module-level singleton instance
_screening_service_instance: Optional[ContractScreeningService] = None


def get_contract_screening_service() -> ContractScreeningService:
    """Returns the singleton instance of ContractScreeningService."""
    global _screening_service_instance
    if _screening_service_instance is None:
        _screening_service_instance = ContractScreeningService()
    return _screening_service_instance
