# TASK 024 — Build Dashboard: Engineering & Verification Report

**Project**: ContractRisk-XAI  
**Task ID**: 024  
**Task Name**: Build dashboard  
**Execution Timestamp**: 2026-10-14T21:15:00+05:30  
**Status**: ✅ COMPLETED  
**Manifest Path**: [`results/task024/task024_dashboard_manifest.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/task024/task024_dashboard_manifest.json)  
**Static Dashboard Artifact**: [`results/task024/index.html`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/task024/index.html)  
**Dedicated Automated Test Suite**: [`tests/test_dashboard.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_dashboard.py) (**6/6 passed in 0.27s**)  
**Full Project Regression Suite**: **57/57 passed in 99.88s** across Tasks 019–024  

---

## 1. Executive Summary & Architecture

Task 024 delivers the **ContractRisk-XAI Research Evaluation & Governance Dashboard**, providing an interactive, visual interface to inspect verified model performance, confusion matrices, evidence attribution rationales, robustness boundaries, and failure mode taxonomies.

To maximize usability and research integrity, the dashboard implements a **Dual Delivery Architecture**:
1. **Live Dynamic Server (`src/dashboard/app.py`)**: A lightweight Flask 3.1.0 application providing RESTful API endpoints and serving dynamic UI views.
2. **Pre-Compiled Standalone HTML (`results/task024/index.html`)**: A self-contained, offline-compatible static dashboard that can be launched directly in any web browser without running background server processes.

### 1.1 Aesthetic & Visual Standards
- **Modern Dark-Mode Palette**: Deep slate background (`#090d16`), frosted glassmorphic card containers (`rgba(18, 25, 43, 0.75)` with `backdrop-filter: blur(8px)`), and curated neon accents (cyan `#38bdf8`, emerald `#34d399`, amber `#fbbf24`, rose `#f87171`).
- **Typography**: Google Fonts typography hierarchy using `Outfit` (headings, data labels), `Inter` (body copy, tabular statistics), and `JetBrains Mono` (hashes, code spans, taxonomic labels).
- **Interactive UI Layout**: Multi-tab switcher, responsive CSS grid layouts, and color-coded confusion heatmaps.
- **Zero Third-Party CSS Framework Dependencies**: Built exclusively with Vanilla CSS for deterministic cross-browser rendering.

---

## 2. Mandatory Data Integrity & Safety Disclaimers

### 2.1 The Legal Safety Disclaimer
A prominent, permanent warning banner is embedded at the top of the dashboard:
> **LEGAL SAFETY NOTICE & ACADEMIC RESEARCH DISCLAIMER**:  
> ContractRisk-XAI is an experimental computer science research benchmark. It is **NOT a validated legal decision-maker**. Model predictions and gradient attribution spans represent statistical patterns and **must not be interpreted as legal advice**, verified rationales, or binding contract interpretations. All findings require independent qualified human attorney review.

### 2.2 Domain Decoupling Safeguards
- **LEDGAR** multi-label provision classification ($12,407$ classes) is strictly isolated from **ContractNLI** document-level natural language inference ($3$ classes) and **CUAD** extractive question answering.
- The dashboard never computes synthetic cross-domain averages or composite accuracy figures.
- Intermediate validation sweep points are clearly labeled as validation data, preventing confusion with empirical held-out test split measurements.

### 2.3 Text Sanitization & XSS Prevention
All contractual text fragments and evidence spans are sanitized through HTML entity escaping (`html.escape()`) via `src/dashboard/data_loader.py` before injection into document templates, preventing DOM injection while preserving exact substring character boundaries.

---

## 3. Implemented Views & Functional Components

The dashboard is structured into six interactive views accessible via header navigation tabs:

```
[ContractRisk-XAI Dashboard]
├── 1. Executive Overview    -> High-level metrics, physical model SHA-256, decoupled dataset cards
├── 2. LEDGAR Multi-Label    -> tau*=0.04 vs tau=0.50 comparison table, long-tail tier breakdown, Macro-F1 collapse analysis
├── 3. ContractNLI Baseline  -> 3x3 confusion matrix heatmap, dominant error flows (NotMentioned -> Entailment)
├── 4. Error Cases & Evidence-> Concrete case studies, highlighted token spans, character invariant verification
├── 5. Robustness Benchmarks -> Input perturbation stability, context budget overflow safety, graph cyclicity
└── 6. Failure Taxonomy      -> Formal failure mode cards (FM-01 through FM-06)
```

### 3.1 Tab 1: Executive Overview & Model Provenance
- Displays model architecture specifications: `nlpaueb/legal-bert-base-uncased` (frozen 109.5M encoder + 9.5M trainable linear classification head).
- Confirms physical model weight hash: `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f` (`476,116,436` bytes).
- Documents the deterministic 10% contract training subset (4,844 contracts, 67,776 provisions, seed 42) with zero split leakage.

