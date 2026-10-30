# Cross-Clause / Hierarchical Context

## 1. Motivation
Clauses within legal contracts do not exist in a vacuum. A clause's legal impact is frequently modified by its parent section, neighboring clauses, and document-wide definitions. This module provides textual contextualization for isolated clauses to allow Legal-BERT to observe structural neighbors.

## 2. Scope
This module strictly provides *input textual contextualization*. 

**Disclaimer**: Cross-clause context provides additional textual context to the model. It does not establish legal relationships, legal dependency, legal validity, or legal interpretation.

## 3. Context Strategies
Four deterministic configuration strategies are supported:
- **NONE**: Default safe strategy. Injects only the target clause.
- **PREVIOUS_NEXT**: Target clause + immediate sequence predecessor and successor.
- **WINDOW**: A sliding window of `N` preceding and `N` succeeding clauses.
- **PARENT_CHILD**: Leverages hierarchy to append the target's explicit structural parent and any immediate children.

## 4. Target Marking
The contextual model input is delineated clearly using plaintext structural markers:
```
[TARGET]
The target clause text.
[/TARGET]

[CONTEXT]
The neighboring clause text.
[/CONTEXT]
```
No silent tokenizer vocabulary modifications are performed.

## 5. Provenance
Every generated component retains its `clause_id`, `source_document_id`, and exact `source_start` / `source_end` integer offsets mapping back to the unsegmented string. `ContextMetadata` records explicitly which clauses were included or excluded.

## 6. Hierarchy Usage
Hierarchy is natively preserved from TASK 006 output. The module reads `parent_segment_id` references directly. It never hallucinates legal hierarchy from generic semantic similarity. If hierarchy is missing, positional strategies (`PREVIOUS_NEXT` or `WINDOW`) function as fallbacks.

## 7. Token Budget
Before text generation, a `ContextBudgeter` measures actual token boundaries using the loaded Hugging Face `FastTokenizer`. It explicitly budgets against `max_sequence_length`. 

## 8. Truncation
If the context exceeds the budget, contextual components are truncated *first* (in reverse order of priority). If the target clause itself exceeds the length independently, `target_truncated = True` is flipped in the metadata.

## 9. Leakage Prevention
Context is structurally confined to the exact `source_document_id` of the target clause. Contextual cross-pollution is impossible since the compiler throws a runtime error if multiple document IDs are requested in a single builder invocation. This prevents Train context from leaking into Validation/Test sets.

## 10. Evidence Compatibility
Contextualized model-input offsets are distinct from original document offsets. Provenance mappings preserve the relationship between model-input components and their original source spans. `ContextMetadata` explicitly exposes `target_model_input_start`, `target_model_input_end`, `target_source_start`, and `target_source_end`. 

Because `ContextComponent` retains mapping logic, TASK 009 Evidence Extraction can trace model attribution directly back to original coordinates, even inside contextual blocks. The literal text slice mapping is preserved deterministically.

## 11. Multiclass/Multilabel Compatibility
The module modifies only textual input arrays. Softmax (multiclass) and Sigmoid (multilabel) inference behaviors from TASK 008 remain entirely decoupled and unaffected.

## 12. Dataset Status
- **LEDGAR**: NOT_RUN_DATA_UNAVAILABLE
- **ContractNLI**: NOT_RUN_DATA_UNAVAILABLE
- **CUAD**: NOT_APPLICABLE
- **CLAUDETTE**: NOT_RUN_LICENSE_UNRESOLVED
- **Construction**: NOT_RUN_DATA_UNAVAILABLE

## 13. Current Project-Result Status
**PROJECT EXPERIMENTAL RESULTS: NONE**

No experimental tests distinguishing contextual models vs non-contextual baselines were executed since actual benchmark datasets were unavailable locally.

## 14. Limitations
- Does not resolve defined terms explicitly across arbitrary document ranges unless they fall sequentially into the window.
- Token budgets severely restrict large parent contexts.

## 15. Why this is not yet a relationship graph
This module appends text physically into the transformer's sequence span. It does not establish explicit directed edges, logic mappings, or cross-reference resolution. Those mechanisms belong to the relationship graph (TASK 011).
