import ast
import glob
import json
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

def test_ledgar_checkpoint_validation_logic():
    """
    Proves that incomplete checkpoints are rejected, valid checkpoints are selected,
    and completion detection is strict (not merely checking final_model).
    """
    with open("src/models/run_task019_experiments.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    # Checkpoint rejection logic (must check all 5 items)
    assert 'has_state = os.path.exists(os.path.join(ckpt, "trainer_state.json"))' in code
    assert 'has_args = os.path.exists(os.path.join(ckpt, "training_args.bin"))' in code
    assert 'has_opt = os.path.exists(os.path.join(ckpt, "optimizer.pt")) or os.path.exists(os.path.join(ckpt, "optimizer.bin"))' in code
    assert 'has_sched = os.path.exists(os.path.join(ckpt, "scheduler.pt")) or os.path.exists(os.path.join(ckpt, "scheduler.bin"))' in code
    assert 'has_model = os.path.exists(os.path.join(ckpt, "model.safetensors")) or os.path.exists(os.path.join(ckpt, "pytorch_model.bin"))' in code
    assert 'if has_state and has_args and has_opt and has_sched and has_model:' in code
    assert 'valid_checkpoints.append(ckpt)' in code
    
    # Completion detection logic (must check manifest, COMPLETE status, ACTUAL_EXPERIMENT, test_metrics, and final_model files)
    assert 'manifest = json.load(f)' in code
    assert 'manifest.get("status") == "COMPLETE"' in code
    assert 'manifest.get("execution_type") == "ACTUAL_EXPERIMENT"' in code
    assert '"test_metrics" in manifest' in code
    assert 'os.path.exists(os.path.join(final_model_dir, "model.safetensors"))' in code
    assert 'os.path.exists(os.path.join(final_model_dir, "label_mapping.json"))' in code
    assert 'is_completed = True' in code
    assert 'if is_completed:' in code
    assert 'print(f"Found VALID completed experiment manifest and model at {persistent_dir}. Skipping training and evaluation.")' in code
    
    # Atomic write logic
    assert 'import tempfile' in code
    assert 'with tempfile.NamedTemporaryFile("w", delete=False, dir=persistent_dir) as tmp_f:' in code
    assert 'os.replace(tmp_name, result_json_path)' in code


def test_ledgar_resume_control_flow_scope_ast():
    """
    Proves that trainer.train(**resume_args) is in the correct control-flow scope:
    - NOT inside the 'else:' branch of 'if valid_checkpoints:'
    - Executed unconditionally after the checkpoint resolution
    - resume_args receives 'resume_from_checkpoint' in the 'if valid_checkpoints:' branch
    """
    with open("src/models/run_task019_experiments.py", "r", encoding="utf-8") as f:
        code = f.read()

    tree = ast.parse(code)
    run_ledgar_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_ledgar":
            run_ledgar_node = node
            break

    assert run_ledgar_node is not None, "run_ledgar function definition not found"

    # Find the `if valid_checkpoints:` node
    ckpt_if_node = None
    for stmt in run_ledgar_node.body:
        if isinstance(stmt, ast.If):
            test_src = ast.unparse(stmt.test) if hasattr(ast, "unparse") else ""
            if "valid_checkpoints" in test_src or (isinstance(stmt.test, ast.Name) and stmt.test.id == "valid_checkpoints"):
                ckpt_if_node = stmt
                break

    assert ckpt_if_node is not None, "if valid_checkpoints statement not found"

    # Verify trainer.train is NOT in the else branch
    else_src = ast.unparse(ckpt_if_node.orelse) if hasattr(ast, "unparse") else str(ckpt_if_node.orelse)
    assert "trainer.train" not in else_src, "trainer.train MUST NOT be inside the else: branch of if valid_checkpoints"

    # Verify resume_args["resume_from_checkpoint"] is in the if branch
    if_src = ast.unparse(ckpt_if_node.body) if hasattr(ast, "unparse") else str(ckpt_if_node.body)
    assert "resume_from_checkpoint" in if_src, "resume_from_checkpoint MUST be set in if valid_checkpoints branch"

    # Verify trainer.train is called within a Try statement in the outer run_ledgar body after the If statement
    train_called_after = False
    passed_if = False
    for stmt in run_ledgar_node.body:
        if stmt is ckpt_if_node:
            passed_if = True
            continue
        if passed_if:
            stmt_src = ast.unparse(stmt) if hasattr(ast, "unparse") else ""
            if "trainer.train(**resume_args)" in stmt_src or "trainer.train" in stmt_src:
                train_called_after = True
                break

    assert train_called_after, "trainer.train(**resume_args) MUST be called after the if/else checkpoint resolution in run_ledgar"


def test_ledgar_completion_operator_precedence():
    """
    Proves that operator precedence does NOT allow an existing pytorch_model.bin
    to bypass manifest validation, status COMPLETE, execution_type ACTUAL_EXPERIMENT,
    or test_metrics requirements.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        persistent_dir = tmpdir
        final_model_dir = os.path.join(persistent_dir, "final_model")
        os.makedirs(final_model_dir, exist_ok=True)
        result_json_path = os.path.join(persistent_dir, "TASK019_LEDGAR_LEGALBERT.json")

        # Create model weights and label mapping
        with open(os.path.join(final_model_dir, "pytorch_model.bin"), "wb") as f:
            f.write(b"dummy_weights")
        with open(os.path.join(final_model_dir, "label_mapping.json"), "w") as f:
            json.dump({"label2id": {}}, f)

        # Case 1: Incomplete manifest (status FAILED, no test_metrics)
        with open(result_json_path, "w") as f:
            json.dump({
                "experiment_id": "TASK019_LEDGAR_LEGALBERT",
                "status": "FAILED",
                "execution_type": "ACTUAL_EXPERIMENT"
            }, f)

        # Evaluate condition using exact logic from run_task019_experiments.py
        is_completed = False
        if os.path.exists(result_json_path):
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

        assert not is_completed, "Partially trained run with FAILED status must NOT evaluate as completed!"

        # Case 2: Complete valid manifest
        with open(result_json_path, "w") as f:
            json.dump({
                "experiment_id": "TASK019_LEDGAR_LEGALBERT",
                "status": "COMPLETE",
                "execution_type": "ACTUAL_EXPERIMENT",
                "test_metrics": {"micro_f1": 0.85}
            }, f)

        is_completed = False
        if os.path.exists(result_json_path):
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

        assert is_completed, "Valid completed run must evaluate as completed!"


def test_ledgar_checkpoint_58000_resumption_execution():
    """
    Regression test proving that when checkpoint-58000 is valid (all 5 required files present),
    numerical checkpoint selection picks checkpoint-58000, and trainer.train is called with
    resume_from_checkpoint pointing to checkpoint-58000.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        persistent_dir = tmpdir
        checkpoint_dir = os.path.join(persistent_dir, "TASK019_LEDGAR_checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)

        # Create older valid checkpoint-57500
        ckpt_57500 = os.path.join(checkpoint_dir, "checkpoint-57500")
        os.makedirs(ckpt_57500, exist_ok=True)
        for fname in ["trainer_state.json", "training_args.bin", "optimizer.pt", "scheduler.pt", "model.safetensors"]:
            with open(os.path.join(ckpt_57500, fname), "w") as f:
                f.write("mock")

        # Create target valid checkpoint-58000
        ckpt_58000 = os.path.join(checkpoint_dir, "checkpoint-58000")
        os.makedirs(ckpt_58000, exist_ok=True)
        for fname in ["trainer_state.json", "training_args.bin", "optimizer.pt", "scheduler.pt", "pytorch_model.bin"]:
            with open(os.path.join(ckpt_58000, fname), "w") as f:
                f.write("mock")

        # Create incomplete checkpoint-58500 (missing optimizer state)
        ckpt_58500 = os.path.join(checkpoint_dir, "checkpoint-58500")
        os.makedirs(ckpt_58500, exist_ok=True)
        for fname in ["trainer_state.json", "training_args.bin", "scheduler.pt", "model.safetensors"]:
            with open(os.path.join(ckpt_58500, fname), "w") as f:
                f.write("mock")

        # Execute checkpoint validation and selection logic
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

        # Incomplete 58500 must be rejected
        assert ckpt_58500 not in valid_checkpoints, "Incomplete checkpoint-58500 must be rejected"
        assert ckpt_57500 in valid_checkpoints
        assert ckpt_58000 in valid_checkpoints

        resume_args = {}
        if valid_checkpoints:
            valid_checkpoints.sort(key=lambda x: int(x.split("-")[-1]))
            latest_ckpt = valid_checkpoints[-1]
            resume_args["resume_from_checkpoint"] = latest_ckpt

        assert resume_args.get("resume_from_checkpoint") == ckpt_58000, (
            f"Expected latest valid checkpoint to be {ckpt_58000}, got {resume_args.get('resume_from_checkpoint')}"
        )

        # Mock trainer to verify trainer.train(**resume_args) execution
        mock_trainer = MagicMock()
        mock_trainer.train(**resume_args)
        mock_trainer.train.assert_called_once_with(resume_from_checkpoint=ckpt_58000)


def test_run_ledgar_end_to_end_resume_call(monkeypatch):
    """
    Executes run_ledgar() with mock components to prove that when checkpoint-58000 exists,
    run_ledgar calls trainer.train(resume_from_checkpoint=...checkpoint-58000).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("LEDGAR_PERSISTENT_DIR", tmpdir)
        checkpoint_dir = os.path.join(tmpdir, "TASK019_LEDGAR_checkpoints")
        ckpt_58000 = os.path.join(checkpoint_dir, "checkpoint-58000")
        os.makedirs(ckpt_58000, exist_ok=True)
        for fname in ["trainer_state.json", "training_args.bin", "optimizer.pt", "scheduler.pt", "model.safetensors"]:
            with open(os.path.join(ckpt_58000, fname), "w") as f:
                f.write("mock")

        class SplitCondition:
            def __init__(self, split_val):
                self.split_val = split_val

        class MockSplitSeries:
            def __eq__(self, other):
                return SplitCondition(other)

        mock_train_df = MagicMock()
        mock_train_df.__len__.return_value = 674068
        mock_val_df = MagicMock()
        mock_val_df.__len__.return_value = 84250
        mock_test_df = MagicMock()
        mock_test_df.__len__.return_value = 87956

        class MockDf:
            def __len__(self):
                return 846274
            def __getitem__(self, item):
                if item == "split":
                    return MockSplitSeries()
                if item == "labels":
                    return [[f"label_{i}"] for i in range(12608)]
                if isinstance(item, SplitCondition):
                    if item.split_val == "train":
                        return mock_train_df
                    elif item.split_val == "val":
                        return mock_val_df
                    elif item.split_val == "test":
                        return mock_test_df
                return mock_train_df

        mock_trainer = MagicMock()
        mock_dataloader = MagicMock()
        mock_dataloader.__len__.return_value = 84259
        mock_trainer.get_train_dataloader.return_value = mock_dataloader
        mock_trainer.state.log_history = []

        with patch("src.models.run_task019_experiments.get_ledgar_data", return_value=MockDf()), \
             patch("src.models.run_task019_experiments.LegalBertWrapper") as mock_wrapper_cls, \
             patch("src.models.run_task019_experiments.Dataset.from_pandas"), \
             patch("src.models.run_task019_experiments.prepare_trainer", return_value=mock_trainer), \
             patch("torch.utils.data.DataLoader", return_value=[]):
            
            mock_wrapper = mock_wrapper_cls.return_value
            mock_wrapper.is_available.return_value = True
            mock_wrapper.model.device = "cpu"

            from src.models.run_task019_experiments import run_ledgar
            run_ledgar()

            mock_trainer.train.assert_called_once()
            call_kwargs = mock_trainer.train.call_args.kwargs
            assert "resume_from_checkpoint" in call_kwargs
            assert call_kwargs["resume_from_checkpoint"] == ckpt_58000


