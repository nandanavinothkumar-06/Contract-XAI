import pytest
from src.preprocessing.pipeline import PreprocessingPipeline
from src.preprocessing.config import PreprocessingConfig
from src.adapters.schema import DatasetRecord, TaskType

def make_dummy_record(text: str) -> DatasetRecord:
    return DatasetRecord(
        record_id="1", source_dataset="TEST", source_document_id="doc1",
        text=text, task=TaskType.OTHER, original_label="Label", metadata={"is_test_fixture": True}
    )

def test_deterministic_output():
    text = "Some  text \r\n with \x00 artifacts."
    r1 = make_dummy_record(text)
    r2 = make_dummy_record(text)
    
    pipeline = PreprocessingPipeline()
    p1 = pipeline.preprocess_record(r1)
    p2 = pipeline.preprocess_record(r2)
    
    assert p1.processed_text == p2.processed_text
    assert p1.text_hash == p2.text_hash
    assert p1.config_hash == p2.config_hash
    assert p1.preprocessing_version == p2.preprocessing_version

def test_config_hash_changes_with_config():
    c1 = PreprocessingConfig(unicode_normalization="NFC")
    c2 = PreprocessingConfig(unicode_normalization="NFD")
    assert c1.config_hash() != c2.config_hash()
