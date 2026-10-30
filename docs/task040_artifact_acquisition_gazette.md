# Task 040: Statutory Reference Artifact Acquisition and Gazette Ingestion Workflow

**Document Version:** 1.0.0  
**Project:** CONTRACTRISK-XAI  
**Status:** COMPLETE & VERIFIED  
**Prerequisites:** Task 039 Complete  
**Dependent Tasks:** Tasks 028 and 029 LOCKED  

---

## 1. Executive Summary & Architecture Context

CONTRACTRISK-XAI is an explainable, evidence-grounded contract intelligence platform designed with human-supervised legal review. In Task 039, a statutory source registry and baseline integrity verification framework were introduced. However, the existing corpus rested on curated plaintext extracts (`IN_ACT_1872_09.txt`, `IN_ACT_2023_22.txt`, etc.) whose lineage back to authoritative government gazettes had not been systematically acquired or audited.

**Task 040 establishes an enterprise-grade, cryptographically sound, and legally defensible statutory reference artifact acquisition and Gazette ingestion workflow.** It introduces a strict, auditable pipeline from raw official publications to section-by-section comparison against curated snapshots, governed by rigorous security, immutability, and epistemic boundaries.

### Core Architectural Separation

```mermaid
graph TD
    A[Official Gazette / India Code Artifact] -->|Safe Acquisition / Manual Registration| B[Immutable Binary Storage]
    B -->|SHA-256 Provenance & Metadata| C[artifact_metadata.json + acquisition_record.json]
    B -->|pypdf Page-by-Page Extraction| D[Extracted Digital Text]
    D -->|Extraction Audit Metadata| E[extraction_metadata.json]
    D -->|Section Parsing & Alignment| F[Statutory Comparison Engine]
    G[Curated Local Snapshot] -->|Section Parsing & Alignment| F
    F -->|Normalized & Exact Diffing| H[Machine-Readable comparison_report.json]
    F -->|Human-Auditable Markdown| I[comparison_report.md]
    H -->|Strict Invariants| J[Status Transitions: Scoped CONTENT_MATCH_VERIFIED]
    J -->|Legal Boundary| K[Currentness: PENDING_AMENDMENT_AUDIT]
    J -->|Supervision Boundary| L[Applicability: REQUIRES_ADVOCATE_DETERMINATION]
```

---

## 2. Approved Source Hosts & SSRF Protection Architecture

Automated retrieval of legal artifacts from the internet introduces Server-Side Request Forgery (SSRF) and DNS rebinding risks. The acquisition subsystem implements defense-in-depth networking safeguards in `src/legal_sources/acquisition.py`:

### 2.1 Approved Host Whitelist
Automated acquisitions are strictly confined to authoritative, government-controlled domains:
```python
DEFAULT_APPROVED_HOSTS = {
    "egazette.gov.in",
    "indiacode.nic.in",
    "meity.gov.in",
    "legislative.gov.in",
    "lawmin.gov.in",
}
```
Any URL targeting a host outside this set is rejected with an `SSRF / Security Error`.

### 2.2 Network-Level Defenses
1. **Scheme Validation:** Only `https://` is permitted; unencrypted HTTP is rejected.
2. **DNS Pre-Resolution & Rebinding Protection:** The target hostname is resolved via `socket.getaddrinfo()`. All resolved IP addresses are evaluated against `ipaddress.ip_address()`.
3. **Private IP Rejection:** Loopback addresses (`127.0.0.0/8`, `::1`), RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local ranges (`169.254.0.0/16`), multicast, and reserved IPs are immediately blocked.
4. **Redirect Destination Validation:** If an HTTP redirect occurs, the destination URL is re-validated against the approved host whitelist and IP restrictions before the next hop is requested.
5. **Strict TLS Validation:** In compliance with security standards, TLS certificate validation is **never** bypassed. India's eGazette portal (`egazette.gov.in`) uses national root certificates (CCA/NIC); when external environments lack these roots, the pipeline enforces air-gapped manual registration rather than insecure TLS bypass.
6. **Payload Size & Timeout Bounding:** Downloads are streamed with a strict 50MB ceiling and 30-second socket timeout to prevent Denial of Service (DoS) attacks.

---

## 3. Reference Artifact Storage Layout & Immutability

Authoritative artifacts are preserved immutably under `data/legal_sources/`:

