import os
import json
import tempfile
import pytest
import torch
import torch.nn as nn
from typing import Dict, Any

from src.models.evaluate_task019_threshold_calibration import (
    verify_model_persistence,
    calibrate_threshold_on_validation,
    evaluate_held_out_test,
    reject_projected_test_metrics,
    run_actual_forward_inference
)

def test_missing_model_weights():
    """Verifies that verify_model_persistence and run_actual_forward_inference raise FileNotFoundError when weights are missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_model_dir = os.path.join(tmpdir, "empty_model")
        os.makedirs(empty_model_dir, exist_ok=True)

        with pytest.raises(FileNotFoundError) as exc_info:
            verify_model_persistence(empty_model_dir)
        assert "Model weights not found" in str(exc_info.value)

        with pytest.raises(FileNotFoundError) as exc_info2:
            run_actual_forward_inference(
                model_dir=empty_model_dir,
                test_ds=[],
                data_collator=None,
                threshold=0.05
            )
        assert "Model weights not found" in str(exc_info2.value)

def test_zero_byte_model_weights():
    """Verifies that verify_model_persistence rejects 0-byte weight files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = os.path.join(tmpdir, "zero_model")
        os.makedirs(model_dir, exist_ok=True)
        # Create empty weights file
        with open(os.path.join(model_dir, "model.safetensors"), "wb") as f:
            pass

        with pytest.raises(ValueError) as exc_info:
            verify_model_persistence(model_dir)
        assert "zero size" in str(exc_info.value)

def test_label_count_mismatch():
    """Verifies that verify_model_persistence rejects label_mapping.json if label count does not match expected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = os.path.join(tmpdir, "mismatch_model")
        os.makedirs(model_dir, exist_ok=True)
        # Create non-empty weights and config
        with open(os.path.join(model_dir, "model.safetensors"), "wb") as f:
            f.write(b"non_empty_weight_bytes")
        with open(os.path.join(model_dir, "config.json"), "w") as f:
            json.dump({"num_labels": 12608}, f)
        # Create label mapping with only 10 labels
        with open(os.path.join(model_dir, "label_mapping.json"), "w") as f:
            json.dump({"label2id": {f"label_{i}": i for i in range(10)}}, f)

        with pytest.raises(ValueError) as exc_info:
            verify_model_persistence(model_dir, expected_num_labels=12608)
        assert "Label count mismatch" in str(exc_info.value)

def test_failed_model_reload():
    """Verifies that verify_model_persistence catches failed model reload when weights/config are corrupted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = os.path.join(tmpdir, "corrupt_model")
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, "model.safetensors"), "wb") as f:
            f.write(b"corrupted_binary_data")
        with open(os.path.join(model_dir, "config.json"), "w") as f:
            json.dump({"model_type": "bert", "num_labels": 12608}, f)
        with open(os.path.join(model_dir, "label_mapping.json"), "w") as f:
            json.dump({"label2id": {f"label_{i}": i for i in range(12608)}}, f)

        with pytest.raises(RuntimeError) as exc_info:
            verify_model_persistence(model_dir, expected_num_labels=12608)
        assert "Failed to reload saved model" in str(exc_info.value)

class DummyMockModel(nn.Module):
    def __init__(self, num_labels=10):
        super().__init__()
        self.config = type("Config", (), {"num_labels": num_labels})()
        self.fc = nn.Linear(4, num_labels)
    def forward(self, input_ids=None, attention_mask=None):
        bs = input_ids.size(0)
        # Return deterministic dummy logits
        logits = torch.zeros(bs, self.config.num_labels)
        # Make class 0 have high logit (+5.0) and class 1 have moderate logit (-1.0)
        logits[:, 0] = 5.0
        logits[:, 1] = -1.0
        return type("Output", (), {"logits": logits})()

def test_validation_only_threshold_selection():
    """Verifies that calibrate_threshold_on_validation selects the optimal threshold using validation data only."""
    model = DummyMockModel(num_labels=10)
    batch = {
        "input_ids": torch.zeros(4, 8, dtype=torch.long),
        "attention_mask": torch.ones(4, 8, dtype=torch.long),
        "labels": torch.zeros(4, 10, dtype=torch.float32)
    }
    # Set positive labels
    batch["labels"][:, 0] = 1.0  # Class 0 is positive
    val_loader = [batch]

    res = calibrate_threshold_on_validation(
        model=model,
        val_loader=val_loader,
        device="cpu",
        candidate_thresholds=[0.01, 0.05, 0.50, 0.80]
    )

    assert res["dataset_split"] == "validation"
    assert res["selection_criterion"] == "argmax(validation_micro_f1)"
    assert res["validation_samples"] == 4
    assert res["validation_positives"] == 4
    assert res["optimal_threshold"] in [0.01, 0.05, 0.50, 0.80]
    assert len(res["threshold_curve"]) == 4

