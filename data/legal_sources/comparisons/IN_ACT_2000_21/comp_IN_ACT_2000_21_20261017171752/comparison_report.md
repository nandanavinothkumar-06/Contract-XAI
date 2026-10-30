# Statutory Comparison Report: `IN_ACT_2000_21`
**Comparison ID:** `comp_IN_ACT_2000_21_20261017171752`  
**Audit Timestamp:** `2026-10-17T17:17:52.817538+00:00`  
**Defensible Status:** `PARTIALLY_VERIFIED`  
**Concordance Rate:** **66.67%**  

## 1. Executive Comparison Metrics

| Metric | Count | Defensible Meaning |
|---|---|---|
| Snapshot Sections Compared | 6 | Sections present in local curated extract |
| Exact Verbatim Matches | 0 | Exact character-for-character equivalence |
| Normalized Matches | 4 | Equivalent after typography & whitespace normalization |
| Textual Differences | 2 | Textual divergences identified with diffs |
| Missing in Reference | 0 | Sections in extract not found in gazette artifact |
| Reference Sections Omitted from Extract | 2 | Gazette sections omitted from curated snapshot |

## 2. Verification Status & Scope Invariants
- **Verified Scope:** `1, 4, 10A, 72A`
- **Unverified Scope:** `43A, 66A`
- **Currentness:** `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT`
- **Legal Applicability:** `REQUIRES_ADVOCATE_DETERMINATION`
- **Audit Notes:** Partial verification: 4 of 6 sections matched. 2 differing, 0 missing in reference.

## 3. Epistemic Disclosures
1. **Scope Boundary:** Content verification applies ONLY to the specific sections successfully matched. It does not verify the entire Act or omitted sections.
2. **Currentness Invariant:** Matching an official enactment publication verifies textual authenticity as enacted. It does not establish that subsequent amending Acts have been checked or that uncommenced rules have been notified.
3. **Applicability Invariant:** Textual equivalence does not establish legal applicability to any specific contract clause, dispute, or jurisdiction. Independent advocate evaluation is required.

## 4. Section-by-Section Alignment Results

| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |
|---|---|---|---|---|---|
| `1` | Short title, extent, commencement and application | ✅ `NORMALIZED_TEXT_MATCH` | 543 | 544 | Text matches after normalizing typography and whitespace |
| `4` | Legal recognition of electronic records | ✅ `NORMALIZED_TEXT_MATCH` | 434 | 436 | Text matches after normalizing typography and whitespace |
| `10A` | Validity of contracts formed through electronic means | ✅ `NORMALIZED_TEXT_MATCH` | 484 | 485 | Text matches after normalizing typography and whitespace |
| `43A` | Compensation for failure to protect data | ⚠️ `TEXT_DIFFERENCE` | 1601 | 1484 | Textual divergence detected between snapshot and official reference |
| `66A` | Punishment for sending offensive messages through communication service, etc | ⚠️ `TEXT_DIFFERENCE` | 1029 | 837 | Textual divergence detected between snapshot and official reference |
| `72A` | Punishment for disclosure of information in breach of lawful contract | ✅ `NORMALIZED_TEXT_MATCH` | 727 | 729 | Text matches after normalizing typography and whitespace |

## 5. Textual Divergence Details (Unified Diffs)

### Section 43A: Compensation for failure to protect data
```diff
--- snapshot_Section_43A
+++ reference_Section_43A
@@ -1,6 +1,23 @@
-Section 43A. Compensation for failure to protect data.—Where a body corporate, possessing, dealing or handling any sensitive personal data or information in a computer resource which it owns, controls or operates, is negligent in implementing and maintaining reasonable security practices and procedures and thereby causes wrongful loss or wrongful gain to any person, such body corporate shall be liable to pay damages by way of compensation to the person so affected.
-Explanation.—For the purposes of this section,—
-(i) "body corporate" means any company and includes a firm, sole proprietorship or other association of individuals engaged in commercial or professional activities;
-(ii) "reasonable security practices and procedures" means security practices and procedures designed to protect such information from unauthorised access, damage, use, modification, disclosure or impairment, as may be specified in an agreement between the parties or as may be specified in any law for the time being in force and in the absence of such agreement or any law, such reasonable security practices and procedures, as may be prescribed by the Central Government in consultation with such professional bodies or associations as it may consider necessary;
-(iii) "sensitive personal data or information" means such personal information as may be prescribed by the Central Government in consultation with such professional bodies or associations as it may consider necessary.
-[Note: Section 43A is subject to omission upon the full commencement of Section 44 of the Digital Personal Data Protection Act, 2023.]
+Section 43A. Compensation for failure to protect data.—
+ Where a body corporate, possessing, dealing or handling any sensitive
+personal data or information in a computer resource which it owns, controls
+or operates, is negligent in implementing and maintaining reasonable
+security practices and procedures and thereby causes wrongful loss or
+
+--- PAGE 2 ---
+wrongful gain to any person, such body corporate shall be liable to pay
+damages by way of compensation to the person so affected. Explanation.—For
+the purposes of this section,— (i) "body corporate" means any company and
+includes a firm, sole proprietorship or other association of individuals
+engaged in commercial or professional activities; (ii) "reasonable security
+practices and procedures" means security practices and procedures designed
+to protect such information from unauthorised access, damage, use,
+modification, disclosure or impairment, as may be specified in an agreement
+between the parties or as may be specified in any law for the time being in
+force and in the absence of such agreement or any law, such reasonable
+security practices and procedures, as may be prescribed by the Central
+Government in consultation with such professional bodies or associations as
+it may consider necessary; (iii) "sensitive personal data or information"
+means such personal information as may be prescribed by the Central
```

### Section 66A: Punishment for sending offensive messages through communication service, etc
```diff
--- snapshot_Section_66A
+++ reference_Section_66A
@@ -1,8 +1,12 @@
-Section 66A. Punishment for sending offensive messages through communication service, etc.—Any person who sends, by means of a computer resource or a communication device,—
-(a) any information that is grossly offensive or has menacing character; or
-(b) any information which he knows to be false, but for the purpose of causing annoyance, inconvenience, danger, obstruction, insult, injury, criminal intimidation, enmity, hatred or ill will, persistently by making use of such computer resource or a communication device; or
-(c) any electronic mail or electronic mail message for the purpose of causing annoyance or inconvenience or to deceive or to mislead the addressee or recipient about the origin of such messages,
-shall be punishable with imprisonment for a term which may extend to three years and with fine.
-[Note: Section 66A was struck down in its entirety as unconstitutional by the Supreme Court of India in Shreya Singhal v. Union of India (2015) 5 SCC 1, and is legally void and unenforceable.]
-
+Section 66A. Punishment for sending offensive messages through communication service, etc.—
+ Any person who sends, by means of a computer resource or a communication
+device,— (a) any information that is grossly offensive or has menacing
+character; or (b) any information which he knows to be false, but for the
+purpose of causing annoyance, inconvenience, danger, obstruction, insult,
+injury, criminal intimidation, enmity, hatred or ill will, persistently by
+making use of such computer resource or a communication device; or (c) any
+electronic mail or electronic mail message for the purpose of causing
+annoyance or inconvenience or to deceive or to mislead the addressee or
+recipient about the origin of such messages, shall be punishable with
+imprisonment for a term which may extend to three years and with fine.
 CHAPTER XI OFFENCES
```

