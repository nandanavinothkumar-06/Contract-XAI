from typing import List
from src.adapters.schema import EvidenceSpan
from .schema import ProcessedEvidenceSpan

def process_evidence_spans(
    original_spans: List[EvidenceSpan], 
    offsets_preserved: bool
) -> List[ProcessedEvidenceSpan]:
    processed = []
    for span in original_spans:
        if offsets_preserved:
            processed.append(ProcessedEvidenceSpan(
                original_start=span.start,
                original_end=span.end,
                processed_start=span.start,
                processed_end=span.end,
                text=span.text,
                source_field=span.source_field,
                offset_mapping_status="AVAILABLE"
            ))
        else:
            processed.append(ProcessedEvidenceSpan(
                original_start=span.start,
                original_end=span.end,
                processed_start=None,
                processed_end=None,
                text=span.text,
                source_field=span.source_field,
                offset_mapping_status="UNAVAILABLE"
            ))
    return processed
