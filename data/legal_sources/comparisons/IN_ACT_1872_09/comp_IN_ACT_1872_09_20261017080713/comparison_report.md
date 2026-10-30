# Statutory Comparison Report: `IN_ACT_1872_09`
**Comparison ID:** `comp_IN_ACT_1872_09_20261017080713`  
**Audit Timestamp:** `2026-10-17T08:07:13.177137+00:00`  
**Defensible Status:** `VERIFICATION_FAILED`  
**Concordance Rate:** **0.0%**  

## 1. Executive Comparison Metrics

| Metric | Count | Defensible Meaning |
|---|---|---|
| Snapshot Sections Compared | 11 | Sections present in local curated extract |
| Exact Verbatim Matches | 0 | Exact character-for-character equivalence |
| Normalized Matches | 0 | Equivalent after typography & whitespace normalization |
| Textual Differences | 10 | Textual divergences identified with diffs |
| Missing in Reference | 1 | Sections in extract not found in gazette artifact |
| Reference Sections Omitted from Extract | 0 | Gazette sections omitted from curated snapshot |

## 2. Verification Status & Scope Invariants
- **Verified Scope:** `NONE`
- **Unverified Scope:** `1, 2, 10, 11, 23, 27, 28, 56, 73, 74, 75`
- **Currentness:** `CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT`
- **Legal Applicability:** `REQUIRES_ADVOCATE_DETERMINATION`
- **Audit Notes:** Zero sections matched between snapshot extract and reference artifact.

## 3. Epistemic Disclosures
1. **Scope Boundary:** Content verification applies ONLY to the specific sections successfully matched. It does not verify the entire Act or omitted sections.
2. **Currentness Invariant:** Matching an official enactment publication verifies textual authenticity as enacted. It does not establish that subsequent amending Acts have been checked or that uncommenced rules have been notified.
3. **Applicability Invariant:** Textual equivalence does not establish legal applicability to any specific contract clause, dispute, or jurisdiction. Independent advocate evaluation is required.

## 4. Section-by-Section Alignment Results

| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |
|---|---|---|---|---|---|
| `1` | Short title | ⚠️ `TEXT_DIFFERENCE` | 443 | 201 | Textual divergence detected between snapshot and official reference |
| `2` | Interpretation | ⚠️ `TEXT_DIFFERENCE` | 1324 | 660 | Textual divergence detected between snapshot and official reference |
| `10` | What agreements are contracts | ⚠️ `TEXT_DIFFERENCE` | 488 | 247 | Textual divergence detected between snapshot and official reference |
| `11` | Who are competent to contract | ⚠️ `TEXT_DIFFERENCE` | 256 | 258 | Textual divergence detected between snapshot and official reference |
| `23` | What considerations and objects are lawful, and what not | ⚠️ `TEXT_DIFFERENCE` | 560 | 562 | Textual divergence detected between snapshot and official reference |
| `27` | Agreement in restraint of trade, void | ⚠️ `TEXT_DIFFERENCE` | 641 | 480 | Textual divergence detected between snapshot and official reference |
| `28` | Agreements in restraint of legal proceedings, void | ⚠️ `TEXT_DIFFERENCE` | 1343 | 374 | Textual divergence detected between snapshot and official reference |
| `56` | Agreement to do impossible act | ⚠️ `TEXT_DIFFERENCE` | 781 | 377 | Textual divergence detected between snapshot and official reference |
| `73` | Compensation for loss or damage caused by breach of contract | ⚠️ `TEXT_DIFFERENCE` | 1156 | 342 | Textual divergence detected between snapshot and official reference |
| `74` | Compensation for breach of contract where penalty stipulated for | ⚠️ `TEXT_DIFFERENCE` | 1275 | 382 | Textual divergence detected between snapshot and official reference |
| `75` | Party rightfully rescinding contract, entitled to compensation | ⚠️ `SECTION_MISSING_IN_REFERENCE` | 229 | 0 | Section present in snapshot extract could not be located in reference text |

## 5. Textual Divergence Details (Unified Diffs)

### Section 1: Short title
```diff
--- snapshot_Section_1
+++ reference_Section_1
@@ -1,3 +1,4 @@
-Section 1. Short title.—This Act may be called the Indian Contract Act, 1872.
-Extent, Commencement.—It extends to the whole of India; and it shall come into force on the first day of September, 1872.
-Saving.—Nothing herein contained shall affect the provisions of any Statute, Act or Regulation not hereby expressly repealed, nor any usage or custom of trade, nor any incident of any contract, not inconsistent with the provisions of this Act.
+Section 1. Short title.—
+ This Act may be called the Indian Contract Act, 1872. Extent,
+Commencement.—It extends to the whole of India; and it shall come into
+force on the first day of September, 1872.
```

