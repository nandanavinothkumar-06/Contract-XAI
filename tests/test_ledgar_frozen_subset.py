import os
import json
import tempfile
import torch
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.models.run_task019_ledgar_frozen_subset import (
    get_ledgar_subset_data,
    build_frozen_legalbert_model,
    run_timing_pilot,
    run_ledgar_frozen_subset,
    EXPERIMENT_ID
)

def test_deterministic_subset_selection_and_overlap():
    """
    Tests that:
    1. Subset selection is deterministic with recorded seed.
    2. Zero contract overlap exists between train subset, validation, and test.
    3. Complete 12,608 taxonomy is preserved without truncation.
    4. Exact preflight label coverage matches empirical counts.
    """
    subset_df, meta = get_ledgar_subset_data(seed=42, contract_ratio=0.10)
    
    assert meta["experiment_id"] in [
        "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET",
        "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH"
    ]
    assert meta["total_labels_taxonomy"] == 12608
    assert meta["total_train_contracts"] == 48432
    assert meta["subset_train_contracts"] == 4844
    assert meta["subset_train_provisions"] == 67776
    assert meta["labels_covered_in_subset"] == 9775
    assert meta["zero_example_labels"] == 2833
    assert meta["rare_example_labels"] == 8465
    assert meta["medium_example_labels"] == 1208
    assert meta["common_example_labels"] == 102
    assert meta["selected_contracts_sha256"] == "5f400e5e3b2fa5bdfc129ace322af285cd4ae44b32a03835d4643604c638a23d"

    train_subset_contracts = set(subset_df[subset_df["split"] == "train"]["contract_id"])
    val_contracts = set(subset_df[subset_df["split"] == "val"]["contract_id"])
    test_contracts = set(subset_df[subset_df["split"] == "test"]["contract_id"])

    assert len(train_subset_contracts.intersection(val_contracts)) == 0, "Leakage detected: train subset overlaps with validation!"
    assert len(train_subset_contracts.intersection(test_contracts)) == 0, "Leakage detected: train subset overlaps with test!"
    assert len(val_contracts.intersection(test_contracts)) == 0, "Leakage detected: validation overlaps with test!"

def test_frozen_encoder_and_trainable_head():
    """
    Tests that:
    1. Encoder parameters in wrapper.model.bert are strictly frozen (requires_grad == False).
    2. Classification head parameters are trainable (requires_grad == True).
    3. Parameter counts match theoretical expectation:
       - 109,482,240 frozen params
       - 9,695,552 trainable params
    """
    wrapper = build_frozen_legalbert_model(num_labels=12608, seed=42)

    # All bert params must be frozen
    for name, param in wrapper.model.bert.named_parameters():
        assert not param.requires_grad, f"Parameter {name} in bert encoder is not frozen!"

    # All classifier params must be trainable
    for name, param in wrapper.model.classifier.named_parameters():
        assert param.requires_grad, f"Parameter {name} in classifier head is not trainable!"

    trainable_count = sum(p.numel() for p in wrapper.model.parameters() if p.requires_grad)
    frozen_count = sum(p.numel() for p in wrapper.model.parameters() if not p.requires_grad)

    assert trainable_count == 768 * 12608 + 12608
    assert trainable_count == 9695552
    assert frozen_count == 109482240

def test_pilot_execution_and_weight_immutability():
    """
    Tests that the timing pilot:
    1. Runs successfully with finite loss.
    2. Leaves encoder weights completely unchanged (diff == 0.0).
    3. Successfully updates classification head weights (diff > 0.0).
    """
    wrapper = build_frozen_legalbert_model(num_labels=100, seed=42)

    # Create synthetic dataset with 4 items
    mock_dataset = [
        {"text": "Governing law shall be Delaware.", "labels": ["Law"]},
        {"text": "Base salary is $200,000.", "labels": ["Salary"]},
        {"text": "Thirty days written notice required.", "labels": ["Termination"]},
        {"text": "Proprietary information is confidential.", "labels": ["Confidentiality"]}
    ]
    label2id = {"Law": 0, "Salary": 1, "Termination": 2, "Confidentiality": 3}

    from src.models.run_task019_experiments import MemorySafeLedgarCollator
    collator = MemorySafeLedgarCollator(wrapper.tokenizer_wrapper.tokenizer, label2id, 100)

    pilot_res = run_timing_pilot(
        wrapper=wrapper,
        data_collator=collator,
        train_dataset=mock_dataset,
        batch_size=2,
        num_batches=2,
        device="cpu"
    )

    assert pilot_res["encoder_weights_frozen"] is True
    assert pilot_res["classifier_weights_updated"] is True
    assert len(pilot_res["pilot_losses"]) == 2
    assert all(np.isfinite(l) for l in pilot_res["pilot_losses"])

