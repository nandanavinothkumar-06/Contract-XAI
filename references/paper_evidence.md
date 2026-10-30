# Verified Paper Evidence

## PAPER 001
### Bibliographic Evidence
Title: LEGAL-BERT: The Muppets straight out of Law School
Authors: Ilias Chalkidis, Manos Fergadiotis, Prodromos Malakasiotis, Nikolaos Aletras, Ion Androutsopoulos
Year: 2020
Venue: Findings of EMNLP 2020
DOI: 10.18653/v1/2020.findings-emnlp.261
URL: https://aclanthology.org/2020.findings-emnlp.261/

### Dataset Evidence
Dataset: 12 GB diverse English legal text corpus
Size: 12 GB
Source: EURLEX, ECHR, US case law, contracts
Annotation: None (Pre-training)

### Method Evidence
Model: BERT
Task: Domain adaptation, Masked Language Modeling

### Result Evidence
Reported result: Outperforms standard BERT on downstream legal tasks.

### Limitation Evidence
Limitations: Generalization to very specialized sub-domains may vary.

### Relevance
Primary encoder for the ContractRisk-XAI system.

### Verification
Verified: YES
Verification source: ACL Anthology

## PAPER 002
### Bibliographic Evidence
Title: LEDGAR: A Large-Scale Multi-label Corpus for Text Classification of Legal Provisions in Contracts
Authors: Don Tuggener, Pius von Däniken, Thomas Peetz, Mark Cieliebak
Year: 2020
Venue: LREC 2020
DOI: 
URL: https://aclanthology.org/2020.lrec-1.55/

### Dataset Evidence
Dataset: LEDGAR
Size: ~100,000 provisions from >60,000 contracts
Source: SEC EDGAR
Annotation: Over 12,000 unique labels

### Method Evidence
Model: Logistic Regression, MLP, DistilBERT
Task: Multi-label text classification

### Result Evidence
Reported result: Transfer experiments evaluated for model generalization.

### Limitation Evidence
Limitations: Focuses entirely on SEC filings, may not generalize to all contracts.

### Relevance
Provides a massive classification baseline and corpus.

### Verification
Verified: YES
Verification source: ACL Anthology

## PAPER 003
### Bibliographic Evidence
Title: ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts
Authors: Yuta Koreeda, Christopher Manning
Year: 2021
Venue: Findings of EMNLP 2021
DOI: 
URL: https://aclanthology.org/2021.findings-emnlp.164/

### Dataset Evidence
Dataset: ContractNLI
Size: 607 annotated contracts
Source: Primarily NDAs
Annotation: Entailment, contradiction, neutral, and evidence-span identification

### Method Evidence
Model: Multi-label span classification
Task: NLI and evidence extraction

### Result Evidence
Reported result: Baseline improvements with context segmentation.

### Limitation Evidence
Limitations: Struggles with "negations by exceptions".

### Relevance
Crucial for the evidence-grounded architecture of ContractRisk-XAI.

### Verification
Verified: YES
Verification source: ACL Anthology

## PAPER 004
### Bibliographic Evidence
Title: Detecting and Explaining Unfairness in Consumer Contracts through Memory Networks
Authors: Federico Ruggeri, Francesca Lagioia, Marco Lippi, Paolo Torroni
Year: 2022
Venue: Artificial Intelligence and Law
DOI: 10.1007/s10506-021-09288-2
URL: https://link.springer.com/article/10.1007/s10506-021-09288-2

### Dataset Evidence
Dataset: CLAUDETTE
Size: 21,063 sentences (2,346 unfair)
Source: 100 online platform Terms of Service
Annotation: 5 categories of unfairness

### Method Evidence
Model: Memory-augmented neural networks (MANNs)
Task: Unfair clause detection and rationale generation

### Result Evidence
Reported result: Improved accuracy and explainability via rationales.

### Limitation Evidence
Limitations: Unfairness is limited to consumer contracts, not general commercial risk.

### Relevance
Provides architectural inspiration for explainability.

### Verification
Verified: YES
Verification source: Springer

## PAPER 005
### Bibliographic Evidence
Title: Automated Detection of Contractual Risk Clauses from Construction Specifications Using BERT
Authors: Seonghyeon Moon, Seokho Chi, Seok-Been Im
Year: 2022
Venue: Automation in Construction
DOI: 10.1016/j.autcon.2022.104465
URL: https://doi.org/10.1016/j.autcon.2022.104465

