import pytest
from src.segmentation.schema import Segment, SegmentType
from src.segmentation.hierarchy import build_hierarchy

def test_hierarchy_levels():
    segs = [
        Segment(segment_id="1", segment_type=SegmentType.CLAUSE, text="1. A", original_start=0, original_end=1, source_dataset="T", source_document_id="1", numbering="1."),
        Segment(segment_id="2", segment_type=SegmentType.CLAUSE, text="1.1 B", original_start=2, original_end=3, source_dataset="T", source_document_id="1", numbering="1.1"),
        Segment(segment_id="3", segment_type=SegmentType.CLAUSE, text="(a) C", original_start=4, original_end=5, source_dataset="T", source_document_id="1", numbering="(a)"),
        Segment(segment_id="4", segment_type=SegmentType.CLAUSE, text="2. D", original_start=6, original_end=7, source_dataset="T", source_document_id="1", numbering="2.")
    ]
    built = build_hierarchy(segs)
    assert built[1].parent_segment_id == "1"
    assert built[2].parent_segment_id == "2"
    assert built[3].parent_segment_id is None # Top level 2.
