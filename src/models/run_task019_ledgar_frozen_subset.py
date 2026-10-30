import os
import json
import time
import math
import hashlib
from typing import Dict, Any, List, Tuple
from collections import Counter

import torch
import numpy as np
import pandas as pd
from datasets import Dataset
import transformers
from transformers import TrainerCallback
import psutil
import gc

from src.models.config import LegalBertConfig, TrainingConfig
from src.models.legalbert import LegalBertWrapper
from src.models.training import prepare_trainer, configure_deterministic_training
from src.models.run_task019_experiments import (
    get_ledgar_data,
    MemorySafeLedgarCollator,
    print_memory_guard,
    get_project_root
)

EXPERIMENT_ID = "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH"

class CheckpointVerificationCallback(TrainerCallback):
    """
    Invoked after every checkpoint is written by the Hugging Face Trainer.
    Verifies that all essential files exist and that model weights are non-empty.
    """
    def on_save(self, args, state, control, **kwargs):
        step = state.global_step
        ckpt_dir = os.path.join(args.output_dir, f"checkpoint-{step}")
        if not os.path.exists(ckpt_dir):
            print(f"[CHECKPOINT WARNING]: Directory {ckpt_dir} not found after save event.")
            return

        has_state = os.path.exists(os.path.join(ckpt_dir, "trainer_state.json"))
        has_args = os.path.exists(os.path.join(ckpt_dir, "training_args.bin"))
        has_opt = os.path.exists(os.path.join(ckpt_dir, "optimizer.pt")) or os.path.exists(os.path.join(ckpt_dir, "optimizer.bin"))
        has_sched = os.path.exists(os.path.join(ckpt_dir, "scheduler.pt")) or os.path.exists(os.path.join(ckpt_dir, "scheduler.bin"))

        safetensors_path = os.path.join(ckpt_dir, "model.safetensors")
        bin_path = os.path.join(ckpt_dir, "pytorch_model.bin")
        weight_file = safetensors_path if os.path.exists(safetensors_path) else (bin_path if os.path.exists(bin_path) else None)
        has_weight = weight_file is not None and os.path.getsize(weight_file) > 0

        if not (has_state and has_args and has_opt and has_sched and has_weight):
            msg = f"[CHECKPOINT ERROR]: Checkpoint at {ckpt_dir} is incomplete or has empty weights!"
            print(msg)
            raise RuntimeError(msg)
        else:
            weight_size = os.path.getsize(weight_file)
            print(f"[CHECKPOINT VERIFIED]: Step {step} saved at {ckpt_dir} verified (weights: {os.path.basename(weight_file)}, {weight_size} bytes).")