### Dataset Evidence
Dataset: Custom Construction Specifications
Size: 2,807 clauses from 56 specifications
Source: Construction documents
Annotation: 7 risk categories

### Method Evidence
Model: BERT
Task: Contractual risk clause detection

### Result Evidence
Reported result: Validation accuracy 0.889, Test F1 0.934.

### Limitation Evidence
Limitations: Highly specific to construction domain specifications.

### Relevance
Provides a domain-specific comparison baseline for construction risks.

### Verification
Verified: YES
Verification source: ScienceDirect

## PAPER 006
### Bibliographic Evidence
Title: A Rationale-Augmented NLP Framework to Identify Unilateral Contractual Change Risk for Construction Projects
Authors: Bing Shuai
Year: 2023
Venue: Computers in Industry
DOI: 10.1016/j.compind.2023.103940
URL: https://doi.org/10.1016/j.compind.2023.103940

### Dataset Evidence
Dataset: Construction contracts
Size: Not explicitly extracted
Source: Construction industry
Annotation: Unilateral change risk

### Method Evidence
Model: Rationale-Augmented NLP
Task: Risk identification

### Result Evidence
Reported result: Improved detection of unilateral change risks.

### Limitation Evidence
Limitations: Narrowly focused on unilateral changes, not general risks.

### Relevance
Supports the rationale-augmentation approach.

### Verification
Verified: YES
Verification source: ScienceDirect

## PAPER 007
### Bibliographic Evidence
Title: Intelligent detection on construction project contract missing clauses based on deep learning and NLP
Authors: Hong Zhou, Binwei Gao, Shilong Tang, Bing Li, Shuyu Wang
Year: 2023
Venue: Engineering, Construction and Architectural Management
DOI: 10.1108/ECAM-02-2023-0172
URL: https://doi.org/10.1108/ECAM-02-2023-0172

### Dataset Evidence
Dataset: Custom construction contracts
Size: 1,322 contracts
Source: Construction industry
Annotation: Missing clauses

### Method Evidence
Model: Multi-label classification & MatchPyramid+BERT
Task: Missing clause detection

### Result Evidence
Reported result: Classification accuracy 93%, Similarity accuracy 83%.

### Limitation Evidence
Limitations: "Missing" refers to substantial content omission within defined categories.

### Relevance
Crucial for the missing-provision module of ContractRisk-XAI.

### Verification
Verified: YES
Verification source: Emerald Insight

## PAPER 008
### Bibliographic Evidence
Title: A Survey of Classification Tasks and Approaches for Legal Contracts
Authors: Amrita Singh, Aditya Joshi, Jiaojiao Jiang, Hye-young Paik
Year: 2025
Venue: Artificial Intelligence Review
DOI: 10.1007/s10462-025-11359-8
URL: https://doi.org/10.1007/s10462-025-11359-8

### Dataset Evidence
Dataset: Survey of 14 datasets
Size: N/A
Source: Various
Annotation: N/A

### Method Evidence
Model: Survey
Task: Survey of Legal Contract Classification (LCC)

### Result Evidence
Reported result: Identified 7 key tasks and 8 significant challenges.

### Limitation Evidence
Limitations: Literature review, does not propose a new model.

### Relevance
Helps define the precise research gaps the system addresses.

### Verification
Verified: YES
Verification source: Springer

## PAPER 009
### Bibliographic Evidence
Title: ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial Contracts
Authors: Shuang Liu, Zelong Li, Ruoyun Ma, Haiyan Zhao, Mengnan Du
Year: 2025
Venue: Natural Legal Language Processing Workshop
DOI: 
URL: https://aclanthology.org/2025.nllp-1.19/

### Dataset Evidence
Dataset: ContractEval (based on CUAD)
Size: N/A
Source: CUAD derivatives
Annotation: Legal risk

### Method Evidence
Model: Various LLMs (open-source and proprietary)
Task: Benchmarking LLM clause-level risk identification

### Result Evidence
Reported result: LLMs often exhibit "No Related Clause" bias.

### Limitation Evidence
Limitations: Targeted fine-tuning remains necessary for high-stakes environments.

### Relevance
Crucial context for evaluating LLM alternatives against ContractRisk-XAI.

### Verification
Verified: YES
Verification source: ACL Anthology
