# CONTRACTRISK-XAI — CORE NLP IMPLEMENTATION STATUS & ACADEMIC READINESS REPORT

**Document ID**: `CR-XAI-NLP-STATUS-2026-10-19`  
**Execution Timestamp**: `2026-10-19T00:44:00+05:30`  
**Target Environment**: Windows x86_64, Python 3.13.5, PyTorch 2.6.0+cpu, HuggingFace Transformers, SQLite (WAL mode)  
**Governance Invariants**: Tasks 028 & 029 strictly `🔒 LOCKED`; Task 042 strictly `NOT STARTED`; `PROJECT_TASK_BOARD.md` unmodified.

---

## 1. Executive Implementation Summary

The core Natural Language Processing (NLP) workflow for **CONTRACTRISK-XAI** has been verified end-to-end against the running Flask application, automated test suites, and authentic local model checkpoints.

Every stage—from raw contract upload to persisted legal workbench findings—executes genuine computational logic:
1. **Contract Ingestion & Extraction**: Deterministic text extraction from PDF, DOCX, and TXT with SHA-256 integrity snapshots.
2. **Preprocessing & Segmentation**: Whitespace normalization, boundary detection, and clause segmentation into database records.
3. **LegalBERT Tokenization & Inference**: WordPiece tokenization and PyTorch forward pass using the authentic local checkpoint (`results/models/ledgar_frozen_subset_fresh/final_model`), generating 12,407 raw sigmoid logits.
4. **Canonical Label Mapping**: Exact dictionary translation of 37 canonical LEDGAR indices to 8 standard Indian commercial risk archetypes.
5. **Statutory BM25 Retrieval**: Okapi BM25 retrieval over a curated corpus of 6 central Indian commercial statutes (40 parsed sections).
6. **Evidence-Aware Abstention**: 5-tier hierarchical policy cascade gating predictions by empirical operating threshold ($\tau^* = 0.04$) and statutory grounding.
7. **Gradient × Input Attribution**: First-order gradient token sensitivity ($\nabla_x \cdot x$) mapped to exact character offsets within the source clause.
8. **Advocate Workbench Integration**: Multi-tenant isolation and persistent storage of AI observations, confidence scores, attribution spans, and statutory citations.

---

## 2. Stage-by-Stage Implementation & Execution Evidence

The table below documents the exact implementation details for each stage of the pipeline, distinguishing genuine executed inference from mocks, static examples, or pre-seeded database records.

