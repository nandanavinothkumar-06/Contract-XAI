import pytest
from src.adapters.schema import DatasetRecord, TaskType
from src.preprocessing.pipeline import PreprocessingPipeline
from src.segmentation.pipeline import SegmentationPipeline

def make_preprocessed(text: str):
    rec = DatasetRecord.model_construct(
        record_id="1", source_dataset="TEST", source_document_id="doc1", contract_id=None, clause_id=None,
        text=text, task=TaskType.QA_SPAN_EXTRACTION, original_label="Label", normalized_label=None,
        evidence=[], rationale=None, domain=None, language=None, annotation_source=None, source_reference=None,
        license_status=None, access_status=None, metadata={"is_test_fixture": True}
    )
    return PreprocessingPipeline().preprocess_record(rec)

def test_determinism():
    text = "1. Clause one\n\n2. Clause two"
    r1 = make_preprocessed(text)
    r2 = make_preprocessed(text)
    
    p = SegmentationPipeline()
    d1 = p.segment_record(r1)
    d2 = p.segment_record(r2)
    
    assert d1.segments[0].segment_id == d2.segments[0].segment_id
    assert d1.segmentation_config_hash == d2.segmentation_config_hash
