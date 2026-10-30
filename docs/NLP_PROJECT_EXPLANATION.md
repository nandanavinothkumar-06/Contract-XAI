# CONTRACTRISK-XAI: Technical Explanation of Core NLP & Explainable AI Architecture

**Document Type**: Technical Reference & Viva Defense Guide  
**Project**: CONTRACTRISK-XAI (Explainable AI System for Indian Commercial Contract Screening)  
**Authors**: Antigravity AI Engineering & Research Team  
**Governing Standard**: Research Governance Framework RDR-002 (Synthetically Grounded, Non-Lawyer Disclaimer)  
**Last Updated**: October 2026  

---

## Table of Contents
1. [Problem Statement & Research Hypothesis](#1-problem-statement--research-hypothesis)
2. [NLP System Architecture & End-to-End Workflow](#2-nlp-system-architecture--end-to-end-workflow)
3. [LegalBERT Tokenization, Inference & Output Taxonomy](#3-legalbert-tokenization-inference--output-taxonomy)
4. [Multi-Label Classification & Risk-Category Mapping](#4-multi-label-classification--risk-category-mapping)
5. [Gradient × Input Token Attribution (Explainability)](#5-gradient--input-token-attribution-explainability)
6. [BM25 Statutory Evidence Retrieval](#6-bm25-statutory-evidence-retrieval)
7. [Evidence-Aware Abstention & Threshold Calibration](#7-evidence-aware-abstention--threshold-calibration)
8. [Dataset Roles & Evaluation Methodology](#8-dataset-roles--evaluation-methodology)
9. [Empirical Benchmark Results & Failure Analysis](#9-empirical-benchmark-results--failure-analysis)
10. [Limitations, Ethical Safeguards & Future Work](#10-limitations-ethical-safeguards--future-work)
11. [Comprehensive Viva Defense Q&A](#11-comprehensive-viva-defense-qa)

---

## 1. Problem Statement & Research Hypothesis

### 1.1 The Legal-Technical Problem
In commercial contracting under Indian law, standard legal due diligence is slow, expensive, and error-prone. Commercial agreements frequently contain clauses that are:
- Legally void *ab initio* (e.g., post-employment non-compete covenants violating Section 27 of the Indian Contract Act, 1872).
- Restraints on legal proceedings or arbitrary exclusive jurisdiction provisions violating Section 28 of the Indian Contract Act, 1872.
- Unreasonable unilateral indemnifications, asymmetric liability caps, or penal liquidated damages violating Section 74 of the Contract Act.

Standard large language models (LLMs) and generic Transformer models exhibit critical deficiencies when deployed for legal risk screening:
1. **Hallucination & Legal Invention**: Generic LLMs invent statutory citations, confuse foreign jurisdictions (e.g., Delaware corporate law vs. Indian Companies Act 2013), and generate plausible but legally invalid advice.
2. **Confidence Miscalibration**: Raw neural classification scores are uncalibrated; models output high confidence on out-of-distribution clauses or boilerplate phrases.
3. **Black-Box Opacity**: Legal professionals cannot ethically or professionally rely on ungrounded AI predictions without verifiable token-level rationales and statutory sources.
4. **Client Liability Leakage**: Prematurely disclosing unverified AI risk guesses directly to business clients creates catastrophic liability for legal advisory firms.

### 1.2 The Research Hypothesis
> **Hypothesis**: *A domain-specialized transformer architecture (LegalBERT) coupled with multi-label empirical threshold calibration ($\tau^*$), character-aligned Gradient $\times$ Input attribution, BM25 statutory retrieval across codified Indian commercial acts, and a 5-tier evidence-aware abstention policy can identify commercial contract risk provisions while provably suppressing hallucinations and withholding sub-threshold or ungrounded assertions before lawyer review.*

---

## 2. NLP System Architecture & End-to-End Workflow

CONTRACTRISK-XAI is architected as a pipeline connecting raw contract ingestion to reviewable advocate findings:

```
Raw Agreement (TXT / PDF / DOCX)
   │
   ▼
[1. Ingestion & Validation Pipeline]
   ├── SHA-256 Content Hashing & Quarantine Check
   ├── Encoding Normalization (UTF-8, Carriage-return normalization)
   └── Clause Segmentation (Regex & layout boundary split)
   │
   ▼
[2. LegalBERT Domain Inference]
   ├── Tokenization (legal-bert-base-uncased tokenizer, max_length=512)
   ├── Embedding Forward Pass & Frozen Backbone Logit Generation
   └── Sigmoid Multi-Label Activation: p_i = σ(z_i) ∈ [0, 1] across 12,407 labels
   │
   ▼
[3. Taxonomy Mapping & Operating Threshold Gating]
   ├── Filter by CANONICAL_LEDGAR_TAXONOMY_MAP (37 verified canonical labels)
   └── Empirical Threshold Gating: Keep candidates with p_i >= τ* (0.04)
   │
   ▼
[4. BM25 Statutory Evidence Retrieval]
   ├── Query Formation from Clause Text
   ├── Okapi BM25 Ranking across 6 Codified Indian Commercial Acts
   └── EvidenceQualityStatus Evaluation (TRACEABLE, NO_MATCHING_EVIDENCE, etc.)
   │
   ▼
[5. Evidence-Aware Abstention Policy (5-Tier Cascade)]
   ├── Tier 1: Version consistency & document hash integrity
   ├── Tier 2: Partition isolation & contamination check
   ├── Tier 3: Statutory applicability & domain grounding check
   ├── Tier 4: Empirical confidence threshold check (p >= 0.04)
   └── Tier 5: Final disposition (ACCEPT -> Grounded Finding, or WITHHOLD)
   │
   ▼
[6. Explainability & Output Synthesis]
   ├── If ACCEPT: Gradient × Input Saliency (token-to-character offset alignment)
   ├── If WITHHOLD: risk_label = "NO_ACTIONABLE_RISK", Attribution = None
   └── Persist to Database ClauseFindingRecord (is_disclosed_to_client = False)
```

---

## 3. LegalBERT Tokenization, Inference & Output Taxonomy

### 3.1 Domain-Specific Backbone: LegalBERT
CONTRACTRISK-XAI utilizes `nlpaueb/legal-bert-base-uncased` (Chalkidis et al., EMNLP 2020):
- **Parameters**: 110M parameters, 12 transformer layers, 768 hidden dimensions, 12 attention heads.
- **Vocabulary**: 30,522 legal and sub-word tokens pre-trained on 12 GB of diverse legal corpora (legislation, court opinions, contracts, SEC filings).
- **Domain Advantage**: Unlike standard BERT trained on Wikipedia and BooksCorpus, LegalBERT understands legal syntactic conventions, terms of art (*indemnify*, *severability*, *jurisdiction*, *force majeure*), and statutory drafting syntax.

### 3.2 Tokenization & Padding Strategy
- **Max Sequence Length**: 512 tokens.
- **Truncation Policy**: Truncates rightward (`truncation=True`) while recording truncation status in candidate metadata (`truncation_status=True/False`).
- **Special Tokens**: `[CLS]` (token 101) prepended for pooled classification; `[SEP]` (token 102) appended at clause end.

### 3.3 Output Taxonomy
The classification head outputs logits over the **12,407 categories** defined in the LEDGAR taxonomy (Tuggener et al., LREC 2020). The final dense layer projection has dimensions:
$$W \in \mathbb{R}^{768 \times 12407}, \quad b \in \mathbb{R}^{12407}$$

---

## 4. Multi-Label Classification & Risk-Category Mapping

### 4.1 Multi-Label Formulations vs. Multi-Class Softmax
Commercial contract clauses frequently embody multiple legal consequences simultaneously (e.g., a clause may be both an *indemnity* and a *limitation of liability*). Softmax ($\sum p_i = 1$) introduces an artificial negative correlation between mutually compatible legal obligations. 

CONTRACTRISK-XAI uses independent sigmoid multi-label activations:
$$p_i = \sigma(z_i) = \frac{1}{1 + e^{-z_i}} \quad \forall i \in \{1, \dots, 12407\}$$
Each provision's category probability is computed independently.

### 4.2 Canonical Taxonomy Mapping (Eliminating Heuristic Guessing)
To prevent hallucinated category assignments, `_build_label_mapping` rejects heuristic substring matching (`if "indemn" in label...`) and enforces an exact, one-to-one canonical dictionary (`CANONICAL_LEDGAR_TAXONOMY_MAP`) verified against `label_mapping.json`:

| Indian Risk Archetype | Canonical LEDGAR Label | Taxonomy Index | Target Legal Concept |
| :--- | :--- | :--- | :--- |
| **`GOVERNING_LAW_DISPUTE`** | `governing laws`<br>`governing law: jurisdiction`<br>`submission to jurisdiction` | `4741`<br>`4740`<br>`11011` | Choice of law, forum selection, exclusive jurisdiction clauses |
| **`INDEMNIFICATION`** | `indemnifications`<br>`indemnity`<br>`indemnification - general`<br>`additional indemnification`<br>`additional indemnity` | `5150`<br>`5156`<br>`5149`<br>`434`<br>`435` | Hold-harmless covenants, defense obligations, third-party claim liabilities |
| **`LIMITATION_OF_LIABILITY`**| `limitation of liability`<br>`limitation on liability`<br>`limitations of liability`<br>`limitations on liability`<br>`limitation of consequential damages`<br>`limitation of damages`<br>`limits of liability`<br>`liability limitations` | `5979`<br>`5978`<br>`6035`<br>`6036`<br>`5975`<br>`5976`<br>`6078`<br>`5879` | Consequential damage exclusions, aggregate monetary liability caps |
| **`CONFIDENTIALITY_UNILATERAL`**| `confidentiality`<br>`confidential information`<br>`confidential terms`<br>`confidential`<br>`confidential agreement`<br>`confidentiality agreements` | `2377`<br>`2374`<br>`2378`<br>`2373`<br>`2372`<br>`2380` | Non-disclosure obligations, trade secret protections, proprietary information |
| **`TERMINATION_CONVENIENCE`**| `termination for convenience`<br>`termination by company`<br>`termination by company without cause`<br>`terminations` | `11425`<br>`11420`<br>`11422`<br>`11432` | At-will termination rights, without-cause cancellation |
| **`ARBITRATION_EXCLUSIVE_JURISDICTION`**| `arbitration`<br>`arbitration procedures`<br>`arbitration of disputes`<br>`arbitration agreements`<br>`agreement to arbitrate` | `865`<br>`870`<br>`869`<br>`866`<br>`528` | Mandatory arbitration clauses, arbitral tribunal venue |
| **`SEVERABILITY_RESTRAINT`**| `severability`<br>`severability clause`<br>`severability of provisions` | `10408`<br>`10409`<br>`10411` | Blue-pencil doctrine, survival of legal covenants |
| **`NON_COMPETE_RESTRAINT`** | `non-compete agreements`<br>`non-competition agreements`<br>`non-competition covenants` | `7244`<br>`7245`<br>`7246` | Restraints of trade, post-termination employment bans |

---

## 5. Gradient × Input Token Attribution (Explainability)

### 5.1 Mathematical Formulation
Post-hoc model explainability uses the **Gradient $\times$ Input** saliency formulation (Denil et al., 2014; Atanasova et al., 2020). Let $x = (w_1, \dots, w_N)$ be the token sequence, and $e_t \in \mathbb{R}^D$ be the embedding vector for token $w_t$.

For a target risk label $c$ with logit $z_c(x)$, the gradient vector with respect to token embedding $e_t$ is:
$$g_t = \frac{\partial z_c(x)}{\partial e_t}$$
The scalar saliency score $S(w_t)$ is the inner product of the gradient and the input embedding:
$$S(w_t) = g_t \cdot e_t = \sum_{d=1}^D \frac{\partial z_c(x)}{\partial e_{t,d}} \cdot e_{t,d}$$

### 5.2 Token-to-Character Alignment via `TokenAligner`
WordPiece tokenizers fragment words into subwords (e.g., `indemnification` $\to$ `in`, `##dem`, `##nifi`, `##cation`). Saliencies must map back to exact character slices in the user's contract without offset drift:
1. `TokenAligner` extracts character offset tuples $(s_t, e_t)$ from `tokenizer(return_offsets_mapping=True)`.
2. Special tokens (`[CLS]`, `[SEP]`, `[PAD]`) are masked using `get_special_token_mask()`.
3. Contiguous subword tokens are aggregated using normalized ranking scores.
4. Substring invariant: `clause_text[start:end] == span.text` is mathematically verified.

### 5.3 Mandatory Attribution Suppression on Abstention
When a prediction is withheld (confidence $< \tau^*$ or ungrounded statute), computing attribution targeting an arbitrary label creates false token sensitivities. In CONTRACTRISK-XAI:
$$\text{Attribution}(x) = \begin{cases} \text{ExtractGradientXInput}(x, c) & \text{if PolicyAction} = \text{ACCEPT} \\ \text{None} & \text{if PolicyAction} = \text{WITHHOLD} \end{cases}$$

---

## 6. BM25 Statutory Evidence Retrieval

### 6.1 Codified Indian Statutory Corpus
CONTRACTRISK-XAI indexes 6 foundational Indian commercial statutes:
1. **Indian Contract Act, 1872** (Sections 10, 23, 27, 28, 73, 74).
2. **Specific Relief Act, 1963** (Injunctions, specific performance).
3. **Arbitration and Conciliation Act, 1996** (Arbitration agreements, Section 7, 8).
4. **Sale of Goods Act, 1930** (Warranties, conditions, breach remedies).
5. **Companies Act, 2013** (Director liabilities, indemnities, corporate powers).
6. **Information Technology Act, 2000** (Electronic contracts, Section 10A, data protection).

### 6.2 Okapi BM25 Ranking Algorithm
Given clause text $Q$ with query terms $q_1, \dots, q_m$ and statutory provision document $D$:
$$\text{BM25}(D, Q) = \sum_{i=1}^m \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
Parameters: $k_1 = 1.5$, $b = 0.75$.

### 6.3 Evidence Quality Status
Every retrieval result is categorized into a formal status:
- `TRACEABLE`: Direct textual relevance match against codified statutory provisions.
- `NO_MATCHING_EVIDENCE`: Clause content does not match statutory keywords.
- `INAPPLICABLE_OR_SUPERSEDED`: Retrieved statute is irrelevant to the predicted risk archetype.
- `STALE_EVIDENCE`: Retrieval was computed against an earlier contract version.

---

## 7. Evidence-Aware Abstention & Threshold Calibration

### 7.1 The 5-Tier Hierarchical Abstention Cascade
Rather than relying solely on raw probability, CONTRACTRISK-XAI implements a defensive 5-tier policy:

```
[Candidate Finding Record]
   │
   ├── Tier 1: Version Consistency
   │     └── document_content_hash mismatch? ─────────► WITHHOLD [STALE_DOCUMENT_VERSION]
   │
   ├── Tier 2: Partition Isolation
   │     └── Test/Validation partition leakage? ──────► WITHHOLD [CROSS_PARTITION_CONTAMINATION]
   │
   ├── Tier 3: Statutory Grounding
   │     └── Inapplicable/conflicting statute? ───────► WITHHOLD [INAPPLICABLE_OR_SUPERSEDED_STATUTE]
   │
   ├── Tier 4: Empirical Confidence
   │     └── Model Sigmoid Probability < τ* (0.04)? ──► WITHHOLD [BELOW_CONFIDENCE_THRESHOLD]
   │
   └── Tier 5: Final Disposition
         └── Grounded & Above-Threshold? ─────────────► ACCEPT   [GROUNDED_STATUTORY_FINDING]
```

### 7.2 Why Default $\tau = 0.50$ Fails in Legal Multi-Label NLP
In standard binary classification, $0.50$ is the natural decision boundary. In extreme multi-label classification across 12,407 categories:
- The probability mass is dispersed over thousands of competing classes.
- A model probability of $0.05$ (5%) is **over 600 times higher** than the uniform random prior ($\frac{1}{12407} \approx 0.0000806$).
- At $\tau = 0.50$, the model produces massive false negatives (recall drops to $0.0094$).
- Through two-stage empirical threshold calibration on 84,250 validation provisions (`TASK019`), the optimal threshold maximizing micro-F1 was proven to be $\tau^* = 0.04$.

---

## 8. Dataset Roles & Evaluation Methodology

CONTRACTRISK-XAI enforces strict separation between public benchmark corpora and Indian commercial risk screening:

| Dataset | Split & Scale | Architectural Role | Evaluation Role |
| :--- | :--- | :--- | :--- |
| **LEDGAR** (Tuggener et al., 2020) | 84,250 validation provisions<br>87,956 test provisions | Multi-label provision classification pre-training (12,407 labels) | Empirical threshold calibration ($\tau^* = 0.04$) and baseline benchmarking |
| **ContractNLI** (Koreeda & Manning, 2021) | 607 annotated contracts | Document-level NLI baseline for clause-hypothesis entailment | Benchmark comparison for evidence-grounded hypotheses |
| **Indian Central Commercial Statutes** | 6 primary acts (2,400 sections) | Statutory knowledge corpus for BM25 retrieval | Grounding layer for Indian commercial risk verification |
| **Synthetic Agreement Suite** | Multi-clause test fixtures | Deterministic end-to-end integration verification | Safe evaluation without ingesting unverified real-world contracts (RDR-002) |

---

## 9. Empirical Benchmark Results & Failure Analysis

### 9.1 Held-Out Test Evaluation Results (`TASK019`)
Evaluated on **87,956 held-out test provisions** across 12,407 classes:

| Metric | Calibrated Threshold ($\tau^* = 0.04$) | Default Baseline ($\tau = 0.50$) | Relative Gain / Factor |
| :--- | :--- | :--- | :--- |
| **True Positives** | **12,699** | 989 | **$+11,710$ ($12.83\times$ gain)** |
| **False Positives** | 58,947 | 438 | Trade-off (absorbed by abstention) |
| **False Negatives** | 92,584 | 104,294 | $-11,710$ reduction |
| **Micro-Precision** | 0.1772 | **0.6931** | High baseline precision |
| **Micro-Recall** | **0.1206** | 0.0094 | **$12.83\times$ Recall Gain** |
| **Micro-F1** | **0.1435** | 0.0185 | **$+675.68\%$ relative gain** |
| **Weighted-F1** | **0.0937** | 0.0141 | $+564.5\%$ gain |

### 9.2 Failure Mode Analysis
1. **Background Logit Bias (FM-01)**: High-frequency contract headings (e.g., `governing laws`) have high baseline logits (~0.02 - 0.035). Un-gated `argmax` falsely selects them for ambiguous or short clauses. *Mitigation*: Threshold gating ($\ge 0.04$) and Tier 4 abstention.
2. **Missing Sub-provision Exception (FM-02)**: Legal clauses often contain internal carve-outs (*"provided however that liability for gross negligence shall not be limited"*). Single-label representations miss conditional negations. *Mitigation*: Multi-label formulation and token-level saliency inspection.
3. **Punctuation Sensitivity in Saliency (FM-03)**: Gradient $\times$ Input can exhibit sensitivity to periods, colons, or numbering (*"1. Governing Law:"*). *Mitigation*: Subword token ranking and research warning disclosure.

---

## 10. Limitations, Ethical Safeguards & Future Work

### 10.1 Technical & Legal Limitations
- **No Legal Advice**: Statistical model predictions do not constitute legal advice, judicial rulings, or formal legal opinions.
- **US SEC vs. Indian Drafting Divergence**: The underlying LEDGAR model was trained on SEC EDGAR filings. While commercial contract archetypes overlap, Indian drafting conventions contain distinct statutory idioms.
- **CPU Inference Latency**: Gradient $\times$ Input requires a forward and backward pass per clause, requiring ~2-5 seconds per provision on CPU hardware.

### 10.2 Ethical Safeguards & RDR-002 Invariants
1. **Advocate-in-the-Loop**: All AI findings are private to the supervising lawyer (`is_disclosed_to_client = False`). AI never directly communicates findings to corporate clients.
2. **Fail-Closed Abstention**: If confidence is low or statutory grounding fails, the system defaults to `WITHHOLD` rather than speculating.
3. **Audit Immutability**: All decisions, thresholds, and raw scores are cryptographically tracked in tamper-evident database audit logs.

---

## 11. Comprehensive Viva Defense Q&A

### Q1: Why did you use LegalBERT instead of a modern decoder LLM like Llama 3 or GPT-4?
**Answer**:
1. **Deterministic Reproducibility & Auditable Weights**: LegalBERT operates locally with fixed weights (SHA-256: `7cd08d2c...`), enabling strict compliance audits without non-deterministic temperature drift.
2. **Gradient-Based White-Box Explainability**: Encoder architectures allow direct computation of mathematical gradients ($\frac{\partial z}{\partial e}$), giving true input-token attribution. Decoder LLMs rely on external prompting or perturb-and-guess approximations.
3. **Data Privacy & Legal Professional Privilege**: Commercial agreements contain non-public, confidential terms. Transmitting client contracts to third-party commercial APIs violates Indian Bar Council ethics and nondisclosure covenants.
4. **Targeted Multi-Label Classification**: LegalBERT with a multi-label classification head outputs simultaneous, independent probabilities across legal categories, avoiding natural language parsing ambiguity.

### Q2: Why did clauses without Governing Law headings previously receive `GOVERNING_LAW_DISPUTE` predictions?
**Answer**:
Two interacting defects caused this behavior:
1. **Taxonomy & Logit Asymmetry**: In the LEDGAR corpus, boilerplate clauses like `governing laws` occur with very high frequency, giving `idx 4741` a higher baseline logit (~0.015 to 0.035) than rare tail labels like `confidentiality` (~0.001).
2. **Unconditional `argmax` and Heuristic Substring Matching**: The previous screening logic matched labels via loose substrings (`"limitation of liability"` missed canonical label `"limitation on liability"`, idx 5978) and took `sub_probs.argmax()` unconditionally without threshold gating. Even when all mapped probabilities were below $\tau^* = 0.04$, `governing laws` had the highest background score and was assigned as `pred_category`.
3. **Resolution**: We enforced `CANONICAL_LEDGAR_TAXONOMY_MAP` (37 exact indices), gated selection by $p \ge 0.04$, and enforced that withheld findings return `risk_label = "NO_ACTIONABLE_RISK"` with suppressed attribution spans.

### Q3: Why is your operating threshold $\tau^* = 0.04$ instead of the usual $0.50$?
**Answer**:
In extreme multi-label classification with 12,407 competing classes, the uniform probability mass prior is $\frac{1}{12407} \approx 0.00008$. A sigmoid probability of $0.04$ (4%) is **500 times higher than random chance**. At $\tau = 0.50$, the model's test recall was only $0.0094$ (missing over 99% of contract provisions). Through empirical validation calibration on 84,250 samples, $\tau^* = 0.04$ was proven to be the optimal F1 operating point, boosting recall by $12.83\times$ ($12,699$ true positives vs. $989$).

### Q4: How does your explainability module avoid the token offset misalignment bug common in HuggingFace pipelines?
**Answer**:
Standard subword tokenizers break words into pieces (`indemnification` $\to$ `in`, `##dem`, `##nifi`, `##cation`). Naive character slicing based on token count causes offset drift. We use `TokenAligner`, which extracts the tokenizer's exact byte/character offset mapping (`return_offsets_mapping=True`). Saliency scores are aggregated across subwords, and character slices are checked against the source string. Our test suite asserts `clause_text[span.start:span.end] == span.text` identically.

### Q5: What is the difference between your statutory retriever and a standard RAG pipeline?
**Answer**:
Standard RAG retrieves documents, feeds them into an LLM prompt, and allows the LLM to generate free-form text, which often hallucinates statutory interpretations. In CONTRACTRISK-XAI:
1. Retrieval is performed using Okapi BM25 directly across 6 codified Indian commercial acts.
2. The retrieved statutory provisions are evaluated for grounding quality (`TRACEABLE`, `NO_MATCHING_EVIDENCE`).
3. The statutory grounding feeds into a formal **5-Tier Abstention Policy**. If statutory grounding fails, the prediction is **withheld** rather than guessed.
4. The exact statutory text is presented alongside the model observation as verifiable reference material for the reviewing advocate.

### Q6: How does the system protect business clients from AI errors?
**Answer**:
Under the **Client Disclosure Isolation Invariant**, every generated finding is stored with `is_disclosed_to_client = False`. The client interface receives only lawyer-vetted and approved disclosures. Unassigned advocates or clients cannot view raw, uncalibrated, or withheld AI observations, preventing AI speculation from ever becoming a client-facing liability.
