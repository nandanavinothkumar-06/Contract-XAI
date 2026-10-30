import uuid
import datetime
from typing import List, Tuple
from src.abstention.schema import UncertaintySignals, AbstentionDecision
from src.abstention.config import AbstentionConfig
from src.abstention.provenance import AbstentionState, AbstentionReasonCode, PredictionType, CalibrationStatus

class AbstentionPolicy:
    def __init__(self, config: AbstentionConfig):
        self.config = config

    def evaluate(self, signals: UncertaintySignals) -> AbstentionDecision:
        reasons = []
        status = None
        
        # 1. Invalid input
        if signals.prediction_type not in [PredictionType.MULTICLASS, PredictionType.MULTILABEL, PredictionType.MISSING_PROVISION]:
            reasons.append(AbstentionReasonCode.INVALID_INPUT)
            return self._build_decision(signals, AbstentionState.NOT_ASSESSED, reasons)
            
        # 2. Missing model
        if not signals.model_id:
            reasons.append(AbstentionReasonCode.MISSING_MODEL)
            return self._build_decision(signals, AbstentionState.NOT_ASSESSED, reasons)
            
        # 3. Missing required metadata
        if self.config.calibration_requirement == "REQUIRE_CALIBRATION" and signals.calibration_status != CalibrationStatus.CALIBRATED:
            reasons.append(AbstentionReasonCode.CALIBRATION_UNAVAILABLE)
            
        if self.config.retrieval_policy == "REQUIRE_RETRIEVAL" and not signals.retrieval_available:
            reasons.append(AbstentionReasonCode.RETRIEVAL_UNAVAILABLE)

        if AbstentionReasonCode.CALIBRATION_UNAVAILABLE in reasons or AbstentionReasonCode.RETRIEVAL_UNAVAILABLE in reasons:
             return self._build_decision(signals, AbstentionState.NOT_ASSESSED, reasons)
             
        # 4. Input/context truncation
        if signals.input_truncated or signals.context_incomplete:
            if signals.input_truncated:
                reasons.append(AbstentionReasonCode.TRUNCATED_INPUT)
            if signals.context_incomplete:
                reasons.append(AbstentionReasonCode.CONTEXT_INCOMPLETE)
                
            if self.config.truncation_policy == "ABSTAIN":
                return self._build_decision(signals, AbstentionState.ABSTAIN, reasons)
            elif self.config.truncation_policy == "REVIEW_REQUIRED":
                status = AbstentionState.REVIEW_REQUIRED

        # 5. Missing evidence when required
        if self.config.require_evidence and signals.evidence_available is False:
            reasons.append(AbstentionReasonCode.INSUFFICIENT_EVIDENCE)
            return self._build_decision(signals, AbstentionState.ABSTAIN, reasons)
            
        # 6. High uncertainty & 7. Threshold ambiguity
        if signals.prediction_type == PredictionType.MULTICLASS:
            if signals.top_probability is not None:
                if signals.top_probability < self.config.confidence_review_threshold:
                    reasons.append(AbstentionReasonCode.HIGH_UNCERTAINTY)
                    status = AbstentionState.ABSTAIN
                elif signals.top_probability < self.config.confidence_accept_threshold:
                    reasons.append(AbstentionReasonCode.BELOW_ACCEPT_THRESHOLD)
                    status = status or AbstentionState.REVIEW_REQUIRED
            
            if signals.margin is not None and signals.margin < self.config.margin_threshold:
                reasons.append(AbstentionReasonCode.LOW_MARGIN)
                status = status or AbstentionState.REVIEW_REQUIRED
                
            if signals.entropy is not None and signals.entropy > self.config.entropy_threshold:
                reasons.append(AbstentionReasonCode.HIGH_ENTROPY)
                status = status or AbstentionState.REVIEW_REQUIRED
                
        elif signals.prediction_type == PredictionType.MULTILABEL:
            if signals.near_threshold_labels:
                reasons.append(AbstentionReasonCode.NEAR_THRESHOLD)
                status = status or AbstentionState.REVIEW_REQUIRED
                
        elif signals.prediction_type == PredictionType.MISSING_PROVISION:
            # For missing provision, confidence acts as a mapping. If the signal was potentally missing we accept it.
            pass
            
        # 8. Accept
        if not status:
            status = AbstentionState.ACCEPT
            
        return self._build_decision(signals, status, reasons)
        
    def _build_decision(self, signals: UncertaintySignals, status: AbstentionState, reasons: List[AbstentionReasonCode]) -> AbstentionDecision:
        # Sort reasons deterministically
        sorted_reasons = sorted(list(set(reasons)), key=lambda x: x.value)
        
        return AbstentionDecision(
            decision_id=str(uuid.uuid4()),
            prediction_id=signals.prediction_id,
            status=status,
            reasons=sorted_reasons,
            uncertainty_signals=signals,
            policy_version=self.config.policy_version,
            model_id=signals.model_id,
            model_version=signals.model_version,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            is_test_fixture=False
        )
