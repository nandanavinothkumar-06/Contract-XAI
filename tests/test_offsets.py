import pytest
from src.preprocessing.pipeline import PreprocessingPipeline
from src.adapters.schema import DatasetRecord, TaskType, EvidenceSpan

def test_evidence_span_validation():
    # Valid span
    span = EvidenceSpan(start=0, end=5, text="Hello", source_field="text")
    record = DatasetRecord(
        record_id="1", source_dataset="TEST", source_document_id="doc1",
        text="Hello world", task=TaskType.QA_SPAN_EXTRACTION, original_label="Label",
        evidence=[span], metadata={"is_test_fixture": True}
    )
    
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert len(processed.evidence) == 1
    assert processed.evidence[0].original_start == 0

def test_evidence_out_of_bounds_flag():
    # Out of bounds span creates a quality flag, but DOES NOT drop the record
    span = EvidenceSpan(start=0, end=50, text="long", source_field="text")
    record = DatasetRecord.model_construct(
        record_id="1", source_dataset="TEST", source_document_id="doc1", contract_id=None, clause_id=None,
        text="Hello", task=TaskType.QA_SPAN_EXTRACTION, original_label="Label", normalized_label=None,
        evidence=[span], rationale=None, domain=None, language=None, annotation_source=None, source_reference=None,
        license_status=None, access_status=None, metadata={"is_test_fixture": True}
    )
    
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert "EVIDENCE_OUT_OF_BOUNDS" in processed.quality_flags

def test_offset_mapping_unavailable_when_length_changes():
    # Whitespace normalization changes length, so processed_start should be None
    span = EvidenceSpan(start=0, end=5, text="Hello", source_field="text")
    record = DatasetRecord(
        record_id="1", source_dataset="TEST", source_document_id="doc1",
        text="Hello   world", task=TaskType.QA_SPAN_EXTRACTION, original_label="Label",
        evidence=[span], metadata={"is_test_fixture": True}
    )
    
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert processed.evidence[0].offset_mapping_status == "UNAVAILABLE"
    assert processed.evidence[0].processed_start is None

def test_offset_mapping_available_when_length_preserved():
    # Just unicode replacing that preserves length
    span = EvidenceSpan(start=0, end=5, text="Hello", source_field="text")
    record = DatasetRecord(
        record_id="1", source_dataset="TEST", source_document_id="doc1",
        text="Hello world", task=TaskType.QA_SPAN_EXTRACTION, original_label="Label",
        evidence=[span], metadata={"is_test_fixture": True}
    )
    
    # disable whitespace normalization so length doesn't change implicitly if there were spaces
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert processed.evidence[0].offset_mapping_status == "AVAILABLE"
    assert processed.evidence[0].processed_start == 0
