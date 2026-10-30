import pytest
import json
from src.segmentation.schema import Segment, SegmentType
from src.graph.builder import GraphBuilder
from src.graph.query import GraphQueryInterface
from src.graph.schema import RelationType, ResolutionStatus, RelationshipGraph

def build_segments(doc_id: str, partition: str = "TRAIN") -> list:
    return [
        Segment(
            segment_id="s0",
            segment_type=SegmentType.SECTION_HEADING,
            text="1. Termination",
            original_start=0,
            original_end=14,
            sequence=0,
            source_dataset="TEST",
            source_document_id=doc_id,
            metadata={"partition": partition}
        ),
        Segment(
            segment_id="s1",
            segment_type=SegmentType.CLAUSE,
            text="1.1 The contract terminates as subject to Section 2.",
            original_start=15,
            original_end=67,
            sequence=1,
            parent_segment_id="s0",
            source_dataset="TEST",
            source_document_id=doc_id,
            metadata={"partition": partition}
        ),
        Segment(
            segment_id="s2",
            segment_type=SegmentType.SECTION_HEADING,
            text="2. Obligations",
            original_start=68,
            original_end=82,
            sequence=2,
            source_dataset="TEST",
            source_document_id=doc_id,
            metadata={"partition": partition}
        ),
        Segment(
            segment_id="s3",
            segment_type=SegmentType.CLAUSE,
            text="2.1 Obligations under this Section 2.1 are final.",
            original_start=83,
            original_end=132,
            sequence=3,
            parent_segment_id="s2",
            source_dataset="TEST",
            source_document_id=doc_id,
            metadata={"partition": partition}
        ),
        Segment(
            segment_id="s4",
            segment_type=SegmentType.CLAUSE,
            text="2.2 Unresolved reference to Section 99.",
            original_start=133,
            original_end=172,
            sequence=4,
            parent_segment_id="s2",
            source_dataset="TEST",
            source_document_id=doc_id,
            metadata={"partition": partition}
        )
    ]

def test_graph_builder_structural():
    segments = build_segments("doc1")
    builder = GraphBuilder()
    graph = builder.build(segments)
    
    assert len(graph.nodes) == 5
    
    query = GraphQueryInterface(graph)
    parents = query.get_parents("s1")
    assert len(parents) == 1
    assert parents[0].clause_id == "s0"
    
    children = query.get_children("s2")
    assert len(children) == 2
    assert children[0].clause_id == "s3"
    assert children[1].clause_id == "s4"
    
    preceding = query.get_preceding("s1")
    assert len(preceding) == 1
    assert preceding[0].clause_id == "s0"

def test_graph_cross_references():
    segments = build_segments("doc1")
    builder = GraphBuilder()
    graph = builder.build(segments)
    query = GraphQueryInterface(graph)
    
    refs = query.get_cross_references("s1")
    assert len(refs) == 1
    edge = refs[0]
    assert edge.resolution_status == ResolutionStatus.RESOLVED
    assert edge.target_node == "doc1_s2"
    assert edge.evidence.text == "Section 2"
    assert edge.evidence.source_start == 57 # 15 + "1.1 The contract terminates as subject to ".length (42) -> 57
    
    # Verify offset invariant
    assert segments[1].text[edge.evidence.source_start - segments[1].original_start : edge.evidence.source_end - segments[1].original_start] == edge.evidence.text
    
    # Self reference
    refs2 = query.get_cross_references("s3")
    assert len(refs2) == 0 # SELF_REFERENCE edges are omitted

    # Unresolved reference
    refs3 = query.get_cross_references("s4")
    assert len(refs3) == 1
    assert refs3[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert refs3[0].target_node is None

def test_graph_leakage_and_integrity():
    builder = GraphBuilder()
    
    # Cross partition
    train_segs = build_segments("doc1", "TRAIN")
    val_segs = build_segments("doc1", "VALIDATION")
    
    with pytest.raises(ValueError, match="FAILED_LEAKAGE_CHECK"):
        builder.build([train_segs[0], val_segs[1]])
        
    # Cross document
    doc1 = build_segments("doc1", "TRAIN")
    doc2 = build_segments("doc2", "TRAIN")
    
    with pytest.raises(ValueError, match="FAILED_GRAPH_INTEGRITY"):
        builder.build([doc1[0], doc2[1]])

def test_graph_serialization():
    segments = build_segments("doc1")
    builder = GraphBuilder()
    graph = builder.build(segments)
    
    # Test JSON dump
    data = graph.model_dump()
    json_str = json.dumps(data)
    
    # Can deserialize back
    graph2 = RelationshipGraph.model_validate_json(json_str)
    assert len(graph2.nodes) == len(graph.nodes)
    assert len(graph2.edges) == len(graph.edges)
