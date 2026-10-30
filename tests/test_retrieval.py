import pytest
import numpy as np
import tempfile
import os
from src.retrieval.schema import RetrievalQuery
from src.retrieval.config import RetrievalConfig
from src.retrieval.embeddings import EmbeddingsModule
from src.retrieval.index import VectorIndex
from src.retrieval.retriever import SemanticRetriever
from src.segmentation.schema import Segment, SegmentType

def build_segments(doc_id: str, count: int, partition: str = "TRAIN", start_id: int = 0) -> list:
    return [
        Segment(
            segment_id=f"c{start_id+i}",
            segment_type=SegmentType.CLAUSE,
            text=f"This is clause {start_id+i} for testing semantic retrieval in {partition}",
            original_start=(start_id+i)*100,
            original_end=(start_id+i)*100 + 50,
            sequence=start_id+i,
            source_dataset="TEST",
            source_document_id=doc_id,
            metadata={"partition": partition}
        ) for i in range(count)
    ]

@pytest.fixture
def config():
    return RetrievalConfig(force_mock=True, top_k=3)

@pytest.fixture
def embeddings(config):
    return EmbeddingsModule(config)

def test_embeddings_normalization(embeddings):
    # is_test_fixture = True
    texts = ["hello world", "contract testing"]
    embs, meta = embeddings.encode(texts)
    
    # Check L2 normalization
    norms = np.linalg.norm(embs, axis=1)
    np.testing.assert_allclose(norms, np.ones(2), rtol=1e-5)

def test_faiss_index_mapping_and_serialization(embeddings):
    # is_test_fixture = True
    segments = build_segments("doc1", 5, "TRAIN")
    index = VectorIndex("idx_1", "TRAIN", embeddings)
    index.build(segments)
    
    assert len(index.mapping) == 5
    assert len(index.clause_data) == 5
    
    # Save & Load
    with tempfile.TemporaryDirectory() as tmpdir:
        index.save(tmpdir)
        index2 = VectorIndex("idx_2", "TRAIN", embeddings)
        index2.load(tmpdir)
        
        assert index2.partition == "TRAIN"
        assert len(index2.mapping) == 5
        assert len(index2.clause_data) == 5
        assert index2.mapping[0] == "c0"
        
def test_partition_isolation(embeddings):
    # is_test_fixture = True
    train_segs = build_segments("doc1", 2, "TRAIN", 0)
    val_segs = build_segments("doc2", 2, "VALIDATION", 2)
    test_segs = build_segments("doc3", 2, "TEST", 4)
    
    idx_train = VectorIndex("idx_t", "TRAIN", embeddings)
    idx_train.build(train_segs)
    
    idx_val = VectorIndex("idx_v", "VALIDATION", embeddings)
    idx_val.build(val_segs)
    
    idx_test = VectorIndex("idx_test", "TEST", embeddings)
    idx_test.build(test_segs)
    
    retriever_train = SemanticRetriever(idx_train, RetrievalConfig(force_mock=True))
    retriever_val = SemanticRetriever(idx_val, RetrievalConfig(force_mock=True))
    
    # Valid
    query_train = RetrievalQuery(
        query_clause_id="q1",
        query_source_document_id="doc_q",
        query_text="Find something similar",
        partition="TRAIN"
    )
    res = retriever_train.retrieve(query_train)
    assert len(res) == 2
    
    # Invalid (query partition doesn't match index)
    with pytest.raises(ValueError, match="FAILED_LEAKAGE_CHECK"):
        query_val = RetrievalQuery(
            query_clause_id="q2",
            query_source_document_id="doc_q",
            query_text="Find something",
            partition="VALIDATION" # querying train index with validation partition
        )
        retriever_train.retrieve(query_val)
        
def test_exact_text_leakage(embeddings):
    # is_test_fixture = True
    # Build two indices with exact same text
    segs = build_segments("doc1", 1, "TRAIN")
    segs2 = build_segments("doc2", 1, "VALIDATION")
    segs2[0].text = segs[0].text # Force exact duplicate
    
    idx1 = VectorIndex("idx1", "TRAIN", embeddings)
    idx1.build(segs)
    
    idx2 = VectorIndex("idx2", "VALIDATION", embeddings)
    idx2.build(segs2)
    
    with pytest.raises(ValueError, match="FAILED_LEAKAGE_CHECK: Exact text overlap"):
        idx1.check_exact_leakage(idx2)

def test_retriever_filters(embeddings):
    # is_test_fixture = True
    segs = build_segments("doc1", 5, "TRAIN")
    idx = VectorIndex("idx1", "TRAIN", embeddings)
    idx.build(segs)
    
    config = RetrievalConfig(force_mock=True, top_k=2, exclude_query=True)
    retriever = SemanticRetriever(idx, config)
    
    # Exclude self retrieval
    query = RetrievalQuery(
        query_clause_id="c0", # Self
        query_source_document_id="doc1",
        query_text=segs[0].text,
        partition="TRAIN"
    )
    
    results = retriever.retrieve(query)
    assert len(results) == 2
    for r in results:
        assert r.result_clause_id != "c0" # Should not contain c0
        assert r.source_start > 0
        # Invariant check
        assert r.result_text == idx.clause_data[r.result_clause_id].text
        
def test_empty_handling(embeddings):
    # is_test_fixture = True
    config = RetrievalConfig(force_mock=True)
    idx = VectorIndex("idx", "TRAIN", embeddings)
    retriever = SemanticRetriever(idx, config)
    
    # Empty query
    with pytest.raises(ValueError, match="Empty query"):
        retriever.retrieve(RetrievalQuery(
            query_clause_id="q",
            query_source_document_id="d",
            query_text="",
            partition="TRAIN"
        ))
        
    # Empty corpus
    with pytest.raises(ValueError, match="Empty corpus"):
        retriever.retrieve(RetrievalQuery(
            query_clause_id="q",
            query_source_document_id="d",
            query_text="hello",
            partition="TRAIN"
        ))
        
def test_contextualized_query(embeddings):
    # is_test_fixture = True
    segs = build_segments("doc1", 2, "TRAIN")
    idx = VectorIndex("idx1", "TRAIN", embeddings)
    idx.build(segs)
    
    config = RetrievalConfig(force_mock=True, exclude_query=True)
    retriever = SemanticRetriever(idx, config)
    
    query = RetrievalQuery(
        query_clause_id="ctx_001",
        query_source_document_id="doc1",
        query_text="[CONTEXT] ... [/CONTEXT] [TARGET] " + segs[1].text + " [/TARGET]",
        partition="TRAIN",
        is_contextualized=True,
        target_clause_id="c1" # Maps back to actual clause c1
    )
    
    results = retriever.retrieve(query)
    # Ensure c1 was excluded from results due to exclude_query = True acting on target_clause_id
    for r in results:
        assert r.result_clause_id != "c1"
        assert r.query_clause_id == "c1" # Contextualized query tracks original target
