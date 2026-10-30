import json
import hashlib
from typing import Any, Dict
from src.audit.schema import AuditEvent

def canonical_serialize(data: Any) -> str:
    """
    Produce a deterministic, JSON-safe serialization.
    Sorts dictionary keys recursively.
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'))

def calculate_event_hash(event: AuditEvent) -> str:
    """
    Calculate the SHA-256 hash of the deterministic event payload.
    The hash computation EXCLUDES the 'event_hash' field itself to avoid circularity,
    but MUST include the 'previous_event_hash' to form the tamper-evident chain.
    """
    # Exclude event_hash for calculation
    event_dict = event.model_dump(exclude_none=True, exclude={"event_hash"})
    
    canonical_string = canonical_serialize(event_dict)
    
    # Calculate SHA-256
    sha256 = hashlib.sha256()
    sha256.update(canonical_string.encode('utf-8'))
    
    return sha256.hexdigest()
