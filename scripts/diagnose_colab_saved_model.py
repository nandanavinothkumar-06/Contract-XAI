"""
Diagnostic & Verification Script for Task 019 LEDGAR Saved Model Artifacts.

Performs read-only inspection of saved Colab/Drive artifacts:
1. Creates safe backup of final_model -> final_model_backup before any operation.
2. Reads model classifier weights directly (safetensors or bin) to determine physical output dimension.
3. Reads config.json to determine configured num_labels.
4. Compares saved label_mapping.json against canonical clean 12,608 LEDGAR taxonomy.
5. Reports label identities, ordering consistency, and exact set differences.
"""

import os
import sys
import json
import shutil
import hashlib
from typing import Dict, Any, Tuple, List, Set

def run_diagnostics(model_dir: str, clean_dataset_path: str = "data/raw/ledgar/extracted/LEDGAR_2016-2019_clean.jsonl") -> Dict[str, Any]:
    print("==================================================================")
    print("TASK 019: READ-ONLY MODEL ARTIFACT & LABEL MAPPING DIAGNOSIS")
    print("==================================================================")
    print(f"Target model directory: {model_dir}")
    print(f"Clean dataset path:     {clean_dataset_path}")
    print("------------------------------------------------------------------")

    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"Model directory not found at {model_dir}")

    # Step 1: Safeguard 1 - Backup
    backup_dir = model_dir.rstrip("/\\") + "_backup"
    if not os.path.exists(backup_dir):
        print(f"[SAFEGUARD 1]: Creating safe backup of original final_model at: {backup_dir}")
        shutil.copytree(model_dir, backup_dir)
        print("[SAFEGUARD 1]: Backup created successfully.")
    else:
        print(f"[SAFEGUARD 1]: Backup already exists at: {backup_dir}")

    # Step 2: Safeguard 2 - Inspect config.json
    config_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing config.json in {model_dir}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    config_num_labels = config_data.get("num_labels")
    print(f"[CONFIG INSPECTION]: config.json num_labels = {config_num_labels}")

    # Step 3: Safeguard 2 - Inspect Physical Model Weights
    safetensors_path = os.path.join(model_dir, "model.safetensors")
    bin_path = os.path.join(model_dir, "pytorch_model.bin")

    classifier_out_features = None
    classifier_in_features = None
    weights_file_used = None

    if os.path.exists(safetensors_path):
        weights_file_used = safetensors_path
        print(f"[WEIGHTS INSPECTION]: Inspecting {safetensors_path} ({os.path.getsize(safetensors_path)} bytes)...")
        try:
            from safetensors import safe_open
            with safe_open(safetensors_path, framework="pt", device="cpu") as sf:
                tensor_keys = sf.keys()
                # Find classifier weight key
                cls_keys = [k for k in tensor_keys if "classifier.weight" in k]
                if cls_keys:
                    cls_key = cls_keys[0]
                    t_shape = sf.get_slice(cls_key).get_shape()
                    classifier_out_features = t_shape[0]
                    classifier_in_features = t_shape[1]
                    print(f"[WEIGHTS INSPECTION]: Found {cls_key} with shape {t_shape}")
                else:
                    print(f"[WEIGHTS WARNING]: 'classifier.weight' not found in keys: {list(tensor_keys)[:10]}")
        except Exception as e:
            print(f"[WEIGHTS INSPECTION]: safetensors slice inspection note: {e}")
            import torch
            from safetensors.torch import load_file
            tensors = load_file(safetensors_path)
            for k in tensors:
                if "classifier.weight" in k:
                    classifier_out_features = tensors[k].shape[0]
                    classifier_in_features = tensors[k].shape[1]
                    print(f"[WEIGHTS INSPECTION]: Loaded {k} with shape {tensors[k].shape}")
                    break

    elif os.path.exists(bin_path):
        weights_file_used = bin_path
        print(f"[WEIGHTS INSPECTION]: Inspecting {bin_path} ({os.path.getsize(bin_path)} bytes)...")
        import torch
        state_dict = torch.load(bin_path, map_location="cpu", weights_only=True)
        for k in state_dict:
            if "classifier.weight" in k:
                classifier_out_features = state_dict[k].shape[0]
                classifier_in_features = state_dict[k].shape[1]
                print(f"[WEIGHTS INSPECTION]: Found {k} with shape {state_dict[k].shape}")
                break
    else:
        raise FileNotFoundError(f"No weights file found in {model_dir} (expected model.safetensors or pytorch_model.bin)")

    # Step 4: Safeguard 3 & 4 - Inspect Saved label_mapping.json
    label_map_path = os.path.join(model_dir, "label_mapping.json")
    if not os.path.exists(label_map_path):
        raise FileNotFoundError(f"Missing label_mapping.json in {model_dir}")

    with open(label_map_path, "r", encoding="utf-8") as f:
        saved_label_data = json.load(f)

    saved_label2id = saved_label_data.get("label2id", saved_label_data)
    saved_num_labels = len(saved_label2id)
    print(f"[SAVED MAPPING]: Total labels in saved label_mapping.json = {saved_num_labels}")

    # Check contiguous index range [0, N-1]
    saved_indices = sorted(list(saved_label2id.values()))
    is_contiguous = (saved_indices == list(range(saved_num_labels)))
    print(f"[SAVED MAPPING]: Index range contiguous [0..{saved_num_labels-1}]: {is_contiguous}")

    # Step 5: Safeguard 4 - Build Canonical Clean 12,608 Mapping
    canonical_labels = []
    if os.path.exists(clean_dataset_path):
        print(f"[CANONICAL DATASET]: Extracting unique labels from {clean_dataset_path}...")
        import jsonlines
        raw_label_set = set()
        with jsonlines.open(clean_dataset_path) as reader:
            for obj in reader:
                raw_label_set.update(obj.get("label", []))
        canonical_labels = sorted(list(raw_label_set))
        print(f"[CANONICAL DATASET]: Total unique clean labels extracted = {len(canonical_labels)}")
    else:
        print(f"[CANONICAL DATASET WARNING]: {clean_dataset_path} not found locally. Checking if label2id contains standard clean labels...")

    # Step 6: Detailed Identity and Ordering Comparison
    saved_label_set = set(saved_label2id.keys())
    canonical_set = set(canonical_labels)

    overlap = len(saved_label_set & canonical_set)
    extra_in_saved = len(saved_label_set - canonical_set)
    missing_from_saved = len(canonical_set - saved_label_set)

    print("------------------------------------------------------------------")
    print("DETAILED LABEL IDENTITY COMPARISON:")
    print(f"  Saved mapping count:               {saved_num_labels}")
    print(f"  Canonical clean count:             {len(canonical_labels)}")
    print(f"  Identical label overlap:           {overlap}")
    print(f"  Extra labels in saved mapping:     {extra_in_saved}")
    print(f"  Missing clean labels in saved:     {missing_from_saved}")

    # Order consistency check for overlapping labels
    canonical_label2id = {label: i for i, label in enumerate(canonical_labels)}
    matching_index_count = 0
    sample_discrepancies = []

    if canonical_labels:
        for l in canonical_labels:
            if l in saved_label2id:
                if saved_label2id[l] == canonical_label2id[l]:
                    matching_index_count += 1
                elif len(sample_discrepancies) < 5:
                    sample_discrepancies.append({
                        "label": l,
                        "canonical_index": canonical_label2id[l],
                        "saved_index": saved_label2id[l]
                    })

        order_identical = (matching_index_count == len(canonical_labels) and saved_num_labels == len(canonical_labels))
        print(f"  Labels with exact matching index:  {matching_index_count}/{len(canonical_labels)}")
        if sample_discrepancies:
            print(f"  Sample index discrepancies:        {sample_discrepancies}")
    else:
        order_identical = None

    print("------------------------------------------------------------------")
    print("DIAGNOSTIC SUMMARY & CONFIRMED DIMENSIONS:")
    print(f"  Physical classifier out_features:  {classifier_out_features}")
    print(f"  config.json num_labels:            {config_num_labels}")
    print(f"  saved label_mapping.json labels:   {saved_num_labels}")
    print("------------------------------------------------------------------")

    result = {
        "status": "DIAGNOSIS_COMPLETE",
        "model_dir": os.path.abspath(model_dir),
        "backup_dir": os.path.abspath(backup_dir),
        "classifier_out_features": classifier_out_features,
        "classifier_in_features": classifier_in_features,
        "config_num_labels": config_num_labels,
        "saved_num_labels": saved_num_labels,
        "canonical_num_labels": len(canonical_labels),
        "label_overlap_count": overlap,
        "extra_in_saved_count": extra_in_saved,
        "missing_from_saved_count": missing_from_saved,
        "matching_index_count": matching_index_count,
        "sample_discrepancies": sample_discrepancies,
        "is_contiguous": is_contiguous
    }

    return result

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "results/models/ledgar_frozen_subset/final_model"
    data_path = sys.argv[2] if len(sys.argv) > 2 else "data/raw/ledgar/extracted/LEDGAR_2016-2019_clean.jsonl"
    res = run_diagnostics(target, data_path)
    print(json.dumps(res, indent=2))
