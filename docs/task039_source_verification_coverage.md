# Task 039: Indian Legal Source Verification and Statutory Coverage Framework

**Project:** CONTRACTRISK-XAI  
**Status:** IMPLEMENTED & AUDITED  
**Date:** 2026-10-17  
**Prerequisite:** Task 038 (Evidence-Grounded Analysis & Evidence Quality States)  

---

## 1. Executive Summary & Epistemic Boundaries

CONTRACTRISK-XAI operates as an explainable, lawyer-in-the-loop contract intelligence system. Task 039 establishes a rigorous, defensible legal-source verification and coverage framework for the Indian statutory corpus.

The system rigorously enforces categorical separation between six distinct claims:
1. **Repository Presence:** A statutory snapshot file physically exists on disk and is parseable.
2. **Checksum Reproducibility:** A local SHA-256 digest reproduces deterministically against a stored baseline, proving snapshot integrity and detecting local tampering.
3. **Metadata Internal Consistency:** Manifest fields, section references, date formats, and URL syntax are internally valid.
4. **Authoritative Publication Match:** Statutory text has been compared byte-for-byte against an official Gazette of India or India Code reference artifact using a documented diff method.
5. **Legal Currentness & Commencement:** The enactment has been audited against official government notifications as in force as of a recorded date.
6. **Legal Applicability:** A statutory provision applies as a matter of law to a specific transaction, contract clause, party, jurisdiction, or dispute.

> [!CAUTION]
> **Fundamental Epistemic Invariant:**  
> A locally computed SHA-256 checksum proves file reproducibility. **It does NOT establish authenticity, completeness, currency, or legal applicability.**  
> Retrieval scores (BM25 or lexical overlap) are heuristic ranking metrics. **They do NOT represent legal probabilities or confidence that a provision applies.**

---

## 2. Statutory Corpus Reality: Curated Commercial Extracts

The repository contains six curated commercial statutory snapshots:

| Source ID | Canonical Title | Act Number | Enacted Sections | In Extract | Coverage % | Status |
|---|---|---|---|---|---|---|
| `IN_ACT_1872_09` | The Indian Contract Act, 1872 | Act 9 of 1872 | 238 active (266 orig) | 11 | 4.62% | `PARTIALLY_VERIFIED` |
| `IN_ACT_2000_21` | The Information Technology Act, 2000 | Act 21 of 2000 | 94 active | 6 | 6.38% | `PARTIALLY_VERIFIED` |
| `IN_ACT_2023_22` | The Digital Personal Data Protection Act, 2023 | Act 22 of 2023 | 44 active | 8 | 18.18% | `PARTIALLY_VERIFIED` |
| `IN_ACT_1963_47` | The Specific Relief Act, 1963 | Act 47 of 1963 | 44 active | 6 | 13.64% | `PARTIALLY_VERIFIED` |
| `IN_ACT_1996_26` | The Arbitration and Conciliation Act, 1996 | Act 26 of 1996 | 87 active | 6 | 6.90% | `PARTIALLY_VERIFIED` |
| `IN_ACT_2023_47` | The Bharatiya Sakshya Adhiniyam, 2023 | Act 47 of 2023 | 170 active | 3 | 1.76% | `PARTIALLY_VERIFIED` |
| **Total** | **Curated Central Statutory Corpus** | — | **677 active (705 total)** | **40** | **5.91%** | **Curated Extracts** |

### Known Statutory Omissions:
- **Contract Law (ICA 1872):** Indemnity (Sec 124-125), Guarantee (Sec 126-147), Bailment/Pledge (Sec 148-181), and Agency (Sec 182-238) are omitted.
- **Cyber Law (IT Act 2000):** Intermediary liability safe-harbor (Sec 79), CERT-In regulations, and SPDI Rules 2011 are omitted. Sec 66A is annotated as struck down.
- **Data Protection (DPDP Act 2023):** Children's data (Sec 9), Significant Data Fiduciary duties (Sec 10), Data Principal rights (Sec 11-14), and Data Protection Board of India provisions (Sec 18-34) are omitted. Substantive provisions (Sections 3 to 44) remain uncommenced pending Central Government notification.
- **Specific Relief (SRA 1963):** Recovery of possession (Sec 5-8), rectification, rescission, cancellation, and declaratory decrees (Sec 26-35) are omitted. Incorporates 2018 mandatory specific performance amendment.
- **Arbitration (ACA 1996):** Appointment of arbitrators (Sec 11), foreign award enforcement under New York/Geneva Conventions (Part II, Sec 44-60), conciliation, and institutional rules are omitted.
- **Evidence Law (BSA 2023):** Only electronic evidence sections (Sec 61, 63) are present; all oral and physical documentary rules (167 sections) are omitted.
- **State Legislation & Subordinate Rules:** **0.0% coverage.** Zero state amendments, municipal regulations, stamp acts, or sectoral regulations are indexed.

