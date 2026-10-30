import pytest
from src.adapters.schema import DatasetRecord, TaskType
from src.preprocessing.pipeline import PreprocessingPipeline
from src.segmentation.pipeline import SegmentationPipeline
from src.segmentation.schema import SegmentType

def make_preprocessed(text: str):
    rec = DatasetRecord.model_construct(
        record_id="1", source_dataset="TEST", source_document_id="doc1", contract_id=None, clause_id=None,
        text=text, task=TaskType.QA_SPAN_EXTRACTION, original_label="Label", normalized_label=None,
        evidence=[], rationale=None, domain=None, language=None, annotation_source=None, source_reference=None,
        license_status=None, access_status=None, metadata={"is_test_fixture": True}
    )
    p = PreprocessingPipeline()
    return p.preprocess_record(rec)

def test_multiline_clause():
    text = (
        "1. Confidentiality\n\n"
        "The Receiving Party shall protect Confidential Information\n"
        "and shall not disclose such information to any third party\n"
        "except as permitted under this Agreement.\n\n"
        "1.1 Exceptions\n\n"
        "The obligations above shall not apply where ..."
    )
    p = SegmentationPipeline()
    doc = p.segment_record(make_preprocessed(text))
    
    # 1. Confidentiality
    # Body of 1.
    # 1.1 Exceptions
    # Body of 1.1
    # Actually, "1. Confidentiality" is detected as CLAUSE.
    # The next paragraph is merged because it has no numbering!
    # Wait, "1. Confidentiality" has numbering "1.". 
    # But does the block itself have a new line? The text has "\n\n" after "Confidentiality".
    # So "1. Confidentiality" is block 1.
    # "The Receiving Party..." is block 2.
    # Block 2 has no numbering. So it gets merged into Block 1!
    # Let's verify.
    
    assert len(doc.segments) == 2
    assert doc.segments[0].numbering == "1."
    assert "Receiving Party" in doc.segments[0].text
    assert doc.segments[1].numbering == "1.1"
    assert "obligations above" in doc.segments[1].text
    
def test_offset_invariant():
    text = (
        "1. First clause.\n\n"
        "This is the second physical block of the first clause.\n\n"
        "2. Second clause."
    )
    p = SegmentationPipeline()
    doc = p.segment_record(make_preprocessed(text))
    
    for seg in doc.segments:
        # EXACT source-text substring invariant
        assert seg.text == text[seg.original_start:seg.original_end]
        
def test_representative_structural_fixture():
    text = (
        "DOCUMENT TITLE\n\n"
        "1. Confidentiality\n\n"
        "1.1 Confidential Information\n\n"
        "1.1.1 Definition\n\n"
        "(a) First obligation\n\n"
        "(b) Second obligation\n\n"
        "(i) Nested item\n\n"
        "(ii) Nested item\n\n"
        "2. Termination\n\n"
        "\"Confidential Information\" means information disclosed by one party..."
    )
    p = SegmentationPipeline()
    doc = p.segment_record(make_preprocessed(text))
    
    segs = doc.segments
    assert segs[0].segment_type == SegmentType.DOCUMENT_TITLE
    assert segs[1].numbering == "1."
    assert segs[1].level == 2
    assert segs[2].numbering == "1.1"
    assert segs[2].level == 3
    assert segs[3].numbering == "1.1.1"
    assert segs[3].level == 4
    assert segs[4].numbering == "(a)"
    assert segs[4].level == 5
    assert segs[6].numbering == "(i)"
    assert segs[6].level == 6
    assert segs[8].numbering == "2."
    assert segs[9].segment_type == SegmentType.DEFINITION
    
    # Hierarchy
    assert segs[1].parent_segment_id == segs[0].segment_id
    assert segs[2].parent_segment_id == segs[1].segment_id
    assert segs[3].parent_segment_id == segs[2].segment_id
    assert segs[4].parent_segment_id == segs[3].segment_id
    assert segs[6].parent_segment_id == segs[5].segment_id
