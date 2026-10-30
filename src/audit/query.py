from typing import List
from src.audit.schema import AuditEvent
from src.audit.store import AuditStore

def query_by_prediction_id(store: AuditStore, prediction_id: str) -> List[AuditEvent]:
    return [e for e in store.get_all() if e.prediction_id == prediction_id]

def query_by_review_id(store: AuditStore, review_id: str) -> List[AuditEvent]:
    return [e for e in store.get_all() if e.review_id == review_id]

def query_by_document(store: AuditStore, source_document_id: str) -> List[AuditEvent]:
    return [e for e in store.get_all() if e.source_document_id == source_document_id]

def query_by_document_clause(store: AuditStore, source_document_id: str, clause_id: str) -> List[AuditEvent]:
    return [
        e for e in store.get_all() 
        if e.source_document_id == source_document_id and e.clause_id == clause_id
    ]