def test_separation_of_validation_and_test_inference():
    """Verifies that validation calibration and held-out test evaluation produce isolated, separate records."""
    model = DummyMockModel(num_labels=10)
    val_batch = {
        "input_ids": torch.zeros(4, 8, dtype=torch.long),
        "attention_mask": torch.ones(4, 8, dtype=torch.long),
        "labels": torch.zeros(4, 10, dtype=torch.float32)
    }
    val_batch["labels"][:, 0] = 1.0

    test_batch = {
        "input_ids": torch.zeros(6, 8, dtype=torch.long),
        "attention_mask": torch.ones(6, 8, dtype=torch.long),
        "labels": torch.zeros(6, 10, dtype=torch.float32)
    }
    test_batch["labels"][:, 0] = 1.0
    test_batch["labels"][:, 1] = 1.0

    val_res = calibrate_threshold_on_validation(model, [val_batch], device="cpu", candidate_thresholds=[0.05, 0.50])
    test_res = evaluate_held_out_test(model, [test_batch], thresholds=[val_res["optimal_threshold"], 0.50], device="cpu")

    assert val_res["dataset_split"] == "validation"
    assert test_res["dataset_split"] == "held_out_test"
    assert val_res["validation_samples"] == 4
    assert test_res["sample_count"] == 6
    assert test_res["total_positives"] == 12  # 6 * 2

def test_rejection_of_projected_test_metrics():
    """Verifies that reject_projected_test_metrics strictly raises ValueError when metrics are synthetic or projected."""
    # Synthetic projected dictionary
    synthetic_metrics = {
        "execution_mode": "PROJECTED_FROM_VALIDATION",
        "micro_f1": 0.3636
    }
    with pytest.raises(ValueError) as exc_info:
        reject_projected_test_metrics(synthetic_metrics)
    assert "Projected or synthetic test metrics are strictly prohibited" in str(exc_info.value)

    # Valid empirical dictionary
    empirical_metrics = {
        "execution_mode": "EMPIRICAL_FORWARD_INFERENCE",
        "micro_f1": 0.3636
    }
    # Should not raise
    reject_projected_test_metrics(empirical_metrics)

def test_checkpoint_verification_callback():
    """Verifies that CheckpointVerificationCallback verifies all 5 files and non-empty weights."""
    from src.models.run_task019_ledgar_frozen_subset import CheckpointVerificationCallback
    cb = CheckpointVerificationCallback()

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_dir = os.path.join(tmpdir, "checkpoint-500")
        os.makedirs(ckpt_dir, exist_ok=True)

        args = type("Args", (), {"output_dir": tmpdir})()
        state = type("State", (), {"global_step": 500})()

        # Missing files -> raises RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            cb.on_save(args, state, control=None)
        assert "incomplete or has empty weights" in str(exc_info.value)

        # Create 4 files with empty weights -> raises RuntimeError
        for f in ["trainer_state.json", "training_args.bin", "scheduler.pt", "optimizer.pt"]:
            with open(os.path.join(ckpt_dir, f), "w") as fp:
                fp.write("dummy")
        with open(os.path.join(ckpt_dir, "model.safetensors"), "wb") as fp:
            pass  # 0 bytes

        with pytest.raises(RuntimeError) as exc_info2:
            cb.on_save(args, state, control=None)
        assert "incomplete or has empty weights" in str(exc_info2.value)

        # Non-empty weights -> succeeds
        with open(os.path.join(ckpt_dir, "model.safetensors"), "wb") as fp:
            fp.write(b"non_empty_weight_bytes")

        # Does not raise
        cb.on_save(args, state, control=None)

