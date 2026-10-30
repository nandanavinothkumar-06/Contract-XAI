from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RelationType(str, Enum):
    CONTAINS = "CONTAINS"
    PARENT_OF = "PARENT_OF"
    PRECEDES = "PRECEDES"
    FOLLOWS = "FOLLOWS"
    EXPLICIT_CROSS_REFERENCE = "EXPLICIT_CROSS_REFERENCE"

class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    SELF_REFERENCE = "SELF_REFERENCE"

class EdgeEvidence(BaseModel):
    text: str
    source_start: int
    source_end: int

class GraphEdge(BaseModel):
    source_node: str
    target_node: Optional[str] = None
    relation_type: RelationType
    direction: str
    method: str
    evidence: Optional[EdgeEvidence] = None
    resolution_status: Optional[ResolutionStatus] = None
    
    # Deterministic sorting representation
    def sort_key(self) -> str:
        return f"{self.source_node}-{self.target_node}-{self.relation_type}-{self.resolution_status}"

class GraphNode(BaseModel):
    node_id: str
    clause_id: str
    source_document_id: str
    partition: str
    text: str
    source_start: int
    source_end: int
    parent_segment_id: Optional[str] = None
    sequence: int

class RelationshipGraph(BaseModel):
    graph_version: str = "1.0.0"
    source_document_id: str
    partition: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
