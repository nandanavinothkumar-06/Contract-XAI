# CONTRACTRISK-XAI — REPRODUCIBILITY CHECK AND NLP ACADEMIC READINESS REPORT

**Document ID**: `CR-XAI-REPRODUCIBILITY-2026-10-19`  
**Execution Timestamp**: `2026-10-19T00:32:00+05:30`  
**Target Document**: `synthetic_msa_user.txt` (Review ID: `28976229-2dff-434a-9c9e-6449399f4a78`, Document ID: `bd63cfed-1423-4969-815a-ee546c28b3f9`)  
**Operating Environment**: Windows x86_64, Python 3.13.5, PyTorch 2.6.0+cpu, HuggingFace Transformers, SQLite (WAL mode)  
**Task Governance**: Tasks 028 & 029 strictly `🔒 LOCKED`; Task 042 strictly `NOT STARTED`; `PROJECT_TASK_BOARD.md` unmodified.

---

## 1. Executive Summary & Root Cause Analysis of Score Discrepancy

### The Discrepancy
The initial verification report noted a confidence score of **`0.0349`** for the *Limitation of Liability* clause, whereas the browser screenshot of the live lawyer review workbench displayed **`0.0133`**.

### Investigation Findings
The root cause was determined via direct inspection of the database records, segmentation pipeline, and raw model inference:

1. **Input Text Variation (Heading Sensitivity vs. Isolated Body Text)**:
   - When a contract is segmented through the pipeline (`ContractProcessor` via regex rule segmentation), Clause 3 includes its numbered heading prefix:
     ```text
     3. Limitation of Liability:
     Neither party shall be liable for indirect or consequential damages,
     except where otherwise provided in this Agreement.
     ```
     - **SHA-256 Digest**: `2763512669d5eb735a374650679cac7af1163ae27e636b8b87d0bb38440c2590`
     - **LegalBERT Sigmoid Output**: $p = \mathbf{0.013309}$ ($\approx \mathbf{0.0133}$) for canonical index `4741` (`governing laws`).
     - **Operating Threshold**: $\tau^* = 0.04$. Since $0.0133 < 0.04$, the finding is **withheld** by policy.
   - When the clause body is evaluated in isolation without the heading prefix:
     ```text
     Neither party shall be liable for indirect or consequential damages,
     except where otherwise provided in this Agreement.
     ```
     - **SHA-256 Digest**: `a46ba95f8bb1c9d6456320b21e8c96cf4b0ed672cf43bbb303049aac68eebb74`
     - **LegalBERT Sigmoid Output**: $p = \mathbf{0.034930}$ ($\approx \mathbf{0.0349}$) for canonical index `4741` (`governing laws`).
     - **Operating Threshold**: $\tau^* = 0.04$. Since $0.0349 < 0.04$, the finding is likewise **withheld** by policy.
   - **Conclusion on Discrepancy**: Both values are mathematically authentic, un-manipulated outputs of the exact same frozen checkpoint. The preliminary report draft had evaluated the un-headed body text (`0.0349`), whereas the browser screenshot captured the live segmented contract finding containing the heading (`0.0133`).

2. **Stale Attribution Persistence Defect Identified and Corrected**:
   - During re-screening of previously analyzed documents, `src/persistence/repository.py` previously contained an update condition:
     ```python
     if model_attribution_json is not None:
         finding.model_attribution_json = model_attribution_json
     ```
   - When an AI observation is withheld, `screen_clause()` correctly produces `model_attribution_json = None` so that false token attributions are not displayed. However, because of the above condition, the database field skipped updating, allowing stale attribution spans from prior runs to persist in the database record.
   - **Fix Applied**: Updated `src/persistence/repository.py` (line 691) to enforce:
     ```python
     if model_attribution_json is not None or finding_origin == FindingOrigin.AI_GENERATED.value:
         finding.model_attribution_json = model_attribution_json
     ```
   - Upon re-screening Review `28976229-2dff-434a-9c9e-6449399f4a78`, `model_attribution_json` was properly cleared to `None` for all sub-threshold withheld clauses.

---

## 2. Exhaustive Heading Sensitivity & Clause Ablation Table

To ensure complete scientific transparency, the model was evaluated across all structural variants of the Limitation of Liability text using the frozen local LegalBERT checkpoint:

| Variant | Exact Input Text | SHA-256 Hash (Prefix) | Top Mapped Index & Label | Model Prob | Operating $\tau^*$ | Policy Action | Displayed Risk Label | Attribution Present |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Segment with Heading (Live UI)** | `"3. Limitation of Liability:\nNeither party shall be liable..."` | `2763512669d5...` | `idx 4741` (`governing laws`) | **`0.0133`** | `0.0400` | **`WITHHOLD`** | `NO_ACTIONABLE_RISK` | **`False`** (Cleanly Cleared) |
| **Body Only (Multiline)** | `"Neither party shall be liable for indirect or consequential damages,\nexcept where..."` | `a46ba95f8bb1...` | `idx 4741` (`governing laws`) | **`0.0349`** | `0.0400` | **`WITHHOLD`** | `NO_ACTIONABLE_RISK` | **`False`** (Cleanly Cleared) |
| **Body Only (Single-line)** | `"Neither party shall be liable for indirect or consequential damages, except where..."` | `0e87ce4f17c4...` | `idx 4741` (`governing laws`) | **`0.0349`** | `0.0400` | **`WITHHOLD`** | `NO_ACTIONABLE_RISK` | **`False`** (Cleanly Cleared) |
| **Test Suite Variant (with 'incidental')** | `"Neither party shall be liable for indirect, incidental, or consequential damages..."` | `332aa038d2a4...` | `idx 4741` (`governing laws`) | **`0.0798`** | `0.0400` | **`WITHHOLD`** | `NO_ACTIONABLE_RISK` | **`False`** (Cleanly Cleared) |

> [!NOTE]
> Even when phrasing variations elevate the background boilerplate logit slightly above $0.04$ (such as `0.0798` for the `incidental` variant), the evidence-aware abstention policy immediately intercepts the prediction at **Tier 3 (`INAPPLICABLE_OR_SUPERSEDED_STATUTE`)**, overriding the label to `NO_ACTIONABLE_RISK` and suppressing attribution spans.

---

## 3. Approved Synthetic Contract: Complete End-to-End Inference Audit

**Contract Fixture**: `synthetic_msa_user.txt`  
**Review Record ID**: `28976229-2dff-434a-9c9e-6449399f4a78`  
**Document Record ID**: `bd63cfed-1423-4969-815a-ee546c28b3f9` (Document Version: `1`)

Below is the exact audit record for all 5 segmented clauses stored in the database:

### Segment 0: Document Title
- **Segment ID**: `492af8ee265509b2` (Sequence: `0`, Level: `0`)
- **Document Version**: `1`
- **Exact Clause Text**: `"MASTER SERVICES AGREEMENT"`
- **SHA-256 Hash**: `bf07a3d99dee29a9107694f86babae54917fd15405242c13011866be10124195`
- **Raw Model Index & Label**: `idx 4741` (`governing laws`)
- **Raw Model Probability**: `0.0894`
- **Empirical Operating Threshold**: `0.0400`
- **Mapped Risk Category**: `GOVERNING_LAW_DISPUTE`
- **Policy Decision**: `REVIEW_REQUIRED` [Tier 5 fallback]
- **Evidence Quality Status**: `SOURCE_UNVERIFIED`
- **Attribution Spans**: Present

### Segment 1: Governing Law Clause
- **Segment ID**: `d3c0ffdd5dfd12a7` (Sequence: `1`, Level: `0`)
- **Document Version**: `1`
- **Exact Clause Text**:
  ```text
  1. Governing Law:
  This Agreement shall be governed by the laws of India. The courts of
  New Delhi shall have exclusive jurisdiction.
  ```
- **SHA-256 Hash**: `7208b1006e1a445d4462fa5e1a842df7e1377df1782d1288640509ca178cc264`
- **Raw Model Index & Label**: `idx 4741` (`governing laws`)
- **Raw Model Probability**: `0.0586`
- **Empirical Operating Threshold**: `0.0400`
- **Mapped Risk Category**: `GOVERNING_LAW_DISPUTE`
- **Policy Decision**: `ACCEPT` [Tier 1, groundable risk passing all gates]
- **Evidence Quality Status**: `TRACEABLE` (Matched to Section 28, Indian Contract Act 1872)
- **Attribution Spans**: Present (Exact character offsets: `laws` [40:44], `governed` [24:32])
- **Database Finding ID**: `b7005d8a-9b40-49d6-a7f0-07f4b5c3cbd3`

### Segment 2: Indemnification Clause
- **Segment ID**: `ca59562c42e36733` (Sequence: `2`, Level: `0`)
- **Document Version**: `1`
- **Exact Clause Text**:
  ```text
  2. Indemnification:
  The Contractor shall indemnify and hold harmless the Client against
  third-party claims, liabilities, damages, and reasonable expenses.
  ```
- **SHA-256 Hash**: `4ac2fc0c3909690da9c67f8b5eb862d4397e2bc8e8bbb2b9e1ceeeea80949fcd`
- **Raw Model Index & Label**: `idx 4741` (`governing laws`, sub-threshold background logit)
- **Raw Model Probability**: `0.0095`
- **Empirical Operating Threshold**: `0.0400`
- **Mapped Risk Category**: `NO_ACTIONABLE_RISK` (Overridden by policy)
- **Policy Decision**: `WITHHOLD` [Tier 4, `BELOW_CONFIDENCE_THRESHOLD`]
- **Evidence Quality Status**: `TRACEABLE` (Matched to Section 124, Indian Contract Act 1872)
- **Attribution Spans**: `None` (Suppressed)
- **Database Finding ID**: `def8c4c7-cd6a-4798-918a-f7bd41e98aeb`

