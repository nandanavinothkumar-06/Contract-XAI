# Statutory Comparison Report: `IN_ACT_1996_26`
**Comparison ID:** `comp_IN_ACT_1996_26_20261017090923`  
**Audit Timestamp:** `2026-10-17T09:09:23.172924+00:00`  
**Defensible Status:** `PARTIALLY_VERIFIED`  
**Concordance Rate:** **50.0%**  

## 1. Executive Comparison Metrics

| Metric | Count | Defensible Meaning |
|---|---|---|
| Snapshot Sections Compared | 6 | Sections present in local curated extract |
| Exact Verbatim Matches | 0 | Exact character-for-character equivalence |
| Normalized Matches | 3 | Equivalent after typography & whitespace normalization |
| Textual Differences | 3 | Textual divergences identified with diffs |
| Missing in Reference | 0 | Sections in extract not found in gazette artifact |
| Reference Sections Omitted from Extract | 2 | Gazette sections omitted from curated snapshot |

## 2. Verification Status & Scope Invariants
- **Verified Scope:** `7, 8, 34`
- **Unverified Scope:** `1, 9, 16`
- **Currentness:** `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT`
- **Legal Applicability:** `REQUIRES_ADVOCATE_DETERMINATION`
- **Audit Notes:** Partial verification: 3 of 6 sections matched. 3 differing, 0 missing in reference.

## 3. Epistemic Disclosures
1. **Scope Boundary:** Content verification applies ONLY to the specific sections successfully matched. It does not verify the entire Act or omitted sections.
2. **Currentness Invariant:** Matching an official enactment publication verifies textual authenticity as enacted. It does not establish that subsequent amending Acts have been checked or that uncommenced rules have been notified.
3. **Applicability Invariant:** Textual equivalence does not establish legal applicability to any specific contract clause, dispute, or jurisdiction. Independent advocate evaluation is required.

## 4. Section-by-Section Alignment Results

| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |
|---|---|---|---|---|---|
| `1` | Short title, extent and commencement | ⚠️ `TEXT_DIFFERENCE` | 329 | 282 | Textual divergence detected between snapshot and official reference |
| `7` | Arbitration agreement | ✅ `NORMALIZED_TEXT_MATCH` | 1108 | 1110 | Text matches after normalizing typography and whitespace |
| `8` | Power to refer parties to arbitration where there is an arbitration agreement | ✅ `NORMALIZED_TEXT_MATCH` | 769 | 771 | Text matches after normalizing typography and whitespace |
| `9` | Interim measures, etc | ⚠️ `TEXT_DIFFERENCE` | 828 | 799 | Textual divergence detected between snapshot and official reference |
| `16` | Competence of arbitral tribunal to rule on its jurisdiction | ⚠️ `TEXT_DIFFERENCE` | 733 | 690 | Textual divergence detected between snapshot and official reference |
| `34` | Application for setting aside arbitral award | ✅ `NORMALIZED_TEXT_MATCH` | 713 | 715 | Text matches after normalizing typography and whitespace |

## 5. Textual Divergence Details (Unified Diffs)

### Section 1: Short title, extent and commencement
```diff
--- snapshot_Section_1
+++ reference_Section_1
@@ -1,6 +1,5 @@
-Section 1. Short title, extent and commencement.—(1) This Act may be called the Arbitration and Conciliation Act, 1996.
-(2) It extends to the whole of India.
-(3) It shall come into force on such date as the Central Government may, by notification in the Official Gazette, appoint.
-
-PART I ARBITRATION
-CHAPTER I GENERAL PROVISIONS
+Section 1. Short title, extent and commencement.—
+ (1) This Act may be called the Arbitration and Conciliation Act, 1996. (2)
+It extends to the whole of India. (3) It shall come into force on such date
+as the Central Government may, by notification in the Official Gazette,
+appoint.
```

### Section 9: Interim measures, etc
```diff
--- snapshot_Section_9
+++ reference_Section_9
@@ -1,9 +1,14 @@
-Section 9. Interim measures, etc. by Court.—(1) A party may, before or during arbitral proceedings or at any time after the making of the arbitral award but before it is enforced in accordance with section 36, apply to a court—
-(ii) for an interim measure of protection in respect of any of the following matters, namely:—
-(a) the preservation, interim custody or sale of any goods which are the subject-matter of the arbitration agreement;
-(b) securing the amount in dispute in the arbitration;
-(c) the detention, preservation or inspection of any property or thing which is the subject-matter of the dispute in arbitration;
-(d) interim injunction or the appointment of a receiver;
-(e) such other interim measure of protection as may appear to the court to be just and convenient.
+Section 9. Interim measures, etc. by Court.—
+ (1) A party may, before or during arbitral proceedings or at any time after

-CHAPTER IV JURISDICTION OF ARBITRAL TRIBUNALS
+--- PAGE 2 ---
+the making of the arbitral award but before it is enforced in accordance
+with section 36, apply to a court— (ii) for an interim measure of
+protection in respect of any of the following matters, namely:— (a) the
+preservation, interim custody or sale of any goods which are the
+subject-matter of the arbitration agreement; (b) securing the amount in
+dispute in the arbitration; (c) the detention, preservation or inspection
+of any property or thing which is the subject-matter of the dispute in
+arbitration; (d) interim injunction or the appointment of a receiver; (e)
+such other interim measure of protection as may appear to the court to be
+just and convenient.
```

### Section 16: Competence of arbitral tribunal to rule on its jurisdiction
```diff
--- snapshot_Section_16
+++ reference_Section_16
@@ -1,6 +1,10 @@
-Section 16. Competence of arbitral tribunal to rule on its jurisdiction.—(1) The arbitral tribunal may rule on its own jurisdiction, including ruling on any objections with respect to the existence or validity of the arbitration agreement, and for that purpose,—
-(a) an arbitration clause which forms part of a contract shall be treated as an agreement independent of the other terms of the contract; and
-(b) a decision by the arbitral tribunal that the contract is null and void shall not entail ipso jure the invalidity of the arbitration clause.
-(2) A plea that the arbitral tribunal does not have jurisdiction shall be raised not later than the submission of the statement of defence.
-
-CHAPTER VII RECOURSE AGAINST ARBITRAL AWARD
+Section 16. Competence of arbitral tribunal to rule on its jurisdiction.—
+ (1) The arbitral tribunal may rule on its own jurisdiction, including
+ruling on any objections with respect to the existence or validity of the
+arbitration agreement, and for that purpose,— (a) an arbitration clause
+which forms part of a contract shall be treated as an agreement independent
+of the other terms of the contract; and (b) a decision by the arbitral
+tribunal that the contract is null and void shall not entail ipso jure the
+invalidity of the arbitration clause. (2) A plea that the arbitral tribunal
+does not have jurisdiction shall be raised not later than the submission of
+the statement of defence.
```

