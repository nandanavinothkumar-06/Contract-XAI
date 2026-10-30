import pytest
from src.preprocessing.pipeline import PreprocessingPipeline
from src.preprocessing.config import PreprocessingConfig
from src.adapters.schema import DatasetRecord, TaskType

def make_record(text: str, label=None, source_id="") -> DatasetRecord:
    return DatasetRecord(
        record_id="1",
        source_dataset="TEST",
        source_document_id=source_id,
        text=text,
        task=TaskType.QA_SPAN_EXTRACTION,
        original_label=label,
        metadata={"is_test_fixture": True}
    )

def test_quality_flags_missing_metadata():
    record = make_record("valid text")
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert "MISSING_SOURCE_ID" in processed.quality_flags
    assert "MISSING_LABEL" in processed.quality_flags
    assert "MISSING_EVIDENCE" in processed.quality_flags

def test_empty_very_short_text():
    with pytest.raises(ValueError):
        make_record("   ")  # DatasetRecord validation catches empty text
        
    record = make_record("short", label="a", source_id="1")
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert "VERY_SHORT_TEXT" in processed.quality_flags

def test_excessive_whitespace_and_unicode_anomalies():
    record = make_record("text \x00 with  spaces", label="a", source_id="1")
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    assert "UNICODE_ANOMALY" in processed.quality_flags
    assert "EXCESSIVE_WHITESPACE" in processed.quality_flags

def test_duplicate_fingerprint_generation():
    text = "This is a contract."
    r1 = make_record(text, label="a", source_id="1")
    r2 = make_record(text, label="b", source_id="2")
    
    pipeline = PreprocessingPipeline(PreprocessingConfig(deduplicate=True))
    dataset = list(pipeline.preprocess_dataset([r1, r2]))
    
    assert len(dataset) == 2
    assert dataset[0].text_hash == dataset[1].text_hash
    assert "DUPLICATE_TEXT" not in dataset[0].quality_flags
    assert "DUPLICATE_TEXT" in dataset[1].quality_flags

def test_no_default_record_deletion():
    r1 = make_record("same text", label="a", source_id="1")
    r2 = make_record("same text", label="b", source_id="2")
    
    pipeline = PreprocessingPipeline(PreprocessingConfig(deduplicate=True, drop_duplicates=True))
    dataset = list(pipeline.preprocess_dataset([r1, r2]))
    
    assert len(dataset) == 1
    assert dataset[0].original_record.source_document_id == "1"
