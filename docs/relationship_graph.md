# Relationship Graph

## 1. Purpose
The Contract Relationship Graph builds an observable, provenance-aware edge structure over existing clause segments. It models spatial hierarchy, adjacency, and explicit textual cross-references. 

**Disclaimer**: The relationship graph represents document-grounded structural and explicit textual relationships. It does not establish legal validity, legal dependency, enforceability, or legal interpretation.

## 2. Node Schema
Nodes natively wrap existing `Segment` definitions. They require:
- `node_id` (deterministically composite string)
- `clause_id`
- `source_document_id`
- `partition`
- `text`
- `source_start` / `source_end`
- `parent_segment_id`
- `sequence`

## 3. Edge Schema
Edges structurally map relationships:
- `source_node`
- `target_node`
- `relation_type`
- `direction`
- `method`
- `evidence` (mapping exact `text` and `source_start` / `source_end` of the reference)
- `resolution_status`

## 4. Supported Relationship Types
- **CONTAINS**: Container → Contained (structural).
- **PARENT_OF**: Parent → Child (structural).
- **PRECEDES**: Earlier → Later (sequential adjacency).
- **FOLLOWS**: Later → Earlier (sequential adjacency).
- **EXPLICIT_CROSS_REFERENCE**: Referencing Clause → Referenced Clause (textual resolution).

## 5. Structural Relationship Derivation
Hierarchy (`PARENT_OF` / `CONTAINS`) is ingested exclusively from TASK 006 output matrices. No heuristic hallucination of legal hierarchy is performed. Adjacency (`PRECEDES` / `FOLLOWS`) relies identically on strictly bounded integer sorting over clause indices. 

## 6. Cross-Reference Resolution
Explicit regex sweeps detect standard legal markers (e.g. `Section 7`, `Clause 12.3`). When text corresponds unequivocally to an existing segment's numerical mapping, the resolution succeeds (`RESOLVED`).
- Unmatched targets yield `UNRESOLVED`.
- Multiple colliding matches yield `AMBIGUOUS`.
- Clauses citing their own number map to `SELF_REFERENCE` (edges structurally omitted to avoid degenerate loops). 

**Disclaimer**: An explicit cross-reference is evidence that one clause refers to another; it does not establish the legal effect of that reference.

## 7. Provenance
Every explicit edge generated retains `method="RULE_BASED_REFERENCE_RESOLUTION"` and stores the verbatim `evidence.text` bounding box.

## 8. Offset Handling
`source_start` and `source_end` integers are natively preserved untouched from TASK 005. They do not drift. Cross-reference offsets sum the local regex match offset with the global `source_start` baseline to guarantee accurate global character bounds. 

## 9. Document Boundaries
A relationship edge is restricted rigorously to matching `source_document_id`s. Any infraction instantly fails pipeline execution (`FAILED_GRAPH_INTEGRITY`). 

## 10. Partition Boundaries
A relationship edge is restricted strictly to matching `partition` metadata dimensions (e.g., TRAIN). Edges connecting across partitions unconditionally throw runtime errors (`FAILED_LEAKAGE_CHECK`). 

## 11. Graph Integrity
Duplicate edges mapping identical tuples are collapsed deterministically prior to aggregation. The complete list sorts logically using a deterministic composite string key. Invalid edge constructions fail eagerly without silent patching. 

## 12. Serialization
The graph supports total deterministic JSON serialization mapping `RelationshipGraph.model_dump()` to raw JSON schemas, retaining identical dictionary hierarchies natively. 

## 13. Query Interface
The module exports basic structural navigators:
- `get_node(clause_id)`
- `get_parents(clause_id)`
- `get_children(clause_id)`
- `get_preceding(clause_id)`
- `get_following(clause_id)`
- `get_cross_references(clause_id)`

## 14. Limitations
- Unresolved references lacking normalized numerical identities are dropped securely.
- Synonymous references (e.g. "as set forth above") are ignored gracefully. 

## 15. Difference Between Explicit Textual Relationships and Legal Reasoning
The EXPLICIT_CROSS_REFERENCE detects strings like "subject to Section 4". It models the textual assertion. It does NOT structurally resolve the logical validity of Section 4 or synthesize the combined textual truth into a composite meaning graph. Semantic similarity matching and embedding comparisons are NOT implemented here. 

## 16. Dataset Status
- **LEDGAR**: NOT_RUN_DATA_UNAVAILABLE
- **ContractNLI**: NOT_RUN_DATA_UNAVAILABLE
- **CUAD**: NOT_APPLICABLE
- **CLAUDETTE**: NOT_RUN_LICENSE_UNRESOLVED
- **Construction Data**: NOT_RUN_DATA_UNAVAILABLE

## 17. Project Result Status
**PROJECT EXPERIMENTAL RESULTS: NONE**
Only simulated synthetic test fixtures (`is_test_fixture=True`) were processed, proving offset integrity and partition isolation bounds. No real semantic similarity models or accuracy benchmarks were derived.
