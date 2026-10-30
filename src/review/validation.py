from typing import List
from src.review.schema import PredictionContext, ReviewRecord
from src.review.provenance import ReviewDecision

def validate_prediction_context(context: PredictionContext):
    if not context.prediction_id:
        raise ValueError("prediction_id is required.")
    if not context.source_document_id:
        raise ValueError("source_document_id is required.")
    if not context.clause_id:
        raise ValueError("clause_id is required.")

def validate_review_references(
    context: PredictionContext,
    evidence_ids: List[str],
    retrieval_ids: List[str],
    missing_provision_ids: List[str],
    legal_source_ids: List[str]
):
    # Reject unknown evidence references
    for e_id in evidence_ids:
        if e_id not in context.evidence_ids:
            raise ValueError(f"Unknown evidence reference rejected: {e_id}")
            
    # Reject unknown retrieval references
    for r_id in retrieval_ids:
        if r_id not in context.retrieval_ids:
            raise ValueError(f"Unknown retrieval reference rejected: {r_id}")
            
    # Reject unknown missing-provision references
    for m_id in missing_provision_ids:
        if m_id not in context.missing_provision_ids:
            raise ValueError(f"Unknown missing-provision reference rejected: {m_id}")
            
    # Reject unknown legal-source references
    for l_id in legal_source_ids:
        if l_id not in context.legal_source_ids:
            raise ValueError(f"Unknown legal-source reference rejected: {l_id}")

def validate_document_partition_match(context: PredictionContext, request_source_document_id: str, request_clause_id: str):
    if context.source_document_id != request_source_document_id:
        raise ValueError(f"Document mismatch rejected. Expected {context.source_document_id}, got {request_source_document_id}")
    if context.clause_id != request_clause_id:
        raise ValueError(f"Partition mismatch rejected. Expected {context.clause_id}, got {request_clause_id}")

def validate_review_record(record: ReviewRecord):
    validate_prediction_context(record.prediction_context)
    
    if not isinstance(record.decision, ReviewDecision):
        raise ValueError("Invalid decision enum.")
        
    validate_review_references(
        record.prediction_context,
        record.referenced_evidence_ids,
        record.referenced_retrieval_ids,
        record.referenced_missing_provision_ids,
        record.referenced_legal_source_ids
    )
