import copy
from typing import List, Optional
from src.audit.schema import AuditEvent

class AuditStore:
    def __init__(self):
        self._events: List[AuditEvent] = []
        
    def append(self, event: AuditEvent):
        # Store a deep copy to ensure immutability inside the store
        self._events.append(event.model_copy(deep=True))
        
    def get_all(self) -> List[AuditEvent]:
        return [e.model_copy(deep=True) for e in self._events]
        
    def get_last_event(self) -> Optional[AuditEvent]:
        if not self._events:
            return None
        return self._events[-1].model_copy(deep=True)