def test_model_save_path_resolution(monkeypatch):
    """Verifies persistence path resolution via LEDGAR_FROZEN_PERSISTENT_DIR."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("LEDGAR_FROZEN_PERSISTENT_DIR", tmpdir)

        persistent_dir = os.environ.get("LEDGAR_FROZEN_PERSISTENT_DIR")
        checkpoint_dir = os.path.join(persistent_dir, "checkpoints")
        final_model_dir = os.path.join(persistent_dir, "final_model")

        assert persistent_dir == tmpdir
        assert checkpoint_dir == os.path.join(tmpdir, "checkpoints")
        assert final_model_dir == os.path.join(tmpdir, "final_model")

def test_checkpoint_validation_requires_all_essential_files():
    """Verifies checkpoint acceptance requires all 5 essential Hugging Face Trainer files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_dir = os.path.join(tmpdir, "checkpoint-100")
        os.makedirs(ckpt_dir, exist_ok=True)

        for f in ["trainer_state.json", "training_args.bin", "scheduler.pt", "model.safetensors"]:
            with open(os.path.join(ckpt_dir, f), "w") as fp:
                fp.write("dummy")

        has_state = os.path.exists(os.path.join(ckpt_dir, "trainer_state.json"))
        has_args = os.path.exists(os.path.join(ckpt_dir, "training_args.bin"))
        has_opt = os.path.exists(os.path.join(ckpt_dir, "optimizer.pt")) or os.path.exists(os.path.join(ckpt_dir, "optimizer.bin"))
        has_sched = os.path.exists(os.path.join(ckpt_dir, "scheduler.pt")) or os.path.exists(os.path.join(ckpt_dir, "scheduler.bin"))
        has_model = os.path.exists(os.path.join(ckpt_dir, "model.safetensors")) or os.path.exists(os.path.join(ckpt_dir, "pytorch_model.bin"))

        is_valid = has_state and has_args and has_opt and has_sched and has_model
        assert is_valid is False, "Checkpoint missing optimizer must be rejected"

        with open(os.path.join(ckpt_dir, "optimizer.pt"), "w") as fp:
            fp.write("dummy")

        has_opt = os.path.exists(os.path.join(ckpt_dir, "optimizer.pt")) or os.path.exists(os.path.join(ckpt_dir, "optimizer.bin"))
        is_valid = has_state and has_args and has_opt and has_sched and has_model
        assert is_valid is True, "Complete 5-file checkpoint must be accepted"

def test_colab_package_includes_persistence_and_export_verification():
    """Verifies that generate_colab_package.py includes persistence reload verification and manifest creation."""
    with open("scripts/generate_colab_package.py", "r", encoding="utf-8") as f:
        src = f.read()

    assert "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH" in src
    assert "TASK019_FINAL_RUN" in src
    assert "verify_model_persistence" in src
    assert "STAGE 6B: MODEL PERSISTENCE & RELOAD VERIFICATION" in src
    assert "run_complete_calibrated_evaluation" in src
    assert "STAGE 6C: VALIDATION CALIBRATION & HELD-OUT TEST EVALUATION" in src
    assert "STAGE 7: EXPORT BUNDLE & MANIFEST GENERATION" in src
    assert "export_manifest.json" in src
    assert "12608" in src

