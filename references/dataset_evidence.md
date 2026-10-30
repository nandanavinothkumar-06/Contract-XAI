# Verified Dataset Evidence

## Contract Understanding Atticus Dataset (CUAD)
### Bibliographic Evidence
Original Paper: CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review
URL: https://www.atticusprojectai.org/cuad

### Provenance Evidence
Document origin: Commercial legal contracts
Annotation source: Legal experts (The Atticus Project)

### Scale Evidence
Document count: 510 contracts
Clause count: >13,000 annotations
Label count: 41 categories

### Task and Label Evidence
Task type: Question Answering / Span Extraction
Label schema: 41 categories (e.g., limitation of liability)

### Evidence/Rationale Evidence
Evidence type: Evidence spans included

### License Evidence
License: Dataset released under CC BY 4.0; underlying contract rights remain subject to the source/disclaimer conditions.
Source: Kaggle/Atticus Project
Commercial use: Allowed (for dataset)

### Access Evidence
Status: Open download via HuggingFace and Zenodo

### Suitability
Suitability: PRIMARY. Essential for commercial clause extraction.

### Limitations / Unknowns
Underlying contract copyright status varies.

### Sources
HuggingFace, Zenodo, Atticus Project Website.

## Labeled EDGAR (LEDGAR)
### Bibliographic Evidence
Original Paper: LEDGAR: A Large-Scale Multi-label Corpus...
URL: https://aclanthology.org/2020.lrec-1.55/

### Provenance Evidence
Document origin: US SEC EDGAR filings
Annotation source: Automatic extraction

### Scale Evidence
Document count: More than 60,000 contracts
Provision count: Almost 100,000 provisions
Label count: More than 12,000 labels

### Task and Label Evidence
Task type: Multi-label Text Classification
Label schema: More than 12,000 labels

### Evidence/Rationale Evidence
Evidence type: None

### License Evidence
License: MIT (via LexGLUE/official distribution)
Source: HuggingFace / GitHub
Commercial use: Allowed

### Access Evidence
Status: Open download

### Suitability
Suitability: PRIMARY. Essential for scale and domain adaptation.

### Limitations / Unknowns
Limited to US SEC filings.

### Sources
ACL Anthology, HuggingFace.

## Contract Natural Language Inference (ContractNLI)
### Bibliographic Evidence
Original Paper: ContractNLI...
URL: https://stanfordnlp.github.io/contract-nli/

### Provenance Evidence
Document origin: Non-disclosure agreements (NDAs)
Annotation source: Expert/Annotator

### Scale Evidence
Document count: 607 contracts
Clause count: Not verified
Label count: 3 (Entailment, Contradiction, Neutral)

### Task and Label Evidence
Task type: Document-level NLI
Label schema: NLI labels

### Evidence/Rationale Evidence
Evidence type: Evidence spans included

### License Evidence
License: Dataset: CC BY 4.0 (Baseline Implementation: Apache 2.0)
Source: StanfordNLP GitHub
Commercial use: Allowed

### Access Evidence
Status: Open download

### Suitability
Suitability: PRIMARY. Essential for evidence extraction evaluation.

### Limitations / Unknowns
Focused purely on NDAs.

### Sources
StanfordNLP GitHub, ACL Anthology.

## CLAUDETTE
### Bibliographic Evidence
Original Paper: Detecting and Explaining Unfairness in Consumer Contracts...
URL: http://claudette.eui.eu

### Provenance Evidence
Document origin: Online platform Terms of Service
Annotation source: Legal experts

### Scale Evidence
Document count: 100 ToS
Clause count: 21,063 sentences
Label count: 5 categories

### Task and Label Evidence
Task type: Unfair Clause Detection
Label schema: 5 unfairness categories

### Evidence/Rationale Evidence
Evidence type: Rationales/explanations included

### License Evidence
License: Not explicitly verified from authoritative source
Source: N/A
Commercial use: Not verified

### Access Evidence
Status: Open download

### Suitability
Suitability: SECONDARY. Crucial for explainability.

### Limitations / Unknowns
Unfairness in consumer contracts is NOT general commercial risk. Commercial licensing is unresolved.

### Sources
Springer, HuggingFace.

## Construction Datasets (Moon, Shuai, Zhou)
### Bibliographic Evidence
Papers: Moon et al. (2022), Shuai (2023), Zhou dataset (2023 online / 2025 issue)
Zhou DOI: 10.1108/ECAM-02-2023-0172 (Vol 32, Issue 3, Pages 1546-1580)

### Provenance Evidence
Document origin: Construction contracts and specifications.
Annotation source: Researchers
No official public dataset download/repository independently verified during TASK 003.

### Scale Evidence
Moon: 56 specs, 2,807 clauses.
Zhou: 1,322 contracts.
Shuai: Not verified.

### Task and Label Evidence
Task type: Various (Clause classification, Unilateral change risk, Missing clause)
Label schema: Specific to each paper

### Evidence/Rationale Evidence
Shuai includes rationales.

### License Evidence
License: Not verified
Source: N/A
Commercial use: Not verified

### Access Evidence
Status: Unresolved / not independently verified

### Suitability
Suitability: RESTRICTED.

### Limitations / Unknowns
Access and licensing remain completely unresolved.

### Sources
ScienceDirect, Emerald Insight.