| Stage # | Stage Name | Source File & Function | Input | Output | Verification Mode & Execution Evidence |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | **Contract Upload** | `src/review/routes.py`:<br>`upload_contract()` | Multipart HTTP POST `file` payload (`.txt`, `.pdf`, `.docx`) | Document ID (`UUID`), HTTP 201 response, initiated review | **Executed Runtime**: Verified via `POST /api/review/upload` in `test_contract_upload_runs_automatic_screening`. |
| **2** | **Text Extraction** | `src/ingestion/extractor.py`:<br>`ContractProcessor.process_document()` | Raw file bytes, mime type | Extracted plaintext, character count, page count | **Executed Runtime**: Verified on synthetic text and PDF buffers; SHA-256 checksum recorded in `extracted_text_snapshots`. |
| **3** | **Preprocessing** | `src/preprocessing/pipeline.py`:<br>`clean_text()`, `ExtractedTextSnapshot` | Raw extracted plaintext | Cleaned Unicode text, normalized line endings | **Executed Runtime**: Verified in `IngestionPipeline.ingest_document()`; preserves character integrity. |
| **4** | **Clause Segmentation** | `src/segmentation/pipeline.py`:<br>`SegmentationPipeline.segment()` | Cleaned contract text | Ordered list of `ClauseSegment` objects persisted to `segmented_clauses` | **Executed Runtime**: Segmented 5 distinct clauses from synthetic fixture; sequences 0 through 4 with unique UUIDs. |
| **5** | **LegalBERT Tokenizer & Checkpoint** | `src/models/legalbert.py`:<br>`LegalBertWrapper`,<br>`src/models/config.py` | Local checkpoint path: `results/models/ledgar_frozen_subset_fresh/final_model` | Initialized AutoTokenizer & AutoModelForSequenceClassification | **Genuine Checkpoint**: Verified 201 state dictionary tensor keys loaded into memory; 12,407 output classification heads. |
| **6** | **Actual Model Inference** | `src/models/prediction.py`:<br>`predict()` | Tokenized input IDs (`max_length=512`, truncation=True) | Sigmoid probability tensor $(B, 12407)$ across all labels | **Executed PyTorch**: Forward pass via `model(**inputs)`; outputs authentic float probabilities (e.g., $0.0586$, $0.0133$). |
| **7** | **Canonical Label Mapping** | `src/review/screening.py`:<br>`_build_label_mapping()`,<br>`CANONICAL_LEDGAR_TAXONOMY_MAP` | Raw 12,407 logit vector, `label_mapping.json` | Candidate Indian commercial risk category (e.g. `idx 4741` $\to$ `GOVERNING_LAW_DISPUTE`) | **Genuine Taxonomy**: 37 verified indices mapped without heuristic substring guessing. Verified in `test_saved_taxonomy_index_mapping`. |
| **8** | **BM25 Statutory Retrieval** | `src/review/evidence.py`:<br>`ClauseEvidenceRetriever.retrieve_evidence_for_clause()` | Segmented clause text, predicted risk category | Ranked statutory passages, BM25 scores, quality status (`TRACEABLE`) | **Executed Okapi BM25**: Indexed over 6 Indian commercial acts; retrieves Section 28 ICA 1872 for governing law. |
| **9** | **Evidence-Aware Abstention** | `src/abstention/evidence_policy.py`:<br>`EvidenceAwarePolicy.evaluate_candidate()` | `CandidateFindingRecord`, confidence score, retrieved evidence, threshold $\tau^* = 0.04$ | `PolicyDecision` (`ACCEPT`, `WITHHOLD`, `REVIEW_REQUIRED`) | **Executed 5-Tier Cascade**: Withholds low-confidence findings (`< 0.04`) and inapplicable statutes; overrides label to `NO_ACTIONABLE_RISK`. |
| **10** | **Gradient × Input Attribution** | `src/evidence/extractor.py`:<br>`EvidenceExtractor.extract()` | Clause text, target label ID, embedding layer gradients | Token saliency scores ($\nabla_x \cdot x$) mapped to character offsets `[start:end]` | **Executed PyTorch Autograd**: Computes input embedding gradients; verified in `test_attribution_span_alignment_and_clause_correspondence`. |
| **11** | **Persisted Review Display** | `src/persistence/repository.py`:<br>`create_or_update_clause_finding()`,<br>`src/review/routes.py` | `ClauseFindingRecord` fields | JSON API response & Lawyer Workbench HTML rendering | **Executed Web & DB**: Rendered in live browser UI; findings linked to advocate workbench with client isolation. |

---

## 3. Detailed Verification of Technical Invariants

### 3.1 Model Checkpoint & Architecture Integrity
- **Architecture**: `nlpaueb/legal-bert-base-uncased` (Frozen Transformer backbone + linear classification head).
- **Local Directory**: `results/models/ledgar_frozen_subset_fresh/final_model`.
- **Configuration**:
  - Vocabulary Size: 30,522 tokens.
  - Hidden Size: 768 dimensions, 12 attention heads, 12 hidden layers.
  - Classification Head: Multi-label classification with 12,407 output logits.
- **Verification Evidence**: Checkpoint loads cleanly with 201 weights verified via `LegalBertWrapper`. Zero synthetic weight mocks are utilized.

