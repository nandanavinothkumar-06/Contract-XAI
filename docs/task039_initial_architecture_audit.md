# CONTRACTRISK-XAI: Task 039 — Baseline Architecture Audit: Indian Legal Source Verification & Coverage

**Document Version:** 1.0.0  
**Status:** Audit Completed  
**Classification:** Engineering Specification & Baseline Audit  
**Date:** 2026-10-17  
**Prerequisites:** Task 038 Completed  

---

## 1. Executive Summary

Task 039 establishes a defensible, rigorous source-verification and legal-coverage framework for the Indian statutory corpus in **CONTRACTRISK-XAI**.

The primary objective is to fundamentally enforce the distinction between:
- **A. Repository Presence:** A source file physically exists in the repository.
- **B. Checksum Reproducibility:** A local file has a reproducible cryptographic hash (SHA-256).
- **C. Internal Metadata Consistency:** Manifest headers, file paths, and identifier formats match.
- **D. Authoritative Content Match:** The text has been compared byte-for-byte or section-by-section against an authoritative government reference artifact (e.g., India Code PDF/HTML or The Gazette of India).
- **E. Legal Currentness & Commencement:** The statutory text reflects the law in force as of a documented verification timestamp, accounting for amendments, omissions, and commencement notifications.
- **F. Legal Applicability:** The provision legally governs a specific contract clause, transaction, jurisdiction, or party.

This audit establishes the baseline of existing files, metadata, retrieval adapters, evidence quality logic, and test suites, and details all misleading claims and verification gaps prior to code implementation.

---

## 2. Actual Files Inspected

| Category | File Path | Size (Bytes) | Role & Current State |
| :--- | :--- | :--- | :--- |
| **Corpus Manifest** | `data/legal_sources/corpus_manifest.json` | 8,670 | Lists 6 statutory sources; all labeled `VERIFIED_OFFICIAL` with local hashes. |
| **Snapshots** | `data/legal_sources/snapshots/IN_ACT_1872_09.txt` | 8,873 | Curated commercial extract of 14 sections (Indian Contract Act, 1872). |
| **Snapshots** | `data/legal_sources/snapshots/IN_ACT_2000_21.txt` | 5,536 | Curated extract of 6 sections (Information Technology Act, 2000); includes editorial note on Sec 66A. |
| **Snapshots** | `data/legal_sources/snapshots/IN_ACT_2023_22.txt` | 4,982 | Curated extract of 7 sections (DPDP Act, 2023); substantive sections uncommenced. |
| **Snapshots** | `data/legal_sources/snapshots/IN_ACT_1963_47.txt` | 3,223 | Curated extract of 6 sections (Specific Relief Act, 1963); includes editorial note on 2018 amendment. |
| **Snapshots** | `data/legal_sources/snapshots/IN_ACT_1996_26.txt` | 4,878 | Curated extract of 5 sections (Arbitration & Conciliation Act, 1996). |
| **Snapshots** | `data/legal_sources/snapshots/IN_ACT_2023_47.txt` | 3,644 | Curated extract of 3 sections (Bharatiya Sakshya Adhiniyam, 2023). |
| **Provenance** | `src/legal_sources/provenance.py` | 2,278 | Defines enums `VerificationStatus`, `CurrentnessStatus`, `CommencementStatus`, `SourceType`, `RetrievalMethod`. |
| **Schema** | `src/legal_sources/schema.py` | 4,734 | Defines Pydantic models `LegalSource`, `LegalPassage`, `LegalSourceQuery`, `LegalSourceRetrievalResult`. |
| **Ingestion** | `src/legal_sources/ingestion.py` | 9,607 | `StatutoryIngestionEngine`: regex section boundary extraction and local SHA-256 verification. |
| **Registry** | `src/legal_sources/registry.py` | 3,485 | In-memory `LegalSourceRegistry` and `get_authoritative_indian_corpus()` loader. |
| **Index & Retrieval** | `src/legal_sources/index.py`, `retriever.py`, `bm25.py` | ~18 KB | Lexical BM25 indexing, exact section lookup, and query execution. |
| **Evidence Connector** | `src/review/evidence.py` | 8,691 | `ClauseEvidenceRetriever`: computes Task 038 evidence quality states (`TRACEABLE`, `PARTIAL`, etc.). |
| **Tests** | `tests/test_indian_legal_sources.py` | 35,846 | 27 automated tests validating Task 032 baseline capabilities. |
| **Tests** | `tests/test_evidence_grounded_analysis.py` | 30,622 | 21 automated tests validating Task 038 end-to-end evidence chain. |
| **Documentation** | `docs/task032_indian_legal_sources.md` | 16,211 | Task 032 specification document. |
| **Documentation** | `docs/task038_evidence_grounded_analysis.md` | 16,060 | Task 038 specification document. |

---

## 3. Current Source Identifiers & Snapshot Coverage

