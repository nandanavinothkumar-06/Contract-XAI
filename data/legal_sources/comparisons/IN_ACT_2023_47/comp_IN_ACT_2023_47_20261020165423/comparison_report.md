# Statutory Comparison Report: `IN_ACT_2023_47`
**Comparison ID:** `comp_IN_ACT_2023_47_20261020165423`  
**Audit Timestamp:** `2026-10-20T16:54:23.473948+00:00`  
**Defensible Status:** `PARTIALLY_VERIFIED`  
**Concordance Rate:** **66.67%**  

## 1. Executive Comparison Metrics

| Metric | Count | Defensible Meaning |
|---|---|---|
| Snapshot Sections Compared | 3 | Sections present in local curated extract |
| Exact Verbatim Matches | 0 | Exact character-for-character equivalence |
| Normalized Matches | 2 | Equivalent after typography & whitespace normalization |
| Textual Differences | 1 | Textual divergences identified with diffs |
| Missing in Reference | 0 | Sections in extract not found in gazette artifact |
| Reference Sections Omitted from Extract | 2 | Gazette sections omitted from curated snapshot |

## 2. Verification Status & Scope Invariants
- **Verified Scope:** `61, 63`
- **Unverified Scope:** `1`
- **Currentness:** `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT`
- **Legal Applicability:** `REQUIRES_ADVOCATE_DETERMINATION`
- **Audit Notes:** Partial verification: 2 of 3 sections matched. 1 differing, 0 missing in reference.

## 3. Epistemic Disclosures
1. **Scope Boundary:** Content verification applies ONLY to the specific sections successfully matched. It does not verify the entire Act or omitted sections.
2. **Currentness Invariant:** Matching an official enactment publication verifies textual authenticity as enacted. It does not establish that subsequent amending Acts have been checked or that uncommenced rules have been notified.
3. **Applicability Invariant:** Textual equivalence does not establish legal applicability to any specific contract clause, dispute, or jurisdiction. Independent advocate evaluation is required.

## 4. Section-by-Section Alignment Results

| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |
|---|---|---|---|---|---|
| `1` | Short title, application and commencement | ⚠️ `TEXT_DIFFERENCE` | 637 | 478 | Textual divergence detected between snapshot and official reference |
| `61` | Admissibility of electronic or digital record | ✅ `NORMALIZED_TEXT_MATCH` | 328 | 330 | Text matches after normalizing typography and whitespace |
| `63` | Admissibility of electronic records | ✅ `NORMALIZED_TEXT_MATCH` | 2359 | 2377 | Text matches after normalizing typography and whitespace |

## 5. Textual Divergence Details (Unified Diffs)

### Section 1: Short title, application and commencement
```diff
--- snapshot_Section_1
+++ reference_Section_1
@@ -1,6 +1,7 @@
-Section 1. Short title, application and commencement.—(1) This Act may be called the Bharatiya Sakshya Adhiniyam, 2023.
-(2) It applies to all judicial proceedings in or before any Court, including Courts-martial, but not to affidavits presented to any Court or officer, nor to proceedings before an arbitrator.
-(3) It shall come into force on such date as the Central Government may, by notification in the Official Gazette, appoint.
-[Note: Commenced on 1st July, 2024 vide Ministry of Home Affairs Notification S.O. 849(E) dated 23rd February, 2024. Supersedes the Indian Evidence Act, 1872.]
-
-PART III CHAPTER V OF DOCUMENTARY EVIDENCE
+Section 1. Short title, application and commencement.—
+ (1) This Act may be called the Bharatiya Sakshya Adhiniyam, 2023. (2) It
+applies to all judicial proceedings in or before any Court, including
+Courts-martial, but not to affidavits presented to any Court or officer,
+nor to proceedings before an arbitrator. (3) It shall come into force on
+such date as the Central Government may, by notification in the Official
+Gazette, appoint. PART III CHAPTER V OF DOCUMENTARY EVIDENCE
```

