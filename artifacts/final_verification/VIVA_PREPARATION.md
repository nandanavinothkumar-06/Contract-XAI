# CONTRACTRISK-XAI: COMPREHENSIVE VIVA VOCE DEFENSE & TECHNICAL PREPARATION GUIDE

**Document Identifier**: `CRXAI-VIVA-PREP-2026-FINAL`  
**Consolidation Date**: `2026-10-20`  
**Physical Weights Checkpoint**: `results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors`  
**Model Checkpoint SHA-256**: `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f`  
**Operating Environment**: Windows x86_64, Python 3.13.5, PyTorch 2.6.0+cpu, Transformers 5.17.0/5.18.0, Scikit-Learn 1.7.1  
**Governance Invariants**: Tasks 028 & 029 strictly `🔒 LOCKED`; Task 042 strictly `NOT STARTED`; `PROJECT_TASK_BOARD.md` unmodified.

---

> [!WARNING]
> ### VIVA CANDIDATE DEFENSE MANDATE — HONESTY & INTELLECTUAL INTEGRITY FIRST
> **NEVER CLAIM UNVALIDATED LEGAL ACCURACY.** When asked about real-world legal risk accuracy, Indian contract performance, or superiority over human lawyers, you must state clearly that **real-world Indian commercial law accuracy has not been validated**. The system is an evidence-grounded research benchmark and assistive triage pipeline tested on authentic US SEC EDGAR benchmarks and verified on synthetic contract fixtures. Overclaiming will lead to immediate failure in academic defense.

---

