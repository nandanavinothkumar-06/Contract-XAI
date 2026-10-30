# Statutory Comparison Report: `IN_ACT_1963_47`
**Comparison ID:** `comp_IN_ACT_1963_47_20261020165423`  
**Audit Timestamp:** `2026-10-20T16:54:23.448058+00:00`  
**Defensible Status:** `PARTIALLY_VERIFIED`  
**Concordance Rate:** **83.33%**  

## 1. Executive Comparison Metrics

| Metric | Count | Defensible Meaning |
|---|---|---|
| Snapshot Sections Compared | 6 | Sections present in local curated extract |
| Exact Verbatim Matches | 0 | Exact character-for-character equivalence |
| Normalized Matches | 5 | Equivalent after typography & whitespace normalization |
| Textual Differences | 1 | Textual divergences identified with diffs |
| Missing in Reference | 0 | Sections in extract not found in gazette artifact |
| Reference Sections Omitted from Extract | 2 | Gazette sections omitted from curated snapshot |

## 2. Verification Status & Scope Invariants
- **Verified Scope:** `1, 14, 14A, 16, 20A`
- **Unverified Scope:** `10`
- **Currentness:** `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT`
- **Legal Applicability:** `REQUIRES_ADVOCATE_DETERMINATION`
- **Audit Notes:** Partial verification: 5 of 6 sections matched. 1 differing, 0 missing in reference.

## 3. Epistemic Disclosures
1. **Scope Boundary:** Content verification applies ONLY to the specific sections successfully matched. It does not verify the entire Act or omitted sections.
2. **Currentness Invariant:** Matching an official enactment publication verifies textual authenticity as enacted. It does not establish that subsequent amending Acts have been checked or that uncommenced rules have been notified.
3. **Applicability Invariant:** Textual equivalence does not establish legal applicability to any specific contract clause, dispute, or jurisdiction. Independent advocate evaluation is required.

## 4. Section-by-Section Alignment Results

| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |
|---|---|---|---|---|---|
| `1` | Short title, extent and commencement | ✅ `NORMALIZED_TEXT_MATCH` | 337 | 338 | Text matches after normalizing typography and whitespace |
| `10` | Specific performance in respect of contracts | ⚠️ `TEXT_DIFFERENCE` | 436 | 226 | Textual divergence detected between snapshot and official reference |
| `14` | Contracts not specifically enforceable | ✅ `NORMALIZED_TEXT_MATCH` | 583 | 585 | Text matches after normalizing typography and whitespace |
| `14A` | Power of court to engage experts | ✅ `NORMALIZED_TEXT_MATCH` | 492 | 494 | Text matches after normalizing typography and whitespace |
| `16` | Personal bars to relief | ✅ `NORMALIZED_TEXT_MATCH` | 727 | 745 | Text matches after normalizing typography and whitespace |
| `20A` | Special provisions for contract relating to infrastructure project | ✅ `NORMALIZED_TEXT_MATCH` | 355 | 357 | Text matches after normalizing typography and whitespace |

## 5. Textual Divergence Details (Unified Diffs)

### Section 10: Specific performance in respect of contracts
```diff
--- snapshot_Section_10
+++ reference_Section_10
@@ -1,2 +1,4 @@
-Section 10. Specific performance in respect of contracts.—The specific performance of a contract shall be enforced by the court subject to the provisions contained in sub-section (2) of section 11, section 14 and section 16.
-[Note: Substituted by the Specific Relief (Amendment) Act, 2018 (Act 18 of 2018), w.e.f. 1-10-2018. The grant of specific performance is now mandatory rather than discretionary, subject to statutory exceptions.]
+Section 10. Specific performance in respect of contracts.—
+ The specific performance of a contract shall be enforced by the court
+subject to the provisions contained in sub-section (2) of section 11,
+section 14 and section 16.
```

