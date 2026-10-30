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

def test_offsets_validity():
    text = "Hello\n\nWorld"
    doc = SegmentationPipeline().segment_record(make_preprocessed(text))
    
    assert doc.segments[0].original_start == 0
    assert doc.segments[0].original_end == 5
    assert doc.segments[0].text == "Hello"
    
    assert doc.segments[1].original_start == 7
    assert doc.segments[1].original_end == 12
    assert doc.segments[1].text == "World"
    
    assert "INVALID_OFFSET" not in doc.quality_flags
