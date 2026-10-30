import re
from typing import List, Optional
from src.graph.schema import GraphNode, GraphEdge, EdgeEvidence, RelationType, ResolutionStatus

class CrossReferenceDetector:
    def __init__(self):
        # Regex to find explicit references like "Section 7", "Clause 12.3", "Paragraph (a)"
        self.ref_pattern = re.compile(
            r'\b(?:[Ss]ection|[Cc]lause|[Pp]aragraph)\s+([A-Za-z0-9\.\(\)]+)\b'
        )

    def extract_references(self, nodes: List[GraphNode]) -> List[GraphEdge]:
        edges = []
        
        # Build a lookup for resolution
        # Key: lowercased normalized heading/numbering, Value: List of matching nodes
        # Wait, nodes don't explicitly carry numbering in GraphNode schema, let's extract it from the text roughly 
        # or we could rely on segment metadata if it was passed. 
        # Let's assume we can parse out the number from the node text for a simple resolution mapping.
        
        number_map = {}
        for node in nodes:
            # Simplistic: assume the text starts with the section number e.g. "12.3 Termination"
            # Or we look for a numbering prefix
            match = re.match(r'^([A-Za-z0-9\.\(\)]+)', node.text.strip())
            if match:
                num = match.group(1).lower().rstrip('.')
                if num not in number_map:
                    number_map[num] = []
                number_map[num].append(node)
                
        for node in nodes:
            for match in self.ref_pattern.finditer(node.text):
                ref_text = match.group(0)
                ref_num = match.group(1).lower().rstrip('.')
                
                source_start = node.source_start + match.start()
                source_end = node.source_start + match.end()
                
                evidence = EdgeEvidence(
                    text=ref_text,
                    source_start=source_start,
                    source_end=source_end
                )
                
                targets = number_map.get(ref_num, [])
                
                if len(targets) == 0:
                    status = ResolutionStatus.UNRESOLVED
                    target_node_id = None
                elif len(targets) == 1:
                    if targets[0].node_id == node.node_id:
                        status = ResolutionStatus.SELF_REFERENCE
                        target_node_id = targets[0].node_id
                    else:
                        status = ResolutionStatus.RESOLVED
                        target_node_id = targets[0].node_id
                else:
                    status = ResolutionStatus.AMBIGUOUS
                    target_node_id = None
                    
                edge = GraphEdge(
                    source_node=node.node_id,
                    target_node=target_node_id,
                    relation_type=RelationType.EXPLICIT_CROSS_REFERENCE,
                    direction="referencing_clause->referenced_clause",
                    method="RULE_BASED_REFERENCE_RESOLUTION",
                    evidence=evidence,
                    resolution_status=status
                )
                
                # Exclude self-references as per acceptance criteria (don't create edge for it, just mark status)
                # If we omit the graph edge, we shouldn't even append it unless it's useful.
                # Requirement: "Prefer: resolution_status = SELF_REFERENCE and omit the graph edge."
                if status != ResolutionStatus.SELF_REFERENCE:
                    edges.append(edge)
                
        return edges
