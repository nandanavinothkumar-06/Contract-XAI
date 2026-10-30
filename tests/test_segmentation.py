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

def test_heading_and_paragraph():
    text = "CONFIDENTIALITY\n\nThis is a confidential agreement."
    p = SegmentationPipeline()
    doc = p.segment_record(make_preprocessed(text))
    
    assert len(doc.segments) == 2
    assert doc.segments[0].segment_type == SegmentType.DOCUMENT_TITLE
    assert doc.segments[1].segment_type == SegmentType.PARAGRAPH

def test_numbered_clauses():
    text = "1. First clause.\n\n2. Second clause.\n\n2.1 Subclause."
    p = SegmentationPipeline()
    doc = p.segment_record(make_preprocessed(text))
    
    assert len(doc.segments) == 3
    assert doc.segments[0].numbering == "1."
    assert doc.segments[2].numbering == "2.1"
    assert doc.segments[2].parent_segment_id == doc.segments[1].segment_id

def test_definitions():
    text = "\"Agreement\" means the document."
    p = SegmentationPipeline()
    doc = p.segment_record(make_preprocessed(text))
    assert doc.segments[0].segment_type == SegmentType.DEFINITION
