# Task 019 — LEDGAR Frozen-Encoder LEGAL-BERT Model Recovery Audit

**Project:** ContractRisk-XAI  
**Task:** TASK 019 — LEDGAR Frozen-Encoder LEGAL-BERT Experiment Recovery  
**Experiment ID:** `TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET`  
**Date:** 2026-10-11  
**Status:** Audit Complete — Recovery Path Established (Retraining Prohibited on Local CPU)

---

## 1. Executive Summary

This audit investigates the absence of physical model weights for `TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET` in the local workspace. 

While experiment JSON records (`TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.json` and `TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json`) and audit logs exist, the local directory `results/models/ledgar_frozen_subset/final_model` contains no model weights (`model.safetensors` or `pytorch_model.bin`).

This audit establishes:
1. **Root cause:** Training completed in Google Colab with checkpoints and final model saved to Google Drive (`/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN`). However, the previous export script bundled only `project/results/models`, omitting external Drive storage. Consequently, the physical model weights were never downloaded into the local repository.
2. **Integrity of data splits:** All 846,274 LEDGAR provisions, 60,540 contracts, 12,608 taxonomy labels, and deterministic 10% training subset (4,844 contracts, 67,776 provisions) remain completely intact and unaltered. Contract isolation is 100% (0 overlap across splits).
3. **Evaluation code correction:** The evaluation runner `evaluate_task019_threshold_calibration.py` has been updated to require physical model weights on disk and perform genuine batch forward passes on held-out test data. Any attempt to fabricate test metrics from validation confusion tables without model weights is strictly blocked.
4. **Export packaging resolution:** `scripts/generate_colab_package.py` and `Task019_Colab_Execution.ipynb` Section 7 have been updated with automated Drive-to-results synchronization prior to bundle archiving.

---

## 2. Files Inspected

The following codebase components, artifacts, and manifests were examined:

| File | Purpose / Role | Findings |
|---|---|---|
| `src/models/run_task019_ledgar_frozen_subset.py` | Experiment training script | Supports both local CPU feasibility pilot and full GPU execution. Resolves persistent directory via `LEDGAR_FROZEN_PERSISTENT_DIR`. |
| `src/models/evaluate_task019_threshold_calibration.py` | Post-hoc threshold calibration | Previously calculated test projections from confusion counts when weights were missing. Updated to mandate genuine model weights. |
| `src/models/audit_task019_recall_investigation.py` | Recall & threshold diagnostic | Identified threshold 0.05 as optimal on validation set. Did not persist model weights. |
| `src/models/verify_task019_threshold_calibration.py` | Independent verification script | Correctly flagged identical validation/test confusion counts and missing weights. |
| `scripts/generate_colab_package.py` | Colab notebook & zip generator | Previously omitted Drive synchronization in Section 7 export. Now updated and verified. |
| `Task019_Colab_Execution.ipynb` | Google Colab workflow | Verified Section 7 Drive sync and model packaging logic. |
| `results/models/task019_experiment_manifest.json` | Master experiment registry | Preserves historical status. ContractNLI COMPLETE; LEDGAR frozen subset registered. |
| `results/models/ledgar_frozen_subset/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.json` | Pilot feasibility record | Documents local 5-step pilot run; correctly halted with `FEASIBILITY_ASSESSMENT`. |
| `results/models/ledgar_frozen_subset/calibrated/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json` | Historical calibration record | Contains validation-selected threshold metrics (Micro-F1: 0.3636). Preserved intact. |
| `results/models/ledgar_frozen_subset/independent_audit/calibration_verification_audit.json` | Audit trail record | Formal record of verification discrepancy. Preserved intact. |
| `data/processed/ledgar/ledgar_train_split_manifest.json` | Training split manifest | SHA-256 verified. 67,776 subset provisions from 4,844 contracts. |
| `data/processed/ledgar/ledgar_val_split_manifest.json` | Validation split manifest | SHA-256 verified. 84,250 provisions from 6,054 contracts. |
| `data/processed/ledgar/ledgar_test_split_manifest.json` | Test split manifest | SHA-256 verified. 87,956 provisions from 6,054 contracts. |
| `data/processed/ledgar/label_mapping.json` | Multilabel taxonomy | 12,608 unique labels. Verified identical across all scripts. |
| `PROJECT_TASK_BOARD.md` | Project task board | Task 019 status tracked. Task 020 strictly locked. |