## Table of Contents
1. [Core Project Overview & Research Motivation](#1-core-project-overview--research-motivation)
2. [NLP Pipeline Architecture & Complete Workflow](#2-nlp-pipeline-architecture--complete-workflow)
3. [LegalBERT Architecture, Tokenization & Multi-Label Head](#3-legalbert-architecture-tokenization--multi-label-head)
4. [Extreme Multi-Label Classification & Threshold Calibration](#4-extreme-multi-label-classification--threshold-calibration)
5. [Traditional Baselines: TF-IDF, Linear SVM & NLI Fallacy](#5-traditional-baselines-tf-idf-linear-svm--nli-fallacy)
6. [Okapi BM25 Statutory Retrieval & Curated Legal Corpus](#6-okapi-bm25-statutory-retrieval--curated-legal-corpus)
7. [Explainability: Gradient × Input & Offset Invariants](#7-explainability-gradient--input--offset-invariants)
8. [Evidence-Aware Abstention: Five-Tier Decision Cascade](#8-evidence-aware-abstention-five-tier-decision-cascade)
9. [Dataset Provenance, Licensing & Excluded Corpora](#9-dataset-provenance-licensing--excluded-corpora)
10. [Evaluation Metrics & Forensic Macro-F1 Collapse Analysis](#10-evaluation-metrics--forensic-macro-f1-collapse-analysis)
11. [Forensic Error Analysis & Systemic Failure Modes](#11-forensic-error-analysis--systemic-failure-modes)
12. [Academic Boundaries, Governance & Non-Validation of Indian Law](#12-academic-boundaries-governance--non-validation-of-indian-law)
13. [High-Probability Tough Viva Questions & Defensible Answers](#13-high-probability-tough-viva-questions--defensible-answers)

---

## 1. Core Project Overview & Research Motivation

### Q1.1: What is the primary objective of the ContractRisk-XAI project?
**Answer**:
ContractRisk-XAI is an evidence-grounded natural language processing benchmark and assistive human-in-the-loop review platform for commercial contracts. Its primary computer science research objective is to address four foundational challenges in legal NLP:
1. Handling extreme long-tail class imbalance (>12,000 provision categories).
2. Investigating decision threshold calibration ($\tau^* = 0.04$) to mitigate catastrophic true-positive omission.
3. Enforcing mathematical character-offset alignment ($100\%$ bijective string slicing) in neural explainability.
4. Integrating an evidence-aware abstention cascade that withholds predictions when contracts are stale or statutory evidence is absent.

### Q1.2: What is the core novelty of your research?
**Answer**:
Our primary conceptual contribution is the formalization and verification of an **Evidence-Aware Abstention Framework** that conditions transformer provision predictions on a 5-tier precedence cascade (document version currency, statutory currentness, evidence sufficiency, and operating thresholds). Rather than allowing a model to output ungrounded classifications based on weak raw logits, the system withholds low-confidence or unbacked predictions, routing them to advocate review or suppressing them as `NO_ACTIONABLE_RISK`. We also provide an exhaustive forensic characterization of why Macro-F1 mathematically collapses in extreme legal taxonomies.

---

## 2. NLP Pipeline Architecture & Complete Workflow

### Q2.1: Walk me through the exact path an uploaded contract takes from bytes to reviewable output.
**Answer**:
The platform executes a 10-stage decoupled pipeline:
1. **Contract Ingestion**: PDF, DOCX, or TXT file bytes are received via HTTP multipart POST. A cryptographic SHA-256 digest is computed and stored in `extracted_text_snapshots`.
2. **Text Extraction & Cleaning**: Extracted plaintext undergoes non-destructive Unicode normalization without mutating character offsets.
3. **Clause Segmentation**: Regex boundary rules segment the text into ordered `SegmentRecord` entities with start/end character coordinates.
4. **LegalBERT Tokenization**: WordPiece tokenization (`vocab_size=30522`, `max_length=512`).
5. **Model Forward Pass**: PyTorch sigmoid projection computes independent probabilities $p_i = \sigma(z_i)$ across 12,407 classes.
6. **Canonical Label Mapping**: `CANONICAL_LEDGAR_TAXONOMY_MAP` translates 37 verified LEDGAR indices into 8 Indian risk archetypes without heuristic substring guessing.
7. **Statutory Retrieval**: Okapi BM25 retrieves relevant legal provisions from a curated corpus of 40 sections across 6 Indian commercial acts.
8. **Evidence-Aware Abstention**: A 5-tier policy evaluates candidate findings against operating threshold $\tau^* = 0.04$ and statutory currency. Sub-threshold findings are withheld (`NO_ACTIONABLE_RISK`).
9. **Gradient × Input Attribution**: Token sensitivities are computed via first-order input embedding gradients and mapped bijectively back to source character coordinates.
10. **Workbench Persistence**: Findings are saved as `ClauseFindingRecord` rows in SQLite/PostgreSQL, rendered in the advocate review workbench with client isolation.

---

## 3. LegalBERT Architecture, Tokenization & Multi-Label Head

### Q3.1: Why did you choose LegalBERT over general BERT or a generative LLM?
**Answer**:
We adopted `nlpaueb/legal-bert-base-uncased` (Chalkidis et al., 2020) because it was pre-trained on 12 GB of diverse English legal text (legislation, court cases, contracts). General BERT struggles with legal domain vocabulary (e.g., `indemnification`, `severability`, `force majeure`, `subrogation`). We selected a frozen discriminative transformer over a generative LLM because:
1. It guarantees deterministic, reproducible classification outputs with zero generative hallucinations.
2. It allows exact mathematical gradient computation ($\nabla_x \cdot x$) at the embedding layer.
3. It complies with strict local compute boundaries (runs inference on local CPU without cloud API leakage).

### Q3.2: How was the model fine-tuned and configured?
**Answer**:
We utilized a **linear probe** (frozen encoder) architecture:
- **Encoder**: 12 transformer layers, 768 hidden dimensions, 109.5M frozen parameters.
- **Classification Head**: Trainable linear layer (`768 -> 12407`, 9.5M parameters).
- **Training Setup**: Trained on a deterministic 10% contract subset of LEDGAR (67,776 provisions from 4,844 contracts) using multi-label binary cross-entropy loss with logits (`BCEWithLogitsLoss`).
- **Physical Checkpoint**: Verified on disk at `results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors` (476,116,436 bytes, SHA-256: `7cd08d2c...`).

---

## 4. Extreme Multi-Label Classification & Threshold Calibration

### Q4.1: Why did you tune the operating threshold to $\tau^* = 0.04$ instead of using the standard $0.50$?
**Answer**:
In multi-label classification trained with binary cross-entropy over 12,407 classes, positive class instances represent an extreme minority (<0.01% of all class-provision combinations). Under a frozen encoder, the output logits are heavily squashed towards large negative numbers, meaning sigmoid probabilities $p = \sigma(z)$ rarely exceed 0.20.

On the 87,956-provision held-out test split:
- At default threshold **$\tau = 0.50$**, the model suffers a catastrophic **99.06% omission rate**: true positives collapse to **989**, and recall drops to **0.94%** (Micro-F1: 0.0185).
- Conducting a grid search on the independent 84,250-provision **validation split** identified **$\tau^* = 0.04$** as the $\arg\max(\text{Validation Micro-F1})$.
- Applying frozen $\tau^* = 0.04$ on the held-out test set recovered **12,699 true positives**—a **12.83× recall boost** and a **+675.7% relative gain in Micro-F1** (0.1435).

### Q4.2: What is the price paid for this threshold calibration?
**Answer**:
This is the classic **Precision-Recall Threshold Dilemma (Failure Mode FM-02)**:
While recall increased by 12.83×, false positives surged by **134.6×** (from 438 to 58,947), pulling Micro-Precision down from 69.31% to 17.72%. In an automated pipeline, this would cause alert fatigue; in ContractRisk-XAI, our 5-tier evidence-aware policy and human-in-the-loop review workbench act as downstream filters to triage these candidates.

---

## 5. Traditional Baselines: TF-IDF, Linear SVM & NLI Fallacy

### Q5.1: How did traditional ML baselines perform on ContractNLI?
**Answer**:
We benchmarked TF-IDF feature extraction (118,497 unigrams and bigrams) paired with Linear Support Vector Classifier (`LinearSVC`) and Logistic Regression on ContractNLI (official held-out test set of 2,091 instances across 123 NDAs):
- **TF-IDF + Linear SVM**: Accuracy: **65.57%**, Macro-F1: **0.5844**, Weighted-F1: **0.6385**.
- **TF-IDF + Logistic Regression**: Accuracy: **62.65%**, Macro-F1: **0.4303**, Weighted-F1: **0.5795**.

### Q5.2: What is the "Lexical Overlap Fallacy" discovered in your error analysis?
**Answer**:
In **Failure Mode FM-04**, confusion matrix analysis revealed that **42.41% of `NotMentioned` instances (383 / 903)** were falsely predicted as `Entailment` by the Linear SVM. 

Commercial NDAs share ubiquitous boilerplate phrasing (`confidentiality`, `party`, `disclosed`, `proprietary`, `information`). The TF-IDF representation computes high cosine similarity between the hypothesis and the contract text simply because the words match, even when the contract completely lacks the substantive legal obligation or carveout exception specified in the hypothesis. Bag-of-words models cannot resolve polarity, exceptions, or scope qualifiers.

---

## 6. Okapi BM25 Statutory Retrieval & Curated Legal Corpus

### Q6.1: Why use Okapi BM25 instead of a dense embedding retriever (like Contriever or DPR)?
**Answer**:
1. **Verifiable Lexical Grounding**: In statutory interpretation, exact terminology matters (e.g., Section 28 of ICA 1872 uses specific terms like "restraint of legal proceedings", "void", "tribunal"). Lexical term matching avoids semantic drift.
2. **Computational Reproducibility**: BM25 requires zero GPU acceleration and executes with sub-millisecond latency on CPU.
3. **Non-Inference Ranking Metric**: BM25 scores are explicit term-frequency ranking metrics, eliminating any risk of confusing retrieval rankings with legal confidence probabilities.

### Q6.2: What does your statutory corpus contain?
**Answer**:
The corpus covers **40 commercial sections** across six central Indian statutes:
1. Indian Contract Act, 1872 (ICA): Sec 10, 23, 27, 28, 73, 74, 124, 126.
2. Information Technology Act, 2000 (ITA): Sec 43A, 65, 72A.
3. Digital Personal Data Protection Act, 2023 (DPDP): Sec 4, 5, 6, 8, 44 (tracked as uncommenced).
4. Specific Relief Act, 1963 (SRA): Sec 10, 14, 16, 20.
5. Arbitration and Conciliation Act, 1996 (ACA): Sec 7, 8, 9, 11, 34.
6. Bharatiya Sakshya Adhiniyam, 2023 (BSA): Sec 57, 61, 63.

All texts are cryptographically verified with 100% SHA-256 match in `data/legal_sources/corpus_manifest.json`.

---

## 7. Explainability: Gradient × Input & Offset Invariants

### Q7.1: How does Gradient × Input work in your system?
**Answer**:
Gradient × Input computes the element-wise dot product between the input token embedding vector $e_i \in \mathbb{R}^{768}$ and the gradient of the predicted class logit with respect to that embedding:
$$\text{Saliency}(w_i) = \left| \nabla_{e_i} \mathcal{L}(y^*) \cdot e_i \right|$$
This measures first-order local sensitivity: how much small perturbations in token $w_i$'s representation would alter the output logit for the predicted risk class.

### Q7.2: What is your character-offset invariant, and how did you verify it?
**Answer**:
Tokenizers fragment text into WordPiece subwords (e.g., `indirect` -> `in`, `##direct`). If token spans are mapped back to character indices carelessly, coordinates drift. 
We enforce the invariant:
$$\text{source\_clause}[start\_char : end\_char] == span[\text{"text"}]$$
In our automated test suite (`tests/test_nlp_correctness_validation.py`), we verified that 100% of extracted spans achieve exact character-level equality without offset drift.

### Q7.3: Does token saliency provide a legally valid explanation?
**Answer**:
**NO.** As documented in **Failure Mode FM-05**, gradient saliency measures neural sensitivity, not legal reasoning. Gradients frequently highlight common function words (`and`, `the`, `of`) or punctuation tokens due to their influence on self-attention routing. While character offsets are mathematically exact, these chips are visual assistive aids and must never be interpreted as judicial reasoning.

---

## 8. Evidence-Aware Abstention: Five-Tier Decision Cascade

### Q8.1: Explain the Five-Tier Precedence Cascade.
**Answer**:
The abstention policy in [src/abstention/evidence_policy.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/abstention/evidence_policy.py) evaluates candidate findings in strict order of legal and operational precedence:
- **Tier 1 (Accepted Risk)**: Confidence meets $\tau^* = 0.04$, contract version is current, and relevant statutory provisions are verified (`PolicyAction.ACCEPT`).
- **Tier 2 (Document Version Integrity)**: If the finding was computed on an obsolete draft (`VersionConsistencyStatus.STALE`), it is immediately withheld (`PolicyAction.WITHHOLD`).
- **Tier 3 (Statutory Currentness & Applicability)**: If the retrieved statute is uncommenced (e.g., substantive DPDP rules), repealed, or ungrounded, it is withheld (`PolicyAction.WITHHOLD`).
- **Tier 4 (Operating Threshold Gate)**: If the sigmoid score falls below $\tau^* = 0.04$, it is withheld (`PolicyAction.WITHHOLD`).
- **Tier 5 (Valid Commercial Fallback)**: Genuine commercial covenants without statutory matches (e.g., price indexation) are routed to advocate triage (`PolicyAction.REVIEW_REQUIRED`).

### Q8.2: What were the results of the offline comparison?
**Answer**:
On a synthetic benchmark of 58 candidates across 15 contract clusters, evaluating at matched useful-finding coverage ($\text{UFC} = 0.6818$):
- Confidence-only baseline ($\tau = 0.57$): Unsupported-Finding Rate (UFR) = **41.67%** (accepted 3 stale-draft findings).
- Evidence-aware policy: Unsupported-Finding Rate (UFR) = **16.67%** (0 stale-draft findings).
- **Result**: A **25.00% absolute reduction in unsupported findings** ($\Delta\text{UFR} = -0.2500$).

---

## 9. Dataset Provenance, Licensing & Excluded Corpora

### Q9.1: Which datasets were physically used in your evaluated models?
**Answer**:
1. **LEDGAR (Clean 2016–2019)**: MIT License. 846,274 provisions from US SEC EDGAR filings. Used to train and evaluate the multi-label LegalBERT linear probe.
2. **ContractNLI (v1.0)**: CC BY 4.0. 607 NDAs from Stanford. Used to benchmark TF-IDF baseline NLI models.
3. **CUAD (v1.0)**: CC BY 4.0. 510 commercial contracts. Used for representation geometry analysis.

### Q9.2: Why were CLAUDETTE and the Construction datasets excluded?
**Answer**:
- **CLAUDETTE**: License terms in public repositories were ambiguous and could not be independently authenticated from authoritative sources.
- **Moon, Shuai, and Zhou Construction Datasets**: These are proprietary or restricted research corpora without public licenses.
- In strict adherence to our data governance rules, unverified and restricted datasets were excluded.

---

## 10. Evaluation Metrics & Forensic Macro-F1 Collapse Analysis

### Q10.1: Why is your Macro-F1 on LEDGAR only $0.0045$ while Micro-F1 is $0.1435$?
**Answer**:
This is the most critical technical question of the project:
- **Micro-F1** aggregates true positives, false positives, and false negatives globally across all test provisions:
  $$\text{Micro-F1} = \frac{2 \sum TP_k}{2 \sum TP_k + \sum FP_k + \sum FN_k}$$
  It is dominated by frequent head classes (`governing laws`, `terminations`), where the model achieves solid provision recovery.
- **Macro-F1** computes the unweighted arithmetic mean of F1 scores across every individual class $k \in \{1, \dots, 12407\}$:
  $$\text{Macro-F1} = \frac{1}{12407} \sum_{k=1}^{12407} \text{F1}_k$$
- **The Forensic Cause**: In the 10% subset, **2,833 classes have 0 training examples** (22.5% of taxonomy), and **8,465 classes have under 10 examples** (67.1%). Over **91.1% of all classes** have zero or near-zero recall. Averaging 11,000 zeros with 1,000 positive scores mathematically anchors the macro average at $0.0045$. Reporting both micro and macro metrics transparently exposes this long-tail phenomenon.

---

## 11. Forensic Error Analysis & Systemic Failure Modes

### Q11.1: Summarize your 5 Failure Modes (FM-01 through FM-05).
**Answer**:
1. **FM-01 (Extreme Tail Starvation & Zero-Shot Collapse)**: 91.1% of taxonomy classes have $<10$ training examples, making statistical generalization impossible for rare provisions.
2. **FM-02 (Precision-Recall Threshold Dilemma)**: Lowering the threshold to $\tau^* = 0.04$ recovers 12.8× recall but increases false positives by 134.6× (58,947 false alarms on test set).
3. **FM-03 (Linear Probe Bottleneck)**: Frozen BERT encoder parameters cannot adapt domain-specific contract representations without full fine-tuning.
4. **FM-04 (Lexical Overlap Fallacy in NLI)**: Pervasive boilerplate vocabulary causes TF-IDF classifiers to predict Entailment falsely on 42.41% of unmentioned covenants.
5. **FM-05 (Gradient Saliency Function-Word Bias)**: Neural gradients highlight syntactic stopwords (`and`, `the`, punctuation) rather than substantive legal terms.

---

## 12. Academic Boundaries, Governance & Non-Validation of Indian Law

### Q12.1: Does ContractRisk-XAI prove that LegalBERT is accurate for Indian contract law?
**Answer**:
**NO, EMPHATICALLY NO.** 
We explicitly state in all documentation that **real-world Indian commercial law accuracy has not been validated**. 
1. LegalBERT was pre-trained and fine-tuned on US SEC EDGAR filings, which reflect American corporate drafting styles.
2. The statutory retrieval engine covers a curated subset of 40 central sections, excluding state amendments and judicial precedents.
3. All live demonstrations were performed on synthetic contract fixtures pursuant to research governance rule RDR-002.
4. The system is designed as an assistive advocate triage tool; human advocate adjudication is mandatory.

---

## 13. High-Probability Tough Viva Questions & Defensible Answers

### Tough Q1: *"Your Micro-F1 of 0.1435 is very low compared to standard NLP benchmarks. How can you claim this is a successful model?"*
**Defensible Answer**:
"In standard NLP benchmarks, tasks typically have 2 to 20 balanced classes where random guessing yields F1 > 0.10. In LEDGAR, the classification head projects into **12,407 simultaneous classes** under extreme long-tail sparsity, with the encoder completely frozen on CPU. 
At default threshold $\tau = 0.50$, the model omitted 99.06% of true labels (Micro-F1: 0.0185). Our validation calibration to $\tau^* = 0.04$ achieved a **+675.7% relative improvement** and recovered 12,699 true provisions. The low absolute F1 is a direct, honest reflection of evaluating all 12,407 extreme tail classes rather than artificially subsetting to the top 20 classes as many papers do. We prioritize scientific realism over inflated metrics."

### Tough Q2: *"Why didn't you fine-tune the entire LegalBERT model instead of freezing the encoder?"*
**Defensible Answer**:
"We conducted a formal 5-step feasibility pilot in Task 019. On CPU hardware, training a single step of full LegalBERT across 12,407 classes took 4.75 seconds. Full training across 674,068 provisions was projected at **1,184.8 hours (49.3 days)** of continuous compute. Under our strict governance directive prohibiting multi-hour unaccelerated CPU training loops, freezing the encoder and training only the linear head was the only methodologically sound, reproducible engineering choice."

### Tough Q3: *"In your earlier reproducibility check, why was Limitation of Liability reported as 0.0349 in text but 0.0133 on the screen?"*
**Defensible Answer**:
"We forensically investigated this exact discrepancy:
When the contract segmentation pipeline processes Clause 3, it includes the section heading:
`'3. Limitation of Liability:\nNeither party shall be liable...'`
This input token sequence yields a sigmoid probability of **0.013309** for canonical index 4741. When the body text is evaluated in isolation without the heading, LegalBERT outputs **0.034930**. 
Both values are authentic model outputs reflecting input heading sensitivity, and both are strictly below our operating threshold $\tau^* = 0.04$. The initial report draft had evaluated the isolated body, while the browser displayed the live segmented clause. Furthermore, our investigation identified and resolved a database persistence bug in `repository.py` where stale attribution spans from prior runs were not being cleared on sub-threshold abstentions."

### Tough Q4: *"Can your system replace a junior contract lawyer?"*
**Defensible Answer**:
"No. ContractRisk-XAI is explicitly designed as an **assistive screening and triage tool**, not an autonomous decision-maker. It surfaces candidate provisions, highlights sensitive tokens, and retrieves relevant central statutes. The final determination (`ACCEPT_AI_OBSERVATION`, `CORRECT`, `REJECT`) requires a verified advocate's legal judgment. Autonomous legal decision-making is strictly cautioned against."