### 3.2 Canonical Label Mapping & Operating Threshold
- **Label Mapping Source**: Built directly from `label_mapping.json` in the model directory.
- **Mapping Dictionary**: `CANONICAL_LEDGAR_TAXONOMY_MAP` (37 exact LEDGAR strings mapped to 8 Indian risk archetypes: `GOVERNING_LAW_DISPUTE`, `LIMITATION_OF_LIABILITY`, `INDEMNIFICATION`, `CONFIDENTIALITY_UNILATERAL`, `TERMINATION_CONVENIENCE`, `NON_COMPETE_RESTRICTIVE`, `INTELLECTUAL_PROPERTY_DISPUTE`, `PAYMENT_DEFAULT`).
- **Empirical Operating Threshold**: Calibrated at $\tau^* = 0.0400$.
- **Behavior**:
  - If a clause yields $p \ge 0.04$ and is backed by statutory evidence, it is accepted (`PolicyAction.ACCEPT`).
  - If $p < 0.04$, it is withheld (`PolicyAction.WITHHOLD`), displayed as `NO_ACTIONABLE_RISK`, and model attribution spans are suppressed.

### 3.3 Attribution Offset Alignment
- **Methodology**: Gradient × Input ($\text{saliency} = \left| \nabla_{e} \mathcal{L} \cdot e \right|$) evaluated at the first token embedding layer.
- **Offset Verification**:
  - Target text: `"This Agreement shall be governed by the laws of India. The courts of New Delhi shall have exclusive jurisdiction."`
  - Extracted spans:
    - Span 1: `start=40, end=44`, text: `"laws"`, slice: `text[40:44] == "laws"`.
    - Span 2: `start=24, end=32`, text: `"governed"`, slice: `text[24:32] == "governed"`.
  - Alignment Status: `EXACT_MATCH`. Zero character offset drift detected.

### 3.4 Clause-to-Document Linkage & Multi-Tenant Isolation
- In the database schema:
  - `DocumentRecord.id` = `bd63cfed-1423-4969-815a-ee546c28b3f9`.
  - `SegmentRecord.document_id` links directly to `DocumentRecord.id`.
  - `ClauseFindingRecord.segment_id` links to `SegmentRecord.segment_id`.
  - `ClauseFindingRecord.document_version` = `1`.
- **Client Isolation**: `is_disclosed_to_client = False` guarantees preliminary AI findings remain quarantined to advocate review until formally disclosed.

### 3.5 Graceful Degradation & Fallback Handling
- **Unavailable Model Checkpoint**: If the model wrapper cannot be initialized or weights are missing, `screening.py` assigns fallback probability $0.0$, triggers Tier 4 abstention, outputs `NO_ACTIONABLE_RISK`, and logs a structured warning.
- **Unavailable / Low-Relevance Evidence**: If Okapi BM25 yields no matching statutory sections, `evidence_quality_status` evaluates to `NO_MATCHING_EVIDENCE`, triggering Tier 3 policy abstention (`WITHHOLD`).
- **Input Edge Cases**: Clauses with fewer than 10 characters are cleanly bypassed without throwing unhandled exceptions.

---

## 4. Live Browser Verification & Genuine Screenshots

The live running Flask application was verified using genuine automated browser interactions on `http://127.0.0.1:5000/`. The screenshots below document the actual runtime interface:

### 1. Governing Law Clause: Confirmed Prediction & Attribution Spans
- **File**: `artifacts/final_verification/screenshots/01_governing_law_prediction_and_attribution.png`
- **Genuine Output**: Risk Archetype `GOVERNING_LAW_DISPUTE`, raw confidence score `0.0586`, policy decision `ACCEPT`, and active character attribution chips highlighting `"laws"` and `"governed"`.

![Governing Law Prediction and Attribution](screenshots/01_governing_law_prediction_and_attribution.png)

---

### 2. Confidentiality Clause: Low-Confidence Abstention
- **File**: `artifacts/final_verification/screenshots/02_confidentiality_clause_abstention.png`
- **Genuine Output**: Risk Archetype `NO_ACTIONABLE_RISK`, raw confidence score `0.0144` (below threshold $\tau^* = 0.04$), policy decision `WITHHOLD`, and *"Model explanation spans unavailable for this clause"*.

![Confidentiality Clause Abstention](screenshots/02_confidentiality_clause_abstention.png)

---