### Section 2: Interpretation
```diff
--- snapshot_Section_2
+++ reference_Section_2
@@ -1,11 +1,10 @@
-Section 2. Interpretation-clause.—In this Act the following words and expressions are used in the following senses, unless a contrary intention appears from the context:—
-(a) When one person signifies to another his willingness to do or to abstain from doing anything, with a view to obtaining the assent of that other to such act or abstinence, he is said to make a proposal;
-(b) When the person to whom the proposal is made signifies his assent thereto, the proposal is said to be accepted. A proposal, when accepted, becomes a promise;
-(c) The person making the proposal is called the "promisor", and the person accepting the proposal is called the "promisee";
-(d) When, at the desire of the promisor, the promisee or any other person has done or abstained from doing, or does or abstains from doing, or promises to do or to abstain from doing, something, such act or abstinence or promise is called a consideration for the promise;
-(e) Every promise and every set of promises, forming the consideration for each other, is an agreement;
-(h) An agreement enforceable by law is a contract;
-(i) An agreement which is not enforceable by law is said to be void;
-(j) A contract which ceases to be enforceable by law becomes void when it ceases to be enforceable.
-
-CHAPTER II OF CONTRACTS, VOIDABLE CONTRACTS AND VOID AGREEMENTS
+Section 2. Interpretation-clause.—
+ In this Act the following words and expressions are used in the following
+senses, unless a contrary intention appears from the context:— (a) When one
+person signifies to another his willingness to do or to abstain from doing
+anything, with a view to obtaining the assent of that other to such act or
+abstinence, he is said to make a proposal; (b) When the person to whom the
+proposal is made signifies his assent thereto, the proposal is said to be
+accepted. A proposal, when accepted, becomes a promise; (h) An agreement
+enforceable by law is a contract; (i) An agreement which is not enforceable
+by law is said to be void.
```

### Section 10: What agreements are contracts
```diff
--- snapshot_Section_10
+++ reference_Section_10
@@ -1,2 +1,4 @@
-Section 10. What agreements are contracts.—All agreements are contracts if they are made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object, and are not hereby expressly declared to be void.
-Nothing herein contained shall affect any law in force in India, and not hereby expressly repealed, by which any contract is required to be made in writing or in the presence of witnesses, or any law relating to the registration of documents.
+Section 10. What agreements are contracts.—
+ All agreements are contracts if they are made by the free consent of
+parties competent to contract, for a lawful consideration and with a lawful
+object, and are not hereby expressly declared to be void.
```

### Section 11: Who are competent to contract
```diff
--- snapshot_Section_11
+++ reference_Section_11
@@ -1 +1,4 @@
-Section 11. Who are competent to contract.—Every person is competent to contract who is of the age of majority according to the law to which he is subject, and who is of sound mind and is not disqualified from contracting by any law to which he is subject.
+Section 11. Who are competent to contract.—
+ Every person is competent to contract who is of the age of majority
+according to the law to which he is subject, and who is of sound mind and
+is not disqualified from contracting by any law to which he is subject.
```

### Section 23: What considerations and objects are lawful, and what not
```diff
--- snapshot_Section_23
+++ reference_Section_23
@@ -1,7 +1,8 @@
-Section 23. What considerations and objects are lawful, and what not.—The consideration or object of an agreement is lawful, unless—
-it is forbidden by law; or
-is of such a nature that, if permitted, it would defeat the provisions of any law; or
-is fraudulent; or
-involves or implies, injury to the person or property of another; or
-the Court regards it as immoral, or opposed to public policy.
-In each of these cases, the consideration or object of an agreement is said to be unlawful. Every agreement of which the object or consideration is unlawful is void.
+Section 23. What considerations and objects are lawful, and what not.—
+ The consideration or object of an agreement is lawful, unless— it is
+forbidden by law; or is of such a nature that, if permitted, it would
+defeat the provisions of any law; or is fraudulent; or involves or implies,
+injury to the person or property of another; or the Court regards it as
+immoral, or opposed to public policy. In each of these cases, the
+consideration or object of an agreement is said to be unlawful. Every
+agreement of which the object or consideration is unlawful is void.
```

### Section 27: Agreement in restraint of trade, void
```diff
--- snapshot_Section_27
+++ reference_Section_27
@@ -1,2 +1,7 @@
-Section 27. Agreement in restraint of trade, void.—Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, is to that extent void.
-Exception 1.—Saving of agreement not to carry on business of which good-will is sold.—One who sells the good-will of a business may agree with the buyer to refrain from carrying on a similar business, within specified local limits, so long as the buyer, or any person deriving title to the good-will from him, carries on a like business therein, provided that such limits appear to the Court reasonable, regard being had to the nature of the business.
+Section 27. Agreement in restraint of trade, void.—
+ Every agreement by which any one is restrained from exercising a lawful
+profession, trade or business of any kind, is to that extent void.
+Exception 1.—Saving of agreement not to carry on business of which
+good-will is sold.—One who sells the good-will of a business may agree with
+the buyer to refrain from carrying on a similar business, within specified
+local limits, so long as the buyer carries on a like business therein.
```