The repository contains exactly 6 snapshot files under `data/legal_sources/snapshots/`. The table below records what text is **actually** present versus the full scope of each Act:

| Source ID | Statute Title | Actual Sections in Local Snapshot | Total Sections in Full Statute | Local Completeness Ratio |
| :--- | :--- | :--- | :--- | :--- |
| `IN_ACT_1872_09` | The Indian Contract Act, 1872 | Sections 1, 2, 10, 11, 23, 27, 28, 56, 73, 74, 124, 125, 148, 172 (14 sections) | 238 active sections (originally 266) | **~5.9%** (Curated Commercial Extract) |
| `IN_ACT_2000_21` | The Information Technology Act, 2000 | Sections 1, 4, 10A, 43A, 66A, 72A (6 sections) | 94 sections + schedules | **~6.4%** (Curated Commercial Extract) |
| `IN_ACT_2023_22` | The Digital Personal Data Protection Act, 2023 | Sections 1, 2, 4, 5, 6, 8, 36, 44 (8 sections) | 44 sections + schedule | **~18.2%** (Curated Commercial Extract) |
| `IN_ACT_1963_47` | The Specific Relief Act, 1963 | Sections 1, 10, 14, 14A, 16, 20A (6 sections) | 44 sections + schedule | **~13.6%** (Curated Commercial Extract) |
| `IN_ACT_1996_26` | The Arbitration and Conciliation Act, 1996 | Sections 1, 7, 8, 9, 16, 34 (6 sections) | 86 sections + schedules | **~7.0%** (Curated Commercial Extract) |
| `IN_ACT_2023_47` | The Bharatiya Sakshya Adhiniyam, 2023 | Sections 1, 61, 63 (3 sections) | 170 sections + schedule | **~1.8%** (Curated Commercial Extract) |

**Key Finding:** The statutory corpus is strictly a **curated commercial extract collection (43 sections total)**, NOT a collection of full legislative Acts.

---

## 4. Existing Hash Behavior vs. Authoritative Reference Checksums

### Current Implementation
- In `src/legal_sources/ingestion.py`:
  ```python
  def verify_snapshot_integrity(self, snapshot_path: str, expected_sha256: Optional[str] = None):
      with open(snapshot_path, "rb") as f:
          data = f.read()
      computed = hashlib.sha256(data).hexdigest()
      if expected_sha256 and computed.lower() != expected_sha256.lower():
          return False, computed, len(data)
      return True, computed, len(data)
  ```
- In `corpus_manifest.json`:
  `content_checksum_sha256` records the hash of the local text file generated during development.

### The Verification Fallacy
- The system currently equates `computed_sha == expected_sha` with `verification_status: VERIFIED_OFFICIAL`.
- **Deficiency:** A local SHA-256 only proves that the local text file has not changed since it was saved to disk. It does **not** prove:
  1. That the text matches the official publication issued by the Ministry of Law & Justice or published in the Gazette of India.
  2. That the text is free from manual editing, truncation, or typo insertion.
  3. That the provisions are legally in force or amended up to date.

---

## 5. Identification of Misleading Claims & Deficiencies

### 5.1 Misleading Claim: "VERIFIED_OFFICIAL" Status
- **Location:** `data/legal_sources/corpus_manifest.json` (lines 22, 49, 79, 108, 135, 162).
- **Issue:** All 6 sources are marked `"verification_status": "VERIFIED_OFFICIAL"`. In reality, no automated or documented byte-by-byte comparison against official gazette or India Code reference artifacts was recorded. They are local extracts.
- **Correction Required:** The status should distinguish between `REPOSITORY_PRESENT`, `CHECKSUM_RECORDED`, and `OFFICIAL_SOURCE_IDENTIFIED`, remaining `UNVERIFIED` or `PARTIALLY_VERIFIED` with respect to external official content comparison.

### 5.2 Misleading Claim: Implied Act Completeness
- **Location:** Manifest titles (`"The Indian Contract Act, 1872"`), UI labels, and citation headings.
- **Issue:** A user seeing "The Indian Contract Act, 1872" in the registry or search view may infer that the whole statute is searched. If a clause addresses bailment liens (Sec 170) or agency termination (Sec 201), the search returns `NO_MATCHING_EVIDENCE`, which could be misinterpreted as "Indian law does not regulate this issue."
- **Correction Required:** The system must explicitly disclose:
  1. `source_scope = "CURATED_COMMERCIAL_EXTRACT"`
  2. `source_completeness_status = "CURATED_EXTRACT"`
  3. Explicit list of `covered_sections` (e.g. `["1", "2", "10", "11", "23", "27", "28", "56", "73", "74", "124", "125", "148", "172"]`).
  4. Explicit notice that omitted sections are not searched.

