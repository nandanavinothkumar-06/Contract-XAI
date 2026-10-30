import uuid
import datetime
from typing import Dict, Any, Optional, List
from src.audit.schema import AuditEvent
from src.audit.provenance import EventType, ActorType
from src.audit.store import AuditStore
from src.audit.events import calculate_event_hash

class AuditLogger:
    def __init__(self, store: AuditStore):
        self.store = store
        
    def log_event(
        self,
        event_type: EventType,
        actor_type: ActorType,
        source_document_id: Optional[str] = None,
        clause_id: Optional[str] = None,
        partition: Optional[str] = None,
        prediction_id: Optional[str] = None,
        review_id: Optional[str] = None,
        actor_reference: Optional[str] = None,
        module_name: Optional[str] = None,
        module_version: Optional[str] = None,
        input_references: Optional[List[str]] = None,
        output_references: Optional[List[str]] = None,
        configuration_reference: Optional[str] = None,
        event_payload: Optional[Dict[str, Any]] = None,
        is_test_fixture: bool = False
    ) -> AuditEvent:
        
        last_event = self.store.get_last_event()
        previous_hash = last_event.event_hash if last_event else None
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            source_document_id=source_document_id,
            clause_id=clause_id,
            partition=partition,
            prediction_id=prediction_id,
            review_id=review_id,
            actor_type=actor_type,
            actor_reference=actor_reference,
            module_name=module_name,
            module_version=module_version,
            input_references=input_references or [],
            output_references=output_references or [],
            configuration_reference=configuration_reference,
            event_payload=event_payload or {},
            previous_event_hash=previous_hash,
            is_test_fixture=is_test_fixture
        )
        
        event.event_hash = calculate_event_hash(event)
        
        # Append securely
        self.store.append(event)
        
        return event.model_copy(deep=True)