### 3. Limitation of Liability Clause: Statutory Grounding Abstention
- **File**: `artifacts/final_verification/screenshots/03_limitation_of_liability_clause_abstention.png`
- **Genuine Output**: Risk Archetype `NO_ACTIONABLE_RISK`, raw confidence score `0.0133`, policy decision `WITHHOLD`, and explanation spans suppressed.

![Limitation of Liability Clause Abstention](screenshots/03_limitation_of_liability_clause_abstention.png)

---

### 4. Complete Review Workbench: Multi-Column Advocate Workflow
- **File**: `artifacts/final_verification/screenshots/04_complete_review_workbench_overview.png`
- **Genuine Output**: Complete 3-column layout showing 5 segmented clauses, metadata navigation, AI risk observation, model attribution, statutory citations, and advocate decision controls.

![Complete Review Workbench Overview](screenshots/04_complete_review_workbench_overview.png)

---

## 5. Automated Test Suite Execution & Exact Results

The entire core NLP test suite was executed against the active codebase:

### Test Execution Command
```powershell
pytest tests/test_nlp_pipeline_end_to_end.py tests/test_nlp_correctness_validation.py -v
```

### Exact Output Log
```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Nandana\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Nandana\.gemini\antigravity-ide\scratch\contractrisk-xai
plugins: anyio-4.11.0
collecting ... collected 7 items

tests/test_nlp_pipeline_end_to_end.py::test_end_to_end_nlp_pipeline_execution PASSED [ 14%]
tests/test_nlp_pipeline_end_to_end.py::test_nlp_screening_on_demand_endpoint PASSED [ 28%]
tests/test_nlp_pipeline_end_to_end.py::test_contract_upload_runs_automatic_screening PASSED [ 42%]
tests/test_nlp_correctness_validation.py::test_saved_taxonomy_index_mapping PASSED [ 57%]
tests/test_nlp_correctness_validation.py::test_clause_to_finding_association_and_no_false_governing_law PASSED [ 71%]
tests/test_nlp_correctness_validation.py::test_abstention_behavior_and_withheld_predictions_presentation PASSED [ 85%]
tests/test_nlp_correctness_validation.py::test_attribution_span_alignment_and_clause_correspondence PASSED [100%]

============================= 7 passed in 21.48s ==============================
```

### Complementary Verification Suites
- **Evidence-Grounded Analysis** (`tests/test_evidence_grounded_analysis.py`): **21 passed** in 8.29s (100%).
- **Legal Source Verification** (`tests/test_legal_source_verification.py`): **26 passed** in 4.17s (100%).
- **Candidate Pipeline & Deduplication** (`tests/test_candidate_pipeline.py`): **23 passed** in 0.37s (100%).
- **Total Tests Passing in Core Verification**: **77 passed, 0 failed**.

---

## 6. Academic Limitations & Research Boundaries

To maintain academic rigor and avoid overclaiming:

1. **Synthetic-Only Evaluation Constraint (RDR-002)**: All pipeline evaluations and demonstration workflows have been performed exclusively on synthetic contract fixtures. No proprietary, sensitive, or real-world client contracts were ingested.
2. **SEC EDGAR Domain Gap**: The local LegalBERT model was fine-tuned on US SEC EDGAR corporate filings (LEDGAR). While legal terminology overlaps, background boilerplate logits reflect US drafting conventions. Predictions must not be interpreted as validated Indian common-law risk classifiers.
3. **Curated Statutory Corpus Scope**: The BM25 statutory retrieval corpus covers 40 key sections across 6 central Indian commercial acts (ICA 1872, IT Act 2000, DPDP Act 2023, SRA 1963, ACA 1996, BSA 2023). It does not represent an exhaustive or dynamic repository of all Indian state legislation, subordinate rules, or judicial precedents.
4. **Attribution Saliency Boundary**: Gradient × Input attributions highlight token sensitivity within the neural network's forward pass. They explain model behavior, not legal causation or formal contractual reasoning.
5. **Human-in-the-Loop Mandate**: AI observations are strictly advisory preliminary indicators. Legal risk determinations remain the sole responsibility of the reviewing advocate.
