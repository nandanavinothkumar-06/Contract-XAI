import pytest
from src.audit.schema import AuditEvent
from src.audit.store import AuditStore
from src.audit.logger import AuditLogger
from src.audit.provenance import EventType, ActorType, IntegrityStatus
from src.audit.integrity import AuditVerifier
from src.audit.events import calculate_event_hash, canonical_serialize
from src.audit.query import query_by_prediction_id, query_by_review_id, query_by_document, query_by_document_clause

@pytest.fixture
def store():
    return AuditStore()

@pytest.fixture
def logger(store):
    return AuditLogger(store)

@pytest.fixture
def verifier():
    return AuditVerifier()

def test_valid_event_creation(logger, store):
    event = logger.log_event(
        event_type=EventType.DOCUMENT_INGESTED,
        actor_type=ActorType.TEST,
        source_document_id="doc_1",
        is_test_fixture=True
    )
    assert event.event_type == EventType.DOCUMENT_INGESTED
    assert event.actor_type == ActorType.TEST
    assert len(store.get_all()) == 1

def test_required_field_validation():
    with pytest.raises(ValueError):
        # Missing required actor_type, event_type, etc.
        AuditEvent(event_id="e1", timestamp="2026")

def test_event_type_validation(logger):
    with pytest.raises(ValueError):
        logger.log_event(
            event_type="INVALID_TYPE",
            actor_type=ActorType.TEST,
            is_test_fixture=True
        )

def test_deterministic_canonical_serialization():
    d1 = {"b": 2, "a": {"z": 9, "y": 8}}
    d2 = {"a": {"y": 8, "z": 9}, "b": 2}
    assert canonical_serialize(d1) == canonical_serialize(d2)

def test_deterministic_event_hash(logger):
    event1 = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    hash1 = event1.event_hash
    hash2 = calculate_event_hash(event1)
    assert hash1 == hash2

def test_first_event_behavior(logger):
    event = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    assert event.previous_event_hash is None

def test_hash_chain_creation(logger):
    e1 = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    e2 = logger.log_event(EventType.CLAUSE_SEGMENTED, ActorType.TEST, is_test_fixture=True)
    assert e2.previous_event_hash == e1.event_hash

def test_valid_chain_verification(logger, verifier, store):
    logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    logger.log_event(EventType.CLAUSE_SEGMENTED, ActorType.TEST, is_test_fixture=True)
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.VALID
    assert msg is None

def test_modified_event_detection(logger, verifier, store):
    logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    e2 = logger.log_event(EventType.CLAUSE_SEGMENTED, ActorType.TEST, is_test_fixture=True)
    
    # Modify store's internal memory manually (bypassing the deep copy safety just for testing integrity)
    store._events[0].event_payload = {"hacked": True}
    
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.INVALID_HASH

def test_modified_previous_hash_detection(logger, verifier, store):
    logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    logger.log_event(EventType.CLAUSE_SEGMENTED, ActorType.TEST, is_test_fixture=True)
    
    store._events[1].previous_event_hash = "fake_hash"
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.INVALID_PREVIOUS_HASH

def test_reordered_event_detection(logger, verifier, store):
    e1 = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    e2 = logger.log_event(EventType.CLAUSE_SEGMENTED, ActorType.TEST, is_test_fixture=True)
    e3 = logger.log_event(EventType.MODEL_PREDICTION, ActorType.TEST, is_test_fixture=True)
    
    # Swap 2 and 3
    store._events[1], store._events[2] = store._events[2], store._events[1]
    
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.INVALID_PREVIOUS_HASH

def test_invalid_provenance_reference(logger, verifier, store):
    # Duplicate IDs are an invalid reference
    e1 = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    store._events.append(e1.model_copy(deep=True))
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.INVALID_REFERENCE

def test_document_mismatch(logger, verifier, store):
    # Partition provided without document ID
    logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, partition="part1", is_test_fixture=True)
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.INVALID_REFERENCE

def test_partition_mismatch(logger, verifier, store):
    # Clause provided without document ID
    logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, clause_id="c1", is_test_fixture=True)
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.INVALID_REFERENCE

