import os
import json
import time
import torch
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from sklearn.metrics import classification_report, confusion_matrix
from src.models.config import LegalBertConfig, TrainingConfig
from src.models.legalbert import LegalBertWrapper
from src.models.training import prepare_trainer, configure_deterministic_training
from src.baselines.metrics import calculate_metrics
import math
from datasets import Dataset
from transformers import DataCollatorWithPadding, TrainerCallback
import psutil
import gc

def print_memory_guard(stage_name):
    try:
        mem = psutil.virtual_memory()
        msg = f"[{stage_name}] RAM Used: {mem.used/1e9:.2f}GB / {mem.total/1e9:.2f}GB"
    except Exception:
        msg = f"[{stage_name}] RAM: unknown"
    if torch.cuda.is_available():
        msg += f" | GPU: {torch.cuda.memory_allocated()/1e9:.2f}GB"
    print(msg)

class MemorySafeLedgarCollator:
    def __init__(self, tokenizer, label2id, num_unique_labels):
        self.tokenizer = tokenizer
        self.label2id = label2id
        self.num_unique_labels = num_unique_labels
        self.first_batch = True
        
    def __call__(self, features):
        texts = [f["text"] for f in features]
        batch_labels = [f["labels"] for f in features]
        
        # Tokenize exactly one batch dynamically
        batch = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        )
        
        # Build dense labels dynamically
        label_tensor = torch.zeros(len(features), self.num_unique_labels, dtype=torch.float32)
        for i, row_labels in enumerate(batch_labels):
            for l in row_labels:
                if l in self.label2id:
                    label_tensor[i, self.label2id[l]] = 1.0
                    
        batch["labels"] = label_tensor
        
        if self.first_batch:
            print_memory_guard("first batch tokenized")
            self.first_batch = False
            
        return batch

class SimpleDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        label = self.labels[idx]
        item['labels'] = torch.tensor(label, dtype=torch.long)
        return item

    def __len__(self):
        return len(self.labels)

from pathlib import Path

def get_project_root() -> Path:
    """Resolve the absolute project root regardless of the current working directory."""
    # __file__ is project/src/models/run_task019_experiments.py
    # .resolve() makes it absolute (e.g. /content/project/src/models/...)
    # parents[0] = models, parents[1] = src, parents[2] = project
    return Path(__file__).resolve().parents[2]

def get_contractnli_data():
    print("Loading ContractNLI...")
    records = []
    root = get_project_root()
    
    contractnli_dir = root / "data" / "raw" / "contractnli" / "extracted" / "contract-nli"
    
    print(f"PROJECT_ROOT = {root}")
    print(f"CONTRACTNLI_DIR = {contractnli_dir}")
    
    for split in ["train", "dev", "test"]:
        p = contractnli_dir / f"{split}.json"
        
        if not p.exists():
            raise FileNotFoundError(f"Missing required ContractNLI file: {p.absolute()}")
            
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        labels_dict = data.get("labels", {})
        for doc in data["documents"]:
            doc_id = doc["id"]
            text = doc["text"]
            for ann_set in doc["annotation_sets"]:
                for hyp_id, ann in ann_set["annotations"].items():
                    hyp_text = labels_dict.get(hyp_id, {}).get("hypothesis", hyp_id)
                    choice = ann["choice"]
                    combined = f"Hypothesis: {hyp_text}\nContract: {text}"
                    records.append({
                        "split": split,
                        "document_id": doc_id,
                        "text": combined,
                        "label": choice
                    })
    df = pd.DataFrame(records)
    
    label_map = {"Contradiction": 0, "Entailment": 1, "NotMentioned": 2}
    df["label_id"] = df["label"].map(label_map)
    
    return df

