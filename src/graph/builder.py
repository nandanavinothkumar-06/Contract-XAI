from typing import List, Dict, Optional
from src.segmentation.schema import Segment
from src.graph.schema import RelationshipGraph, GraphNode, GraphEdge, RelationType
from src.graph.cross_reference import CrossReferenceDetector
import json

class GraphBuilder:
    def __init__(self):
        self.ref_detector = CrossReferenceDetector()
        
    def _create_node_id(self, source_document_id: str, clause_id: str) -> str:
        return f"{source_document_id}_{clause_id}"

    def build(self, segments: List[Segment]) -> RelationshipGraph:
        if not segments:
            raise ValueError("No segments provided")
            
        doc_id = segments[0].source_document_id
        partition = segments[0].metadata.get("partition", "UNKNOWN")
        
        # 1. Validation
        for s in segments:
            if s.source_document_id != doc_id:
                raise ValueError("FAILED_GRAPH_INTEGRITY: Cross-document edges rejected")
            if s.metadata.get("partition", "UNKNOWN") != partition:
                raise ValueError("FAILED_LEAKAGE_CHECK: Cross-partition edges rejected")
                
        # 2. Build Nodes
        nodes = []
        node_map = {}
        for s in segments:
            n_id = self._create_node_id(s.source_document_id, s.segment_id)
            parent_node_id = self._create_node_id(s.source_document_id, s.parent_segment_id) if s.parent_segment_id else None
            
            node = GraphNode(
                node_id=n_id,
                clause_id=s.segment_id,
                source_document_id=s.source_document_id,
                partition=s.metadata.get("partition", "UNKNOWN"),
                text=s.text,
                source_start=s.original_start,
                source_end=s.original_end,
                parent_segment_id=parent_node_id,
                sequence=s.sequence
            )
            nodes.append(node)
            node_map[n_id] = node
            
        # Ensure node sequence ordering
        nodes.sort(key=lambda x: x.sequence)
        
        edges = []
        
        # 3. Structural Relationships
        for node in nodes:
            if node.parent_segment_id and node.parent_segment_id in node_map:
                edges.append(GraphEdge(
                    source_node=node.parent_segment_id,
                    target_node=node.node_id,
                    relation_type=RelationType.PARENT_OF,
                    direction="parent->child",
                    method="STRUCTURAL_SEGMENTATION"
                ))
                edges.append(GraphEdge(
                    source_node=node.parent_segment_id,
                    target_node=node.node_id,
                    relation_type=RelationType.CONTAINS,
                    direction="container->contained",
                    method="STRUCTURAL_SEGMENTATION"
                ))
                
        # 4. Adjacency Relationships
        for i in range(len(nodes) - 1):
            curr_node = nodes[i]
            next_node = nodes[i+1]
            edges.append(GraphEdge(
                source_node=curr_node.node_id,
                target_node=next_node.node_id,
                relation_type=RelationType.PRECEDES,
                direction="earlier->later",
                method="STRUCTURAL_SEQUENCE"
            ))
            edges.append(GraphEdge(
                source_node=next_node.node_id,
                target_node=curr_node.node_id,
                relation_type=RelationType.FOLLOWS,
                direction="later->earlier",
                method="STRUCTURAL_SEQUENCE"
            ))
            
        # 5. Cross-References
        ref_edges = self.ref_detector.extract_references(nodes)
        edges.extend(ref_edges)
        
        # 6. Duplicate Edge Removal and Sorting
        unique_edges = {}
        for edge in edges:
            unique_edges[edge.sort_key()] = edge
            
        final_edges = list(unique_edges.values())
        final_edges.sort(key=lambda x: x.sort_key())
        
        return RelationshipGraph(
            source_document_id=doc_id,
            partition=partition,
            nodes=nodes,
            edges=final_edges
        )