### 3.2 Tab 2: LEDGAR Multi-Label Provision Deep Dive
- Side-by-side performance table contrasting calibrated operating point $\tau^* = 0.04$ against uncalibrated baseline $\tau = 0.50$ across 87,956 held-out test provisions:
  - $\tau^* = 0.04$: $TP=12,699; FP=58,947; FN=92,584$; Micro-P: 17.72%; Micro-R: 12.06%; Micro-F1: 0.1435; Macro-F1: 0.0045; Weighted-F1: 0.0937.
  - $\tau = 0.50$: $TP=989; FP=438; FN=104,294$; Micro-P: 69.31%; Micro-R: 0.94%; Micro-F1: 0.0185; Macro-F1: 0.0009; Weighted-F1: 0.0141.
- Visual breakdown of the $12,608$-class long-tail frequency tiers:
  - **Zero-Shot Unlearned**: 2,833 classes (22.47%) with 0 examples (0.0% theoretical recall).
  - **Extreme Tail**: 8,465 classes (67.14%) with 1–9 examples.
  - **Moderate Tail**: 1,208 classes (9.58%) with 10–99 examples.
  - **Common Head**: 102 classes (0.81%) with $\ge 100$ examples.
- Detailed explanation of the Macro-F1 collapse mechanism.

### 3.3 Tab 3: ContractNLI Baseline Evaluation
- Interactive $3 \times 3$ confusion matrix for the TF-IDF Linear SVM baseline across 2,091 test pairs:
  - Contradiction: 81 TP, 90 misclassified as Entailment, 49 misclassified as NotMentioned.
  - Entailment: 834 TP, 20 misclassified as Contradiction, 114 misclassified as NotMentioned.
  - NotMentioned: 456 TP, 383 misclassified as Entailment, 64 misclassified as Contradiction.
- Overall Accuracy: 65.57% | Macro-F1: 0.5844.
- In-depth documentation of the dominant error flow: **NotMentioned $\rightarrow$ Entailment (383 instances, 42.41% error rate)** caused by lexical boilerplate overlap.

### 3.4 Tab 4: Verified Error Case Studies & Evidence Visualizer
- Traceable case cards displaying real contract excerpts, ground-truth labels, model predictions, and exact substring offsets:
  - `ERR_CASE_01`: Morphological collision penalty (predicting plural `governing laws` instead of singular `governing law` and `applicable laws`).
  - `ERR_CASE_04`: Evidence attribution stopword bias, rendering highlighted spans (`"and"`, `"the"`, `"accordance"`) and displaying a warning that gradient saliency does not equal legal validity.

### 3.5 Tab 5: Robustness & Context Stress Benchmarks
- Summarizes the Task 022 robustness findings:
  - Input perturbation stability: Mean probability cosine similarities $\ge 0.9311$ across UPPERCASE, WHITESPACE, TYPOGRAPHICAL NOISE, and ENTITY SUBSTITUTIONS.
  - Context stress invariants: 100% target preservation under $>1,000$ token context overflow; 100% rejection of cross-document injection attacks.
  - Graph topology robustness: Non-recursive handling of mutual circular citations (`cl_1_1` $\leftrightarrow$ `cl_2_1`) and safe `UNRESOLVED` tagging for dangling citations.

### 3.6 Tab 6: Failure Mode Taxonomy & Governance
- Structured cards for all 6 systemic failure modes:
  - `FM-01`: Long-Tail Starvation & Zero-Shot Collapse
  - `FM-02`: Precision-Recall Threshold Dilemma
  - `FM-03`: Linear Probe Representation Bottleneck
  - `FM-04`: Bag-of-Words Fallacy & Lexical False Entailment
  - `FM-05`: Saliency Noise & Stopword Dominance
  - `FM-06`: Taxonomy Granularity & Morphological Clashing

---

## 4. REST API Endpoint Specification

The dynamic dashboard server (`src/dashboard/app.py`) exposes clean JSON endpoints for programmatic integration:

| Method | Endpoint | Description | Response Structure |
|---|---|---|---|
| `GET` | `/` | Web User Interface | HTML Document (`text/html`) |
| `GET` | `/api/provenance` | Model architecture & SHA-256 hash | JSON: `{ "model_architecture", "expected_weights_sha256", "weights_file_exists", "safety_notice" }` |
| `GET` | `/api/ledgar` | LEDGAR test metrics, curve, and tiers | JSON: `{ "calibrated_metrics_tau_0_04", "baseline_metrics_tau_0_50", "label_frequency_tiers" }` |
| `GET` | `/api/contractnli`| ContractNLI confusion matrix & error flows | JSON: `{ "accuracy", "macro_f1", "confusion_matrix", "dominant_error_flow" }` |
| `GET` | `/api/cross_domain`| Cross-domain compatibility audit | JSON: `{ "task_compatibility_matrix", "representation_clustering" }` |
| `GET` | `/api/robustness` | 5-dimension robustness benchmarks | JSON: `{ "input_perturbations", "context_stress_invariants", "sequence_token_gini" }` |
| `GET` | `/api/cases` | Verified error cases & failure modes | JSON: `{ "cases", "failure_modes" }` |
| `GET` | `/api/health` | System data-source integrity check | JSON: `{ "status": "HEALTHY", "data_sources": { ... } }` |

