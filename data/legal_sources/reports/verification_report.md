# Indian Legal Source Verification Audit Report
**Audit Timestamp:** `2026-10-20T17:02:43.275483+00:00`  
**Manifest Path:** `data/legal_sources/corpus_manifest.json`  
**Manifest Valid:** `YES`  

## 1. Executive Summary

| Metric | Count | Defensible Meaning |
|---|---|---|
| Total Declared Sources | 6 | Curated statutory instruments declared in manifest |
| Local Files Present | 6 | Snapshot files existing on repository disk |
| SHA-256 Reproducible | 6 | Local hashes matching recorded baseline digests |
| Content-Match Verified | 0 | Exact byte-for-byte verified against official gazette |
| Partially Verified | 6 | Hash/metadata valid; official publication comparison uncompleted |
| Fully Authoritative Corpus | NO (Curated Extracts Only) | Honest corpus certification |

## 2. Source-by-Source Verification Status

| Source ID | Canonical Title | Present | Hash Valid | Sections | Tier | Completeness | Limitations |
|---|---|---|---|---|---|---|---|
| `IN_ACT_1872_09` | The Indian Contract Act, 1872 | ✅ | ✅ | 11 sections | `PARTIALLY_VERIFIED` | `CURATED_EXTRACT` | Extract contains selected general principles of contract formation, void agreements, frustration, and damages. Does not include indemnity, guarantee, bailment, agency, or partnership provisions. Legal applicability to specific contract disputes requires independent advocate review. |
| `IN_ACT_2000_21` | The Information Technology Act, 2000 | ✅ | ✅ | 6 sections | `PARTIALLY_VERIFIED` | `CURATED_EXTRACT` | Curated extract. Section 66A struck down as unconstitutional (Shreya Singhal v. Union of India). Section 43A pending repeal upon full commencement of DPDP Act 2023 Section 44. Does not cover intermediary guidelines or CERT-In regulations. |
| `IN_ACT_2023_22` | The Digital Personal Data Protection Act, 2023 | ✅ | ✅ | 8 sections | `PARTIALLY_VERIFIED` | `CURATED_EXTRACT` | Only Section 1 commenced on 11 Aug 2023. Under Section 1(2), substantive provisions (Sections 3 to 44) require appointment of dates by Central Government notification. Substantive rules and Data Protection Board of India remain pending full notification as of verification date. |
| `IN_ACT_1963_47` | The Specific Relief Act, 1963 | ✅ | ✅ | 6 sections | `PARTIALLY_VERIFIED` | `CURATED_EXTRACT` | Extract focuses on post-2018 mandatory specific performance and infrastructure injunction bars. Does not cover rectification, rescission, cancellation, or declaratory decrees (Sections 26-35). |
| `IN_ACT_1996_26` | The Arbitration and Conciliation Act, 1996 | ✅ | ✅ | 6 sections | `PARTIALLY_VERIFIED` | `CURATED_EXTRACT` | Extract covers domestic arbitration agreements, interim measures, competence, and award set-aside grounds. Does not cover Part II (Foreign Awards / New York Convention), conciliation, mediation, or institution rules. |
| `IN_ACT_2023_47` | The Bharatiya Sakshya Adhiniyam, 2023 | ✅ | ✅ | 3 sections | `PARTIALLY_VERIFIED` | `CURATED_EXTRACT` | Extract covers electronic records admissibility (Sec 61) and electronic record certificates (Sec 63). Does not cover other evidence provisions (oral, documentary, burden of proof, witnesses). Supersedes Indian Evidence Act 1872 for proceedings post-July 1, 2024. |

## 3. Disclosures and Verification Boundaries

1. **Cryptographic vs. Legal Authenticity:** A locally computed SHA-256 hash proves local file integrity and detects post-ingestion tampering. It does NOT establish authenticity against the official publication, currency, or legal applicability.
2. **Coverage Scope:** The current corpus contains curated commercial extracts from six Indian central statutes. It does NOT constitute complete statutory Acts, subordinate rules, state amendments, or exhaustive Indian law.
3. **Network Invariance:** HTTP 200 responses confirm endpoint availability only. They do not constitute statutory text verification.

## 4. Warnings and Audit Findings

- No warnings recorded.
