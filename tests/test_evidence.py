import pytest
from src.evidence.schema import EvidenceSpan, EvidenceResult
from src.evidence.aggregation import aggregate_and_rank_evidence
from src.evidence.extractor import EvidenceExtractor
from src.models.config import LegalBertConfig
from src.models.legalbert import LegalBertWrapper

def test_evidence_schema():
    span = EvidenceSpan(
        evidence_id="123",
        source_start=0,
        source_end=5,
        text="Hello",
        raw_score=0.9,
        ranking_score=0.9,
        rank=1,
        method="Test",
        prediction_label="L1",
        prediction_score=0.8
    )
    assert span.is_model_derived is True
    assert span.is_ground_truth is False
    assert span.evidence_type == "MODEL_DERIVED_EVIDENCE"

def test_aggregate_and_rank_adjacent():
    text = "Hello world this is a test"
    # Say 'Hello', 'world' have high scores
    token_scores = [0.9, 0.8, 0.1, 0.1, 0.1, 0.1]
    offsets = [(0, 5), (6, 11), (12, 16), (17, 19), (20, 21), (22, 26)]
    special_tokens_mask = [0, 0, 0, 0, 0, 0]
    
    spans = aggregate_and_rank_evidence(
        token_scores=token_scores,
        offsets=offsets,
        special_tokens_mask=special_tokens_mask,
        source_text=text,
        top_k=2
    )
    
    assert len(spans) > 0
    assert spans[0].text == "Hello world"
    assert spans[0].source_start == 0
    assert spans[0].source_end == 11
    # Check invariant
    assert text[spans[0].source_start:spans[0].source_end] == spans[0].text
    assert spans[0].raw_score > 0
    assert spans[0].ranking_score == abs(spans[0].raw_score)

def test_aggregate_and_rank_special_tokens():
    text = "Hello"
    token_scores = [0.9, 0.8, 0.9] # [CLS] Hello [SEP]
    offsets = [(0, 0), (0, 5), (0, 0)]
    special_tokens_mask = [1, 0, 1]
    
    spans = aggregate_and_rank_evidence(
        token_scores=token_scores,
        offsets=offsets,
        special_tokens_mask=special_tokens_mask,
        source_text=text,
        top_k=1
    )
    
    assert len(spans) == 1
    assert spans[0].text == "Hello"

def test_aggregate_and_rank_padding():
    text = "Hello"
    token_scores = [0.8, 0.0, 0.0] 
    offsets = [(0, 5), (0, 0), (0, 0)]
    special_tokens_mask = [0, 1, 1]
    
    spans = aggregate_and_rank_evidence(
        token_scores=token_scores,
        offsets=offsets,
        special_tokens_mask=special_tokens_mask,
        source_text=text,
        top_k=1
    )
    
    assert len(spans) == 1
    assert spans[0].text == "Hello"

def test_extractor_unavailable():
    config = LegalBertConfig(model_checkpoint="invalid/nonexistent", tokenizer_name="invalid/nonexistent")
    wrapper = LegalBertWrapper(config)
    extractor = EvidenceExtractor(wrapper)
    assert not extractor.is_available()
    
    res = extractor.extract("Test", target_label_id=0, target_label_str="Test")
    assert res.alignment_status == "FAILED"
    assert len(res.evidence_spans) == 0

def test_fixture_separation():
    res = EvidenceResult(
        evidence_spans=[],
        method="Test",
        target_label="A",
        target_score=0.9,
        is_test_fixture=True
    )
    assert res.is_test_fixture is True

def test_extractor_immutability():
    config = LegalBertConfig(model_checkpoint="invalid/nonexistent", tokenizer_name="invalid/nonexistent")
    wrapper = LegalBertWrapper(config)
    
    # Mocking unavailable to avoid downloading weights
    if not wrapper.is_available():
        return
        
    import torch
    import copy
    
    # Clone weights
    initial_state = {k: v.clone() for k, v in wrapper.model.state_dict().items()}
    
    extractor = EvidenceExtractor(wrapper)
    res = extractor.extract("This is a test document.", target_label_id=0, target_label_str="TestLabel")
    
    # Verify weights unchanged
    for k, v in wrapper.model.state_dict().items():
        assert torch.equal(v, initial_state[k])
