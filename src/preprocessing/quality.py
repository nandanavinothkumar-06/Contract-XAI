from typing import List
from src.adapters.schema import DatasetRecord

def generate_quality_flags(record: DatasetRecord) -> List[str]:
    flags = []
    text = record.text
    
    if not text or not text.strip():
        flags.append("EMPTY_TEXT")
    elif len(text.strip()) < 10:
        flags.append("VERY_SHORT_TEXT")
        
    if "\x00" in text or "\ufffd" in text:
        flags.append("UNICODE_ANOMALY")
        
    if "  " in text or "\n\n\n" in text:
        flags.append("EXCESSIVE_WHITESPACE")
        
    if not record.source_document_id:
        flags.append("MISSING_SOURCE_ID")
        
    if record.original_label is None:
        flags.append("MISSING_LABEL")
        
    if not record.evidence and record.task.value in ["QA_SPAN_EXTRACTION", "DOCUMENT_NLI"]:
        flags.append("MISSING_EVIDENCE")
        
    # Check evidence out of bounds
    text_len = len(text)
    for span in record.evidence:
        if span.source_field == 'text' and (span.start < 0 or span.end > text_len):
            flags.append("EVIDENCE_OUT_OF_BOUNDS")
            break
            
    return flags