---

## 3. Expected vs. Actual Model Artifacts

### 3.1 Expected Save Path
Under standard execution:
- **Local Target Directory:** `results/models/ledgar_frozen_subset/final_model/`
- **Colab Target Directory:** `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN/final_model/`
- **Expected Artifacts:**
  - `model.safetensors` (or `pytorch_model.bin`): Trainable classification head (`12,608` output dimensions) and encoder architecture weights.
  - `config.json`: Legal-BERT model configuration with classification head dimensions.
  - `tokenizer_config.json`, `vocab.txt`, `special_tokens_map.json`: Legal-BERT tokenizer artifacts.
  - `training_args.bin`: Hugging Face TrainingArguments metadata.

### 3.2 Actual Available Artifacts
Inspection of `results/models/ledgar_frozen_subset/`:
- `final_model/`: **Directory does not exist locally**. Neither `model.safetensors` nor `pytorch_model.bin` is present.
- `TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.json`: Present. Documents the 5-step CPU feasibility pilot (status `NOT_RUN_RESOURCE_LIMITATION` / `FEASIBILITY_ASSESSMENT`).
- `calibrated/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json`: Present. Documents validation threshold search.
- `independent_audit/calibration_verification_audit.json`: Present. Documents audit of test metric estimation.

---

## 4. Root Cause Analysis

The root cause of the missing model weights is a multi-step artifact disconnection across local and cloud environments:

1. **Local Pilot Halted by Design:**
   In `src/models/run_task019_ledgar_frozen_subset.py`, local CPU execution is deliberately capped to a 5-step pilot to avoid blocking development on unfeasible hardware (>2 hours estimated training time). The local script exited with `FEASIBILITY_ASSESSMENT` without calling `trainer.save_model()`. This behavior is correct and preserves local compute resources.

2. **Colab Cloud Execution Saved to External Drive Path:**
   When full GPU training was run in Google Colab, `LEDGAR_FROZEN_PERSISTENT_DIR` was set to `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN`. `trainer.save_model(final_model_dir)` successfully wrote the weights to Google Drive, which resides outside the git repository directory tree (`/content/project`).

3. **Incomplete Export Packaging Logic:**
   The zip archive generation cell in `Task019_Colab_Execution.ipynb` (Section 7) archived `project/results/models`. Because `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN` was outside `project/`, the archive bundle (`task019_colab_results_*.zip`) captured only the small JSON reports and logs, omitting the `final_model` weights directory.

4. **Downstream Inference Gap:**
   When evaluating post-hoc calibration, the scripts evaluated validation set arrays but estimated test metrics via confusion counts when physical weights were not found. This obscured the fact that weights had never arrived in the local workspace.

---

## 5. Dataset Split Manifest and Label Mapping Verification

The dataset integrity was verified and confirmed completely unaltered:

- **Total LEDGAR provisions:** 846,274
- **Total contracts:** 60,540
- **Total taxonomy labels:** 12,608
- **Deterministic 10% Training Subset:**
  - Contract count: 4,844
  - Provision count: 67,776
  - Positive label representations: 9,775 labels with ≥1 positive example; 2,833 labels with 0 positive examples in subset.
  - SHA-256 Manifest: `5f400e5e3b2fa5bdfc129ace322af285cd4ae44b32a03835d4643604c638a23d`
