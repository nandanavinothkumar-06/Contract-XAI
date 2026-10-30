import pytest
from src.abstention.config import AbstentionConfig
from src.abstention.evaluator import AbstentionEvaluator
from src.abstention.provenance import AbstentionState, AbstentionReasonCode, CalibrationStatus

@pytest.fixture
def config():
    c = AbstentionConfig()
    c.confidence_accept_threshold = 0.85
    c.confidence_review_threshold = 0.50
    c.margin_threshold = 0.10
    c.entropy_threshold = 0.80
    return c
    
@pytest.fixture
def evaluator(config):
    return AbstentionEvaluator(config)

def test_multiclass_confidence_accept(evaluator):
    decision = evaluator.evaluate_multiclass(
        prediction_id="p1",
        probabilities=[0.90, 0.05, 0.05],
        model_id="m1"
    )
    assert decision.status == AbstentionState.ACCEPT
    assert decision.uncertainty_signals.top_probability == 0.90
    assert decision.uncertainty_signals.margin == 0.85

def test_multiclass_margin_abstain(evaluator):
    # Top prob is > 0.50 so it's not strictly HIGH_UNCERTAINTY by top prob alone
    # But margin = 0.51 - 0.49 = 0.02 < 0.10
    decision = evaluator.evaluate_multiclass(
        prediction_id="p2",
        probabilities=[0.51, 0.49, 0.00],
        model_id="m1"
    )
    assert decision.status == AbstentionState.REVIEW_REQUIRED
    assert AbstentionReasonCode.LOW_MARGIN in decision.reasons

def test_multiclass_entropy_abstain(evaluator):
    decision = evaluator.evaluate_multiclass(
        prediction_id="p3",
        probabilities=[0.34, 0.33, 0.33],
        model_id="m1"
    )
    # entropy = 3 * 0.33 * log(0.33) ~ 1.09 > 0.80
    # top_prob = 0.34 < 0.50 -> HIGH_UNCERTAINTY -> ABSTAIN
    assert decision.status == AbstentionState.ABSTAIN
    assert AbstentionReasonCode.HIGH_UNCERTAINTY in decision.reasons
    assert AbstentionReasonCode.HIGH_ENTROPY in decision.reasons
    
def test_multiclass_threshold_boundaries(evaluator):
    # Exactly at boundary
    evaluator.config.margin_threshold = 0.10
    decision = evaluator.evaluate_multiclass(
        prediction_id="pb",
        probabilities=[0.55, 0.45, 0.00],
        model_id="m1"
    )
    # margin = 0.10. Our logic: < margin_threshold => REVIEW_REQUIRED
    # So 0.10 should be ACCEPT (or at least pass margin check)
    # Wait, top prob is 0.55 < 0.85, so it triggers BELOW_ACCEPT_THRESHOLD
    assert AbstentionReasonCode.BELOW_ACCEPT_THRESHOLD in decision.reasons
    assert AbstentionReasonCode.LOW_MARGIN not in decision.reasons

def test_multilabel_probabilities(evaluator):
    decision = evaluator.evaluate_multilabel(
        prediction_id="pm1",
        probabilities={"L1": 0.99, "L2": 0.01},
        threshold=0.5,
        model_id="m1"
    )
    assert decision.status == AbstentionState.ACCEPT
    
def test_multilabel_near_threshold(evaluator):
    decision = evaluator.evaluate_multilabel(
        prediction_id="pm2",
        probabilities={"L1": 0.52, "L2": 0.10},
        threshold=0.5,
        model_id="m1"
    )
    assert decision.status == AbstentionState.REVIEW_REQUIRED
    assert AbstentionReasonCode.NEAR_THRESHOLD in decision.reasons
    assert "L1" in decision.uncertainty_signals.near_threshold_labels

def test_truncation(evaluator):
    decision = evaluator.evaluate_multiclass(
        prediction_id="t1",
        probabilities=[0.90, 0.05, 0.05],
        model_id="m1",
        input_truncated=True
    )
    assert decision.status == AbstentionState.REVIEW_REQUIRED
    assert AbstentionReasonCode.TRUNCATED_INPUT in decision.reasons
    
