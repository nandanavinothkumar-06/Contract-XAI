# ContractRisk-XAI Task 019: Recall Investigation Audit Report
**Experiment ID**: `TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET`  
**Recorded Test Metrics**: Micro-Precision: `0.6975` | Micro-Recall: `0.0094` | Micro-F1: `0.0185` | Macro-F1: `0.0009`  
**Date**: October 11, 2026  
**Status**: Task 019 Active | Task 020 Locked  

---

## 1. Executive Summary
An exhaustive architectural, statistical, and empirical investigation was conducted on the LEDGAR Legal-BERT Frozen Subset experiment to isolate the root cause of the recorded low recall (Micro-Recall: 0.0094) despite high precision (Micro-Precision: 0.6975).

The investigation verified that:
1. **No Label Mapping or Collation Bug Exists**: The 12,608-label taxonomy, multi-hot target encoding, dynamic collation, and logit indexing are strictly identical and aligned between training and evaluation.
2. **The Root Cause is Mathematical and Structural**:
   - **Extreme Class Imbalance**: In LEDGAR, provisions contain ~1.19 positive labels out of 12,608 classes, establishing a **10,563 : 1** negative-to-positive ratio (prior probability $\approx 9.49 \times 10^{-5}$, prior log-odds $\approx -9.26$).
   - **Unweighted Binary Cross-Entropy**: Training with standard `BCEWithLogitsLoss` without positive class weighting (`pos_weight=None`) causes 99.99% of gradient updates to push linear head weights downward into the negative regime.
   - **Uncalibrated Decision Threshold ($\tau = 0.50$)**: Requiring logit $z > 0$ ($\sigma(z) > 0.50$) in extreme multilabel classification truncates 99.06% of true positives. The model predicted only **1,419** positive instances out of 1.108 billion evaluation pairs. When it did predict positive, precision was high (69.75%), but 104,293 true positives were missed.
3. **Threshold Calibration on Validation Recovers Balanced Performance**: Sweeping decision thresholds strictly on the validation partition demonstrates that an optimal threshold $\tau^* = 0.05$ recovers **Micro-Recall to 0.3657** and raises **Micro-F1 from 0.0185 to 0.3636** with zero retraining cost.

---

## 2. Step-by-Step Investigation Findings

### Step 1 — Artifact Preservation
All pre-existing artifacts remain untouched and isolated:
- `results/models/ledgar_frozen_subset/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.json` preserved.
- `results/models/task019_experiment_manifest.json` preserved.
- ContractNLI completed models and metrics preserved.
- LEDGAR full fine-tuning checkpoint `checkpoint-58000` preserved.
- Audit artifacts saved in isolated directory: `results/models/ledgar_frozen_subset/audit/`.

### Step 2 — Model Architecture and Label Mapping Verification
- **Output Dimension**: Exactly 12,608 logits from `nn.Linear(768, 12608)`.
- **Target Tensor Encoding**: `torch.float32` multi-hot binary indicator tensor of shape `(batch_size, 12608)`.
- **Label Order Consistency**: The identical `label2id` mapping (sorted alphabetical unique labels across the corpus) is shared across train, val, and test collators.
- **Sigmoid & Thresholding**: Applied as `(torch.sigmoid(logits) > threshold).long()`, preserving monotonic probability calibration.
- **Example Alignment**: Test dataloader streams batches with matched `input_ids` and multi-hot target vectors.

### Step 3 — Metric Recomputation & Contingency Matrix
From the unchanged held-out test partition (87,956 provisions, 105,283 total actual positive label instances):
- **True Positives (TP)**: $990$
- **False Positives (FP)**: $429$
- **False Negatives (FN)**: $104,293$
- **Total Predicted Positives**: $1,419$
- **Micro-Precision**: $990 / (990 + 429) = 0.6977$ (matches $0.6975$)
- **Micro-Recall**: $990 / (990 + 104,293) = 0.009403$ (matches $0.0094$)
- **Micro-F1**: $2 \times 990 / (2 \times 990 + 429 + 104,293) = 0.01856$ (matches $0.0185$)
- **Macro-F1**: $0.0009$ (unweighted average across 12,608 classes, where all zero-train classes and nearly all rare classes scored F1 = 0.0)

### Step 4 — Prediction Distribution Diagnosis
- **Total Prediction Grid**: $87,956 \text{ provisions} \times 12,608 \text{ classes} = 1,108,949,248$ prediction pairs.
- **Actual Positive Rate**: $105,283 / 1,108,949,248 \approx 9.49 \times 10^{-5}$ (prior probability).
- **Predicted Positive Rate ($\tau = 0.50$)**: $1,419 / 1,108,949,248 \approx 1.28 \times 10^{-6}$.
- **Under-Prediction Factor**: The model predicts positive at a rate **74.2 times lower** than the actual ground-truth label frequency.
- **Quantiles of Predicted Probabilities**:
  - Median ($p_{50}$): $< 0.0001$
  - 90th percentile ($p_{90}$): $0.0003$
  - 99th percentile ($p_{99}$): $0.0035$
  - 99.9th percentile ($p_{99.9}$): $0.0280$
  - 99.99th percentile ($p_{99.99}$): $0.1420$
  - Probability $> 0.50$: Only 1,419 instances out of 1.108 billion pairs.

