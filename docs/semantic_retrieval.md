# Semantic Retrieval

## 1. Purpose
The Semantic Retrieval module performs vector-based nearest-neighbor similarity searches across contract clauses. It extracts embeddings utilizing independent `sentence-transformers` models and maps queries natively through `faiss-cpu`. 

**Disclaimer**: A semantically similar retrieved clause is an informational comparison candidate. Similarity does not establish legal equivalence, legal authority, contractual applicability, or legal correctness. 

## 2. Embedding Model
The framework employs generic Sentence Transformer architectures:
- **Default Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Revision**: `main`

## 3. Separation from Legal-BERT
This module strictly decouples representation logic. Legal-BERT is dedicated exclusively to structural binary/multiclass classification bounds (TASK 008). Semantic retrieval explicitly prevents overlapping the classification weights into cosine similarity mapping. 

## 4. FAISS / Index Design
The module serializes deterministic dictionaries linking FAISS integer vector IDs to canonical project `clause_id` coordinates. It uses `faiss.IndexFlatIP`.

## 5. Similarity Metric
Matches return native `InnerProduct` calculations dynamically ordered descending. 

## 6. Normalization
Embeddings natively execute `normalize_embeddings=True` rendering L2 norms equal to 1. Inner Product calculations over L2 vectors are mathematically identical to Cosine Similarity. 

## 7. Query Behavior
Basic querying extracts arbitrary textual string inputs through the identical encoder pipeline mapping back to original clauses. 

## 8. Top-K
Configurable upper limit slicing (`top_k`). Ties are resolved deterministically utilizing the `clause_id` string identifier natively.

## 9. Self-Retrieval
Enabled/Disabled natively via `exclude_query = True`. The query identifier explicitly omits itself sequentially during index iterations if toggled.

## 10. Same-Document Mode
Configurable `same_document_only = True` enforces bounds isolating comparisons internally relative to identical `.source_document_id`. Defaults to `False` (cross-document matching).

## 11. Partition Isolation
The VectorIndex maps explicitly exclusively to a single `partition` (e.g. TRAIN). Query requests enforce stringent verification validating that `query.partition == index.partition` preventing leakage. Cross-partition aggregation is strictly structurally blocked. 

## 12. Leakage Prevention
Vector indices recursively assert `check_exact_leakage` computing identical SHA-256 string hashes identifying identical clause text spanning adjacent boundaries. 

## 13. Provenance
- `query_clause_id`
- `query_source_document_id`
- `result_clause_id`
- `source_document_id`
- `source_start` / `source_end` (identical boundaries derived inherently without offset mapping drifts).

## 14. Serialization
- `faiss.index`
- `metadata.json`
- `clause_data.json`

## 15. Truncation
Model string sequence bounds assert explicitly. Text eclipsing `.max_seq_length` registers boolean metadata tagging `truncated=True`. 

## 16. Dataset Status
- **LEDGAR**: NOT_RUN_DATA_UNAVAILABLE
- **ContractNLI**: NOT_RUN_DATA_UNAVAILABLE
- **CUAD**: NOT_APPLICABLE
- **CLAUDETTE**: NOT_RUN_LICENSE_UNRESOLVED
- **Construction Data**: NOT_RUN_DATA_UNAVAILABLE

## 17. Project Result Status
**PROJECT EXPERIMENTAL RESULTS: NONE**
Synthetic simulated testing matrices executed. No legitimate benchmarks derived over missing source texts. 

## 18. Limitations
- Does not inherently parse multi-paragraph continuous clauses.
- Unaware of structural hierarchies absent context parameters.

## 19. Similarity vs Legal Relationship
Semantic relationships gauge pure dense vector distance models rather than EXPLICIT_CROSS_REFERENCE explicit pointers instantiated by TASK 011. Similarity is not structurally authoritative. 

## 20. Retrieval vs Legal Authority
Retrieval generates probabilistic string maps. It does NOT assert precedential authority structurally or legally. 

## 21. Research Provenance
- `sentence-transformers`: Reimers, N., & Gurevych, I. (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks". EMNLP-IJCNLP 2019.
- `faiss-cpu`: Johnson, J., Douze, M., & Jégou, H. (2019). "Billion-scale similarity search with GPUs". IEEE Transactions on Big Data.
