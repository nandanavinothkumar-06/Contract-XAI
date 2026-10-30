from .schema import SegmentedDocument

def validate_segments(doc: SegmentedDocument, full_text_length: int):
    max_len = 0
    for seg in doc.segments:
        if seg.original_start >= seg.original_end:
            doc.quality_flags.append("INVALID_OFFSET")
        if seg.original_end > max_len:
            max_len = seg.original_end
            
    for i in range(1, len(doc.segments)):
        if doc.segments[i].original_start < doc.segments[i-1].original_end:
            # allow overlap only if one is parent
            if doc.segments[i].parent_segment_id != doc.segments[i-1].segment_id:
                doc.quality_flags.append("OVERLAPPING_SEGMENTS")
            
    covered = sum(seg.original_end - seg.original_start for seg in doc.segments)
    if full_text_length > 0:
        ratio = covered / full_text_length
        if ratio < 0.5:
            doc.quality_flags.append("LOW_COVERAGE")
