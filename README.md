# CONTRACTRISK-XAI

> **An Evidence-Grounded, Explainable, and Domain-Adaptive NLP Framework for Commercial Contract Risk Analysis with Evidence-Aware Abstention.**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Academic%20%2F%20Research%20Only-lightgrey.svg)](LICENSE)
[![Tests Status](https://img.shields.io/badge/tests-717%20passed-brightgreen.svg)](tests/)
[![Architecture](https://img.shields.io/badge/web%20framework-Flask%203.1.0-orange.svg)](src/dashboard/app.py)

---

## 1. Core Principles & Governance Disclaimers

### 1.1 Legal Practice Disclaimer
`CONTRACTRISK-XAI` is an AI-assisted decision-support platform designed for **research, algorithmic auditing, and structured legal triage**. It is **not** a licensed attorney, does not provide legal advice, and must **never** be used as a substitute for professional legal advice, formal due diligence, or qualified statutory compliance review. All automated findings require mandatory independent verification by an enrolled advocate.

### 1.2 Synthetic Evaluation & Non-Confirmatory Pilot Status
All candidate generators, baseline threshold sweeps, and offline comparative evaluations in this repository are executed **strictly on synthetic test fixtures and non-confirmatory feasibility artifacts**. Zero confidential, proprietary, or authentic real-world Indian commercial contracts have been downloaded, scraped, or ingested into this repository.

### 1.3 Methodological Constraints & Prohibition of Superiority Claims (RDR-002)
Per the governing **Research Decision Record ([`docs/research_decision_record_v2_consolidated.md`](docs/research_decision_record_v2_consolidated.md))**:
* The feasibility pilot corpus does **not** constitute an independent confirmatory test set.
* Claims of statistical superiority ($\Delta\text{UFR}_{@\text{MatchedUFC}} > 0$) are strictly **prohibited** without an approved, pre-registered statistical analysis plan that explicitly models clustered contract variance ($\rho$), finite-sample corrections, and verified common support.
* Comparisons between confidence-only baselines and evidence-aware policies are permitted solely under the prespecified matched-coverage estimand ($|\Delta\text{UFC}| \le 0.02$). Forced threshold interpolation across discontinuous points is strictly prohibited.
* **Tasks 028 and 029** remain strictly `🔒 LOCKED`. **Task 042** remains strictly `NOT STARTED`.

---

## 2. Final System Architecture & Pipeline Stages

CONTRACTRISK-XAI formalizes an end-to-end evidence-traceable pipeline connecting untrusted raw document input to human-in-the-loop legal adjudication.

```
[Raw Contract Document: PDF / DOCX / TXT]
                     │
                     ▼
┌───────────────────────────────────────────┐
│ 1. Ingestion Pipeline & Audit Storage     │
│    • DocumentValidator & Quarantine Model │
│    • ModelAgreementProvenanceRecord Hook  │ (Hook 3)
│    • Tamper-Evident SHA-256 Audit Chain   │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│ 2. Preprocessing & Segmentation           │
│    • Non-destructive text normalization   │
│    • Policy A Literal Placeholder Verifier│
│    • Deterministic clause & heading tree  │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│ 3. Candidate Finding Generation           │
│    • ContractConfiguration Filter Hook    │ (Hook 1)
│    • Statutory BM25 Passage Retrieval     │
│    • Deterministic UUID-like Finding ID   │
│    • Semantic Deduplication Engine        │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│ 4. Five-Tier Evidence-Aware Abstention    │
│    • Tier 1: Assessability Safety Gate    │
│    • Tier 2: Evidence Sufficiency Gate    │
│    • Tier 3: Temporal Version Integrity   │
│    • Tier 4: Calibrated Threshold (τ*)    │
│    • Tier 5: Human Review Routing         │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│ 5. Partition-Isolated Evaluation          │
│    • PartitionIsolationValidator Hook     │ (Hook 2: Fail-closed preflight)
│    • Matched Coverage Protocol (±0.02)    │
│    • Primary Estimand: ΔUFR @ Matched UFC │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│ 6. Collaborative Lawyer Review Platform   │
│    • Flask 3.1.0 REST API + UI Shell      │
│    • Role-Based Access Control (4 Roles)  │
│    • Advocate State Bar Verification      │
│    • Final PDF Reports (ReportLab)        │
└───────────────────────────────────────────┘
```

### Module Organization (`src/`):
* **`src/ingestion/`**: Format-specific parsers (PDF, DOCX, TXT with OCR fallback), binary storage, and cryptographic provenance validation.
* **`src/preprocessing/`**: Text normalization and [`OffsetAndPlaceholderVerifier`](src/preprocessing/offset_verifier.py) enforcing Policy A literal preservation across bracketed blanks, dates, and amounts.
* **`src/segmentation/`**: Deterministic structural clause segmenter preserving Python Unicode character offsets and hierarchical levels.
* **`src/candidates/`**: Candidate finding generation, deterministic finding IDs, deduplication, and active configuration filtering.
* **`src/retrieval/` & `src/evidence/`**: Statutory BM25 retrieval over 40 provisions across 6 Indian commercial statutes, evaluating evidence quality (`TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, `STALE`).
* **`src/abstention/`**: Five-tier decision cascade implementation (`EvidenceAwarePolicy`).
* **`src/evaluation/`**: Abstention evaluation harness (`abstention_eval.py`) computing UFR, UFC, UAR, SEAR, and HRW metrics, and [`PartitionIsolationValidator`](src/evaluation/partition_validator.py).
* **`src/models/`**: Legal-BERT classifier wrapper (`nlpaueb/legal-bert-base-uncased`), multi-label inference, and threshold calibration.
* **`src/persistence/`**: SQLAlchemy models (Users, Documents, Snapshots, Segments, Audits, Reviews, Revisions, Reports, Feedback, Blinded Annotations/Adjudications).
* **`src/audit/`**: Cryptographic, tamper-evident SHA-256 audit log chain (`AuditStore`, `AuditLogger`, `AuditVerifier`).
* **`src/auth/`**: Role-based access control, Argon2id password hashing, JWT bearer tokens, and CSRF protection.
* **`src/review/` & `src/reporting/`**: Collaborative lawyer review workbench, lawyer decision logging, client clarification threads, and PDF report generation.
* **`src/dashboard/`**: Flask 3.1.0 live web application (`src/dashboard/app.py`), serving REST endpoints and a responsive single-page workbench.

---

## 3. The Three Strategy A Integration Hooks

In accordance with Strategy A (RDR-002), three integration hooks are wired directly into the operational pipelines:

| Hook | Component | Integration Point | Invariant Enforced |
| :--- | :--- | :--- | :--- |
| **Hook 1** | **Candidate Pipeline** | [`src/candidates/pipeline.py`](src/candidates/pipeline.py) in `generate_candidates_for_clauses()` | Accepts optional `active_configuration`. Validates configuration against available alternative groups and skips inactive alternative clauses prior to model inference. Preserves all clauses when omitted. |
| **Hook 2** | **Evaluation Pipeline** | [`src/evaluation/abstention_eval.py`](src/evaluation/abstention_eval.py) in `evaluate_policy()` & `compare_policies_at_matched_coverage()` | Invokes `preflight_partition_check()` using `PartitionIsolationValidator` before threshold evaluation when partition metadata is supplied. **Fails closed** on detected leakage or DoE macro-family misallocation. |
| **Hook 3** | **Ingestion Pipeline** | [`src/ingestion/pipeline.py`](src/ingestion/pipeline.py) in `ingest_document()` | Accepts optional `model_agreement_provenance`. Validates metadata using `DocumentValidator`. Rejects invalid metadata immediately (`IngestionStatus.FAILED`). Persists valid metadata safely in the tamper-evident audit store and `DatasetRecord.metadata` without unapproved relational table migrations. |

---

## 4. Empirical Model Results & Baseline Metrics

The following metrics represent verified repository evaluation findings across experimental stages:

* **Underlying Checkpoint:** `nlpaueb/legal-bert-base-uncased` (frozen transformer backbone with linear classification heads; possesses zero domain pre-training on authentic Indian commercial legal drafting).
* **Decision Threshold Calibration Dilemma (Task 021/023):**
  * **Uncalibrated Baseline ($\tau = 0.50$):** Suppressed true positive risk classifications by **92.2%** (TP dropped from 12,699 to 989 on full test set) due to uncalibrated linear head probabilities over a frozen encoder.
  * **Empirical Validation Calibration ($\tau^* = 0.04$):** Calibrated threshold locked from validation data achieved **Micro-F1 = 0.1435** on full test data (+675.7% relative gain over $\tau = 0.50$).
* **Evidence-Aware Abstention Comparison (Task 043/047):**
  * Triage reliability is evaluated on a synthetic candidate pool across 7 risk archetypes under the prespecified matched-coverage protocol ($\epsilon = \pm 0.02$).
  * The baseline sweeps continuous thresholds $\tau_{\text{conf}} \in [0.0, 1.0]$. If $|\text{UFC}_{\text{baseline}} - \text{UFC}_{\text{evid}}| > 0.02$, `MATCHED_COVERAGE_UNACHIEVED` is reported and no superiority claim is computed.

---

## 5. Unresolved External Blockers Ledger

In adherence to Strategy A data governance, physical corpus acquisition and ingestion of real Indian commercial contracts remain strictly blocked pending resolution of four formal blockers:

| Blocker ID | Domain | Issue Summary | Resolution Prerequisite |
| :--- | :--- | :--- | :--- |
| **BLK-LEGAL-01** | Copyright / Statutory Law | Scope of Indian Copyright Act, 1957 (§52(1)(a)(i) vs. absence of express statutory Text and Data Mining exception) for multi-user server processing. | Qualified advocate legal opinion. |
| **BLK-LICENSE-02** | Sovereign Terms of Use | Official terms on `doe.gov.in` and `niti.gov.in` restrict redistribution of raw document text without written departmental consent. | Administrative authorization or internal-only research protocol sign-off. |
| **BLK-ACCESS-03** | Network / WAF | DEA portal (`pppinindia.gov.in`) returns `HTTP 403 Forbidden` to automated HTTP requests. | Validated manual acquisition protocol or official mirror. |
| **BLK-PROVENANCE-04** | Dynamic CMS Endpoints | NITI Aayog model contract reports are served via dynamic CMS URLs rather than static immutable endpoints. | Session-pinned cryptographic provenance logging protocol. |

---

## 6. Environment Setup & Dependency Installation

### 6.1 Prerequisites
* Python 3.10, 3.11, 3.12, or 3.13 (Development and testing verified under Python 3.13.5).
* SQLite3 (bundled with Python) or PostgreSQL 14+.

### 6.2 Standard Virtual Environment Setup
```powershell
# 1. Clone repository and navigate to root
cd contractrisk-xai

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate       # On Windows (PowerShell)
# source venv/bin/activate    # On Linux / macOS

# 3. Upgrade pip and install verified dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 6.3 Conda Environment Setup (Alternative)
```powershell
conda env create -f environment.yml
conda activate contractrisk-xai
```

---

## 7. Application Launch & Demonstration Guide

### 7.1 Running the Live Application
The primary application entry point is [`src/dashboard/app.py`](src/dashboard/app.py):

```powershell
# Launch the live Flask application
python -m src.dashboard.app
```
*(Server starts by default at `http://127.0.0.1:5000/`)*

### 7.2 Verification of Application Health
Verify running endpoints via HTTP GET:
```powershell
curl http://127.0.0.1:5000/api/health
```
**Expected Response:**
```json
{
  "status": "HEALTHY",
  "data_sources": {
    "contractnli_baseline": true,
    "ledgar_calibrated_eval": true,
    "model_weights": true,
    "robustness_manifest": true
  }
}
```

### 7.3 Multi-Role Demonstration Accounts
The application automatically seeds a clean development environment with four standardized roles:

* **Lawyer / Advocate (`advocate@legal.in`):** Accesses the Collaborative Review Workbench, examines segmented clauses, inspects statutory evidence, logs legal rationale, and initiates client clarification threads.
* **Enterprise Client (`client@enterprise.in`):** Uploads contracts, tracks document review status, and responds to advocate clarification inquiries.
* **Supervising Lawyer (`supervisor@legal.in`):** Oversees junior advocate review queues, conducts supervisory review, and authorizes final report release.
* **Compliance Auditor (`auditor@governance.in`):** Inspects the cryptographic tamper-evident SHA-256 audit log hash chain and verifies algorithmic provenance.

> [!NOTE]
> **Local Evaluation Passwords:** To prevent exposing development passwords in public-facing documentation, exact login credentials for local testing are documented separately in [`docs/demo_credentials.md`](docs/demo_credentials.md).

---

## 8. Test Execution & Verification

### 8.1 Full Repository Test Suite
```powershell
pytest -q
```
*Current test suite result: **717 passed, 7 warnings in ~144s** (0 failed).*

### 8.2 Focused Strategy A Integration Suite
```powershell
pytest tests/test_model_agreement_provenance.py `
       tests/test_partition_isolation.py `
       tests/test_drafting_alternatives_validation.py `
       tests/test_offset_placeholder_integrity.py `
       tests/test_candidate_pipeline.py `
       tests/test_abstention_eval.py `
       tests/test_ingestion_persistence.py -v
```
*(99 passed in 2.4s)*

### 8.3 Lifecycle Integration Suite
```powershell
pytest tests/test_contract_lifecycle_integration.py -v
```
*(14 passed in 7.3s)*

### 8.4 Offline Evaluation Scripts
* **Policy Comparison Sweep:**
  ```powershell
  python scripts/evaluate_abstention_comparison.py
  ```
* **Statutory Gazette Reference Pipeline:**
  ```powershell
  python scripts/execute_task041_pipeline.py
  ```
