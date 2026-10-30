# Task 019 — LEDGAR Label Alignment & Model Persistence Audit Report

**Project:** ContractRisk-XAI  
**Task:** TASK 019 — LEDGAR Frozen-Encoder LEGAL-BERT Experiment (Label Recovery & Persistence Audit)  
**Experiment ID:** `TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET`  
**Date:** 2026-10-12  
**Status:** Label Alignment Proven (12,407 Classes) — Model Persistence Verified — Evaluation Unblocked

---

## 1. Executive Summary

This report establishes the complete, mathematically proven investigation into the label-to-index mapping used during training of the 3-epoch frozen-encoder LEGAL-BERT LEDGAR subset model.

### Key Verified Findings:
1. **Classifier Head Architecture:** The physical classifier tensor `classifier.weight` in `model.safetensors` has shape `[12407, 768]`. It was initialized with $12,407$ output classes.
2. **Saved Label Mapping:** `final_model/label_mapping.json` contains exactly $12,407$ labels, strictly contiguous across indices $[0, 12406]$, with exact bijective inverse `id2label`.
3. **Training-Time Mapping Identity:** Training targets were constructed directly in-memory from `all_labels = sorted(list(set(l for labels in subset_df["labels"] for l in labels)))`, where `subset_df` comprises the 10% training subset (67,776 provisions), the full validation set (84,250 provisions), and the full test set (87,956 provisions). The exact in-memory `label2id` dictionary was serialized to `final_model/label_mapping.json` at epoch completion.
4. **The 201 Excluded Labels:** Exactly $201$ rare labels from the full clean taxonomy ($12,608$ labels) appeared exclusively in the 90% unselected training contracts. They have **strictly 0 occurrences** in the 10% training subset, **0 in validation**, and **0 in test**.
5. **No Negative Impact on Evaluation:** Because the 201 excluded labels never occur in validation or test data, their omission from the output head does not reduce true positives or test recall.
6. **Alphabetical Shift Proven:** The first 173 labels (indices $0$ to $172$) match the canonical alphabetical taxonomy identically. Canonical index 173 (`'acknowledgment of liens'`) is the first excluded label, producing a deterministic $+1$ index shift starting at canonical index 174 (`'acknowledgment of no defenses'`).

---

## 2. Phase A — Label Alignment Verification

| Property | Canonical Clean LEDGAR | Saved Model Mapping | Verified Alignment |
|---|---|---|---|
| **Total Labels** | 12,608 | 12,407 | Exact difference: 201 |
| **Index Contiguity** | $[0, 12607]$ | $[0, 12406]$ | 100% Contiguous |
| **Inverse Bijection** | $\text{id2label}[\text{label2id}[x]] = x$ | $\text{id2label}[\text{label2id}[x]] = x$ | 100% Exact Inverse |
| **Overlapping Labels** | 12,407 | 12,407 | 12,407 Shared (100%) |
| **Extra Saved Labels** | 0 | 0 | 0 Extra |
| **Excluded Labels in Train Subset** | — | — | **0 occurrences** |
| **Excluded Labels in Validation** | — | — | **0 occurrences** |
| **Excluded Labels in Held-Out Test** | — | — | **0 occurrences** |

### Mathematical Evidence of Index Shift:
- Indices $0$ through $172$: Exactly identical alphabetical position between canonical 12,608 and subset 12,407 mappings.
- Index 173 in canonical taxonomy: `'acknowledgment of liens'` (excluded: 0 examples in subset).
- Index 173 in subset mapping: `'acknowledgment of no defenses'` (canonical index 174).
- Deterministic shift: $i_{\text{subset}} = i_{\text{canonical}} - 1$ for all subsequent labels until the next omitted label.

---

## 3. Phase B — Model Persistence Verification

### 3.1 Safeguard Compliance
1. **Original Model Preservation:** The directory `/content/drive/MyDrive/ContractRisk_XAI_LEDGAR_FROZEN/TASK019_FINAL_RUN/final_model` and its backup `final_model_backup` are preserved completely untouched.
2. **Read-Only Configuration Rule:** In `final_model/config.json`, `num_labels` was saved as unassigned by Hugging Face `trainer.save_model()`. The original `config.json` is not altered. At reload time, `AutoModelForSequenceClassification.from_pretrained(model_dir, num_labels=12407)` instantiates the classifier with the verified 12,407 classes.
3. **Logit Output Verification:** When reloaded into memory, a dummy forward pass produces logits with shape `[1, 12407]`.
4. **Tokenizer Compatibility:** Tokenizer vocabulary (`vocab.txt`) contains 30,522 tokens matching `nlpaueb/legal-bert-base-uncased`.

---

## 4. Phase C & D — Validation Calibration and Held-Out Test Inference

### 4.1 Root Cause of Cloud Execution Halt
During the Google Colab run:
1. Three epochs of training on the 10% subset completed successfully.
2. Checkpoints (steps 500, 1000, 1500, etc.) were saved and verified.
3. Cell 6b executed `verify_model_persistence(model_dir, expected_num_labels=12608)`.
4. Because `expected_num_labels=12608` was hardcoded while the trained model and `label_mapping.json` had 12,407 classes, the assertion raised `ValueError` and halted Colab before Stage 6c could execute.

### 4.2 Non-Destructive Remediation Implemented
1. `src/models/evaluate_task019_threshold_calibration.py`:
   - Updated `verify_model_persistence(model_dir, expected_num_labels=None)` to dynamically read `actual_num_labels` from `label_mapping.json` (12,407).
   - Updated model loading to supply `num_labels=target_num_labels` dynamically.
2. `Task019_Colab_Execution.ipynb`:
   - Stage 6b updated to call `verify_model_persistence(model_dir)`.
   - Stage 6c updated to initialize `MemorySafeLedgarCollator(tokenizer, label_map, num_unique_labels=len(label_map))`.
   - Stage 7 updated to verify the exported model with `len(label_mapping.json)` (12,407).
3. `scripts/generate_colab_package.py` & `ContractRisk_XAI_source.zip`:
   - Regenerated and verified against all 254 unit tests.

### 4.3 Mandatory Safeguard 3: Prohibition of Fabricated Metrics
In accordance with Strict Safeguard 3 (*"Do not fabricate, estimate, or project evaluation metrics"*), no synthetic test scores have been manufactured. Genuine empirical forward passes on the 84,250 validation and 87,956 test provisions will be performed in the unblocked Colab execution cells.

---

## 5. Phase E — Artifact Inventory

| Artifact Path | Description |
|---|---|
| `results/models/ledgar_frozen_subset/TASK019_LEDGAR_LABEL_ALIGNMENT_AND_PERSISTENCE_AUDIT.json` | Master audit & alignment JSON record |
| `docs/task019_label_alignment_and_persistence_audit.md` | Formal audit documentation |
| `src/models/evaluate_task019_threshold_calibration.py` | Remediated threshold calibration & persistence runner |
| `scripts/generate_colab_package.py` | Package generator with dynamic 12,407 support |
| `Task019_Colab_Execution.ipynb` | Colab notebook with unblocked stages 6b, 6c, and 7 |
| `ContractRisk_XAI_source.zip` | Source bundle for Cloud execution |
| `tests/test_ledgar_model_persistence.py` | 15 passing persistence unit tests (including 12,407 test) |

---

## 6. Task Status & Recommendation

- **Task 019 Status:** 🟡 **IN PROGRESS** (Audit & Label Alignment Complete; Cloud GPU Evaluation Unblocked).
- **Task 020 Status:** 🔒 **LOCKED** (Retained locked until empirical evaluation artifacts are synced and verified).
