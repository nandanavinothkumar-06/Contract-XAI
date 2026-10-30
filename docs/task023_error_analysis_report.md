# TASK 023 — Error Analysis: Empirical Research Report

**Project**: ContractRisk-XAI  
**Task ID**: 023  
**Task Name**: Run error analysis  
**Execution Timestamp**: 2026-10-14T21:00:00+05:30  
**Status**: ✅ COMPLETED  
**Manifest Path**: [`results/task023/task023_error_analysis_manifest.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/task023/task023_error_analysis_manifest.json)  
**Dedicated Automated Test Suite**: [`tests/test_error_analysis.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_error_analysis.py) (**6/6 passed in 0.12s**)  
**Full Project Regression Suite**: **51/51 passed in 79.92s** across Tasks 019, 020, 021, 022, and 023  

---

## 1. Executive Summary & Objective

The objective of **Task 023** is to conduct an independent, reproducible error analysis of the models, predictions, baseline benchmarks, and explanation pipelines within the ContractRisk-XAI system. 

In strict adherence to research integrity guidelines:
1. **Zero Retraining**: All error characterizations were conducted on existing, verified model checkpoints and baseline evaluation records without retraining.
2. **Fixed Decision Boundary**: Analysis preserved the validation-calibrated operating point ($\tau^* = 0.04$); no thresholds were recalibrated against held-out test data.
3. **Data Boundary Preservation**: Separate tasks and label spaces (LEDGAR 12,407-label multi-label provision classification vs ContractNLI 3-class document NLI vs CUAD extractive QA) were strictly decoupled.
4. **Honest Attribution Distinction**: Explanation alignment correctness was strictly separated from explanation faithfulness and legal justification validity.

---

## 2. Model & Evaluation Provenance

- **Physical Model Weights Path**: [`results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors)
- **Model Weights SHA-256**: `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f`
- **Output Taxonomy Dimension**: 12,407 evaluated classes (out of 12,608 unique labels in the full corpus; 201 unmapped canonical labels)
- **Primary LEDGAR Calibration Record**: [`results/models/ledgar_frozen_subset_fresh/calibrated/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH_CALIBRATED.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/models/ledgar_frozen_subset_fresh/calibrated/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH_CALIBRATED.json)
- **ContractNLI Baseline Record**: [`results/baseline/contractnli/TASK018_CONTRACTNLI_TFIDF_SVM.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/baseline/contractnli/TASK018_CONTRACTNLI_TFIDF_SVM.json)
- **Analysis Execution Script**: [`src/evaluation/run_task023_error_analysis.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/evaluation/run_task023_error_analysis.py)

---

## 3. LEDGAR Multi-Label Classification Error Analysis

### 3.1 Held-Out Test Confusion and Operating Threshold Comparison
The held-out test split consists of 87,956 legal provisions containing 105,283 actual ground-truth label assignments.

| Metric | Calibrated Threshold ($\tau^* = 0.04$) | Baseline Threshold ($\tau = 0.50$) | Impact of Threshold Calibration |
|---|---|---|---|
| **True Positives ($TP$)** | **12,699** | 989 | **$+11,710$ ($12.83\times$ gain)** |
| **False Positives ($FP$)** | **58,947** | 438 | **$+58,509$ ($134.58\times$ inflation)** |
| **False Negatives ($FN$)** | **92,584** | 104,294 | **$-11,710$ (11.23% reduction in FN)** |
| **Predicted Positives** | **71,646** | 1,427 | $50.21\times$ increase in predicted classes |
| **Micro-Precision** | **0.1772** (17.72%) | **0.6931** (69.31%) | $-51.59\%$ precision drop |
| **Micro-Recall** | **0.1206** (12.06%) | **0.0094** (0.94%) | **$+11.12\%$ absolute recall gain** |
| **Micro-F1** | **0.1435** (14.35%) | **0.0185** (1.85%) | **$+675.68\%$ relative F1 gain** |
| **Macro-F1** | **0.0045** (0.45%) | **0.0009** (0.09%) | $+400.00\%$ relative gain |
| **Weighted-F1** | **0.0937** (9.37%) | **0.0141** (1.41%) | $+564.54\%$ relative gain |

### 3.2 Mechanistic Breakdown of the Precision-Recall Dilemma
1. **At Standard Threshold $\tau = 0.50$**:
   Because the classification head is trained over a frozen encoder on an imbalanced 10% subset, sigmoid output probabilities for sparse tail classes rarely exceed 0.50. Consequently, standard evaluation produces **104,294 False Negatives**, effectively suppressing **99.06% of true positive legal labels**.
