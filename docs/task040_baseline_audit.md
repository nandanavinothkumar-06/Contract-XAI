# Task 040 Baseline Architecture Audit: Statutory Reference Artifact Acquisition and Gazette Ingestion

**Project:** CONTRACTRISK-XAI  
**Date:** 2026-10-17  
**Auditor:** Antigravity IDE Autonomous Agent  
**Prerequisite:** Task 039 Completed (Source Verification and Legal Coverage Framework)  

---

## 1. Baseline Inspection Summary

A comprehensive inspection of the CONTRACTRISK-XAI codebase was conducted to establish the operational starting point for Task 040.

### A. Core Components Audited:
1. **Provenance Model (`src/legal_sources/provenance.py`):**
   - 10-tier `VerificationStatus` model active: `REPOSITORY_PRESENT`, `METADATA_VALIDATED`, `CHECKSUM_RECORDED`, `OFFICIAL_SOURCE_IDENTIFIED`, `CONTENT_MATCH_VERIFIED`, `CURRENTNESS_VERIFIED`, `PARTIALLY_VERIFIED`, `UNVERIFIED`, `VERIFICATION_FAILED`, and `STALE_OR_REVIEW_REQUIRED`.
   - `is_retrieval_eligible()` and `is_authoritatively_verified()` helper predicates established.
   - Supporting enums: `SourceCompletenessStatus`, `AmendmentCoverageStatus`, `VerificationMethod`, `CurrentnessStatus`, `CommencementStatus`.

2. **Schema & Data Models (`src/legal_sources/schema.py`):**
   - `LegalSource` schema supports all 26 Phase B fields with bidirectional backward-compatible field synchronization (`sync_backward_compatible_fields`).
   - `LegalPassage` preserves verbatim passage text, character offsets, and source linkages.

3. **Ingestion & Registry (`src/legal_sources/ingestion.py`, `src/legal_sources/registry.py`):**
   - `StatutoryIngestionEngine` verifies local snapshot SHA-256 digests and extracts structural sections via regular expressions (`^Section\s+([0-9]+[A-Za-z]?)\.`).
   - `LegalSourceRegistry` maintains in-memory catalog of ingested statutes and section indices.

4. **Verification & Coverage Engines (`src/legal_sources/verification.py`, `src/legal_sources/coverage.py`):**
   - `LegalSourceVerificationWorkflow` validates manifest schema, verifies local file hashes, checks official URL syntax, and produces JSON and Markdown audit reports.
   - `LegalCoverageModel` explicitly tracks Categories A through F across 6 central statutes (40 sections, ~5.91% active section coverage).

5. **Existing Corpus State (`data/legal_sources/corpus_manifest.json`, `data/legal_sources/snapshots/`):**
   - 6 snapshot files present:
     - `IN_ACT_1872_09.txt` (11 sections)
     - `IN_ACT_2000_21.txt` (6 sections)
     - `IN_ACT_2023_22.txt` (8 sections)
     - `IN_ACT_1963_47.txt` (6 sections)
     - `IN_ACT_1996_26.txt` (6 sections)
     - `IN_ACT_2023_47.txt` (3 sections)
   - All 6 sources are classified as `PARTIALLY_VERIFIED` with `CURATED_EXTRACT` completeness.

6. **Environment Capabilities:**
   - Python: 3.13.5
   - `pypdf`: Version 6.20.1 available (pure-Python PDF parsing, extraction, and validation).
   - `requests`: Version 2.32.4 available.
   - `reportlab`: Version 5.0.1 available.
   - `pytesseract`: Version 0.3.13 available (OCR wrapper).

---

## 2. Capability & Gap Analysis for Task 040

| Capability Required | Current System State | Task 040 Gap |
|---|---|---|
| **Authoritative Artifact Acquisition** | Only safe URL syntax validation in `verification.py`; no file download engine. | Need secure acquisition manager with strict SSRF defense (allowlisted hosts, IP filtering), timeout bounds, redirect validation, and download size limits. |
| **Original Byte Preservation** | No directory structure or persistence for acquired binary artifacts. | Need `data/legal_sources/reference_artifacts/<source_id>/<pub_id>/original.pdf` with immutable byte preservation and `acquisition_record.json`. |
| **Multi-Signal Artifact Validation** | Only file existence and SHA-256 checks on local text. | Need magic byte validation (`%PDF-`), MIME validation, parser validation with `pypdf`, and path traversal prevention. |
| **Text Extraction Engine** | Structural regex on `.txt` snapshots only. | Need `StatutoryTextExtractor` parsing Gazette PDFs, capturing page counts, character counts, empty pages, OCR flags, and extraction warnings without modifying original artifacts. |
| **Section-by-Section Comparison** | Basic line-set intersection in `verification.py`. | Need granular `StatutoryComparisonEngine` aligning exact section numbers, computing textual diffs, handling documented normalizations, and reporting omitted vs present provisions. |
| **Verification Status Transitions** | Static `PARTIALLY_VERIFIED` in manifest. | Need fine-grained transition logic enabling sources to advance to `CONTENT_MATCH_VERIFIED` for compared scopes without falsely certifying currentness or legal applicability. |
| **Security & RBAC** | Basic Flask auth in `routes.py`. | Need role-restricted endpoints for acquisition (`SUPERVISING_LAWYER`) and audit logging of artifact actions. |

---

## 3. Implementation Plan for Task 040

1. **Phase B & C — Acquisition & Safe Storage:**
   - Create `src/legal_sources/acquisition.py`: `GazetteArtifactAcquisitionManager`.
   - Implement SSRF protections: approved government domain allowlist (`egazette.gov.in`, `indiacode.nic.in`, `meity.gov.in`, `legislative.gov.in`, `lawmin.gov.in`), block private/loopback/link-local IPs, validate redirect hosts, enforce 50MB max size and strict TLS.
   - Establish storage hierarchy: `reference_artifacts/`, `extracted_text/`, `comparisons/`.
   - Implement manual artifact placement validation for air-gapped / offline verification.

2. **Phase D & E — Provenance & Text Extraction:**
   - Create `src/legal_sources/extraction.py`: `StatutoryTextExtractor`.
   - Use `pypdf` to parse PDFs, extract text per page, record page numbers, detect empty/scanned pages, and log extraction warnings.

3. **Phase F & G — Comparison Engine & Status Transitions:**
   - Create `src/legal_sources/comparison.py`: `StatutoryComparisonEngine`.
   - Implement section-by-section alignment against curated snapshots.
   - Distinguish exact matches, normalized matches, textual differences, and missing sections.
   - Enforce status transition invariants: scoped `CONTENT_MATCH_VERIFIED` requires real byte/text alignment; currentness remains separate.

4. **Phase H & I — Security, Routes & Reporting:**
   - Update `src/legal_sources/routes.py` with acquisition and comparison endpoints restricted to `SUPERVISING_LAWYER`.
   - Update verification reports to include artifact provenance, extraction records, and section diffs.

5. **Phase J — Testing:**
   - Create `tests/test_statutory_artifact_acquisition.py` covering all 32 minimum test requirements using deterministic fixtures and mocked networks.
