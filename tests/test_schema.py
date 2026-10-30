import pytest
from src.adapters.schema import DatasetRecord, TaskType, EvidenceSpan

def test_evidence_span_negative_offsets():
    with pytest.raises(ValueError):
        EvidenceSpan(start=-1, end=5, text="hello", source_field="text")

def test_evidence_span_end_before_start():
    with pytest.raises(ValueError):
        EvidenceSpan(start=5, end=2, text="hel", source_field="text")

def test_dataset_record_empty_text():
    with pytest.raises(ValueError):
        DatasetRecord(
            record_id="1", source_dataset="Test", source_document_id="doc1",
            text="   ", task=TaskType.OTHER, original_label="Label"
        )

def test_evidence_out_of_bounds():
    with pytest.raises(ValueError):
        DatasetRecord(
            record_id="1", source_dataset="Test", source_document_id="doc1",
            text="short", task=TaskType.OTHER, original_label="Label",
            evidence=[EvidenceSpan(start=0, end=10, text="short extra", source_field="text")]
        )
