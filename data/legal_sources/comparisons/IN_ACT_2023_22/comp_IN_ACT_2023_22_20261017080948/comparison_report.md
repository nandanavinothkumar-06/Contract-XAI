# Statutory Comparison Report: `IN_ACT_2023_22`
**Comparison ID:** `comp_IN_ACT_2023_22_20261017080948`  
**Audit Timestamp:** `2026-10-17T08:09:48.061412+00:00`  
**Defensible Status:** `PARTIALLY_VERIFIED`  
**Concordance Rate:** **25.0%**  

## 1. Executive Comparison Metrics

| Metric | Count | Defensible Meaning |
|---|---|---|
| Snapshot Sections Compared | 8 | Sections present in local curated extract |
| Exact Verbatim Matches | 0 | Exact character-for-character equivalence |
| Normalized Matches | 2 | Equivalent after typography & whitespace normalization |
| Textual Differences | 6 | Textual divergences identified with diffs |
| Missing in Reference | 0 | Sections in extract not found in gazette artifact |
| Reference Sections Omitted from Extract | 2 | Gazette sections omitted from curated snapshot |

## 2. Verification Status & Scope Invariants
- **Verified Scope:** `4, 36`
- **Unverified Scope:** `1, 2, 5, 6, 8, 44`
- **Currentness:** `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT`
- **Legal Applicability:** `REQUIRES_ADVOCATE_DETERMINATION`
- **Audit Notes:** Partial verification: 2 of 8 sections matched. 6 differing, 0 missing in reference.

## 3. Epistemic Disclosures
1. **Scope Boundary:** Content verification applies ONLY to the specific sections successfully matched. It does not verify the entire Act or omitted sections.
2. **Currentness Invariant:** Matching an official enactment publication verifies textual authenticity as enacted. It does not establish that subsequent amending Acts have been checked or that uncommenced rules have been notified.
3. **Applicability Invariant:** Textual equivalence does not establish legal applicability to any specific contract clause, dispute, or jurisdiction. Independent advocate evaluation is required.

## 4. Section-by-Section Alignment Results

| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |
|---|---|---|---|---|---|
| `1` | Short title and commencement | ⚠️ `TEXT_DIFFERENCE` | 461 | 314 | Textual divergence detected between snapshot and official reference |
| `2` | Definitions | ⚠️ `TEXT_DIFFERENCE` | 1154 | 658 | Textual divergence detected between snapshot and official reference |
| `4` | Grounds for processing personal data | ✅ `NORMALIZED_TEXT_MATCH` | 394 | 396 | Text matches after normalizing typography and whitespace |
| `5` | Notice | ⚠️ `TEXT_DIFFERENCE` | 467 | 297 | Textual divergence detected between snapshot and official reference |
| `6` | Consent | ⚠️ `TEXT_DIFFERENCE` | 509 | 260 | Textual divergence detected between snapshot and official reference |
| `8` | General obligations of Data Fiduciary | ⚠️ `TEXT_DIFFERENCE` | 933 | 576 | Textual divergence detected between snapshot and official reference |
| `36` | Power of Central Government to call for information | ✅ `NORMALIZED_TEXT_MATCH` | 226 | 228 | Text matches after normalizing typography and whitespace |
| `44` | Amendments to certain Acts | ⚠️ `TEXT_DIFFERENCE` | 321 | 214 | Textual divergence detected between snapshot and official reference |

## 5. Textual Divergence Details (Unified Diffs)

### Section 1: Short title and commencement
```diff
--- snapshot_Section_1
+++ reference_Section_1
@@ -1,2 +1,5 @@
-Section 1. Short title and commencement.—(1) This Act may be called the Digital Personal Data Protection Act, 2023.
-(2) It shall come into force on such date as the Central Government may, by notification in the Official Gazette, appoint and different dates may be appointed for different provisions of this Act and any reference in any such provision to the commencement of this Act shall be construed as a reference to the coming into force of that provision.
+Section 1. Short title and commencement.—
+ (1) This Act may be called the Digital Personal Data Protection Act, 2023.
+(2) It shall come into force on such date as the Central Government may, by
+notification in the Official Gazette, appoint and different dates may be
+appointed for different provisions of this Act.
```