---

## 3. Ten-Tier Source Verification Status Model

Implemented in `src/legal_sources/provenance.py` via `VerificationStatus`:

1. `REPOSITORY_PRESENT`: Local snapshot file exists on disk and is readable.
2. `METADATA_VALIDATED`: Manifest structure and required fields pass syntax and schema checks.
3. `CHECKSUM_RECORDED`: Local SHA-256 digest is recorded and reproducible.
4. `OFFICIAL_SOURCE_IDENTIFIED`: A credible government URL / India Code handle has been identified.
5. `CONTENT_MATCH_VERIFIED`: Local text has been compared byte-for-byte with an official Gazette reference artifact.
6. `CURRENTNESS_VERIFIED`: Enactment, commencement notifications, and amendments verified as of recorded date.
7. `PARTIALLY_VERIFIED`: Local hash and metadata valid; curated extract; external gazette diff uncompleted.
8. `UNVERIFIED`: Source has not undergone structural verification or audit.
9. `VERIFICATION_FAILED`: File missing, hash mismatch, or comparison against reference failed.
10. `STALE_OR_REVIEW_REQUIRED`: Legislation superseded, amended, or requiring lawyer review.

---

## 4. Verification Workflow & Operation

The verification workflow is implemented in `src/legal_sources/verification.py` via `LegalSourceVerificationWorkflow`:

### How to Run:
```python
from src.legal_sources.verification import LegalSourceVerificationWorkflow

workflow = LegalSourceVerificationWorkflow()
report = workflow.run_verification(
    check_network=False, # Set True for safe endpoint reachability inspection
    output_json_path="data/legal_sources/reports/verification_report.json",
    output_md_path="data/legal_sources/reports/verification_report.md"
)
print("Corpus Status:", report["summary"])
```

Via HTTP REST API:
```http
GET /api/legal/verify HTTP/1.1
Host: localhost:5050
```

Via CLI / Script:
```bash
python -c "from src.legal_sources.verification import LegalSourceVerificationWorkflow; LegalSourceVerificationWorkflow().run_verification()"
```

### Safety Principles:
- **No Silent Updates:** The workflow never modifies source snapshot files or automatically promotes statuses.
- **Strict TLS:** Network checks never disable certificate verification (`verify=True`).
- **HTTP 200 Invariance:** Successful HTTP response does NOT upgrade a source to `CONTENT_MATCH_VERIFIED`.
- **Zero Mock Bypasses:** Authoritative comparisons require genuine, immutable reference artifacts.

---

## 5. Coverage Model & Disclosure Reporting

Implemented in `src/legal_sources/coverage.py` via `LegalCoverageModel`:

### Six Explicit Reporting Categories:
- **Category A (Available in Repository):** 6 central statutes (40 parsed sections).
- **Category B (Extract Sections):** Exact list of section numbers present in snapshot.
- **Category C (Authoritatively Verified):** Honest representation of external comparison state.
- **Category D (Currentness Checked):** Version and commencement notes tied to audit date.
- **Category E (Missing Coverage):** 665 central sections omitted, zero state law, zero rules.
- **Category F (Applicability Not Determined):** Clear disclaimer that semantic relevance does not equal legal applicability.

Via HTTP REST API:
```http
GET /api/legal/coverage HTTP/1.1
Host: localhost:5050
```

---

## 6. Safe Procedure for Adding New Statutory Sources

When adding a new legal source to CONTRACTRISK-XAI:
1. Place raw text extract in `data/legal_sources/snapshots/<SOURCE_ID>.txt`.
2. Compute local SHA-256 digest: `sha256sum <file>`.
3. Add entry to `data/legal_sources/corpus_manifest.json` with all 26 required fields.
4. Set initial `verification_status` to `PARTIALLY_VERIFIED` or `UNVERIFIED`.
5. Set `source_completeness_status` to `CURATED_EXTRACT` unless the entire Act is present.
6. Specify exact `covered_sections_or_provisions` list.
7. Document `applicability_limitations` and state exclusions explicitly.
8. If an official Gazette publication is obtained, place it in `data/legal_sources/reference_artifacts/<SOURCE_ID>_authoritative.txt` and run `compare_with_authoritative_artifact`.
9. Require human advocate sign-off before enabling for client reports.

---

## 7. Research Integrity & Separation of Evidence Types

In compliance with Phase J guidelines:
- **Repository Tests (Deterministic Code):** Verify that software invariants, checksums, and filters execute without errors.
- **External Source Verification (Official Publications):** Requires Gazette of India or India Code primary source artifacts.
- **Legal Expert Validation (Lawyer-in-the-Loop):** Qualified advocates determine clause enforceability and legal applicability.
- **Model Evaluation (Machine Learning):** Documented in Task 025/026. The validation threshold of `0.04` is an empirical classification boundary, NOT a calibrated legal probability.
