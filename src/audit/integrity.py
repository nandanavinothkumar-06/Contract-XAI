from typing import Tuple, Optional
from src.audit.store import AuditStore
from src.audit.schema import AuditEvent
from src.audit.events import calculate_event_hash
from src.audit.provenance import IntegrityStatus

class AuditVerifier:
    def verify(self, store: AuditStore) -> Tuple[IntegrityStatus, Optional[str]]:
        """
        Walks the tamper-evident chain to verify sequence, hashes, and schemas.
        Returns a tuple: (IntegrityStatus, Optional[str]) where the string is an error message.
        """
        events = store.get_all()
        if not events:
            return IntegrityStatus.VALID, None
            
        expected_previous_hash = None
        seen_ids = set()
        
        for idx, event in enumerate(events):
            # 4. Event ID consistency
            if event.event_id in seen_ids:
                return IntegrityStatus.INVALID_REFERENCE, f"Duplicate event_id detected at index {idx}: {event.event_id}"
            seen_ids.add(event.event_id)
            
            # 3. Previous-event-hash linkage
            if event.previous_event_hash != expected_previous_hash:
                return IntegrityStatus.INVALID_PREVIOUS_HASH, f"Hash chain broken at index {idx} (event {event.event_id})"
                
            # 2. Event hash correctness
            recomputed_hash = calculate_event_hash(event)
            if event.event_hash != recomputed_hash:
                return IntegrityStatus.INVALID_HASH, f"Tampered payload detected at index {idx} (event {event.event_id})"
                
            # 6. Document/partition consistency
            # E.g. if partition is provided but source_document_id is missing
            if event.partition and not event.source_document_id:
                return IntegrityStatus.INVALID_REFERENCE, f"Partition {event.partition} provided without source_document_id at index {idx}"
            if event.clause_id and not event.source_document_id:
                return IntegrityStatus.INVALID_REFERENCE, f"Clause {event.clause_id} provided without source_document_id at index {idx}"
                
            expected_previous_hash = event.event_hash
            
        return IntegrityStatus.VALID, None