def test_missing_evidence(evaluator):
    evaluator.config.require_evidence = True
    decision = evaluator.evaluate_multiclass(
        prediction_id="e1",
        probabilities=[0.90, 0.05, 0.05],
        model_id="m1",
        evidence_available=False
    )
    assert decision.status == AbstentionState.ABSTAIN
    assert AbstentionReasonCode.INSUFFICIENT_EVIDENCE in decision.reasons

def test_context_incomplete(evaluator):
    decision = evaluator.evaluate_multiclass(
        prediction_id="c1",
        probabilities=[0.90, 0.05, 0.05],
        model_id="m1",
        context_incomplete=True
    )
    assert decision.status == AbstentionState.REVIEW_REQUIRED
    assert AbstentionReasonCode.CONTEXT_INCOMPLETE in decision.reasons

def test_missing_model(evaluator):
    decision = evaluator.evaluate_multiclass(
        prediction_id="mm1",
        probabilities=[0.90, 0.05, 0.05],
        model_id=None
    )
    assert decision.status == AbstentionState.NOT_ASSESSED
    assert AbstentionReasonCode.MISSING_MODEL in decision.reasons

def test_calibration_status(evaluator):
    evaluator.config.calibration_requirement = "REQUIRE_CALIBRATION"
    decision = evaluator.evaluate_multiclass(
        prediction_id="c1",
        probabilities=[0.90, 0.05, 0.05],
        model_id="m1",
        calibration_status=CalibrationStatus.NOT_CALIBRATED
    )
    assert decision.status == AbstentionState.NOT_ASSESSED
    assert AbstentionReasonCode.CALIBRATION_UNAVAILABLE in decision.reasons

def test_missing_retrieval(evaluator):
    evaluator.config.retrieval_policy = "REQUIRE_RETRIEVAL"
    decision = evaluator.evaluate_multiclass(
        prediction_id="r1",
        probabilities=[0.90, 0.05, 0.05],
        model_id="m1"
    )
    # By default signal object has retrieval_available = None (falsey)
    assert decision.status == AbstentionState.NOT_ASSESSED
    assert AbstentionReasonCode.RETRIEVAL_UNAVAILABLE in decision.reasons
    
def test_missing_provision_compatibility(evaluator):
    decision = evaluator.evaluate_missing_provision(
        prediction_id="mp1",
        status_string="UNCERTAIN",
        model_id="m1"
    )
    assert decision.status == AbstentionState.REVIEW_REQUIRED

def test_deterministic_decisions(evaluator):
    d1 = evaluator.evaluate_multiclass("id1", [0.4, 0.4, 0.2], "m1")
    d2 = evaluator.evaluate_multiclass("id2", [0.4, 0.4, 0.2], "m1")
    assert d1.status == d2.status
    assert d1.reasons == d2.reasons

def test_invalid_input(evaluator):
    decision = evaluator.evaluate_multiclass("inv1", [-0.5, 1.5], "m1")
    assert decision.status == AbstentionState.NOT_ASSESSED
    assert AbstentionReasonCode.INVALID_INPUT in decision.reasons

def test_empty_probability_vector(evaluator):
    decision = evaluator.evaluate_multiclass("inv2", [], "m1")
    assert decision.status == AbstentionState.NOT_ASSESSED
    assert AbstentionReasonCode.INVALID_INPUT in decision.reasons

def test_probability_normalization_validation(evaluator):
    decision = evaluator.evaluate_multiclass("inv3", [0.5, 0.6], "m1")
    assert decision.status == AbstentionState.NOT_ASSESSED
    assert AbstentionReasonCode.INVALID_INPUT in decision.reasons
    
def test_no_legal_conclusions(evaluator):
    decision = evaluator.evaluate_multiclass("id", [0.99, 0.01], "m1")
    # Make sure we don't return 'LEGALLY_SAFE' anywhere
    assert decision.status.value not in ["LEGALLY_SAFE", "LEGALLY_CORRECT", "COMPLIANT"]
    assert not hasattr(decision, 'legal_confidence')