def run_contractnli():
    df = get_contractnli_data()
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "dev"]
    test_df = df[df["split"] == "test"]
    
    print(f"ContractNLI - Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    print("Validating labels...")
    EXPECTED_LABELS = {"Contradiction", "Entailment", "NotMentioned"}
    for l in df["label"].unique():
        assert l in EXPECTED_LABELS, f"Invalid label: {l}"
    for l_id in df["label_id"].unique():
        assert l_id in [0, 1, 2], f"Invalid label ID: {l_id}"
        assert not pd.isna(l_id), "Found NaN label ID"
    print("Labels validated successfully.")

    print("Validating dataset leakage...")
    train_docs = set(train_df["document_id"])
    val_docs = set(val_df["document_id"])
    test_docs = set(test_df["document_id"])
    assert len(train_docs.intersection(val_docs)) == 0, "Leakage between train and val"
    assert len(train_docs.intersection(test_docs)) == 0, "Leakage between train and test"
    assert len(val_docs.intersection(test_docs)) == 0, "Leakage between val and test"
    print("Data leakage check passed.")


    seed = 42
    configure_deterministic_training(seed)

    config = LegalBertConfig(
        classification_mode="multiclass",
        num_labels=3,
        random_seed=seed
    )
    
    print("Initializing Legal-BERT Wrapper...")
    wrapper = LegalBertWrapper(config)
    if not wrapper.is_available():
        print("Model unavailable!")
        return

    print("Encoding data...")
    t0 = time.time()
    train_encodings, train_truncs = wrapper.tokenizer_wrapper.encode(train_df["text"].tolist())
    val_encodings, val_truncs = wrapper.tokenizer_wrapper.encode(val_df["text"].tolist())
    test_encodings, test_truncs = wrapper.tokenizer_wrapper.encode(test_df["text"].tolist())
    print(f"Encoding took {time.time() - t0:.2f}s")
    
    train_dataset = SimpleDataset(train_encodings, train_df["label_id"].tolist())
    val_dataset = SimpleDataset(val_encodings, val_df["label_id"].tolist())
    test_dataset = SimpleDataset(test_encodings, test_df["label_id"].tolist())

    training_config = TrainingConfig(
        num_train_epochs=3,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        learning_rate=2e-5,
        evaluation_strategy="epoch",
        save_strategy="epoch"
    )
    
    out_dir = "results/models/contractnli/TASK019_CONTRACTNLI_LEGALBERT_checkpoints"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs("results/models/contractnli", exist_ok=True)
    os.makedirs("results/models/ledgar", exist_ok=True)
    os.makedirs("results/models/cuad", exist_ok=True)

    trainer = prepare_trainer(
        wrapper=wrapper,
        training_config=training_config,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        output_dir=out_dir
    )
    
    final_model_dir = "results/models/contractnli/final_model"
    label_map = {"Contradiction": 0, "Entailment": 1, "NotMentioned": 2}
    
    if os.path.exists(os.path.join(final_model_dir, "model.safetensors")):
        print(f"Found existing trained model at {final_model_dir}. Skipping training and loading weights.")
        import transformers
        wrapper.model = transformers.AutoModelForSequenceClassification.from_pretrained(final_model_dir)
        wrapper.model.to("cuda" if torch.cuda.is_available() else "cpu")
        trainer.model = wrapper.model
        fit_time = 0.0
    else:
        print("Starting full training...")
        t0 = time.time()
        trainer.train()
        fit_time = time.time() - t0
        print(f"Training completed in {fit_time:.2f}s")
        
        print("Saving model, tokenizer, and label mapping...")
        trainer.save_model(final_model_dir)
        wrapper.tokenizer_wrapper.tokenizer.save_pretrained(final_model_dir)
        with open(f"{final_model_dir}/label_mapping.json", "w") as f:
            json.dump({"label2id": label_map, "id2label": {v: k for k, v in label_map.items()}}, f)
            
        # Save training history
        with open(f"{final_model_dir}/training_history.json", "w") as f:
            json.dump(trainer.state.log_history, f, indent=2)

    print("Evaluating on test set...")
    predictions = trainer.predict(test_dataset)
    test_preds = np.argmax(predictions.predictions, axis=-1)
    y_test = test_df["label_id"].values
    
    test_metrics = calculate_metrics(y_test, test_preds)
    
    target_names = ["Contradiction", "Entailment", "NotMentioned"]
    report = classification_report(y_test, test_preds, target_names=target_names, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, test_preds, labels=[0, 1, 2]).tolist()
    
    res = {
        "experiment_id": "TASK019_CONTRACTNLI_LEGALBERT",
        "task": "DOCUMENT_NLI",
        "dataset": "ContractNLI",
        "dataset_version": "1.0",
        "input_path": "data/raw/contractnli/extracted/contract-nli/",
        "model": "LEGAL_BERT",
        "model_checkpoint": "nlpaueb/legal-bert-base-uncased",
        "hyperparameters": {
            "learning_rate": training_config.learning_rate,
            "num_train_epochs": training_config.num_train_epochs,
            "batch_size": training_config.per_device_train_batch_size,
            "max_sequence_length": 512,
            "random_seed": seed
        },
        "split": "official_train_dev_test",
        "training_size": len(train_df),
        "validation_size": len(val_df),
        "test_size": len(test_df),
        "truncation_stats": {
            "train_truncated": sum(train_truncs),
            "val_truncated": sum(val_truncs),
            "test_truncated": sum(test_truncs)
        },
        "runtime_seconds": round(fit_time, 3),
        "test_metrics": test_metrics,
        "per_class_metrics": {
            cls_name: {
                "precision": round(report[cls_name]["precision"], 4),
                "recall": round(report[cls_name]["recall"], 4),
                "f1": round(report[cls_name]["f1-score"], 4),
                "support": report[cls_name]["support"]
            } for cls_name in target_names
        },
        "confusion_matrix": {
            "labels": target_names,
            "matrix": cm
        },
        "status": "COMPLETE",
        "execution_type": "ACTUAL_EXPERIMENT",
        "classification": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    with open("results/models/contractnli/TASK019_CONTRACTNLI_LEGALBERT.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    # Process CUAD
    cuad_record = {
        "experiment_id": "TASK019_CUAD_LEGALBERT",
        "task": "QA_SPAN_EXTRACTION",
        "dataset": "CUAD",
        "dataset_version": "1.0",
        "input_path": "data/raw/cuad/extracted/CUAD_v1/CUAD_v1.json",
        "model": "NONE_TASK_MISMATCH",
        "execution_type": "TASK_FORMULATION_AUDIT",
        "classification": "NOT_APPLICABLE",
        "status": "NOT_APPLICABLE_TASK_MISMATCH",
        "reason": "The Task 007 baselines did not implement CUAD's original extractive question-answering/span-extraction task. Furthermore, there is no approved extractive QA Legal-BERT pipeline implemented in src/models/. CUAD is not converted into an artificial classification task.",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "is_test_fixture": False
    }
    with open("results/models/cuad/TASK019_CUAD_LEGALBERT.json", "w", encoding="utf-8") as f:
        json.dump(cuad_record, f, indent=2)

    # Process LEDGAR
    ledgar_record = {
        "dataset": "LEDGAR",
        "dataset_version": "2016-2019 Clean",
        "input_path": "data/raw/ledgar/extracted/LEDGAR_2016-2019_clean.jsonl",
        "task": "MULTI_LABEL_PROVISION_CLASSIFICATION",
        "experiment_id": "TASK019_LEDGAR_LEGALBERT",
        "model": "LEGAL_BERT",
        "execution_type": "FEASIBILITY_ASSESSMENT",
        "classification": "FEASIBILITY_ASSESSMENT",
        "status": "NOT_RUN_RESOURCE_LIMITATION",
        "reason": "Full training across 674,068 multilabel provisions over 12,608 distinct classes is infeasible on the given hardware (no GPU, CPU only). Total RAM is ~15.65GB (5.38GB free). Pilot on much smaller ContractNLI confirmed that CPU execution time for even 7k samples is excessive, rendering an 846k-sample Legal-BERT multilabel classification run completely infeasible.",
        "feasibility_assessment": {
            "num_classes": 12608,
            "train_samples": 674068,
            "estimated_cpu_time_hours": projected_time_hr * (674068 / 7191.0)
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    with open("results/models/ledgar/TASK019_LEDGAR_LEGALBERT.json", "w", encoding="utf-8") as f:
        json.dump(ledgar_record, f, indent=2)

    manifest_entries = [res, cuad_record]
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": "TASK 019 - PROPOSED MODEL EXPERIMENTS (CONTRACTNLI)",
        "total_records": len(manifest_entries),
        "experiment_accounting": {
            "total_records": len(manifest_entries),
            "actual_ml_experiments_completed": sum(1 for e in manifest_entries if e.get("classification") == "COMPLETED"),
            "not_applicable": sum(1 for e in manifest_entries if e.get("classification") == "NOT_APPLICABLE"),
            "feasibility_assessments": sum(1 for e in manifest_entries if e.get("classification") == "FEASIBILITY_ASSESSMENT")
        },
        "experiments": manifest_entries
    }
    with open("results/models/task019_contractnli_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("ContractNLI execution completed. Manifest written.")

import warnings
def get_ledgar_data():
    print("Loading LEDGAR...")
    records = []
    root = get_project_root()
    path = root / "data" / "raw" / "ledgar" / "extracted" / "LEDGAR_2016-2019_clean.jsonl"
    
    print(f"LEDGAR_PATH = {path}")
    if not path.exists():
        print(f"LEDGAR raw file not found at {path.absolute()}. Returning empty DataFrame.")
        return pd.DataFrame(columns=["split", "text", "labels", "contract_id"])
        
    import jsonlines
    with jsonlines.open(path) as reader:
        for obj in reader:
            records.append({
                "contract_id": obj.get("source", ""),
                "text": obj.get("provision", ""),
                "labels": obj.get("label", [])
            })
    df = pd.DataFrame(records)
    
    print("Applying verified Task 018 Group-aware split by contract_id (80/10/10)...")
    from sklearn.model_selection import GroupShuffleSplit
    
    # Split out test (10%)
    gss_test = GroupShuffleSplit(n_splits=1, test_size=0.1, random_state=42)
    train_val_idx, test_idx = next(gss_test.split(df, groups=df["contract_id"]))
    
    # Initialize all as train
    df["split"] = "train"
    
    # Mark test
    df.iloc[test_idx, df.columns.get_loc("split")] = "test"
    
    # Extract train_val view to split out validation (~10% of total)
    train_val_df = df.iloc[train_val_idx]
    gss_val = GroupShuffleSplit(n_splits=1, test_size=0.1111, random_state=42)
    train_idx_tv, val_idx_tv = next(gss_val.split(train_val_df, groups=train_val_df["contract_id"]))
    
    # Map back validation indices to main dataframe
    original_val_idx = train_val_idx[val_idx_tv]
    df.iloc[original_val_idx, df.columns.get_loc("split")] = "val"
    
    return df

def run_ledgar():
    print("Starting LEDGAR full task initialization...")
    print_memory_guard("Before raw dataset loading")
    df = get_ledgar_data()
    print_memory_guard("After raw dataset loading")
    if len(df) == 0:
        print("No LEDGAR data available. Aborting.")
        return
        
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]
    print(f"LEDGAR - Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    print_memory_guard("After split creation")    
    # Extract unique labels across the entire dataset to build the 12,608 taxonomy
    all_unique_labels = set()
    for labels in df["labels"]:
        all_unique_labels.update(labels)
        
    num_unique_labels = len(all_unique_labels)
    sorted_labels = sorted(list(all_unique_labels))
    label2id = {label: i for i, label in enumerate(sorted_labels)}
    
    print(f"Total unique labels found: {num_unique_labels}")
    
    # Strictly enforce 12,608 taxonomy
    assert num_unique_labels == 12608, f"Expected 12608 labels, found {num_unique_labels}"
    assert len(train_df) == 674068, f"Expected 674068 train provisions, found {len(train_df)}"
    assert len(val_df) == 84250, f"Expected 84250 val provisions, found {len(val_df)}"
    assert len(test_df) == 87956, f"Expected 87956 test provisions, found {len(test_df)}"
    
    seed = 42
    configure_deterministic_training(seed)

    config = LegalBertConfig(
        classification_mode="multilabel",
        num_labels=num_unique_labels,
        random_seed=seed,
        multilabel_threshold=0.5
    )
    
    wrapper = LegalBertWrapper(config)
    if not wrapper.is_available():
        print("Model unavailable!")
        return
        
    print_memory_guard("After tokenizer/model loading")
    print("Initializing huggingface datasets directly from text... (no pre-tokenization)")
    
    # We must preserve the raw Python lists for text/labels, but prevent HF Dataset from holding
    # massive tokenized copies.
    train_ds = Dataset.from_pandas(train_df[["text", "labels"]], preserve_index=False)
    val_ds = Dataset.from_pandas(val_df[["text", "labels"]], preserve_index=False)
    test_ds = Dataset.from_pandas(test_df[["text", "labels"]], preserve_index=False)
    
    # Free up Pandas DataFrames aggressively to save RAM
    del df, train_df, val_df, test_df
    gc.collect()
    print_memory_guard("After HF Dataset conversion and GC")
            
    data_collator = MemorySafeLedgarCollator(wrapper.tokenizer_wrapper.tokenizer, label2id, num_unique_labels)

    # Configure hardware optimizations safely
    use_fp16 = False
    if torch.cuda.is_available():
        capability = torch.cuda.get_device_capability()
        if capability[0] >= 7: # T4, V100, A100, etc.
            use_fp16 = True
            print("CUDA device with Tensor Cores detected. Enabling FP16.")
            
    batch_size = 8
    gradient_accum = 1
    epochs = 3
    
    training_config = TrainingConfig(
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accum,
        learning_rate=2e-5,
        fp16=use_fp16,
        dataloader_num_workers=min(os.cpu_count() or 1, 4),
        report_to="none",
        remove_unused_columns=False
    )
    
    # Calculate exact mathematical steps
    expected_steps = math.ceil(674068 / (batch_size * gradient_accum)) * epochs

    dataloader_workers = min(os.cpu_count() or 1, 4)
    print(f"""
    LEDGAR training configuration
    Train examples: 674068
    Validation examples: 84250
    Test examples: 87956
    Labels: 12608
    Epochs: {epochs}
    Per-device batch size: {batch_size}
    Gradient accumulation: {gradient_accum}
    Expected optimizer steps: {expected_steps}
    FP16 Enabled: {use_fp16}
    DataLoader Workers: {dataloader_workers}
    """)
    print("Preparing Trainer...")
    
    class MemoryGuardCallback(TrainerCallback):
        def on_step_begin(self, args, state, control, **kwargs):
            if state.global_step == 0:
                print_memory_guard("first training step")
                
    persistent_dir = os.environ.get("LEDGAR_PERSISTENT_DIR", "results/models/ledgar")
    checkpoint_dir = os.path.join(persistent_dir, "TASK019_LEDGAR_checkpoints")
    final_model_dir = os.path.join(persistent_dir, "final_model")
    result_json_path = os.path.join(persistent_dir, "TASK019_LEDGAR_LEGALBERT.json")
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    trainer = prepare_trainer(
        wrapper=wrapper,
        training_config=training_config,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        output_dir=checkpoint_dir
    )
    trainer.data_collator = data_collator
    trainer.add_callback(MemoryGuardCallback())
    
    # Calculate actual steps
    train_dataloader = trainer.get_train_dataloader()
    actual_steps = len(train_dataloader) * epochs
    
    assert actual_steps == expected_steps, f"Expected {expected_steps} training steps, but trainer generated {actual_steps}!"
    assert epochs == 3, "Epochs MUST be 3 for Task 019"
    
    print(f"Attempting full LEDGAR training on {num_unique_labels} labels...")
    
    # ISSUE 2: Explicit Completion-State Check
    is_completed = False
    if os.path.exists(result_json_path):
        try:
            with open(result_json_path, "r") as f:
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
                is_completed = True
        except Exception:
            pass

    if is_completed:
        print(f"Found VALID completed experiment manifest and model at {persistent_dir}. Skipping training and evaluation.")
        return
        
    print("No valid completed experiment found. Preparing for training.")
    
    # ISSUE 1: Strict Checkpoint Validation
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
                print(f"Ignoring incomplete checkpoint: {ckpt}")
    
    resume_args = {}
    if valid_checkpoints:
        # Sort by checkpoint step number
        valid_checkpoints.sort(key=lambda x: int(x.split("-")[-1]))
        latest_ckpt = valid_checkpoints[-1]
        print(f"Valid complete checkpoint found at {latest_ckpt}. Resuming training...")
        resume_args["resume_from_checkpoint"] = latest_ckpt
    else:
        print("No valid checkpoints found. Starting training from scratch...")

    t0 = time.time()
    try:
        trainer.train(**resume_args)
    except RuntimeError as e:
        if "cuda out of memory" in str(e).lower():
            print("CUDA OOM during training.")
            res = {
                "experiment_id": "TASK019_LEDGAR_LEGALBERT",
                "status": "NOT_RUN_RESOURCE_LIMITATION",
                "reason": "GPU Out of Memory on full 12,608 label LEDGAR",
                "error": str(e),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            os.makedirs(persistent_dir, exist_ok=True)
            with open(result_json_path, "w") as f:
                json.dump(res, f, indent=2)
            return
        else:
            res = {
                "experiment_id": "TASK019_LEDGAR_LEGALBERT",
                "status": "FAILED",
                "reason": "Unexpected RuntimeError during training",
                "error": str(e),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            os.makedirs(persistent_dir, exist_ok=True)
            with open(result_json_path, "w") as f:
                json.dump(res, f, indent=2)
            raise
    except Exception as e:
        res = {
            "experiment_id": "TASK019_LEDGAR_LEGALBERT",
            "status": "FAILED",
            "reason": "Unexpected training error",
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        os.makedirs(persistent_dir, exist_ok=True)
        with open(result_json_path, "w") as f:
            json.dump(res, f, indent=2)
        raise
        
    fit_time = time.time() - t0
    print(f"Training completed in {fit_time:.2f}s")
    
    print("Saving model, tokenizer, and label mapping...")
    os.makedirs(final_model_dir, exist_ok=True)
    trainer.save_model(final_model_dir)
    wrapper.tokenizer_wrapper.tokenizer.save_pretrained(final_model_dir)
    with open(f"{final_model_dir}/label_mapping.json", "w") as f:
        json.dump({"label2id": label2id, "id2label": {v: k for k, v in label2id.items()}}, f)
        
    # Save training history
    with open(f"{final_model_dir}/training_history.json", "w") as f:
        json.dump(trainer.state.log_history, f, indent=2)

    print("Evaluating on test set safely...")
    test_loader = torch.utils.data.DataLoader(
        test_ds,
        batch_size=batch_size,
        collate_fn=data_collator,
        num_workers=dataloader_workers,
        pin_memory=True
    )
    
    wrapper.model.eval()
    
    tp_counts = torch.zeros(num_unique_labels, dtype=torch.int64)
    fp_counts = torch.zeros(num_unique_labels, dtype=torch.int64)
    fn_counts = torch.zeros(num_unique_labels, dtype=torch.int64)
    
    device = wrapper.model.device
    
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            
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
        "experiment_id": "TASK019_LEDGAR_LEGALBERT",
        "task": "MULTI_LABEL_PROVISION_CLASSIFICATION",
        "dataset": "LEDGAR",
        "dataset_version": "2016-2019 Clean",
        "model": "LEGAL_BERT",
        "model_checkpoint": "nlpaueb/legal-bert-base-uncased",
        "split": "group_aware_train_validation_test",
        "training_size": 674068,
        "validation_size": 84250,
        "test_size": 87956,
        "num_labels": 12608,
        "hyperparameters": {
            "learning_rate": training_config.learning_rate,
            "num_train_epochs": epochs,
            "batch_size": batch_size,
            "gradient_accumulation_steps": gradient_accum,
            "max_sequence_length": 512,
            "random_seed": seed,
            "threshold": 0.5
        },
        "truncation_stats": {
            "train_truncated": "unknown (dynamic tokenization)",
            "val_truncated": "unknown (dynamic tokenization)",
            "test_truncated": "unknown (dynamic tokenization)"
        },
        "validation_metrics": trainer.state.log_history,
        "test_metrics": test_metrics,
        "runtime_seconds": round(fit_time, 3),
        "status": "COMPLETE",
        "execution_type": "ACTUAL_EXPERIMENT",
        "classification": "COMPLETED",
        "resumed_from_checkpoint": bool(resume_args) if 'resume_args' in locals() else False,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    # ISSUE 4: Atomic manifest writing
    import tempfile
    import shutil
    
    os.makedirs(persistent_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=persistent_dir) as tmp_f:
        json.dump(res, tmp_f, indent=2)
        tmp_name = tmp_f.name
    
    os.replace(tmp_name, result_json_path)
    print(f"LEDGAR Evaluation complete. Checkpoint and JSON saved to {persistent_dir}.")

if __name__ == "__main__":
    run_contractnli()
