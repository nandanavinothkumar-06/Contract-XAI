from typing import List, Dict, Optional
from src.abstention.schema import UncertaintySignals, AbstentionDecision
from src.abstention.config import AbstentionConfig
from src.abstention.policy import AbstentionPolicy
from src.abstention.signals import calculate_multiclass_signals, calculate_multilabel_signals
from src.abstention.provenance import PredictionType, CalibrationStatus, AbstentionState

class AbstentionEvaluator:
    def __init__(self, config: AbstentionConfig):
        self.config = config
        self.policy = AbstentionPolicy(config)
        
    def evaluate_multiclass(
        self,
        prediction_id: str,
        probabilities: List[float],
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
        input_truncated: Optional[bool] = None,
        context_incomplete: Optional[bool] = None,
        evidence_available: Optional[bool] = None,
        calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED,
    ) -> AbstentionDecision:
        try:
            signals_data = calculate_multiclass_signals(probabilities)
        except ValueError as e:
            signals = UncertaintySignals(
                prediction_id=prediction_id,
                prediction_type=PredictionType.OTHER, # To trigger INVALID_INPUT
                configuration_version=self.config.policy_version,
                model_id=model_id,
            )
            return self.policy.evaluate(signals)

        signals = UncertaintySignals(
            prediction_id=prediction_id,
            prediction_type=PredictionType.MULTICLASS,
            model_id=model_id,
            model_version=model_version,
            configuration_version=self.config.policy_version,
            top_probability=signals_data["top_probability"],
            second_probability=signals_data["second_probability"],
            margin=signals_data["margin"],
            entropy=signals_data["entropy"],
            input_truncated=input_truncated,
            context_incomplete=context_incomplete,
            evidence_available=evidence_available,
            calibration_status=calibration_status
        )
        return self.policy.evaluate(signals)

    def evaluate_multilabel(
        self,
        prediction_id: str,
        probabilities: Dict[str, float],
        threshold: float,
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
        input_truncated: Optional[bool] = None,
        context_incomplete: Optional[bool] = None,
        evidence_available: Optional[bool] = None,
        calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED,
    ) -> AbstentionDecision:
        try:
            signals_data = calculate_multilabel_signals(probabilities, threshold, self.config.near_threshold_window)
        except ValueError as e:
            signals = UncertaintySignals(
                prediction_id=prediction_id,
                prediction_type=PredictionType.OTHER,
                configuration_version=self.config.policy_version,
                model_id=model_id,
            )
            return self.policy.evaluate(signals)

        signals = UncertaintySignals(
            prediction_id=prediction_id,
            prediction_type=PredictionType.MULTILABEL,
            model_id=model_id,
            model_version=model_version,
            configuration_version=self.config.policy_version,
            per_label_probabilities=signals_data["per_label_probabilities"],
            near_threshold_labels=signals_data["near_threshold_labels"],
            input_truncated=input_truncated,
            context_incomplete=context_incomplete,
            evidence_available=evidence_available,
            calibration_status=calibration_status
        )
        return self.policy.evaluate(signals)

    def evaluate_missing_provision(
        self,
        prediction_id: str,
        status_string: str,
        model_id: Optional[str] = None,
    ) -> AbstentionDecision:
        # Simple mapping for task 013 status. 
        signals = UncertaintySignals(
            prediction_id=prediction_id,
            prediction_type=PredictionType.MISSING_PROVISION,
            model_id=model_id,
            configuration_version=self.config.policy_version
        )
        decision = self.policy.evaluate(signals)
        
        # Override the decision status based on the task 013 result.
        if status_string == "UNCERTAIN" and decision.status != AbstentionState.NOT_ASSESSED:
             decision.status = AbstentionState.REVIEW_REQUIRED
             
        return decision
