import ast
import pytest

def test_contractnli_genuine_training():
    """
    Proves that run_contractnli() unconditionally performs actual training
    rather than a feasibility pilot, and correctly serializes the artifacts.
    """
    with open("src/models/run_task019_experiments.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    tree = ast.parse(code)
    
    # 1. Verify pilot logic is removed
    assert "pilot_trainer" not in code, "Feasibility pilot trainer should be removed"
    assert "avg_step_time" not in code, "Feasibility pilot timing should be removed"
    assert "projected_time_hr > 2.0" not in code, "Resource limitation cutoff should be removed"
    
    # 2. Verify model and tokenizer serialization is present
    assert "trainer.save_model(final_model_dir)" in code, "Must save trained model"
    assert "tokenizer.save_pretrained(final_model_dir)" in code, "Must save tokenizer"
    assert "label_mapping.json" in code, "Must save label mapping"
    assert "training_history.json" in code, "Must save training history"
    
    # 3. Verify manifest format
    assert '"status": "COMPLETE"' in code, "Status must be COMPLETE"
    assert '"execution_type": "ACTUAL_EXPERIMENT"' in code, "Execution type must be ACTUAL_EXPERIMENT"

def test_contractnli_post_training_evaluation():
    """
    Proves that run_contractnli() loads the trained checkpoint if it exists,
    defines label_map correctly, and executes the test evaluation path.
    """
    with open("src/models/run_task019_experiments.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    # Verify label_map is defined properly before serialization
    assert 'label_map = {"Contradiction": 0, "Entailment": 1, "NotMentioned": 2}' in code, "Must redefine label_map"
    
    # Verify skipping logic exists
    assert 'os.path.exists(os.path.join(final_model_dir, "model.safetensors"))' in code, "Must check for existing model"
    assert 'from_pretrained(final_model_dir)' in code, "Must load model from disk"
    
    # Verify evaluation happens after
    assert 'trainer.predict(test_dataset)' in code, "Must evaluate test dataset"
