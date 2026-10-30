import uuid
import datetime
from typing import List, Dict, Optional
from src.review.schema import PredictionContext, ReviewRecord
from src.review.provenance import ReviewDecision
from src.review.validation import validate_document_partition_match, validate_review_record

class ReviewWorkflow:
    def __init__(self, workflow_version: str = "1.0.0"):
        self.workflow_version = workflow_version
        self.history: Dict[str, List[ReviewRecord]] = {}

    def record_review(
        self,
        context: PredictionContext,
        decision: ReviewDecision,
        source_document_id: str,
        clause_id: str,
        reviewer_rationale: Optional[str] = None,
        reviewer_notes: Optional[str] = None,
        referenced_evidence_ids: List[str] = None,
        referenced_retrieval_ids: List[str] = None,
        referenced_missing_provision_ids: List[str] = None,
        referenced_legal_source_ids: List[str] = None,
        reviewer_id: Optional[str] = None,
        is_test_fixture: bool = False
    ) -> ReviewRecord:
        
        # Enforce document/partition matching
        validate_document_partition_match(context, source_document_id, clause_id)
        
        # Deep copy context to ensure we don't accidentally mutate it via reference 
        # (Though Pydantic model_copy handles shallow, we want to ensure immutability)
        immutable_context = context.model_copy(deep=True)
        
        record = ReviewRecord(
            review_id=str(uuid.uuid4()),
            prediction_context=immutable_context,
            decision=decision,
            reviewer_rationale=reviewer_rationale,
            reviewer_notes=reviewer_notes,
            referenced_evidence_ids=referenced_evidence_ids or [],
            referenced_retrieval_ids=referenced_retrieval_ids or [],
            referenced_missing_provision_ids=referenced_missing_provision_ids or [],
            referenced_legal_source_ids=referenced_legal_source_ids or [],
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            workflow_version=self.workflow_version,
            reviewer_id=reviewer_id,
            is_test_fixture=is_test_fixture
        )
        
        # Full validation
        validate_review_record(record)
        
        # Store securely to prevent silent overwrites of previous reviews
        if context.prediction_id not in self.history:
            self.history[context.prediction_id] = []
        
        # Append without overwriting
        self.history[context.prediction_id].append(record)
        
        return record
        
    def get_reviews(self, prediction_id: str) -> List[ReviewRecord]:
        return self.history.get(prediction_id, [])