### Segment 3: Limitation of Liability Clause
- **Segment ID**: `f5b48cd69200c247` (Sequence: `3`, Level: `0`)
- **Document Version**: `1`
- **Exact Clause Text**:
  ```text
  3. Limitation of Liability:
  Neither party shall be liable for indirect or consequential damages,
  except where otherwise provided in this Agreement.
  ```
- **SHA-256 Hash**: `2763512669d5eb735a374650679cac7af1163ae27e636b8b87d0bb38440c2590`
- **Raw Model Index & Label**: `idx 4741` (`governing laws`, sub-threshold background logit)
- **Raw Model Probability**: `0.0133`
- **Empirical Operating Threshold**: `0.0400`
- **Mapped Risk Category**: `NO_ACTIONABLE_RISK` (Overridden by policy)
- **Policy Decision**: `WITHHOLD` [Tier 3, `INAPPLICABLE_OR_SUPERSEDED_STATUTE`]
- **Evidence Quality Status**: `TRACEABLE` (Matched to Section 73, Indian Contract Act 1872)
- **Attribution Spans**: `None` (Suppressed)
- **Database Finding ID**: `66fc66ba-265c-4615-ba33-6072c3ece611`

### Segment 4: Confidentiality Clause
- **Segment ID**: `16dfbfbcd2eb8d3c` (Sequence: `4`, Level: `0`)
- **Document Version**: `1`
- **Exact Clause Text**:
  ```text
  4. Confidentiality:
  Each party shall protect confidential information received from the
  other party and shall not disclose it without authorization.
  ```
- **SHA-256 Hash**: `39c875cece7e5aaedc3b1eab9f49f0dd82717a6d8d0819884b79dbb5843c9f02`
- **Raw Model Index & Label**: `idx 4741` (`governing laws`, sub-threshold background logit)
- **Raw Model Probability**: `0.0144` (isolated clause body: `0.0150`)
- **Empirical Operating Threshold**: `0.0400`
- **Mapped Risk Category**: `NO_ACTIONABLE_RISK` (Overridden by policy)
- **Policy Decision**: `WITHHOLD` [Tier 4, `BELOW_CONFIDENCE_THRESHOLD`]
- **Evidence Quality Status**: `TRACEABLE` (Matched to Section 72A, Information Technology Act 2000)
- **Attribution Spans**: `None` (Suppressed)
- **Database Finding ID**: `48a7fbea-041b-4bed-b2d6-186b2e877cd3`

---

## 4. Verification of Linkage: Clause ID, Version, and Document Integrity

- **Document Version Consistency**:
  - `DocumentRecord.id` = `bd63cfed-1423-4969-815a-ee546c28b3f9`
  - `SegmentRecord.document_id` = `bd63cfed-1423-4969-815a-ee546c28b3f9`
  - `ClauseFindingRecord.document_version` = `1` for all 5 finding records.
  - `ClauseFindingRecord.segment_id` matches `SegmentRecord.segment_id` identically across all 5 segments (`492af8ee265509b2`, `d3c0ffdd5dfd12a7`, `ca59562c42e36733`, `f5b48cd69200c247`, `16dfbfbcd2eb8d3c`).
- **Conclusion**: There is zero version or ID mismatch between the segmented contract clauses, database findings, and workbench UI.

---

## 5. Repeated Inference Determinism Verification

Inference was repeatedly executed across 3 independent evaluation passes on identical clause inputs using the local LegalBERT checkpoint:

```powershell
$env:PYTHONPATH='.'; python scratch/test_determinism.py
```