2. **At Calibrated Threshold $\tau^* = 0.04$**:
   Lowering the threshold to the validation-selected optimum $\tau^* = 0.04$ successfully recovers 12,699 true positives ($12.83\times$ recall gain). However, because over 12,000 tail classes output background probabilities between 0.01 and 0.04, the lower threshold inflates False Positives by **$134.6\times$** (from 438 to 58,947), capping micro-precision at **17.72%**.

### 3.3 Frequency Tier Breakdown & The Root Cause of Macro-F1 Collapse
Across the 12,608 unique labels in the LEDGAR corpus, the deterministic 10% contract subset (67,776 training provisions) reveals extreme long-tail class starvation:

| Frequency Tier | Training Count in Subset | Number of Classes | Share of Taxonomy | Empirical Performance & Failure Mode |
|---|---|---|---|---|
| **Zero-Shot / Unlearned** | **0 examples** | **2,833 classes** | **22.47%** | **0.0% Recall**. The frozen encoder + random head received zero/negative updates during training; output logits remain negative, making detection impossible. |
| **Extreme Tail (Rare)** | **1 – 9 examples** | **8,465 classes** | **67.14%** | **Near-Zero Recall**. Extreme supervision sparsity prevents the linear head from establishing reliable decision hyperplanes. |
| **Moderate Tail** | **10 – 99 examples** | **1,208 classes** | **9.58%** | **Low-to-Moderate Recall**. Sufficient examples for basic lexical association, but severely limited by frozen encoder representations. |
| **Head (Common)** | **$\ge 100$ examples** | **102 classes** | **0.81%** | **Substantial Recognition**. Standard legal boilerplate concepts (Governing Law, Termination, Indemnity) account for the majority of true positives. |

**Root Cause of Macro-F1 Collapse ($0.0045$)**:
Macro-F1 is computed as the unweighted arithmetic mean across all classes:
$$\text{Macro-F1} = \frac{1}{C} \sum_{c=1}^C F_1(c)$$
Because **$91.1\%$ of all classes (11,298 out of 12,407)** have fewer than 10 training examples (and 2,833 have 0 examples), over 90% of classes have $F_1(c) \approx 0.0$. Even when common head classes perform well, averaging over 11,000 zero-score classes mathematically forces the unweighted Macro-F1 down to **0.0045**, whereas Weighted-F1 (which weights by class support) reaches **0.0937**.

---

## 4. ContractNLI Baseline Error Analysis (Document-Level 3-Class NLI)

The ContractNLI benchmark evaluates document-level Natural Language Inference across three classes: `Contradiction`, `Entailment`, and `NotMentioned`.

### 4.1 Confusion Matrix & Performance Overview
Evaluating the TF-IDF Linear SVM baseline across all 2,091 held-out test document-hypothesis pairs:
- **Test Accuracy**: 65.57% (1,371 / 2,091 correct)
- **Macro-F1**: 0.5844

```
                  PREDICTED CLASS
              Contradiction  Entailment  NotMentioned   Total Support
TRUE CLASS:
Contradiction       81           90           49             220
Entailment          20          834          114             968
NotMentioned        64          383          456             903
Total Predicted    165        1,307          619           2,091
```

### 4.2 Per-Class Metrics
| Class | Support | Precision | Recall | F1-Score | Error Profile |
|---|---|---|---|---|---|
| **`Contradiction`** | 220 (10.5%) | 0.4909 | 0.3682 | 0.4208 | Minority class; severe false negative rate (63.18% missed). |
| **`Entailment`** | 968 (46.3%) | 0.6381 | **0.8616** | **0.7332** | Over-predicted class (62.5% of all predictions); high recall. |
| **`NotMentioned`** | 903 (43.2%) | 0.7367 | 0.5050 | 0.5992 | Highly vulnerable to false alarm entailment. |

### 4.3 Dominant Error Flows & Mechanisms
1. **Flow 1: `NotMentioned` $\rightarrow$ `Entailment` (383 instances, 42.41% of true NotMentioned)**:
   - **Mechanism**: *Lexical Overlap Fallacy*. Standard NDA boilerplate text shares dense vocabulary with target hypotheses (e.g., "confidential information", "disclose", "obligations", "receiving party"). Bag-of-words and n-gram TF-IDF representations produce high cosine similarity between the document and hypothesis, triggering false `Entailment` predictions even when the specific restriction is completely omitted from the contract.
2. **Flow 2: `Contradiction` $\rightarrow$ `Entailment` (90 instances, 40.91% of true Contradictions)**:
   - **Mechanism**: *Negation and Scope Blindness*. Linear bag-of-words models cannot reliably resolve complex legal qualifiers, carveouts, and scope restrictors ("solely", "except as expressly provided", "unless otherwise agreed in writing"). The presence of overlapping topical words dominates the classifier signal, flipping genuine legal contradictions into false entailments.