def test_model_prediction_event(logger):
    event = logger.log_event(EventType.MODEL_PREDICTION, ActorType.SYSTEM, prediction_id="p1", is_test_fixture=True)
    assert event.event_type == EventType.MODEL_PREDICTION

def test_evidence_event(logger):
    event = logger.log_event(EventType.EVIDENCE_EXTRACTED, ActorType.SYSTEM, is_test_fixture=True)
    assert event.event_type == EventType.EVIDENCE_EXTRACTED

def test_retrieval_event(logger):
    event = logger.log_event(EventType.RETRIEVAL_PERFORMED, ActorType.SYSTEM, is_test_fixture=True)
    assert event.event_type == EventType.RETRIEVAL_PERFORMED

def test_missing_provision_event(logger):
    event = logger.log_event(EventType.MISSING_PROVISION_ASSESSED, ActorType.SYSTEM, is_test_fixture=True)
    assert event.event_type == EventType.MISSING_PROVISION_ASSESSED

def test_legal_source_event(logger):
    event = logger.log_event(EventType.LEGAL_SOURCE_RETRIEVED, ActorType.SYSTEM, is_test_fixture=True)
    assert event.event_type == EventType.LEGAL_SOURCE_RETRIEVED

def test_abstention_event(logger):
    event = logger.log_event(EventType.ABSTENTION_DECIDED, ActorType.SYSTEM, is_test_fixture=True)
    assert event.event_type == EventType.ABSTENTION_DECIDED

def test_lawyer_review_event(logger):
    event = logger.log_event(EventType.LAWYER_REVIEW_CREATED, ActorType.REVIEWER, review_id="r1", is_test_fixture=True)
    assert event.event_type == EventType.LAWYER_REVIEW_CREATED

def test_multiple_events_for_same_prediction(logger, store):
    logger.log_event(EventType.MODEL_PREDICTION, ActorType.SYSTEM, prediction_id="p1", is_test_fixture=True)
    logger.log_event(EventType.ABSTENTION_DECIDED, ActorType.SYSTEM, prediction_id="p1", is_test_fixture=True)
    events = query_by_prediction_id(store, "p1")
    assert len(events) == 2

def test_multiple_reviews_events_preserved(logger, store):
    logger.log_event(EventType.LAWYER_REVIEW_CREATED, ActorType.REVIEWER, review_id="r1", prediction_id="p1", is_test_fixture=True)
    logger.log_event(EventType.LAWYER_REVIEW_CREATED, ActorType.REVIEWER, review_id="r2", prediction_id="p1", is_test_fixture=True)
    assert len(query_by_prediction_id(store, "p1")) == 2

def test_serialization_round_trip(logger):
    event = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    json_str = event.model_dump_json()
    e2 = AuditEvent.model_validate_json(json_str)
    assert e2.event_id == event.event_id
    assert e2.event_hash == event.event_hash

def test_synthetic_fixture_marking(logger):
    event = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    assert event.is_test_fixture is True

def test_source_object_immutability(logger, store):
    event = logger.log_event(EventType.DOCUMENT_INGESTED, ActorType.TEST, is_test_fixture=True)
    # The caller changing their event copy should not change store
    event.actor_type = ActorType.REVIEWER
    assert store.get_all()[0].actor_type == ActorType.TEST

def test_empty_audit_store(store, verifier):
    status, msg = verifier.verify(store)
    assert status == IntegrityStatus.VALID

def test_query_by_prediction_id(logger, store):
    logger.log_event(EventType.MODEL_PREDICTION, ActorType.TEST, prediction_id="p1", is_test_fixture=True)
    assert len(query_by_prediction_id(store, "p1")) == 1

def test_query_by_review_id(logger, store):
    logger.log_event(EventType.LAWYER_REVIEW_CREATED, ActorType.TEST, review_id="r1", is_test_fixture=True)
    assert len(query_by_review_id(store, "r1")) == 1

def test_query_by_document_clause(logger, store):
    logger.log_event(EventType.MODEL_PREDICTION, ActorType.TEST, source_document_id="doc1", clause_id="c1", is_test_fixture=True)
    assert len(query_by_document(store, "doc1")) == 1
    assert len(query_by_document_clause(store, "doc1", "c1")) == 1
    assert len(query_by_document_clause(store, "doc2", "c1")) == 0
