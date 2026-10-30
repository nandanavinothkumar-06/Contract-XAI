from typing import List, Optional
from src.graph.schema import RelationshipGraph, GraphNode, GraphEdge, RelationType

class GraphQueryInterface:
    def __init__(self, graph: RelationshipGraph):
        self.graph = graph
        self.node_map = {n.clause_id: n for n in graph.nodes}
        self.edges = graph.edges
        
    def get_node(self, clause_id: str) -> Optional[GraphNode]:
        return self.node_map.get(clause_id)
        
    def _find_targets(self, clause_id: str, relation_type: RelationType) -> List[GraphNode]:
        node = self.get_node(clause_id)
        if not node:
            return []
        
        targets = []
        for edge in self.edges:
            if edge.source_node == node.node_id and edge.relation_type == relation_type and edge.target_node:
                # Find target node
                t = next((n for n in self.graph.nodes if n.node_id == edge.target_node), None)
                if t:
                    targets.append(t)
        return targets
        
    def get_parents(self, clause_id: str) -> List[GraphNode]:
        # PARENT_OF goes parent -> child. We need to find edges where target is our clause and type is PARENT_OF
        node = self.get_node(clause_id)
        if not node:
            return []
            
        parents = []
        for edge in self.edges:
            if edge.target_node == node.node_id and edge.relation_type == RelationType.PARENT_OF:
                p = next((n for n in self.graph.nodes if n.node_id == edge.source_node), None)
                if p:
                    parents.append(p)
        return parents

    def get_children(self, clause_id: str) -> List[GraphNode]:
        return self._find_targets(clause_id, RelationType.PARENT_OF)
        
    def get_preceding(self, clause_id: str) -> List[GraphNode]:
        # Edges where target is our clause and type is PRECEDES (meaning source precedes us)
        node = self.get_node(clause_id)
        if not node:
            return []
        prec = []
        for edge in self.edges:
            if edge.target_node == node.node_id and edge.relation_type == RelationType.PRECEDES:
                p = next((n for n in self.graph.nodes if n.node_id == edge.source_node), None)
                if p:
                    prec.append(p)
        return prec
        
    def get_following(self, clause_id: str) -> List[GraphNode]:
        return self._find_targets(clause_id, RelationType.PRECEDES)
        
    def get_cross_references(self, clause_id: str) -> List[GraphEdge]:
        node = self.get_node(clause_id)
        if not node:
            return []
        refs = []
        for edge in self.edges:
            if edge.source_node == node.node_id and edge.relation_type == RelationType.EXPLICIT_CROSS_REFERENCE:
                refs.append(edge)
        return refs