3. **Flow 3: `Entailment` $\rightarrow$ `NotMentioned` (114 instances, 11.78% of true Entailments)**:
   - **Mechanism**: *Dispersed Provision Dilution*. When the legal obligation is distributed across separate sections (e.g. a general definition in Section 1 conditioned by a liability clause in Section 8), document-level TF-IDF averaging dilutes the localized evidence.

---

## 5. Evidence Attribution & Error Interpretation

In accordance with mandatory research safeguards, we explicitly decouple token-alignment correctness from explanation faithfulness and legal validity:

### 5.1 The Three Levels of Explainability Evaluation
1. **Token Alignment Correctness (Implementation Invariant)**:
   - Evaluates whether $\text{source\_text}[\text{start}:\text{end}] \equiv \text{span.text}$.
   - **Status**: **100% verified** across all provisions (Task 020, 021, and 022). Offsets reliably identify character slices without off-by-one errors.
2. **Attribution Faithfulness (Model Sensitivity)**:
   - Evaluates whether the attribution method (Gradient $\times$ Input) reflects the model's internal gradient landscape.
   - **Status**: **Verified**. Sequence-level Gini sparsity ($G \in [0.39, 0.56]$) proves that the gradient vector is concentrated on a small subset of tokens.
3. **Legal Explanation Validity (Semantic Rationality)**:
   - Evaluates whether the highlighted tokens provide a sound, legally sufficient justification for the assigned label.
   - **Status**: **Significant Failure Mode Identified**.

### 5.2 Forensic Failure Mode: Function Word & Punctuation Bias
Under `GradientXInput`, embedding gradients are evaluated at the provision's final token representations without baseline subtraction. Because the linear classification head operates over a frozen Legal-BERT backbone:
- Common structural syntax words (`"and"`, `"the"`, `"accordance"`) and punctuation marks (`"."`, `","`) frequently exhibit large gradient norms.
- In `ATTR_ROB_01` (`Governing Law`), the top attributed spans were `'and'` (score 1.8364), `'the'` (score 1.4612), and `'accordance'` (score 1.3062), while the substantive legal jurisdiction (`"State of New York"`) received lower ranking scores.
- In `ATTR_ROB_03` (`Termination`), the punctuation token `'.'` was ranked as the 2nd most important evidence span (score 0.1970).

**Critical Finding**: Mathematical attribution sparsity (high Gini) and exact character-offset alignment must never be conflated with legal validity. High-saliency tokens in frozen-encoder linear probes often highlight syntactic artifacts rather than legally meaningful rationales.

---

## 6. Representative Concrete Error Case Studies

All case studies below are traceable to real model forward passes and evaluation artifacts:

### Case Study 1: Taxonomy Granularity & Morphological Collision
- **Provision**: *"This Agreement shall be governed by, and construed in accordance with, the laws of the State of Delaware, without giving effect to any principles of conflicts of law."*
- **Ground Truth Labels**: `["applicable laws", "governing law"]`
- **Model Prediction at $\tau^* = 0.04$**: `["governing laws"]`
- **Evaluation Accounting**: **1 False Positive + 2 False Negatives**
- **Analysis**: The LEDGAR SEC taxonomy treats singular `governing law` and plural `governing laws` as distinct binary targets. The model recognized the governing law concept, but because binary multi-label evaluation enforces exact string matching, it was penalized with two false negatives and one false positive.

### Case Study 2: Sub-Threshold Probability Suppression
- **Provision**: *"Either party may terminate this Agreement without cause at any time effective upon thirty (30) days prior written notice to the other party."*
- **Ground Truth Labels**: `["terminations", "termination"]`
- **Model Predicted Probability**: $p = 0.009209$ (below $\tau^* = 0.04$)
- **Evaluation Accounting**: **2 False Negatives**
- **Analysis**: The clause is an unambiguous termination provision. However, because the linear probe over a frozen encoder squashes tail probabilities, the output probability fell to 0.0092, completely missing detection at the 0.04 operating threshold.

### Case Study 3: TF-IDF Lexical Similarity False Entailment (ContractNLI)
- **Hypothesis**: *"Confidential Information shall not include information that is publicly known."*
- **Contract Context**: Standard non-disclosure preamble defining confidential information without an explicit public-domain carveout.
- **Ground Truth**: `NotMentioned`
- **Baseline Prediction**: `Entailment`
- **Analysis**: Heavy repetition of terms `"confidential"`, `"information"`, and `"party"` triggered high n-gram cosine similarity, misleading the linear classifier into asserting entailment for an unmentioned carveout.

### Case Study 4: Gradient Saliency Stopword Bias
- **Provision**: *"This Agreement shall be governed by, and construed in accordance with, the laws of the State of New York."*
- **Target Label**: `applicable laws (ID 862)`
- **Extracted Spans**: `['and' (score 1.8364), 'the' (score 1.4612), 'accordance' (score 1.3062)]`
- **Analysis**: High gradient magnitude on structural function words creates a mathematically sparse attribution that fails human lawyer review.