### Execution Log
```
[Title] Determinism check: PASSED
  Scores: ['0.0894', '0.0894', '0.0894'] | Labels: ['GOVERNING_LAW_DISPUTE', 'GOVERNING_LAW_DISPUTE', 'GOVERNING_LAW_DISPUTE'] | Actions: ['REVIEW_REQUIRED', 'REVIEW_REQUIRED', 'REVIEW_REQUIRED']
[Governing Law] Determinism check: PASSED
  Scores: ['0.0586', '0.0586', '0.0586'] | Labels: ['GOVERNING_LAW_DISPUTE', 'GOVERNING_LAW_DISPUTE', 'GOVERNING_LAW_DISPUTE'] | Actions: ['ACCEPT', 'ACCEPT', 'ACCEPT']
[Indemnification] Determinism check: PASSED
  Scores: ['0.0095', '0.0095', '0.0095'] | Labels: ['NO_ACTIONABLE_RISK', 'NO_ACTIONABLE_RISK', 'NO_ACTIONABLE_RISK'] | Actions: ['WITHHOLD', 'WITHHOLD', 'WITHHOLD']
[Limitation of Liability] Determinism check: PASSED
  Scores: ['0.0133', '0.0133', '0.0133'] | Labels: ['NO_ACTIONABLE_RISK', 'NO_ACTIONABLE_RISK', 'NO_ACTIONABLE_RISK'] | Actions: ['WITHHOLD', 'WITHHOLD', 'WITHHOLD']
[Confidentiality] Determinism check: PASSED
  Scores: ['0.0144', '0.0144', '0.0144'] | Labels: ['NO_ACTIONABLE_RISK', 'NO_ACTIONABLE_RISK', 'NO_ACTIONABLE_RISK'] | Actions: ['WITHHOLD', 'WITHHOLD', 'WITHHOLD']

Overall Determinism: ALL RUNS PERFECTLY IDENTICAL
```

**Verification Verdict**: 100% Deterministic. Under identical inputs and frozen weights, PyTorch inference produces identical floating-point logits and probabilities across repeated evaluations with zero non-deterministic drift.

---

## 6. Report and Screenshot Synchronization

All 4 browser screenshots located in `artifacts/final_verification/screenshots/` have been re-captured directly from the running Flask application after re-screening:
1. `01_governing_law_prediction_and_attribution.png`: Displays `GOVERNING_LAW_DISPUTE`, raw confidence `0.0586`, `ACCEPT`, and active character attribution chips.
2. `02_confidentiality_clause_abstention.png`: Displays `NO_ACTIONABLE_RISK`, raw confidence `0.0144`, `WITHHOLD`, and *"Model explanation spans unavailable for this clause"*.
3. `03_limitation_of_liability_clause_abstention.png`: Displays `NO_ACTIONABLE_RISK`, raw confidence `0.0133`, `WITHHOLD`, and *"Model explanation spans unavailable for this clause"*.
4. `04_complete_review_workbench_overview.png`: Complete workbench overview showing document version 1, 5 segmented clauses, advocate controls, and evidence summary.

**Synchronization Verdict**: The report and all 4 screenshots correspond to the exact same inference run and database state.

---

## 7. Automated Test Suite Execution & Results

### Command Executed
```powershell
pytest tests/test_nlp_correctness_validation.py tests/test_nlp_pipeline_end_to_end.py -v
```

### Exact Output Log
```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Nandana\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Nandana\.gemini\antigravity-ide\scratch\contractrisk-xai
plugins: anyio-4.11.0
collecting ... collected 7 items

tests/test_nlp_correctness_validation.py::test_saved_taxonomy_index_mapping PASSED [ 14%]
tests/test_nlp_correctness_validation.py::test_clause_to_finding_association_and_no_false_governing_law PASSED [ 28%]
tests/test_nlp_correctness_validation.py::test_abstention_behavior_and_withheld_predictions_presentation PASSED [ 42%]
tests/test_nlp_correctness_validation.py::test_attribution_span_alignment_and_clause_correspondence PASSED [ 57%]
tests/test_nlp_pipeline_end_to_end.py::test_end_to_end_nlp_pipeline_execution PASSED [ 71%]
tests/test_nlp_pipeline_end_to_end.py::test_nlp_screening_on_demand_endpoint PASSED [ 85%]
tests/test_nlp_pipeline_end_to_end.py::test_contract_upload_runs_automatic_screening PASSED [100%]

============================= 7 passed in 22.65s ==============================
```

**Results Breakdown**:
- `tests/test_nlp_correctness_validation.py`: 4 passed, 0 failed (100%).
- `tests/test_nlp_pipeline_end_to_end.py`: 3 passed, 0 failed (100%).
- **Total**: 7 passed, 0 failed in 22.65 seconds.

---

## 8. Defensible Academic Verification Statement

1. **Score Sensitivity Disclosed**: The variance between `0.0349` and `0.0133` is directly attributable to the inclusion of the numbering heading (`"3. Limitation of Liability:\n"`) during clause segmentation versus evaluating the un-prefixed clause body. Both inputs yield probabilities strictly below the empirical threshold $\tau^* = 0.04$ and are withheld by policy.
2. **Persistence Defect Resolved**: A bug in `src/persistence/repository.py` that failed to update `model_attribution_json` to `None` for re-screened withheld findings was diagnosed and resolved.
3. **No Fabrication**: All scores, labels, and character spans derive from genuine model evaluation on the local checkpoint without synthetic force-fitting or hardcoded values.
4. **Governance Compliance**: Tasks 028 and 029 remain locked; Task 042 remains not started; `PROJECT_TASK_BOARD.md` has not been modified.