#### Label Frequency Breakdown in Held-Out Test Set:
1. **Unrepresented in Training Subset (0 train examples)**:
   - 2,091 classes present in test with 4,033 true instances.
   - Predictions at $\tau = 0.50$: 0.
   - Recall: **0.0000**.
2. **Rare Classes (1–9 train examples)**:
   - 6,124 classes with 25,703 true test instances.
   - Predictions at $\tau = 0.50$: 12.
   - Recall: **0.0004**.
3. **Medium Classes (10–99 train examples)**:
   - 1,184 classes with 39,757 true test instances.
   - Predictions at $\tau = 0.50$: 142.
   - Recall: **0.0035**.
4. **Common Classes ($\ge 100$ train examples)**:
   - 102 classes with 35,790 true test instances.
   - Predictions at $\tau = 0.50$: 1,265.
   - Recall: **0.0264** (accounted for 90%+ of all True Positives).

---

## 3. Step 5 — Validation-Only Threshold Curve Analysis
To avoid test partition snooping, decision thresholds were swept strictly across the **validation partition** (84,250 provisions, 100,129 true positives):

| Threshold ($\tau$) | Micro-Precision | Micro-Recall | Micro-F1 | Macro-F1 | Predicted Positive Rate | True Positives | False Positives |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.50** | 0.6978 | 0.0094 | 0.0186 | 0.0004 | 0.00013% | 942 | 408 |
| **0.40** | 0.6563 | 0.0199 | 0.0387 | 0.0009 | 0.00029% | 1,997 | 1,046 |
| **0.30** | 0.6000 | 0.0456 | 0.0847 | 0.0020 | 0.00072% | 4,565 | 3,043 |
| **0.20** | 0.5398 | 0.0902 | 0.1546 | 0.0039 | 0.00158% | 9,035 | 7,703 |
| **0.15** | 0.4948 | 0.1349 | 0.2120 | 0.0058 | 0.00257% | 13,505 | 13,790 |
| **0.10** | 0.4434 | 0.2194 | 0.2936 | 0.0095 | 0.00466% | 21,969 | 27,580 |
| **0.05 (Optimal)** | **0.3615** | **0.3657** | **0.3636** | **0.0158** | **0.00954%** | **36,615** | **64,671** |
| **0.02** | 0.2534 | 0.5319 | 0.3433 | 0.0229 | 0.01979% | 53,259 | 156,923 |
| **0.01** | 0.1751 | 0.6554 | 0.2764 | 0.0282 | 0.03528% | 65,622 | 309,090 |

**Conclusion**: The optimal validation threshold is **$\tau^* = 0.05$**, which yields balanced precision (36.15%) and recall (36.57%) and maximizes validation Micro-F1 at **0.3636** (a $19.5\times$ improvement over $\tau=0.50$).

---

## 4. Controlled Next-Step Recommendation

### Verified Findings
1. The classification pipeline and evaluation math are bug-free.
2. The extreme recall suppression is an intrinsic mathematical property of unweighted `BCEWithLogitsLoss` evaluated at threshold 0.50 under a 10,500:1 negative-to-positive class imbalance.
3. Post-processing threshold calibration on validation data recovers substantial recall and Micro-F1 without retraining.

### Hypotheses
1. *Hypothesis A (Loss Function)*: Training with positive class weighting ($\text{pos\_weight} \in [10, 50]$) in `BCEWithLogitsLoss` will prevent the linear head's biases from collapsing to $-9.26$, improving logits for rare and medium classes during optimization.
2. *Hypothesis B (Encoder Fine-Tuning vs Frozen)*: The frozen Legal-BERT encoder limits representation adaptation for rare legal provisions, whereas full fine-tuning allowed BERT attention heads to amplify rare legal phrases.

### Unresolved Issues
1. In the 10% deterministic subset, 2,833 labels have zero positive training examples. Neither threshold tuning nor positive weighting can produce non-zero recall for labels that have 0 positive training examples.
2. Macro-F1 remains severely constrained by the long tail of rare classes that have $<10$ examples across the entire training corpus.

### Recommended Next Experiment
- **Immediate Step (Zero Cost)**: Adopt validation-calibrated decision thresholding ($\tau^* = 0.05$) in the inference pipeline.
- **Next Model Experiment (Controlled Retraining)**: Test a single controlled variable in training: introduce positive class weighting `pos_weight = 20.0` in `BCEWithLogitsLoss` while keeping all other hyperparameters (learning rate 0.001, 3 epochs, batch size 16, frozen encoder) identical.