---

## 5. Setup and Execution Instructions

### Option A: Launching the Dynamic Live Server
To run the live interactive dashboard web server on localhost:
```powershell
python -m src.dashboard.app
```
By default, the application listens on `http://127.0.0.1:5000`. You can configure a custom port via the `PORT` environment variable:
```powershell
$env:PORT="8080"
python -m src.dashboard.app
```

### Option B: Viewing the Pre-Compiled Standalone Dashboard
To inspect the dashboard offline without launching Python web servers:
- Open [`results/task024/index.html`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/task024/index.html) directly in any modern browser (Chrome, Edge, Firefox, Safari).

### Option C: Re-Compiling Static Artifacts
To regenerate the static bundle and manifest after modifying data sources:
```powershell
python src/dashboard/generator.py
```

---

## 6. Metric-to-Source Traceability Matrix

Every single metric presented on the dashboard maps 1:1 to an audited underlying JSON record:

| Displayed Metric | Dashboard Value | Source Artifact | Field Path in Source |
|---|---|---|---|
| Model SHA-256 | `7cd08d2c086f...` | `results/models/.../model.safetensors` | Bitwise SHA-256 calculation |
| Operating Threshold | `0.04` | `TASK019_..._CALIBRATED.json` | `stage1_validation_calibration.optimal_threshold` |
| LEDGAR TP (&tau;=0.04) | `12,699` | `TASK019_..._CALIBRATED.json` | `stage2_held_out_test_evaluation.metrics_at_calibrated_threshold.true_positives` |
| LEDGAR FP (&tau;=0.04) | `58,947` | `TASK019_..._CALIBRATED.json` | `stage2_held_out_test_evaluation.metrics_at_calibrated_threshold.false_positives` |
| LEDGAR FN (&tau;=0.04) | `92,584` | `TASK019_..._CALIBRATED.json` | `stage2_held_out_test_evaluation.metrics_at_calibrated_threshold.false_negatives` |
| LEDGAR Micro-F1 | `0.1435` | `TASK019_..._CALIBRATED.json` | `stage2_held_out_test_evaluation.metrics_at_calibrated_threshold.micro_f1` |
| ContractNLI Accuracy | `65.57%` | `TASK018_CONTRACTNLI_TFIDF_SVM.json` | `test_metrics.accuracy` |
| ContractNLI NM &rarr; E | `383 (42.41%)`| `TASK018_CONTRACTNLI_TFIDF_SVM.json` | `confusion_matrix.matrix[2][1]` |
| Zero-Shot Classes | `2,833` | `task019_experiment_manifest.json` | `preflight_metadata.zero_example_labels` |
| Typographical Cosine | `0.9706` | `task022_robustness_manifest.json` | `experiment_1_input_perturbations.summary_by_perturbation.TYPOGRAPHICAL_NOISE.mean_probability_cosine_similarity` |

---

## 7. Automated Test Suite and Regression Status

### 7.1 Dedicated Task 024 Test Suite ([`tests/test_dashboard.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_dashboard.py))
All 6 dedicated unit tests passed:
- `test_1_dashboard_manifest_integrity`: ✅ **PASSED**
- `test_2_dashboard_data_loader_ledgar`: ✅ **PASSED**
- `test_3_dashboard_data_loader_contractnli`: ✅ **PASSED**
- `test_4_dashboard_data_loader_graceful_missing_handling`: ✅ **PASSED**
- `test_5_flask_rest_api_endpoints`: ✅ **PASSED**
- `test_6_static_dashboard_compiled_and_sanitized`: ✅ **PASSED**  
*(6 passed in 0.27s)*

### 7.2 Full Codebase Regression Status
Full regression execution across Tasks 019–024:
- Task 024 Dashboard Suite: 6 passed
- Task 023 Error Analysis Suite: 6 passed
- Task 022 Robustness Suite: 6 passed
- Task 021 Ablation Suite: 10 passed
- Task 020 Cross-Domain Suite: 20 passed
- Task 019 LEDGAR Split Suite: 4 passed
- LEDGAR Frozen Subset Architecture Suite: 5 passed
- **Total**: **57 passed in 99.88s** with **0 failures and 0 skipped tests**.

---

## 8. Updated Task-Board Status

In [`PROJECT_TASK_BOARD.md`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/PROJECT_TASK_BOARD.md):
- **TASK 024**: Marked as **✅ COMPLETED**
- **TASK 025**: Remains strictly **🔒 LOCKED** (awaiting explicit user authorization)

*Task 024 is complete. No work on Task 025 has been initiated.*