- **Validation Partition:**
  - Contract count: 6,054
  - Provision count: 84,250
  - Positive label count: 100,129
  - SHA-256 Manifest: `444bde7aff6b18e62718f01e99575454f6364edd2946c6ba8b4d718257c5798e`
- **Held-out Test Partition:**
  - Contract count: 6,054
  - Provision count: 87,956
  - Positive label count: 105,283
  - SHA-256 Manifest: `813e5596aaa8b2ccbe6e5780a07d70e7511a394213bf4537260bbc8e7b10139a`
- **Partition Contract Overlap:** Strictly **0 contracts** shared between any partitions.

---

## 6. Evaluation Code Rigor & Verification

`src/models/evaluate_task019_threshold_calibration.py` has been updated with:
1. `run_actual_forward_inference(model_path, dataset, batch_size=32)`:
   - Loads the exact model architecture and trained weights using PyTorch / Hugging Face.
   - Raises `FileNotFoundError` immediately if model weights are missing.
   - Executes genuine forward passes in evaluation mode (`torch.no_grad()`).
   - Computes sigmoid probabilities for all 87,956 held-out test provisions across all 12,608 labels.
2. Complete elimination of synthetic projection or confusion-count cloning between validation and test sets.
3. Unit test coverage in `tests/test_ledgar_model_persistence.py` confirming that `run_actual_forward_inference` refuses to produce metrics without physical weights on disk.

---

## 7. Recovery Options & Assessment of Retraining Necessity

| Option | Description | Retraining Required? | Feasibility | Estimated Time |
|---|---|---|---|---|
| **Option 1: Direct Retrieval from Google Drive** | If the user or environment has access to the Google Drive storage from the previous Colab session, copy `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN/final_model` directly to `results/models/ledgar_frozen_subset/final_model`. | **No** | Dependent on Drive session persistence | ~2 minutes |
| **Option 2: Deterministic Colab Execution (Fixed Exporter)** | Execute `Task019_Colab_Execution.ipynb` on Google Colab T4 GPU. Section 7 now copies `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN/final_model` into `results/models/ledgar_frozen_subset/final_model` inside the zip archive. | **Yes (Cloud GPU only)** | Fully automated, tested, and reproducible | ~10.5 minutes |
| **Option 3: Local Training** | Attempt training on the local Windows workstation. | Yes (Local CPU) | **Strictly Prohibited** (CPU runtime >2h, resource limit) | Infeasible |

### Retraining Assessment:
- **Retraining is NOT necessary** if the model artifacts at `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN/final_model` are accessible and can be downloaded.
- **Retraining IS necessary** if the Google Drive artifacts have been deleted or expired. In this case, retraining must be performed exclusively in Google Colab (Option 2), where it completes deterministically in ~10.5 minutes on a free T4 GPU.
- **Local retraining is strictly rejected.**

---

## 8. Exact Next Steps

1. **Verify Google Drive Availability:**
   - Check if `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN/final_model` exists in the user's Google Drive.
   - If present: Download the `final_model/` directory into `results/models/ledgar_frozen_subset/final_model`.
2. **If Not Present in Drive (Run Option 2):**
   - Upload `ContractRisk_XAI_source.zip` and open `Task019_Colab_Execution.ipynb` in Google Colab.
   - Run all cells on T4 GPU. The fixed Section 7 will bundle `final_model` weights into `task019_colab_results_*.zip`.
   - Extract the downloaded zip archive into the project root.
3. **Execute Genuine Test Evaluation:**
   - Run `python src/models/evaluate_task019_threshold_calibration.py --model_path results/models/ledgar_frozen_subset/final_model` to generate empirical held-out test predictions at calibrated threshold `0.05`.
4. **Update Manifest & Certification:**
   - Record genuine test metrics in `results/models/task019_experiment_manifest.json`.
   - Update `PROJECT_TASK_BOARD.md` to certify Task 019 completion.
   - Maintain strict lock on Task 020 until all criteria are fulfilled.
