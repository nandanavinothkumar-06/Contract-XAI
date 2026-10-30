import pytest
from src.preprocessing.pipeline import PreprocessingPipeline
from src.preprocessing.config import PreprocessingConfig
from src.adapters.schema import DatasetRecord, TaskType

def make_dummy_record(text: str, label="label") -> DatasetRecord:
    return DatasetRecord(
        record_id="1",
        source_dataset="TEST",
        source_document_id="doc1",
        text=text,
        task=TaskType.OTHER,
        original_label=label,
        metadata={"is_test_fixture": True}
    )

def test_original_text_preserved():
    text = "   This is \r\n some \x00 text.   "
    record = make_dummy_record(text)
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(record)
    
    assert processed.original_record.text == text
    assert processed.processed_text != text

def test_unicode_normalization():
    # 'e' + acute accent vs single character
    text1 = "e\u0301" 
    text2 = "\u00e9"
    config = PreprocessingConfig(unicode_normalization="NFC")
    pipeline = PreprocessingPipeline(config)
    
    p1 = pipeline.preprocess_record(make_dummy_record(text1)).processed_text
    p2 = pipeline.preprocess_record(make_dummy_record(text2)).processed_text
    assert p1 == p2

def test_whitespace_normalization():
    text = "Section 1.   This is\r\n\r\n\r\n\r\na test.    "
    pipeline = PreprocessingPipeline(PreprocessingConfig(normalize_whitespace=True))
    processed = pipeline.preprocess_record(make_dummy_record(text))
    
    assert "\r\n" not in processed.processed_text
    assert "   " not in processed.processed_text
    assert "\n\n\n" not in processed.processed_text

def test_legal_preservation_logs():
    pipeline = PreprocessingPipeline()
    processed = pipeline.preprocess_record(make_dummy_record("Test text 123 (a)"))
    
    ops = [op.operation for op in processed.preprocessing_operations]
    assert "preserve_punctuation" in ops
    assert "preserve_numbers" in ops
    assert "preserve_section_numbers" in ops
    assert "preserve_defined_terms" in ops
    
def test_config_behavior():
    config = PreprocessingConfig(normalize_whitespace=False, remove_accidental_artifacts=False)
    pipeline = PreprocessingPipeline(config)
    text = "   \x00   "
    processed = pipeline.preprocess_record(make_dummy_record(text))
    assert processed.processed_text == text
