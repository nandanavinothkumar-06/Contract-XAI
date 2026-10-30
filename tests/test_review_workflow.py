import pytest
from src.review.schema import PredictionContext, ReviewRecord
from src.review.provenance import ReviewDecision
from src.review.workflow import ReviewWorkflow
from src.review.serialization import serialize_review_record, deserialize_review_record
from src.abstention.schema import UncertaintySignals, AbstentionState
from src.abstention.provenance import PredictionType, CalibrationStatus

@pytest.fixture
def workflow():
    return ReviewWorkflow()

@pytest.fixture
def dummy_context():
    return PredictionContext(
        prediction_id="p_123",
        source_document_id="doc_1",
        clause_id="clause_5",
        original_prediction="HIGH_RISK",
        model_score=0.92,
        abstention_status=AbstentionState.REVIEW_REQUIRED,
        evidence_ids=["ev_1", "ev_2"],
        retrieval_ids=["ret_1"],
        legal_source_ids=["ls_1"]
    )

def test_valid_review_creation_accept(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.ACCEPT,
        source_document_id="doc_1",
        clause_id="clause_5",
        referenced_evidence_ids=["ev_1"]
    )
    assert record.decision == ReviewDecision.ACCEPT
    assert record.referenced_evidence_ids == ["ev_1"]
    assert len(workflow.get_reviews("p_123")) == 1

def test_valid_review_creation_reject(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.REJECT,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    assert record.decision == ReviewDecision.REJECT

def test_valid_review_creation_modify(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.MODIFY,
        source_document_id="doc_1",
        clause_id="clause_5",
        reviewer_rationale="Incorrectly flagged."
    )
    assert record.decision == ReviewDecision.MODIFY

def test_valid_review_creation_request_more_evidence(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.REQUEST_MORE_EVIDENCE,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    assert record.decision == ReviewDecision.REQUEST_MORE_EVIDENCE

def test_valid_review_creation_mark_uncertain(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.MARK_UNCERTAIN,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    assert record.decision == ReviewDecision.MARK_UNCERTAIN

def test_invalid_decision_rejection(workflow, dummy_context):
    with pytest.raises(ValueError, match="1 validation error for ReviewRecord"):
        workflow.record_review(
            context=dummy_context,
            decision="INVALID_DECISION",
            source_document_id="doc_1",
            clause_id="clause_5"
        )

def test_missing_prediction_id_rejection(workflow):
    ctx = PredictionContext(
        prediction_id="",
        source_document_id="doc_1",
        clause_id="clause_5",
        original_prediction="HIGH_RISK"
    )
    with pytest.raises(ValueError, match="prediction_id is required"):
        workflow.record_review(
            context=ctx,
            decision=ReviewDecision.ACCEPT,
            source_document_id="doc_1",
            clause_id="clause_5"
        )

def test_original_prediction_cannot_be_overwritten(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.REJECT,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    assert record.prediction_context.original_prediction == "HIGH_RISK"
    assert record.prediction_context.model_score == 0.92

    # Mutating original should not mutate recorded context
    dummy_context.original_prediction = "LOW_RISK"
    assert record.prediction_context.original_prediction == "HIGH_RISK"

def test_original_model_score_cannot_be_overwritten(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.REJECT,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    # The review record has no 'model_score' field at its root, proving it doesn't overwrite.
    assert not hasattr(record, "model_score")
    assert record.prediction_context.model_score == 0.92

def test_abstention_state_remains_preserved(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.REJECT,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    assert record.prediction_context.abstention_status == AbstentionState.REVIEW_REQUIRED

def test_evidence_provenance_remains_traceable(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.ACCEPT,
        source_document_id="doc_1",
        clause_id="clause_5",
        referenced_evidence_ids=["ev_2"]
    )
    assert "ev_2" in record.referenced_evidence_ids
    assert "ev_2" in record.prediction_context.evidence_ids

def test_unknown_evidence_reference_rejected(workflow, dummy_context):
    with pytest.raises(ValueError, match="Unknown evidence reference rejected: ev_99"):
        workflow.record_review(
            context=dummy_context,
            decision=ReviewDecision.ACCEPT,
            source_document_id="doc_1",
            clause_id="clause_5",
            referenced_evidence_ids=["ev_99"]
        )

def test_unknown_retrieval_reference_rejected(workflow, dummy_context):
    with pytest.raises(ValueError, match="Unknown retrieval reference rejected: ret_99"):
        workflow.record_review(
            context=dummy_context,
            decision=ReviewDecision.ACCEPT,
            source_document_id="doc_1",
            clause_id="clause_5",
            referenced_retrieval_ids=["ret_99"]
        )

def test_unknown_legal_source_reference_rejected(workflow, dummy_context):
    with pytest.raises(ValueError, match="Unknown legal-source reference rejected: ls_99"):
        workflow.record_review(
            context=dummy_context,
            decision=ReviewDecision.ACCEPT,
            source_document_id="doc_1",
            clause_id="clause_5",
            referenced_legal_source_ids=["ls_99"]
        )

def test_document_partition_mismatch_rejected(workflow, dummy_context):
    with pytest.raises(ValueError, match="Document mismatch rejected."):
        workflow.record_review(
            context=dummy_context,
            decision=ReviewDecision.ACCEPT,
            source_document_id="WRONG_DOC",
            clause_id="clause_5"
        )
    with pytest.raises(ValueError, match="Partition mismatch rejected."):
        workflow.record_review(
            context=dummy_context,
            decision=ReviewDecision.ACCEPT,
            source_document_id="doc_1",
            clause_id="WRONG_CLAUSE"
        )

def test_reviewer_information_remains_separate(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.ACCEPT,
        source_document_id="doc_1",
        clause_id="clause_5",
        reviewer_rationale="Looks good."
    )
    assert not hasattr(record.prediction_context, "reviewer_rationale")
    assert record.reviewer_rationale == "Looks good."

def test_multiple_reviews_preserved(workflow, dummy_context):
    workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.MARK_UNCERTAIN,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.ACCEPT,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    history = workflow.get_reviews("p_123")
    assert len(history) == 2
    assert history[0].decision == ReviewDecision.MARK_UNCERTAIN
    assert history[1].decision == ReviewDecision.ACCEPT

def test_serialization_deserialization_round_trip(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.MODIFY,
        source_document_id="doc_1",
        clause_id="clause_5",
        referenced_evidence_ids=["ev_1"]
    )
    json_str = serialize_review_record(record)
    new_record = deserialize_review_record(json_str)
    
    assert new_record.review_id == record.review_id
    assert new_record.decision == ReviewDecision.MODIFY
    assert new_record.prediction_context.original_prediction == "HIGH_RISK"
    assert new_record.referenced_evidence_ids == ["ev_1"]
    assert new_record.timestamp == record.timestamp

def test_deterministic_provenance_behavior(workflow, dummy_context):
    record = workflow.record_review(
        context=dummy_context,
        decision=ReviewDecision.ACCEPT,
        source_document_id="doc_1",
        clause_id="clause_5"
    )
    assert record.prediction_context.source_document_id == "doc_1"
    assert record.prediction_context.clause_id == "clause_5"
    assert record.prediction_context.prediction_id == "p_123"
    assert record.review_id is not None
    assert record.timestamp is not None
