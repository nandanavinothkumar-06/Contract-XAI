# Offline Abstention Policy Comparison: Synthetic Engineering Validation

> [!WARNING]
> **SYNTHETIC ENGINEERING VALIDATION — NOT REAL-CONTRACT EVIDENCE**  
> All data analyzed in this report consists of fictional synthetic candidate records and mock reference decisions generated for software pipeline validation only. It does **not** represent real-world commercial contracts, does **not** establish LegalBERT model accuracy, and does **not** prove the empirical superiority of any legal research hypothesis.

---

## 1. Overview and Engineering Objective

This report documents the offline engineering validation comparing two candidate triage policies:
1. **Policy A (Confidence-Only Baseline):** Automatically retains candidates whose raw model confidence meets a continuous threshold $\tau_{\text{conf}} \in [0.0, 1.0]$, ignoring document version and statutory evidence status (while strictly enforcing input assessability and model label space safety gates).
2. **Policy B (Evidence-Aware Policy):** Evaluates candidates under the formal Five-Tier Precedence Cascade implemented in [`src/abstention/evidence_policy.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/abstention/evidence_policy.py), conditioning retention on document version consistency, statutory currentness, evidence sufficiency, and label space mappings.

Both policies were evaluated on the **exact same synthetic candidate pool** using the standardized metrics suite in [`src/evaluation/abstention_eval.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/evaluation/abstention_eval.py).

---

## 2. Experimental Execution Configuration

- **Execution Command:**
  ```bash
  python scripts/evaluate_abstention_comparison.py --seed 42 --step 0.01 --output-dir results/synthetic_evaluation
  ```
- **Random Seed:** `42` (deterministic reproducibility)
- **Total Synthetic Candidates:** 58
- **Unique Synthetic Contracts:** 15 (demonstrating clause clustering within document clusters)
- **Continuous Threshold Grid:** 101 points ($\tau_{\text{conf}} \in [0.00, 1.00]$, step 0.01)
- **Coverage Matching Tolerance:** $\pm 0.02$
- **Evidence-Aware Policy ID:** `evidence_aware_policy_v1` (Version: `1.0.0`, Default Confidence Threshold: `0.50`)

---

## 3. Matched-Coverage Comparison Results

The continuous threshold sweep identified the baseline operating point achieving the closest Useful-Finding Coverage (UFC) within the prespecified $\pm 0.02$ tolerance:

| Evaluation Dimension | Confidence-Only Baseline ($\tau_{\text{conf}} = 0.57$) | Evidence-Aware Policy (`evidence_aware_policy_v1`) | Difference / Delta ($\Delta$) | Status & Invariants |
| :--- | :---: | :---: | :---: | :--- |
| **Operational Action Rule** | $c(F) \ge 0.57$ | Five-Tier Precedence Cascade | — | Standardized harness |
| **Total Retention Rate (RR)** | 62.07% (36/58) | 31.03% (18/58) | -31.04% | Automatic retention |
| **Useful-Finding Coverage (UFC)** | **0.6818** (15/22) | **0.6818** (15/22) | **0.0000** | **Exact match ($\le \pm 0.02$)** |
| **Unsupported-Finding Rate (UFR)** | **41.67%** (15/36) | **16.67%** (3/18) | **+0.2500** | **$\Delta\text{UFR}_{@\text{MatchedUFC}} = +25.00\%$** |
| **Human Review Workload (HRW)** | 1.72% (1/58) | 29.31% (17/58) | +27.59% | Triage to advocate |
| **Stale-Evidence Acceptance (SEAR)** | 8.33% (3/36) | **0.00%** (0/18) | -8.33% | Stale draft safety |
| **Unnecessary Abstention Rate (UAR)**| 12.28% (7/57) | 12.28% (7/57) | 0.00% | Preserved utility |
| **Coverage Matching Status** | — | — | — | **`MATCHED_COVERAGE_ACHIEVED`** |

---

## 4. Key Engineering Observations on Synthetic Data

1. **Safety Suppression of Outdated Contract Versions:**
   - The confidence-only baseline accepted 3 candidate findings generated on outdated draft contract text (`VersionConsistencyStatus.STALE`) simply because their confidence scores exceeded 0.57.
   - The evidence-aware policy suppressed 100% of stale-version candidates under Tier 2 (`STALE_DOCUMENT_VERSION`), driving $\text{SEAR}_{\text{stale}}$ to 0.0%.
2. **Advocate Triage of Legally Nuanced Findings:**
   - Under the evidence-aware policy, genuine high-severity findings with incomplete statutory evidence or provisions with researcher text differences were safely routed to `REVIEW_REQUIRED` (29.31% workload) rather than being blindly accepted without review or discarded.
3. **Non-Statutory Commercial Risk Preservation:**
   - Fictional commercial risks (such as price adjustments) without statutory matches were correctly retained under Tier 5 (`VALID_NON_STATUTORY_COMMERCIAL_FINDING`), proving that missing statutory passages do not cause erroneous abstention on non-statutory clauses.
4. **Deterministic Tie-Breaking:**
   - When multiple baseline thresholds yielded identical useful-finding coverage, the script selected the higher, more conservative threshold ($\tau = 0.57$), strictly following the documented non-outcome tie-break.

---

## 5. Artifact Directory Inventory

The execution generated the following files in [`results/synthetic_evaluation/`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/synthetic_evaluation):

1. [`synthetic_candidate_pool.jsonl`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/synthetic_evaluation/synthetic_candidate_pool.jsonl): Full dump of all 58 candidate records with reference annotations and metadata.
2. [`confidence_threshold_sweep.csv`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/synthetic_evaluation/confidence_threshold_sweep.csv): Tabular metric results for all 101 baseline thresholds ($\tau \in [0.00, 1.00]$).
3. [`matched_coverage_comparison.csv`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/synthetic_evaluation/matched_coverage_comparison.csv): Direct matched-coverage comparison row between baseline and evidence-aware policy.
4. [`synthetic_evaluation_summary.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/synthetic_evaluation/synthetic_evaluation_summary.json): Machine-readable execution summary with full policy configurations and evaluation metadata.

---

## 6. Methodological Safeguards and Limitations

1. **No Legal Accuracy Claim:** The reduction in UFR observed on synthetic fixtures confirms that the software cascade operates as designed; it does **not** prove that the policy will achieve identical gains on real commercial contracts.
2. **Decoupled Architecture:** Neither policy has been wired into the live web workbench (`src/review/service.py`).
3. **Task Constraints Preserved:**
   - Task 028 and Task 029 remain strictly **`🔒 LOCKED`**.
   - Task 042 remains strictly **`NOT STARTED`**.
   - No database migrations, model fine-tuning, or live inference operations were conducted.
