from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from src.audit.provenance import EventType, ActorType

class AuditEvent(BaseModel):
    event_id: str
    event_type: EventType
    event_version: str = "1.0.0"
    timestamp: str  # ISO-8601 UTC timestamp
    
    source_document_id: Optional[str] = None
    clause_id: Optional[str] = None
    partition: Optional[str] = None
    prediction_id: Optional[str] = None
    review_id: Optional[str] = None
    
    actor_type: ActorType
    actor_reference: Optional[str] = None
    
    module_name: Optional[str] = None
    module_version: Optional[str] = None
    
    input_references: List[str] = Field(default_factory=list)
    output_references: List[str] = Field(default_factory=list)
    configuration_reference: Optional[str] = None
    
    event_payload: Dict[str, Any] = Field(default_factory=dict)
    
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None
    
    is_test_fixture: bool = False
