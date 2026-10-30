import pytest
from src.adapters.registry import registry
from src.adapters.schema import TaskType

def test_registry_contains_adapters():
    assert "CUAD" in registry._adapters
    assert "LEDGAR" in registry._adapters
    assert "ContractNLI" in registry._adapters
    assert "CLAUDETTE" in registry._adapters
    assert "CONSTRUCTION_BASE" in registry._adapters

def test_cuad_adapter():
    adapter = registry.get("CUAD")()
    raw = {
        "document_id": "doc_1", "context": "This is a contract.", "qas_id": "q1",
        "question": "limitation of liability", 
        "answers": [{"text": "contract", "answer_start": 10}],
        "is_test_fixture": True
    }
    assert adapter.validate_source(raw) is True
    record = adapter.convert_record(raw)
    assert record.task == TaskType.QA_SPAN_EXTRACTION
    assert record.original_label == "limitation of liability"
    assert len(record.evidence) == 1
    assert record.evidence[0].start == 10

def test_ledgar_adapter():
    adapter = registry.get("LEDGAR")()
    raw = {
        "provision_id": "p1", "text": "Some provision.", "labels": ["Governing Law", "Jurisdiction"],
        "is_test_fixture": True
    }
    assert adapter.validate_source(raw) is True
    record = adapter.convert_record(raw)
    assert record.task == TaskType.MULTI_LABEL_PROVISION_CLASSIFICATION
    assert record.original_label == ["Governing Law", "Jurisdiction"]
    assert record.source_document_id == "p1"

def test_contractnli_adapter():
    adapter = registry.get("ContractNLI")()
    raw = {
        "document_id": "doc1", "text": "Full text here", "hypothesis": "It entails.",
        "label": "Entailment", "evidence_spans": [{"start": 0, "end": 4, "text": "Full"}],
        "is_test_fixture": True
    }
    record = adapter.convert_record(raw)
    assert record.task == TaskType.DOCUMENT_NLI
    assert record.original_label == "Entailment"
    assert record.evidence[0].start == 0

def test_claudette_adapter():
    adapter = registry.get("CLAUDETTE")()
    raw = {
        "sentence_id": "s1", "text": "Unfair term", "label": "Unilateral change",
        "rationale": "It allows changing terms without notice.",
        "is_test_fixture": True
    }
    record = adapter.convert_record(raw)
    assert record.task == TaskType.UNFAIR_CLAUSE_DETECTION
    assert record.original_label == "Unilateral change"
    assert record.rationale == "It allows changing terms without notice."

def test_construction_adapter():
    adapter = registry.get("CONSTRUCTION_BASE")()
    raw = {
        "document_id": "doc1", "text": "Some spec text", "label": "Risk A",
        "task_type": "CLAUSE_RISK_CLASSIFICATION",
        "is_test_fixture": True
    }
    record = adapter.convert_record(raw)
    assert record.task == TaskType.CLAUSE_RISK_CLASSIFICATION
    assert record.original_label == "Risk A"