### 5.3 Misleading Content: Editorial Annotations in Statutory Text
- **Location:**
  - `IN_ACT_1963_47.txt` line 19: `[Note: Substituted by the Specific Relief (Amendment) Act, 2018...]`
  - `IN_ACT_2000_21.txt` lines 28 & 35: `[Note: Section 66A was struck down in its entirety...]`
  - `IN_ACT_2023_47.txt` line 14: `[Note: Commenced on 1st July, 2024...]`
- **Issue:** Commentary and case law citations are embedded directly into the `.txt` snapshot files, mixing secondary editorial text with statutory text.
- **Correction Required:** A strict distinction between verbatim legislative text and secondary editorial commentary/amendment notes must be maintained.

### 5.4 Misleading Metadata: DPDP Act Commencement Date
- **Location:** `corpus_manifest.json` line 69: `"commencement_date": "2023-08-11"`.
- **Issue:** 11 August 2023 was the date of Presidential Assent and enactment, NOT the date of general commencement. Substantive provisions (Sections 3–44) require appointment of dates by Central Government notification.
- **Correction Required:** Distinguish `enactment_date` (`2023-08-11`) from `commencement_date` (Section 1 commenced on 11 Aug 2023; substantive provisions `NOT_COMMENCED`).

### 5.5 Retrieval Ranking Scores vs. Legal Confidence
- **Location:** UI passages table and review routes.
- **Status in Task 038:** Task 038 added `SCORE_SEMANTICS_DISCLAIMER` stating BM25 is a heuristic ranking metric.
- **Enhancement in Task 039:** Must strictly prevent any transformation of BM25 scores into percentages, confidence ratings, or legal probabilities.

---

## 6. Verification Status Model & Gap Analysis

### Current Status Enum (`src/legal_sources/provenance.py`)
```python
class VerificationStatus(str, Enum):
    VERIFIED_OFFICIAL = "VERIFIED_OFFICIAL"
    VERIFIED_AUTHORITATIVE = "VERIFIED_AUTHORITATIVE"
    USER_SUPPLIED = "USER_SUPPLIED"
    UNVERIFIED = "UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    OUTDATED = "OUTDATED"
```

### Required 10-Tier Verification Status Model (Task 039)
To accurately reflect verifiable evidence, the status model must encompass:
1. `REPOSITORY_PRESENT`: Local file exists and is readable on disk.
2. `METADATA_VALIDATED`: Manifest fields and schema relationships pass validation.
3. `CHECKSUM_RECORDED`: Local SHA-256 has been reproducibly computed and logged.
4. `OFFICIAL_SOURCE_IDENTIFIED`: Plausible authoritative publication URL / gazette identifier recorded, but exact text match unverified.
5. `CONTENT_MATCH_VERIFIED`: Local text has been compared against an authoritative reference artifact using a documented method.
6. `CURRENTNESS_VERIFIED`: Legal version and currentness checked against official gazettes/notifications as of a recorded timestamp.
7. `PARTIALLY_VERIFIED`: Certain sections or metadata verified; others remain unverified or uncommenced.
8. `UNVERIFIED`: Verification has not been established.
9. `VERIFICATION_FAILED`: Comparison or validation attempted and failed.
10. `STALE_OR_REVIEW_REQUIRED`: Legislation superseded, amended, or recheck interval expired.

**Compatibility Strategy:** Retain `VERIFIED_OFFICIAL` and `VERIFIED_AUTHORITATIVE` as recognized values/aliases so existing Task 032 and Task 038 tests continue to pass without regression, while new workflow code transitions sources to honest, defensible states.

---

## 7. Proposed Minimal Architecture Changes

```
src/legal_sources/
├── provenance.py        <-- Extend VerificationStatus (10 states) + CompletenessStatus + AmendmentStatus
├── schema.py            <-- Extend LegalSource with 26 mandatory verification & coverage fields
├── ingestion.py         <-- Support extended schema fields without breaking parsing
├── registry.py          <-- Support extended querying by verification tier & coverage scope
├── verification.py      <-- [NEW] Repeatable verification workflow engine + machine-readable reports
├── coverage.py          <-- [NEW] Legal coverage model & human-readable coverage matrix
└── routes.py            <-- Add /api/legal/verify and /api/legal/coverage endpoints

src/review/
└── evidence.py          <-- Surface source verification tier and completeness in review workspace

docs/
├── task039_initial_architecture_audit.md       <-- [THIS AUDIT]
└── task039_source_verification_coverage.md     <-- [PHASE J SPECIFICATION]

tests/
└── test_legal_source_verification.py           <-- [NEW] 26+ focused verification and coverage tests
```

---

## 8. Summary of Non-Negotiable Constraints
- Tasks 028 and 029 remain strictly `🔒 LOCKED`.
- Task 040 must **NOT** be started.
- Zero mock bypasses for advocate verification, CSRF, or tenant boundaries.
- No live external network dependencies in core test suites; deterministic fixtures and mock responses used.
- Full regression suite across Tasks 001–038 (492 tests) must remain 100% green.