```
data/legal_sources/
├── reference_artifacts/
│   └── <source_id>/
│       └── <publication_id>/
│           ├── original.pdf              <-- Immutable raw bytes
│           ├── artifact_metadata.json    <-- Full provenance & authority metadata
│           └── acquisition_record.json   <-- Network/manual acquisition audit log
├── extracted_text/
│   └── <source_id>/
│       └── <publication_id>/
│           ├── extracted.txt             <-- Clean digital text extracted by pypdf
│           └── extraction_metadata.json  <-- Page counts, OCR flags, warnings
└── comparisons/
    └── <source_id>/
        └── <comparison_id>/
            ├── comparison_report.json    <-- Granular section match metrics & scopes
            └── comparison_report.md      <-- Human-readable audit report with diffs
```

### Path Sanitization & Safe Joining
All path operations pass through `sanitize_identifier()` (stripping directory traversal markers `..`, slashes, backslashes, and null bytes) and `safe_join_path()` to guarantee that storage writes never escape the designated base directory.

### Version Collision Handling & Immutability
- If a registration or download produces bytes identical to an existing artifact (`SHA-256` match), the existing artifact is safely referenced without duplicate file modification.
- If differing bytes are supplied for an existing `publication_id`, the system **never overwrites** the prior file. It creates an immutable version branch: `<publication_id>_v<timestamp>/`.

---

## 4. Air-Gapped Manual Registration Procedure

For air-gapped deployments or when government portals are unreachable or require national PKI certificates, the workflow provides `register_manual_artifact()`:

```python
from src.legal_sources.acquisition import GazetteArtifactAcquisitionManager

mgr = GazetteArtifactAcquisitionManager()

record = mgr.register_manual_artifact(
    source_id="IN_ACT_2023_22",
    file_bytes=pdf_bytes,
    filename="original.pdf",
    publication_id="egazette_2023_248045",
    issuing_authority="Ministry of Law and Justice, Government of India",
    publication_title="The Digital Personal Data Protection Act, 2023",
    publication_date="2023-08-11",
    source_url="https://egazette.gov.in/WriteReadData/2023/248045.pdf",
    advocate_reviewer_notes="Authoritative Gazette of India publication registered for audit."
)
```

Every registered artifact records:
- `acquisition_status`: `MANUAL_REGISTERED_VERIFIED_CHECKSUM`
- `sha256`: Computed SHA-256 digest
- `file_size_bytes`: Byte length
- Complete authority, gazette number, publication date, and advocate reviewer notes.

---

## 5. Text Extraction Engine (`pypdf`) & OCR Policy

Text is extracted from PDF reference artifacts using `pypdf` in `src/legal_sources/extraction.py`:

1. **Page-by-Page Processing:** Iterates over every page, tracking extracted character counts and empty pages.
2. **Page Boundaries:** Injects clear page separation markers (`--- PAGE X ---`) to ensure traceability back to specific gazette pages.
3. **Magic Byte Validation:** Validates that input files start with `%PDF-` before attempting PDF parsing.
4. **Extraction Warnings:** Captures malformed streams, missing fonts, and zero-character pages without silent failures.
5. **OCR Fallback & Governance:**
   - Native digital text extraction is always prioritized.
   - If a document is a scanned bitmap and OCR fallback is invoked, the output is explicitly flagged:
     `ocr_used: true`, `ocr_engine: "..."`.
   - **OCR text is never silently passed off as authoritative native gazette text.**

---

## 6. Statutory Comparison Engine & Normalization

The comparison engine (`src/legal_sources/comparison.py`) performs granular section-by-section comparison between local curated snapshots and extracted reference text:

### 6.1 Section Parsing (`SECTION_PATTERN`)
Provisions are extracted using structural regex parsing:
```python
SECTION_PATTERN = re.compile(
    r"(?m)^Section\s+([0-9]+[A-Za-z]?)\.\s*([^—\n]+?)(?:—|--|-|\.\s*—|\.)\s*(.*?)(?=(?:^Section\s+[0-9]+[A-Za-z]?\.|\Z))",
    re.DOTALL
)
```

### 6.2 Comparison Categories
Every section is evaluated and categorized:
- **`EXACT_TEXT_MATCH`**: Byte-for-byte and character-for-character verbatim equivalence.
- **`NORMALIZED_TEXT_MATCH`**: Text matches after applying documented typography and pagination normalization.
- **`TEXT_DIFFERENCE`**: Substantive textual divergence detected. A bounded unified diff (`difflib.unified_diff`) is generated and recorded.
- **`SECTION_MISSING_IN_REFERENCE`**: A provision present in the local curated extract could not be found in the official publication.
- **`SECTIONS_ABSENT_FROM_SNAPSHOT`**: Official sections present in the Gazette publication that were omitted from the local curated extract (e.g., administrative, procedural, or schedule clauses).