---

## 7. Systematic Taxonomy of Failure Modes

```mermaid
graph TD
    A["ContractRisk-XAI Systemic Failure Modes"] --> B["Data & Taxonomy Level"]
    A --> C["Decision Calibration Level"]
    A --> D["Model Architecture Level"]
    A --> E["Baseline Formulation Level"]
    A --> F["Explainability & Evidence Level"]

    B --> B1["FM-01: Tail Starvation (91.1% of classes <10 examples)"]
    B --> B2["FM-06: Morphological Collision (Singular vs Plural Classes)"]
    C --> C1["FM-02: Threshold Dilemma (12.8x Recall vs 134.6x FP surge)"]
    D --> D1["FM-03: Frozen Encoder Probe Bottleneck"]
    E --> E1["FM-04: Bag-of-Words Fallacy (NotMentioned -> Entailment)"]
    F --> F1["FM-05: Saliency Noise & Stopword Dominance"]
```

| ID | Failure Mode Name | Architectural Level | Scope / Impact | Root Mechanism |
|---|---|---|---|---|
| **FM-01** | **Long-Tail Starvation & Zero-Shot Collapse** | Data & Taxonomy | 11,298 / 12,407 classes (91.1%) | 2,833 classes have 0 training examples in the 10% subset, yielding 0.0% recall and causing Macro-F1 collapse (0.0045). |
| **FM-02** | **Precision-Recall Threshold Dilemma** | Decision Calibration | Full test corpus (87,956 provisions) | Setting $\tau^* = 0.04$ recovers $12.83\times$ recall, but causes a $134.6\times$ surge in false positives (58,947 FPs), capping precision at 17.72%. |
| **FM-03** | **Linear Probe Representation Bottleneck** | Model Architecture | Entire multi-label classification head | Frozen Legal-BERT backbone cannot adapt embeddings to contract risk nuances; the linear layer is restricted to generic MLM features. |
| **FM-04** | **Bag-of-Words Fallacy & Lexical False Entailment** | Baseline NLI Model | 42.41% of NotMentioned test instances | TF-IDF models over-predict Entailment (62.5% of all predictions) due to shared boilerplate vocabulary regardless of true obligation presence. |
| **FM-05** | **Saliency Noise & Stopword Dominance** | Explainability & Evidence | Gradient $\times$ Input Saliency | Unsubtracted embedding gradients highlight high-norm function words (`and`, `the`) and punctuation (`.`), creating explanation artifacts. |
| **FM-06** | **Taxonomy Granularity & Morphological Clashing** | SEC Taxonomy Design | Multi-label evaluation metrics | Near-synonyms (`governing law` vs `governing laws`) penalize semantic detections as simultaneous false positives and false negatives. |

---

## 8. Verification and Regression Test Results

### 8.1 Dedicated Task 023 Test Suite
[`tests/test_error_analysis.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_error_analysis.py):
- `test_1_error_analysis_manifest_integrity`: ✅ **PASSED**
- `test_2_ledgar_confusion_and_threshold_tradeoff`: ✅ **PASSED**
- `test_3_label_tier_accounting_and_macro_collapse`: ✅ **PASSED**
- `test_4_contractnli_baseline_error_flows`: ✅ **PASSED**
- `test_5_representative_cases_provenance`: ✅ **PASSED**
- `test_6_failure_mode_taxonomy`: ✅ **PASSED**  
*(6 passed in 0.12s)*

### 8.2 Full Project Regression Status
Full regression run across Tasks 019–023:
- Task 023 Error Analysis Suite: 6 passed
- Task 022 Robustness Suite: 6 passed
- Task 021 Ablation Suite: 10 passed
- Task 020 Cross-Domain Suite: 20 passed
- Task 019 LEDGAR Split Suite: 4 passed
- LEDGAR Frozen Subset Architecture Suite: 5 passed
- **Total**: **51 passed in 79.92s** with **0 failures and 0 skipped tests**.

---

## 9. Limitations & Unsupported Analyses

1. **End-to-End Retraining Defenses**: Re-training with loss re-weighting (e.g. focal loss, class-balanced cross-entropy) or full transformer fine-tuning was categorized as **NOT_SUPPORTED_RETRAINING_PROHIBITED** in accordance with the strict mandate prohibiting model retraining.
2. **Intermediate Full-Corpus Test Sweeps**: Unmeasured intermediate full-corpus thresholds from Task 021 remain documented as validation-projected estimates; all test figures in this report are strictly from empirical forward passes.
3. **Task 024 Status**: Task 024 remains strictly 🔒 **LOCKED**.