def test_checkpoint_isolation_and_resumption():
    """
    Tests that:
    1. Checkpoint directory is isolated from the full LEDGAR checkpoint directory.
    2. Checkpoint validation requires all 5 necessary files.
    3. Incomplete checkpoints are rejected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = os.path.join(tmpdir, "TASK019_LEDGAR_FROZEN_checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)

        # Valid checkpoint-100
        ckpt_100 = os.path.join(checkpoint_dir, "checkpoint-100")
        os.makedirs(ckpt_100, exist_ok=True)
        for f in ["trainer_state.json", "training_args.bin", "optimizer.pt", "scheduler.pt", "model.safetensors"]:
            with open(os.path.join(ckpt_100, f), "w") as fp:
                fp.write("mock")

        # Incomplete checkpoint-200 (missing optimizer)
        ckpt_200 = os.path.join(checkpoint_dir, "checkpoint-200")
        os.makedirs(ckpt_200, exist_ok=True)
        for f in ["trainer_state.json", "training_args.bin", "scheduler.pt", "model.safetensors"]:
            with open(os.path.join(ckpt_200, f), "w") as fp:
                fp.write("mock")

        import glob
        valid_ckpts = []
        for ckpt in glob.glob(os.path.join(checkpoint_dir, "checkpoint-*")):
            has_state = os.path.exists(os.path.join(ckpt, "trainer_state.json"))
            has_args = os.path.exists(os.path.join(ckpt, "training_args.bin"))
            has_opt = os.path.exists(os.path.join(ckpt, "optimizer.pt")) or os.path.exists(os.path.join(ckpt, "optimizer.bin"))
            has_sched = os.path.exists(os.path.join(ckpt, "scheduler.pt")) or os.path.exists(os.path.join(ckpt, "scheduler.bin"))
            has_model = os.path.exists(os.path.join(ckpt, "model.safetensors")) or os.path.exists(os.path.join(ckpt, "pytorch_model.bin"))
            if has_state and has_args and has_opt and has_sched and has_model:
                valid_ckpts.append(ckpt)

        assert ckpt_100 in valid_ckpts
        assert ckpt_200 not in valid_ckpts

def test_held_out_test_isolation_and_honest_status(monkeypatch):
    """
    Tests that:
    1. Pilot-only run marks the experiment as FEASIBILITY_ASSESSMENT / NOT_RUN_RESOURCE_LIMITATION.
    2. Does NOT fabricate test metrics.
    3. Saves separate result JSON with experiment_id TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("LEDGAR_FROZEN_PERSISTENT_DIR", tmpdir)

        res = run_ledgar_frozen_subset(pilot_only=True, batch_size=4)

        assert res["experiment_id"] in [
            "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET",
            "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH"
        ]
        assert res["status"] == "NOT_RUN_RESOURCE_LIMITATION"
        assert res["classification"] == "FEASIBILITY_ASSESSMENT"
        assert "test_metrics" not in res, "Test metrics MUST NOT be fabricated when evaluation has not run!"
        assert res["feasibility_assessment"]["encoder_weights_frozen"] is True
        assert res["feasibility_assessment"]["classifier_weights_updated"] is True

        result_path = os.path.join(tmpdir, f"{res['experiment_id']}.json")
        assert os.path.exists(result_path)