def get_ledgar_subset_data(seed: int = 42, contract_ratio: float = 0.10) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Deterministically samples a contract-level subset from the verified training partition.
    Preserves 100% of the validation and held-out test partitions.
    Computes exact label coverage across the full 12,608 taxonomy before training.
    """
    df = get_ledgar_data()
    if len(df) == 0:
        return df, {}

    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]

    # Extract all unique labels across entire corpus to preserve full 12,608 taxonomy
    all_unique_labels = sorted(list(set(l for labels in df["labels"] for l in labels)))
    num_unique_labels = len(all_unique_labels)
    assert num_unique_labels == 12608, f"Expected 12608 labels, found {num_unique_labels}"

    # Sample strictly from training contracts
    train_contracts = sorted(train_df["contract_id"].unique())
    num_train_contracts = len(train_contracts)

    rng = np.random.RandomState(seed)
    shuffled_contracts = rng.permutation(train_contracts)
    target_k = int(np.ceil(contract_ratio * num_train_contracts))
    selected_contracts = set(shuffled_contracts[:target_k])

    subset_train_df = train_df[train_df["contract_id"].isin(selected_contracts)].copy()

    # Verify zero contract leakage
    val_contracts = set(val_df["contract_id"].unique())
    test_contracts = set(test_df["contract_id"].unique())
    assert len(selected_contracts.intersection(val_contracts)) == 0, "Leakage: Subset contract in val partition"
    assert len(selected_contracts.intersection(test_contracts)) == 0, "Leakage: Subset contract in test partition"

    # Compute label coverage metrics
    subset_labels_counter = Counter(l for labels in subset_train_df["labels"] for l in labels)
    covered_labels = set(subset_labels_counter.keys())
    num_covered = len(covered_labels)
    coverage_pct = round(num_covered / num_unique_labels * 100.0, 4)

    # Frequency tiers
    zero_labels_count = sum(1 for l in all_unique_labels if subset_labels_counter[l] == 0)
    rare_labels_count = sum(1 for l in all_unique_labels if 1 <= subset_labels_counter[l] < 10)
    medium_labels_count = sum(1 for l in all_unique_labels if 10 <= subset_labels_counter[l] < 100)
    common_labels_count = sum(1 for l in all_unique_labels if subset_labels_counter[l] >= 100)

    # Stable identifier / hash of selected contracts
    sorted_selected_contracts = sorted(list(selected_contracts))
    contracts_str = "\n".join(sorted_selected_contracts)
    contracts_hash = hashlib.sha256(contracts_str.encode("utf-8")).hexdigest()

    metadata = {
        "experiment_id": EXPERIMENT_ID,
        "seed": seed,
        "contract_ratio": contract_ratio,
        "total_corpus_provisions": len(df),
        "total_train_provisions": len(train_df),
        "total_train_contracts": num_train_contracts,
        "subset_train_provisions": len(subset_train_df),
        "subset_train_contracts": len(selected_contracts),
        "validation_provisions": len(val_df),
        "test_provisions": len(test_df),
        "total_labels_taxonomy": num_unique_labels,
        "labels_covered_in_subset": num_covered,
        "label_coverage_pct": coverage_pct,
        "zero_example_labels": zero_labels_count,
        "rare_example_labels": rare_labels_count,
        "medium_example_labels": medium_labels_count,
        "common_example_labels": common_labels_count,
        "selected_contracts_sha256": contracts_hash
    }

    # Combined dataframe with subset train, full val, full test
    subset_df = pd.concat([subset_train_df, val_df, test_df], ignore_index=True)
    return subset_df, metadata

def build_frozen_legalbert_model(num_labels: int = 12608, seed: int = 42) -> LegalBertWrapper:
    """
    Initializes Legal-BERT and strictly freezes all encoder parameters.
    The classification head (nn.Linear) remains trainable.
    """
    configure_deterministic_training(seed)

    config = LegalBertConfig(
        classification_mode="multilabel",
        num_labels=num_labels,
        random_seed=seed,
        multilabel_threshold=0.5
    )

    wrapper = LegalBertWrapper(config)
    if not wrapper.is_available():
        raise RuntimeError("Legal-BERT wrapper unavailable!")

    # Strictly freeze all encoder parameters
    for name, param in wrapper.model.bert.named_parameters():
        param.requires_grad = False

    # Verify classification head is trainable
    for name, param in wrapper.model.classifier.named_parameters():
        param.requires_grad = True

    # Validate parameter counts
    trainable_params = sum(p.numel() for p in wrapper.model.parameters() if p.requires_grad)
    frozen_params = sum(p.numel() for p in wrapper.model.parameters() if not p.requires_grad)
    expected_trainable = 768 * num_labels + num_labels

    assert trainable_params == expected_trainable, (
        f"Expected {expected_trainable} trainable params, got {trainable_params}"
    )
    assert all(not p.requires_grad for p in wrapper.model.bert.parameters()), (
        "Encoder parameters are not frozen!"
    )
    assert all(p.requires_grad for p in wrapper.model.classifier.parameters()), (
        "Classification head is not trainable!"
    )

    return wrapper

def run_timing_pilot(
    wrapper: LegalBertWrapper,
    data_collator: MemorySafeLedgarCollator,
    train_dataset: Dataset,
    batch_size: int = 16,
    num_batches: int = 5,
    device: str = "cpu"
) -> Dict[str, Any]:
    """
    Executes a small timing pilot before launching full training.
    Verifies finite loss, encoder weight immutability, classifier weight updates, and memory stability.
    """
    print(f"\n--- Running Timing Pilot ({num_batches} batches on {device}) ---")
    wrapper.model.to(device)
    wrapper.model.train()

    # Snapshot weights before pilot
    first_enc_param = next(wrapper.model.bert.parameters())
    enc_snap_before = first_enc_param.detach().clone()
    cls_snap_before = wrapper.model.classifier.weight.detach().clone()

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, wrapper.model.parameters()),
        lr=1e-3
    )

    pilot_samples = [train_dataset[i] for i in range(min(len(train_dataset), batch_size * num_batches))]
    step_times = []
    losses = []

    for b in range(num_batches):
        batch_features = pilot_samples[b * batch_size : (b + 1) * batch_size]
        if not batch_features:
            break
        batch = data_collator(batch_features)
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        t0 = time.time()
        optimizer.zero_grad()
        outputs = wrapper.model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        dt = time.time() - t0

        assert torch.isfinite(loss).item(), f"Non-finite loss encountered in pilot step {b+1}: {loss.item()}"
        step_times.append(dt)
        losses.append(loss.item())
        print(f"Pilot step {b+1}/{num_batches}: Loss = {loss.item():.4f}, Time = {dt:.4f}s")

    # Verify weight divergence
    first_enc_param_after = next(wrapper.model.bert.parameters())
    enc_diff = (first_enc_param_after.detach() - enc_snap_before).abs().max().item()
    cls_diff = (wrapper.model.classifier.weight.detach() - cls_snap_before).abs().max().item()

    assert enc_diff == 0.0, f"Violation: Encoder weights changed during training pilot! Max diff: {enc_diff}"
    assert cls_diff > 0.0, "Violation: Classification head weights did not change during training pilot!"

    avg_step_time = float(np.mean(step_times)) if step_times else 0.0
    examples_per_sec = float(batch_size / avg_step_time) if avg_step_time > 0 else 0.0

    peak_gpu_mb = 0.0
    if torch.cuda.is_available():
        peak_gpu_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)

    pilot_results = {
        "num_batches": len(step_times),
        "batch_size": batch_size,
        "device": device,
        "avg_step_time_sec": round(avg_step_time, 4),
        "examples_per_sec": round(examples_per_sec, 2),
        "pilot_losses": [round(l, 4) for l in losses],
        "encoder_weights_frozen": bool(enc_diff == 0.0),
        "classifier_weights_updated": bool(cls_diff > 0.0),
        "peak_gpu_memory_mb": peak_gpu_mb
    }
    print(f"Timing Pilot Complete: avg_step_time = {avg_step_time:.4f}s, examples/s = {examples_per_sec:.2f}")
    return pilot_results

def run_ledgar_frozen_subset(
    contract_ratio: float = 0.10,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 1e-3,
    seed: int = 42,
    pilot_only: bool = False,
    max_train_steps: int = None
):
    """
    Main orchestration entry point for TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.
    Isolates all artifacts in dedicated directories.
    Runs preflight label coverage, timing pilot, training with strict resumption, and held-out evaluation.
    """
    print(f"\n=======================================================")
    print(f"Starting {EXPERIMENT_ID}")
    print(f"=======================================================\n")

    # 1. Output directory isolation
    persistent_dir = os.environ.get(
        "LEDGAR_FROZEN_PERSISTENT_DIR",
        os.path.join(get_project_root(), "results", "models", "ledgar_frozen_subset_fresh")
    )
    checkpoint_dir = os.path.join(persistent_dir, "checkpoints")
    final_model_dir = os.path.join(persistent_dir, "final_model")
    result_json_path = os.path.join(persistent_dir, f"{EXPERIMENT_ID}.json")

    os.makedirs(persistent_dir, exist_ok=True)
    os.makedirs(checkpoint_dir, exist_ok=True)

    # 2. Check for completed experiment
    if os.path.exists(result_json_path):
        try:
            with open(result_json_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if (
                manifest.get("status") == "COMPLETE"
                and manifest.get("execution_type") == "ACTUAL_EXPERIMENT"
                and "test_metrics" in manifest
                and (
                    os.path.exists(os.path.join(final_model_dir, "model.safetensors"))
                    or os.path.exists(os.path.join(final_model_dir, "pytorch_model.bin"))
                )
                and os.path.exists(os.path.join(final_model_dir, "label_mapping.json"))
            ):
                print(f"Found VALID completed experiment at {persistent_dir}. Skipping.")
                return manifest
        except Exception:
            pass

    # 3. Load data and measure preflight label coverage
    subset_df, preflight_meta = get_ledgar_subset_data(seed=seed, contract_ratio=contract_ratio)
    if len(subset_df) == 0:
        print("No LEDGAR data available. Aborting.")
        return

    train_df = subset_df[subset_df["split"] == "train"]
    val_df = subset_df[subset_df["split"] == "val"]
    test_df = subset_df[subset_df["split"] == "test"]

    print(f"Data Partitions: Train Subset = {len(train_df)}, Val = {len(val_df)}, Test Held-Out = {len(test_df)}")
    print(f"Label Coverage: {preflight_meta['labels_covered_in_subset']}/12608 ({preflight_meta['label_coverage_pct']}%)")
    print(f"Zero Labels: {preflight_meta['zero_example_labels']}, Rare: {preflight_meta['rare_example_labels']}")

    # 4. Construct label mapping across all 12,608 labels
    all_labels = sorted(list(set(l for labels in subset_df["labels"] for l in labels)))
    label2id = {label: i for i, label in enumerate(all_labels)}
    num_unique_labels = len(all_labels)

    # 5. Build frozen model
    wrapper = build_frozen_legalbert_model(num_labels=num_unique_labels, seed=seed)

    # 6. Build Hugging Face datasets and collator
    train_ds = Dataset.from_pandas(train_df[["text", "labels"]], preserve_index=False)
    val_ds = Dataset.from_pandas(val_df[["text", "labels"]], preserve_index=False)
    test_ds = Dataset.from_pandas(test_df[["text", "labels"]], preserve_index=False)
    del subset_df, train_df, val_df
    gc.collect()

    data_collator = MemorySafeLedgarCollator(wrapper.tokenizer_wrapper.tokenizer, label2id, num_unique_labels)

    # 7. Run Timing Pilot
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pilot_results = run_timing_pilot(
        wrapper=wrapper,
        data_collator=data_collator,
        train_dataset=train_ds,
        batch_size=batch_size,
        num_batches=5,
        device=device
    )

    # Calculate steps and project runtime
    steps_per_epoch = math.ceil(len(train_ds) / batch_size)
    total_expected_steps = steps_per_epoch * epochs
    projected_seconds = total_expected_steps * pilot_results["avg_step_time_sec"]
    projected_hours = projected_seconds / 3600.0
    print(f"Total expected steps: {total_expected_steps} ({steps_per_epoch} steps/epoch x {epochs} epochs)")
    print(f"Projected training time: {projected_seconds:.2f}s (~{projected_hours:.2f} hours)")

    # If running on CPU and projected time exceeds 2 hours, record resource assessment and halt
    is_cpu_only = not torch.cuda.is_available()
    if pilot_only or (is_cpu_only and projected_hours > 2.0):
        print(f"\n[RESOURCE LIMITATION]: Training on CPU projected to take {projected_hours:.2f} hours (> 2.0 hr limit).")
        print("Halting training gracefully and logging pilot feasibility artifact.")
        res = {
            "experiment_id": EXPERIMENT_ID,
            "task": "MULTI_LABEL_PROVISION_CLASSIFICATION",
            "dataset": "LEDGAR",
            "model": "LEGAL_BERT_FROZEN_ENCODER",
            "execution_type": "FEASIBILITY_ASSESSMENT",
            "classification": "FEASIBILITY_ASSESSMENT",
            "status": "NOT_RUN_RESOURCE_LIMITATION",
            "reason": f"Frozen Legal-BERT subset training is not feasible on CPU hardware. Pilot average step time was {pilot_results['avg_step_time_sec']:.3f}s, projecting {projected_hours:.2f} hours for full subset training.",
            "feasibility_assessment": {
                "avg_step_time_sec": pilot_results["avg_step_time_sec"],
                "total_steps": total_expected_steps,
                "projected_time_hr": round(projected_hours, 3),
                "pilot_losses": pilot_results["pilot_losses"],
                "encoder_weights_frozen": pilot_results["encoder_weights_frozen"],
                "classifier_weights_updated": pilot_results["classifier_weights_updated"],
                "peak_gpu_memory_mb": pilot_results["peak_gpu_memory_mb"]
            },
            "preflight_metadata": preflight_meta,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        with open(result_json_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        update_experiment_manifest(res)
        return res

    # 8. Configure Trainer
    use_fp16 = False
    if torch.cuda.is_available():
        cap = torch.cuda.get_device_capability()
        if cap[0] >= 7:
            use_fp16 = True

    training_config = TrainingConfig(
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=1,
        learning_rate=learning_rate,
        fp16=use_fp16,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=2,
        dataloader_num_workers=min(os.cpu_count() or 1, 4),
        report_to="none",
        remove_unused_columns=False
    )

    trainer = prepare_trainer(
        wrapper=wrapper,
        training_config=training_config,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        output_dir=checkpoint_dir
    )
    trainer.data_collator = data_collator
    trainer.add_callback(CheckpointVerificationCallback())

    # 9. Checkpoint Validation and Strict Resumption
    import glob
    valid_checkpoints = []
    if os.path.exists(checkpoint_dir):
        for ckpt in glob.glob(os.path.join(checkpoint_dir, "checkpoint-*")):
            has_state = os.path.exists(os.path.join(ckpt, "trainer_state.json"))
            has_args = os.path.exists(os.path.join(ckpt, "training_args.bin"))
            has_opt = os.path.exists(os.path.join(ckpt, "optimizer.pt")) or os.path.exists(os.path.join(ckpt, "optimizer.bin"))
            has_sched = os.path.exists(os.path.join(ckpt, "scheduler.pt")) or os.path.exists(os.path.join(ckpt, "scheduler.bin"))
            has_model = os.path.exists(os.path.join(ckpt, "model.safetensors")) or os.path.exists(os.path.join(ckpt, "pytorch_model.bin"))

            if has_state and has_args and has_opt and has_sched and has_model:
                valid_checkpoints.append(ckpt)
            else:
                print(f"Rejecting incomplete checkpoint: {ckpt}")

    resume_args = {}
    if valid_checkpoints:
        valid_checkpoints.sort(key=lambda x: int(x.split("-")[-1]))
        latest_ckpt = valid_checkpoints[-1]
        print(f"Resuming frozen-subset training from checkpoint: {latest_ckpt}")
        resume_args["resume_from_checkpoint"] = latest_ckpt
    else:
        print("No valid checkpoints found. Starting fresh frozen-subset training from scratch...")

    # 10. Execute Training
    t0 = time.time()
    try:
        trainer.train(**resume_args)
    except Exception as e:
        res = {
            "experiment_id": EXPERIMENT_ID,
            "status": "FAILED",
            "reason": f"Training failed with error: {str(e)}",
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        with open(result_json_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        raise

    fit_time = time.time() - t0
    print(f"Training completed in {fit_time:.2f}s")

    # Save final model artifacts
    os.makedirs(final_model_dir, exist_ok=True)
    trainer.save_model(final_model_dir)
    wrapper.tokenizer_wrapper.tokenizer.save_pretrained(final_model_dir)
    with open(f"{final_model_dir}/label_mapping.json", "w", encoding="utf-8") as f:
        json.dump({"label2id": label2id, "id2label": {v: k for k, v in label2id.items()}}, f, indent=2)
    with open(f"{final_model_dir}/training_history.json", "w", encoding="utf-8") as f:
        json.dump(trainer.state.log_history, f, indent=2)
    with open(f"{final_model_dir}/training_config.json", "w", encoding="utf-8") as f:
        json.dump({
            "experiment_id": EXPERIMENT_ID,
            "num_train_epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "seed": seed,
            "save_steps": 500,
            "save_total_limit": 2,
            "trainable_params": 9695552,
            "frozen_params": 109482240,
            "num_labels": num_unique_labels
        }, f, indent=2)
    with open(f"{final_model_dir}/split_metadata.json", "w", encoding="utf-8") as f:
        json.dump(preflight_meta, f, indent=2)

    # 11. Evaluate on 100% Held-Out Test Set
    print("\n--- Evaluating on Held-Out Test Partition (87,956 provisions) ---")
    test_loader = torch.utils.data.DataLoader(
        test_ds,
        batch_size=batch_size,
        collate_fn=data_collator,
        num_workers=min(os.cpu_count() or 1, 4),
        pin_memory=torch.cuda.is_available()
    )

    wrapper.model.eval()
    tp_counts = torch.zeros(num_unique_labels, dtype=torch.int64)
    fp_counts = torch.zeros(num_unique_labels, dtype=torch.int64)
    fn_counts = torch.zeros(num_unique_labels, dtype=torch.int64)
    dev = wrapper.model.device

    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(dev)
            attention_mask = batch["attention_mask"].to(dev)
            labels = batch["labels"].to(dev)

            outputs = wrapper.model(input_ids=input_ids, attention_mask=attention_mask)
            preds = (torch.sigmoid(outputs.logits) > 0.5).long()

            preds_cpu = preds.cpu()
            labels_cpu = labels.long().cpu()

            tp_counts += ((preds_cpu == 1) & (labels_cpu == 1)).sum(dim=0)
            fp_counts += ((preds_cpu == 1) & (labels_cpu == 0)).sum(dim=0)
            fn_counts += ((preds_cpu == 0) & (labels_cpu == 1)).sum(dim=0)

    total_tp = tp_counts.sum().item()
    total_fp = fp_counts.sum().item()
    total_fn = fn_counts.sum().item()

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    per_class_p = tp_counts / (tp_counts + fp_counts).clamp(min=1)
    per_class_p[(tp_counts + fp_counts) == 0] = 0.0
    per_class_r = tp_counts / (tp_counts + fn_counts).clamp(min=1)
    per_class_r[(tp_counts + fn_counts) == 0] = 0.0
    per_class_f1 = 2 * per_class_p * per_class_r / (per_class_p + per_class_r).clamp(min=1e-8)
    per_class_f1[(per_class_p + per_class_r) == 0] = 0.0
    macro_f1 = per_class_f1.mean().item()

    test_metrics = {
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(macro_f1, 4)
    }

    res = {
        "experiment_id": EXPERIMENT_ID,
        "task": "MULTI_LABEL_PROVISION_CLASSIFICATION",
        "dataset": "LEDGAR",
        "dataset_version": "2016-2019 Clean",
        "model": "LEGAL_BERT_FROZEN_ENCODER",
        "model_checkpoint": "nlpaueb/legal-bert-base-uncased",
        "split": "group_aware_train_validation_test",
        "is_subset_experiment": True,
        "preflight_metadata": preflight_meta,
        "pilot_results": pilot_results,
        "hyperparameters": {
            "learning_rate": learning_rate,
            "num_train_epochs": epochs,
            "batch_size": batch_size,
            "threshold": 0.5,
            "trainable_params": 9695552,
            "frozen_params": 109482240
        },
        "test_metrics": test_metrics,
        "runtime_seconds": round(fit_time, 3),
        "status": "COMPLETE",
        "execution_type": "ACTUAL_EXPERIMENT",
        "classification": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    # Atomic write of final result JSON
    import tempfile
    with tempfile.NamedTemporaryFile("w", delete=False, dir=persistent_dir, encoding="utf-8") as tmp_f:
        json.dump(res, tmp_f, indent=2)
        tmp_name = tmp_f.name
    os.replace(tmp_name, result_json_path)

    update_experiment_manifest(res)
    print(f"Experiment {EXPERIMENT_ID} complete. Saved to {result_json_path}.")
    return res

def update_experiment_manifest(new_record: Dict[str, Any]):
    """Safely adds or updates the separate entry in results/models/task019_experiment_manifest.json."""
    manifest_path = "results/models/task019_experiment_manifest.json"
    if not os.path.exists(manifest_path):
        return

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        experiments = manifest.get("experiments", [])
        # Filter out existing entry with same experiment_id if any
        experiments = [e for e in experiments if e.get("experiment_id") != new_record["experiment_id"]]
        experiments.append(new_record)

        manifest["experiments"] = experiments
        manifest["total_records"] = len(experiments)
        manifest["experiment_accounting"]["total_records"] = len(experiments)
        manifest["experiment_accounting"]["actual_ml_experiments_completed"] = sum(
            1 for e in experiments if e.get("classification") == "COMPLETED"
        )
        manifest["experiment_accounting"]["feasibility_assessments"] = sum(
            1 for e in experiments if e.get("classification") == "FEASIBILITY_ASSESSMENT"
        )

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to update manifest: {e}")

if __name__ == "__main__":
    run_ledgar_frozen_subset()