### Section 2: Definitions
```diff
--- snapshot_Section_2
+++ reference_Section_2
@@ -1,8 +1,10 @@
-Section 2. Definitions.—In this Act, unless the context otherwise requires,—
-(i) "Data Fiduciary" means any person who alone or in conjunction with other persons determines the purpose and means of processing of personal data;
-(j) "Data Principal" means the individual to whom the personal data relates and where such individual is— (i) a child, includes the parents or lawful guardian of such a child; (ii) a person with disability, includes her lawful guardian, acting on her behalf;
-(k) "Data Processor" means any person who processes personal data on behalf of a Data Fiduciary;
-(t) "personal data" means any data about an individual who is identifiable by or in relation to such data;
-(x) "processing" in relation to personal data, means a wholly or partly automated operation or set of operations performed on digital personal data, and includes operations such as collection, recording, organisation, structuring, storage, adaptation, retrieval, use, alignment or combination, indexing, sharing, disclosure by transmission, dissemination or otherwise making available, restriction, erasure or destruction.
-
-CHAPTER II OBLIGATIONS OF DATA FIDUCIARY
+Section 2. Definitions.—
+ In this Act, unless the context otherwise requires,— (i) "Data Fiduciary"
+means any person who alone or in conjunction with other persons determines
+the purpose and means of processing of personal data; (j) "Data Principal"
+means the individual to whom the personal data relates; (k) "Data
+Processor" means any person who processes personal data on behalf of a Data
+Fiduciary; (t) "personal data" means any data about an individual who is
+identifiable by or in relation to such data; (x) "processing" in relation
+to personal data, means a wholly or partly automated operation or set of
+operations performed on digital personal data.
```

### Section 5: Notice
```diff
--- snapshot_Section_5
+++ reference_Section_5
@@ -1 +1,5 @@
-Section 5. Notice.—(1) On or before requesting for consent, the Data Fiduciary shall give to the Data Principal an itemised notice in such manner and containing such aspects as may be prescribed, description of personal data sought to be collected and the purpose for which it will be processed, manner in which she may exercise her rights under sub-section (4) of section 6 and section 13 and the manner in which the Data Principal may make a complaint to the Board.
+Section 5. Notice.—
+ (1) On or before requesting for consent, the Data Fiduciary shall give to
+the Data Principal an itemised notice in such manner and containing such
+aspects as may be prescribed, description of personal data sought to be
+collected and the purpose for which it will be processed.
```

### Section 6: Consent
```diff
--- snapshot_Section_6
+++ reference_Section_6
@@ -1,2 +1,5 @@
-Section 6. Consent.—(1) The consent given by the Data Principal shall be free, specific, informed, unconditional and unambiguous with a clear affirmative action, and shall signify an agreement to the processing of her personal data for the specified purpose and be limited to such personal data as is necessary for such specified purpose.
-(4) The Data Principal shall have the right to withdraw her consent at any time, with the ease of doing so being comparable to the ease with which such consent was given.
+Section 6. Consent.—
+ (1) The consent given by the Data Principal shall be free, specific,
+informed, unconditional and unambiguous with a clear affirmative action,
+and shall signify an agreement to the processing of her personal data for
+the specified purpose.
```

### Section 8: General obligations of Data Fiduciary
```diff
--- snapshot_Section_8
+++ reference_Section_8
@@ -1,5 +1,11 @@
-Section 8. General obligations of Data Fiduciary.—(1) A Data Fiduciary shall, irrespective of any agreement to the contrary or failure of a Data Principal to carry out the duties provided under this Act, be responsible for complying with the provisions of this Act and the rules made thereunder in respect of any processing undertaken by it or on its behalf by a Data Processor.
-(2) A Data Fiduciary may engage, appoint, use or otherwise involve a Data Processor to process personal data on its behalf for any activity related to offering of goods or services to Data Principals or for purposes authorized under this Act, only under a valid contract.
-(5) A Data Fiduciary shall protect personal data in its possession or under its control, including in respect of any processing undertaken by it or on its behalf by a Data Processor, by taking reasonable security safeguards to prevent personal data breach.
+Section 8. General obligations of Data Fiduciary.—
+ (1) A Data Fiduciary shall, irrespective of any agreement to the contrary
+or failure of a Data Principal to carry out the duties provided under this
+Act, be responsible for complying with the provisions of this Act. (2) A
+Data Fiduciary may engage, appoint, use or otherwise involve a Data
+Processor to process personal data on its behalf only under a valid
+contract. (5) A Data Fiduciary shall protect personal data in its

-CHAPTER IX MISCELLANEOUS
+--- PAGE 2 ---
+possession by taking reasonable security safeguards to prevent personal
+data breach.
```

### Section 44: Amendments to certain Acts
```diff
--- snapshot_Section_44
+++ reference_Section_44
@@ -1,3 +1,4 @@
-Section 44. Amendments to certain Acts.—(1) In section 14 of the Telecom Regulatory Authority of India Act, 1997, in clause (c)...
-(2) The Information Technology Act, 2000 shall be amended in the manner specified in the Schedule.
-Schedule Amendment: "Section 43A of the Information Technology Act, 2000 shall be omitted."
+Section 44. Amendments to certain Acts.—
+ (1) In section 14 of the Telecom Regulatory Authority of India Act, 1997.
+(2) The Information Technology Act, 2000 shall be amended in the manner
+specified in the Schedule.
```

