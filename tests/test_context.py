import pytest
from typing import List
from src.segmentation.schema import Segment, SegmentType
from src.context.builder import ContextBuilder
from src.context.schema import ContextComponent

class DummyTokenizer:
    def __init__(self):
        self.num_special_tokens = 2
        
    def tokenize(self, text: str) -> List[str]:
        return text.split()
        
    def num_special_tokens_to_add(self) -> int:
        return self.num_special_tokens

class DummyWrapper:
    def __init__(self):
        self.tokenizer = DummyTokenizer()

def build_segments(doc_id: str, count: int, parent_child_enabled: bool = False, partition: str = "TRAIN") -> List[Segment]:
    return [
        Segment(
            segment_id=f"s{i}",
            segment_type=SegmentType.CLAUSE,
            text=f"Clause {i}",
            original_start=i*10,
            original_end=i*10 + 8,
            sequence=i,
            source_dataset="TEST",
            source_document_id=doc_id,
            parent_segment_id=f"s{i-1}" if parent_child_enabled and i > 0 and i % 2 == 1 else None,
            metadata={"partition": partition}
        ) for i in range(count)
    ]

def test_strategy_none():
    segments = build_segments("doc1", 5)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    res = builder.build(segments[2], segments, strategy="NONE")
    
    assert len(res.components) == 1
    assert res.components[0].role == "TARGET"
    assert "TARGET" in res.text

def test_strategy_previous_next():
    segments = build_segments("doc1", 5)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    res = builder.build(segments[2], segments, strategy="PREVIOUS_NEXT")
    
    assert len(res.components) == 3
    roles = [c.role for c in res.components]
    assert roles == ["PREVIOUS", "TARGET", "NEXT"]

def test_strategy_window():
    segments = build_segments("doc1", 5)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    res = builder.build(segments[2], segments, strategy="WINDOW", window_size=2)
    
    assert len(res.components) == 5
    assert len(res.metadata.included_context_clause_ids) == 4

def test_strategy_parent_child():
    segments = build_segments("doc1", 5, parent_child_enabled=True)
    # s1 has parent s0. s0 has child s1.
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    res = builder.build(segments[0], segments, strategy="PARENT_CHILD")
    
    # s0 should have child s1
    roles = [c.role for c in res.components]
    assert "CHILD" in roles
    assert "TARGET" in roles
    
def test_cross_document_leakage():
    doc1 = build_segments("doc1", 2)
    doc2 = build_segments("doc2", 2)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    
    with pytest.raises(ValueError, match="Cross-document context leakage detected"):
        builder.build(doc1[0], doc1 + doc2, strategy="PREVIOUS_NEXT")

def test_token_budget_truncation():
    segments = build_segments("doc1", 5)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=10) # very small budget
    # target takes tokens: "[TARGET]", "Clause", "2", "[/TARGET]", plus 2 special tokens. That is 6 tokens.
    # Budget is 10. Next clause takes "[CONTEXT]" "Clause" "3" "[/CONTEXT]" -> 4 tokens + 1 space = 5 tokens.
    # 6 + 5 = 11 > 10. So context is excluded!
    res = builder.build(segments[2], segments, strategy="PREVIOUS_NEXT")
    
    assert res.metadata.context_truncated is True
    assert len(res.metadata.excluded_context_clause_ids) == 2 # PREV and NEXT both excluded
    assert len(res.metadata.included_context_clause_ids) == 0

def test_target_truncation():
    segments = build_segments("doc1", 5)
    # Target takes 6 tokens + 2 special = 8 tokens. Budget 5 => Target truncated!
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=5)
    res = builder.build(segments[2], segments, strategy="NONE")
    
    assert res.metadata.target_truncated is True

def test_edge_cases():
    segments = build_segments("doc1", 1)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    
    # Single clause
    res = builder.build(segments[0], segments, strategy="PREVIOUS_NEXT")
    assert len(res.components) == 1
    
    segments = build_segments("doc1", 5)
    # First clause
    res = builder.build(segments[0], segments, strategy="PREVIOUS_NEXT")
    assert len(res.components) == 2
    
    # Last clause
    res = builder.build(segments[4], segments, strategy="PREVIOUS_NEXT")
    assert len(res.components) == 2

def test_partition_leakage():
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    
    # Generate some segments for each partition
    train_docs = build_segments("doc1", 2, partition="TRAIN")
    val_docs = build_segments("doc1", 2, partition="VALIDATION") # Same doc id, different partition (should never happen, but let's test strict partition check)
    test_docs = build_segments("doc1", 2, partition="TEST")
    
    # Allowed
    builder.build(train_docs[0], train_docs, strategy="PREVIOUS_NEXT")
    builder.build(val_docs[0], val_docs, strategy="PREVIOUS_NEXT")
    builder.build(test_docs[0], test_docs, strategy="PREVIOUS_NEXT")
    
    # Rejected
    with pytest.raises(ValueError, match="Cross-partition context leakage detected"):
        builder.build(train_docs[0], train_docs + val_docs, strategy="PREVIOUS_NEXT")
        
    with pytest.raises(ValueError, match="Cross-partition context leakage detected"):
        builder.build(train_docs[0], train_docs + test_docs, strategy="PREVIOUS_NEXT")
        
    with pytest.raises(ValueError, match="Cross-partition context leakage detected"):
        builder.build(val_docs[0], val_docs + train_docs, strategy="PREVIOUS_NEXT")
        
    with pytest.raises(ValueError, match="Cross-partition context leakage detected"):
        builder.build(val_docs[0], val_docs + test_docs, strategy="PREVIOUS_NEXT")
        
    with pytest.raises(ValueError, match="Cross-partition context leakage detected"):
        builder.build(test_docs[0], test_docs + train_docs, strategy="PREVIOUS_NEXT")
        
    with pytest.raises(ValueError, match="Cross-partition context leakage detected"):
        builder.build(test_docs[0], test_docs + val_docs, strategy="PREVIOUS_NEXT")

def test_evidence_compatibility_offsets():
    segments = build_segments("doc1", 3)
    builder = ContextBuilder(DummyWrapper(), max_sequence_length=100)
    
    res = builder.build(segments[1], segments, strategy="PREVIOUS_NEXT")
    
    # Verify contextualized text at model input offsets matches the text
    for comp in res.components:
        assert res.text[comp.model_input_start:comp.model_input_end] == comp.text
        
    # Verify target metadata maps perfectly
    assert res.metadata.target_model_input_start >= 0
    
    # Original source invariant check
    # Let's mock an original source string
    # original_start=i*10, original_end=i*10+8, text="Clause i"
    original_source = "Clause 0  Clause 1  Clause 2  "
    target_comp = next(c for c in res.components if c.role == "TARGET")
    
    assert original_source[target_comp.source_start:target_comp.source_end] == target_comp.text
    assert target_comp.text == "Clause 1"
    assert original_source[res.metadata.target_source_start:res.metadata.target_source_end] == "Clause 1"