### Section 28: Agreements in restraint of legal proceedings, void
```diff
--- snapshot_Section_28
+++ reference_Section_28
@@ -1,6 +1,8 @@
-Section 28. Agreements in restraint of legal proceedings, void.—Every agreement,—
-(a) by which any party thereto is restricted absolutely from enforcing his rights under or in respect of any contract, by the usual legal proceedings in the ordinary tribunals, or which limits the time within which he may thus enforce his rights; or
-(b) which extinguishes the rights of any party thereto, or discharges any party thereto, from any liability, under or in respect of any contract on the expiry of a specified period so as to restrict any party from enforcing his rights,
-is void to that extent.
-Exception 1.—Saving of contract to refer to arbitration dispute that may arise.—This section shall not render illegal a contract, by which two or more persons agree that any dispute which may arise between them in respect of any subject or class of subjects shall be referred to arbitration, and that only the amount awarded in such arbitration shall be recoverable in respect of the dispute so referred.
-Exception 2.—Saving of contract to refer questions that have already arisen.—Nor shall this section render illegal any contract in writing, by which two or more persons agree to refer to arbitration any question between them which has already arisen, or affect any provision of any law in force for the time being as to references to arbitration.
+Section 28. Agreements in restraint of legal proceedings, void.—
+ Every agreement by which any party thereto is restricted absolutely from
+
+--- PAGE 2 ---
+enforcing his rights under or in respect of any contract, by the usual
+legal proceedings in the ordinary tribunals, is void to that extent.
+Exception 1.—Saving of contract to refer to arbitration dispute that may
+arise.
```

### Section 56: Agreement to do impossible act
```diff
--- snapshot_Section_56
+++ reference_Section_56
@@ -1,3 +1,6 @@
-Section 56. Agreement to do impossible act.—An agreement to do an act impossible in itself is void.
-Contract to do act afterwards becoming impossible or unlawful.—A contract to do an act which, after the contract is made, becomes impossible, or, by reason of some event which the promisor could not prevent, unlawful, becomes void when the act becomes impossible or unlawful.
-Compensation for loss through non-performance of act known to be impossible or unlawful.—Where one person has promised to do something which he knew, or, with reasonable diligence, might have known, and which the promisee did not know, to be impossible or unlawful, such promisor must make compensation to such promisee for any loss which such promisee sustains through the non-performance of the promise.
+Section 56. Agreement to do impossible act.—
+ An agreement to do an act impossible in itself is void. Contract to do act
+afterwards becoming impossible or unlawful.—A contract to do an act which,
+after the contract is made, becomes impossible, or, by reason of some event
+which the promisor could not prevent, unlawful, becomes void when the act
+becomes impossible or unlawful.
```

### Section 73: Compensation for loss or damage caused by breach of contract
```diff
--- snapshot_Section_73
+++ reference_Section_73
@@ -1,4 +1,5 @@
-Section 73. Compensation for loss or damage caused by breach of contract.—When a contract has been broken, the party who suffers by such breach is entitled to receive, from the party who has broken the contract, compensation for any loss or damage caused to him thereby, which naturally arose in the usual course of things from such breach, or which the parties knew, when they made the contract, to be likely to result from the breach of it.
-Such compensation is not to be given for any remote and indirect loss or damage sustained by reason of the breach.
-Compensation for failure to discharge obligation resembling those created by contract.—When an obligation resembling those created by contract has been incurred and has not been discharged, any person injured by the failure to discharge it is entitled to receive the same compensation from the party in default as if such person had contracted to discharge it and had broken his contract.
-Explanation.—In estimating the loss or damage arising from a breach of contract, the means which existed of remedying the inconvenience caused by the non-performance of the contract must be taken into account.
+Section 73. Compensation for loss or damage caused by breach of contract.—
+ When a contract has been broken, the party who suffers by such breach is
+entitled to receive, from the party who has broken the contract,
+compensation for any loss or damage caused to him thereby, which naturally
+arose in the usual course of things from such breach.
```

### Section 74: Compensation for breach of contract where penalty stipulated for
```diff
--- snapshot_Section_74
+++ reference_Section_74
@@ -1,4 +1,6 @@
-Section 74. Compensation for breach of contract where penalty stipulated for.—When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of such breach, or if the contract contains any other stipulation by way of penalty, the party complaining of the breach is entitled, whether or not actual damage or loss is proved to have been caused thereby, to receive from the party who has broken the contract reasonable compensation not exceeding the amount so named or, as the case may be, the penalty stipulated for.
-Explanation.—A stipulation for increased interest from the date of default may be a stipulation by way of penalty.
-Exception.—When any person enters into any bail-bond, recognizance or other instrument of the same nature, or, under the provisions of any law, or under the orders of the Central Government or of any State Government, gives any bond for the performance of any public duty or act in which the public are interested, he shall be liable, upon breach of the condition of any such instrument, to pay the whole sum mentioned therein.
-Explanation.—A person who enters into a contract with Government does not necessarily thereby undertake any public duty, or promise to do an act in which the public are interested.
+Section 74. Compensation for breach of contract where penalty stipulated for.—
+ When a contract has been broken, if a sum is named in the contract as the
+amount to be paid in case of such breach, or if the contract contains any
+other stipulation by way of penalty, the party complaining of the breach is
+entitled to receive reasonable compensation not exceeding the amount so
+named.
```