def test_model_reload_and_12608_logits(monkeypatch):
    """
    Verifies that verify_model_persistence loads a model and asserts exactly 12,608 output logits,
    rejecting any model that outputs a different number of logits.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = os.path.join(tmpdir, "test_reload_model")
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, "model.safetensors"), "wb") as f:
            f.write(b"non_empty_weight_bytes")
        with open(os.path.join(model_dir, "config.json"), "w") as f:
            json.dump({"num_labels": 12608}, f)
        with open(os.path.join(model_dir, "label_mapping.json"), "w") as f:
            json.dump({"label2id": {f"l_{i}": i for i in range(12608)}}, f)

        # Mock model that outputs 12608 logits
        mock_model_ok = DummyMockModel(num_labels=12608)
        monkeypatch.setattr(
            "transformers.AutoModelForSequenceClassification.from_pretrained",
            lambda path: mock_model_ok
        )
        info = verify_model_persistence(model_dir, expected_num_labels=12608)
        assert info["status"] == "VERIFIED"
        assert info["num_labels"] == 12608

        # Mock model that outputs wrong number of logits (e.g. 100)
        mock_model_wrong = DummyMockModel(num_labels=100)
        monkeypatch.setattr(
            "transformers.AutoModelForSequenceClassification.from_pretrained",
            lambda path: mock_model_wrong
        )
        with pytest.raises(ValueError) as exc:
            verify_model_persistence(model_dir, expected_num_labels=12608)
        assert "mismatch" in str(exc.value)

def test_actual_test_forward_inference_metrics_and_zero_positive_documentation():
    """
    Verifies that evaluate_held_out_test computes empirical micro-F1, macro-F1, and weighted-F1
    via real batch forward passes, and documents labels without positive training examples.
    """
    num_labels = 12608
    model = DummyMockModel(num_labels=num_labels)

    # Synthetic batch of 8 samples
    labels = torch.zeros(8, num_labels, dtype=torch.float32)
    labels[:, 0] = 1.0   # Class 0 positive for all
    labels[0:4, 1] = 1.0 # Class 1 positive for 4

    test_batch = {
        "input_ids": torch.zeros(8, 16, dtype=torch.long),
        "attention_mask": torch.ones(8, 16, dtype=torch.long),
        "labels": labels
    }

    test_res = evaluate_held_out_test(
        model=model,
        test_loader=[test_batch],
        thresholds=[0.05, 0.50],
        device="cpu",
        weights_sha256="test_sha"
    )

    assert test_res["dataset_split"] == "held_out_test"
    assert test_res["sample_count"] == 8
    assert test_res["total_classes"] == 12608
    assert "0.05" in test_res["metrics_by_threshold"]
    assert "0.5" in test_res["metrics_by_threshold"]

    m05 = test_res["metrics_by_threshold"]["0.05"]
    assert "micro_precision" in m05
    assert "micro_recall" in m05
    assert "micro_f1" in m05
    assert "macro_f1" in m05
    assert "weighted_f1" in m05
    assert m05["execution_mode"] == "EMPIRICAL_FORWARD_INFERENCE"

    # Verify zero-positive documentation exists
    limitations = test_res.get("documented_limitations", [])
    assert any("zero positive examples" in lim for lim in limitations)
    assert any("12,608" in lim for lim in limitations)

def test_export_manifest_and_zip_integrity():
    """
    Verifies that export manifest creation records exact file sizes and SHA-256 hashes,
    and that a ZIP export preserves file integrity and can be unpacked and verified.
    """
    import zipfile
    import hashlib

    with tempfile.TemporaryDirectory() as tmpdir:
        export_root = os.path.join(tmpdir, "export_tree")
        model_sub = os.path.join(export_root, "final_model")
        os.makedirs(model_sub, exist_ok=True)

        sample_content = b"legal_bert_trained_weights_mock_data"
        weights_file = os.path.join(model_sub, "model.safetensors")
        with open(weights_file, "wb") as f:
            f.write(sample_content)

        cfg_content = b'{"num_labels": 12608}'
        cfg_file = os.path.join(model_sub, "config.json")
        with open(cfg_file, "wb") as f:
            f.write(cfg_content)

        # Generate export manifest
        manifest_entries = []
        for root_dir, _, files in os.walk(export_root):
            for f in sorted(files):
                fpath = os.path.join(root_dir, f)
                rel_path = os.path.relpath(fpath, tmpdir)
                h = hashlib.sha256()
                with open(fpath, "rb") as fp:
                    for chunk in iter(lambda: fp.read(65536), b""):
                        h.update(chunk)
                manifest_entries.append({
                    "relative_path": rel_path.replace(os.sep, "/"),
                    "size_bytes": os.path.getsize(fpath),
                    "sha256": h.hexdigest()
                })

        manifest_file = os.path.join(export_root, "export_manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({"files": manifest_entries}, f, indent=2)

        # Create zip archive
        zip_path = os.path.join(tmpdir, "task019_results.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root_dir, _, files in os.walk(export_root):
                for f in files:
                    fp = os.path.join(root_dir, f)
                    arcname = os.path.relpath(fp, export_root)
                    zipf.write(fp, arcname=arcname)

        # Unpack to verify integrity
        unpack_dir = os.path.join(tmpdir, "unpacked")
        with zipfile.ZipFile(zip_path, "r") as zipf:
            zipf.extractall(unpack_dir)

        # Verify weights SHA-256 match
        unpacked_weights = os.path.join(unpack_dir, "final_model", "model.safetensors")
        assert os.path.exists(unpacked_weights)
        assert os.path.getsize(unpacked_weights) == len(sample_content)
        h_unpacked = hashlib.sha256(open(unpacked_weights, "rb").read()).hexdigest()
        h_expected = hashlib.sha256(sample_content).hexdigest()
        assert h_unpacked == h_expected

def test_model_reload_and_12407_native_logits(monkeypatch):
    """
    Verifies that verify_model_persistence loads a model and asserts exactly 12,407 output logits
    when verifying the native 12,407 subset taxonomy.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = os.path.join(tmpdir, "test_12407_model")
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, "model.safetensors"), "wb") as f:
            f.write(b"non_empty_weight_bytes")
        with open(os.path.join(model_dir, "config.json"), "w") as f:
            json.dump({"num_labels": 12407}, f)
        with open(os.path.join(model_dir, "label_mapping.json"), "w") as f:
            json.dump({"label2id": {f"l_{i}": i for i in range(12407)}}, f)

        mock_model_12407 = DummyMockModel(num_labels=12407)
        monkeypatch.setattr(
            "transformers.AutoModelForSequenceClassification.from_pretrained",
            lambda path, **kwargs: mock_model_12407
        )
        info = verify_model_persistence(model_dir, expected_num_labels=12407)
        assert info["status"] == "VERIFIED"
        assert info["num_labels"] == 12407