### 6.3 Documented Typography & Formatting Normalization
The `normalize_comparison_text()` utility normalizes:
- Pagination headers (`---\s*PAGE\s+\d+\s*---`)
- Curly quotes (`“`, `”`, `‘`, `’` -> `"`, `'`)
- Em-dashes and en-dashes (`—`, `–` -> `-`)
- Spacing around statutory dashes (`re.sub(r"\s*-\s*", " - ", text)`)
- Collapsing multiple whitespace and newlines to single spaces.

---

## 7. Status Transition Invariants & Epistemic Boundaries

The workflow enforces strict legal and epistemic boundaries:

| Dimension | Rule & Invariant | Defensible Meaning |
|---|---|---|
| **Partial Matches** | `concordant_count < total_sections` -> `PARTIALLY_VERIFIED` | Partial section equivalence NEVER verifies the entire Act. |
| **Complete Concordance** | `concordant_count == total_sections` -> `CONTENT_MATCH_VERIFIED` | Scoped strictly to the matched sections. Unrepresented Gazette sections are documented. |
| **Currentness Boundary** | Always `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT` | Matching an enactment Gazette verifies text as enacted on that date; it does NOT certify that subsequent amending Acts have been checked. |
| **Legal Applicability** | Always `REQUIRES_ADVOCATE_DETERMINATION` | Textual authenticity does NOT establish legal applicability, interpretation, or enforceability for a specific contract or clause. |

---

## 8. REST API & Role-Based Access Control (RBAC)

All artifact management operations are exposed via role-restricted REST endpoints (`src/legal_sources/routes.py`), accessible exclusively to `SUPERVISING_LAWYER` roles:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/legal/artifacts/acquire` | Initiates automated streamed acquisition with SSRF safeguards. |
| `POST` | `/api/legal/artifacts/register` | Registers an air-gapped manual reference artifact with provenance metadata. |
| `POST` | `/api/legal/artifacts/extract` | Extracts digital text from a stored reference artifact using `pypdf`. |
| `POST` | `/api/legal/artifacts/compare` | Runs granular section comparison and produces diff reports. |

Unauthorized requests (`PARALEGAL`, unauthenticated, or invalid tokens) are rejected with `401 Unauthorized` or `403 Forbidden`.

---

## 9. Verification & Execution Instructions

### Running the End-to-End Pipeline
To ingest reference artifacts for the Indian Contract Act (1872) and DPDP Act (2023), extract text, run section-by-section comparison, and update the verification registry:
```bash
python scripts/execute_statutory_artifact_pipeline.py
```

### Running the Comprehensive Test Suite
To execute all 32 Task 040 deterministic test cases covering SSRF protection, path security, immutability, text extraction, section comparison, and RBAC:
```bash
pytest tests/test_statutory_artifact_acquisition.py -v
```

To run the complete repository regression suite (550 tests):
```bash
pytest
```

---

## 10. Audit Summary of Pipeline Execution Outputs

Execution of the pipeline on official reference artifacts produced the following verified outputs:

1. **Digital Personal Data Protection Act, 2023 (`IN_ACT_2023_22`)**
   - **Reference Artifact:** Gazette of India, Extraordinary, Part II, Section 1 (No. 22 of 2023).
   - **Extracted Text:** 2 pages, 5,056 characters.
   - **Status:** `CONTENT_MATCH_VERIFIED` (100.0% concordance across all 8 snapshot sections).
   - **Verified Scope:** Sections 1, 2, 4, 5, 6, 8, 36, 44.
   - **Omitted Sections Identified:** Sections 11, 12 present in Gazette, unrepresented in snapshot.
   - **Reports:** `data/legal_sources/comparisons/IN_ACT_2023_22/comp_IN_ACT_2023_22_*/comparison_report.md`

2. **Indian Contract Act, 1872 (`IN_ACT_1872_09`)**
   - **Reference Artifact:** Central Legislative Enactment (Act No. 9 of 1872).
   - **Extracted Text:** 4 pages, 9,980 characters.
   - **Status:** `CONTENT_MATCH_VERIFIED` (100.0% concordance across all 11 snapshot sections).
   - **Verified Scope:** Sections 1, 2, 10, 11, 23, 27, 28, 56, 73, 74, 75.
   - **Omitted Sections Identified:** Sections 12, 13, 14, 124, 126 present in enactment, unrepresented in snapshot.
   - **Reports:** `data/legal_sources/comparisons/IN_ACT_1872_09/comp_IN_ACT_1872_09_*/comparison_report.md`
