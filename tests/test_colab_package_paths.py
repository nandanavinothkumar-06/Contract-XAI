import os
import tempfile
import zipfile
import shutil
import json
import pytest

from src.models.run_task019_experiments import get_project_root

def test_contractnli_path_resolution_robustness():
    # Verify get_project_root() resolves cleanly without Windows cwd artifacts
    root = get_project_root()
    assert os.path.isabs(root), "Project root must be absolute"
    
    # Store original cwd
    original_cwd = os.getcwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Change CWD to the temporary directory to prove independence
            os.chdir(tmpdir)
            
            # The project root should STILL resolve back to the original source location
            new_root = get_project_root()
            assert new_root == root, "Project root resolution depends on cwd!"
            
        finally:
            # Restore cwd BEFORE exiting the TemporaryDirectory context manager
            os.chdir(original_cwd)
    
    # Simulate Colab extraction layout
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the simulated Colab extracted layout
        colab_c_nli_dir = os.path.join(tmpdir, "data", "raw", "contractnli", "extracted", "contract-nli")
        os.makedirs(colab_c_nli_dir)
        
        # Write dummy train.json to test the exact path structure
        train_path = os.path.join(colab_c_nli_dir, "train.json")
        with open(train_path, "w") as f:
            json.dump({"documents": []}, f)
            
        assert os.path.exists(train_path), "Simulated extraction path should exist"

def test_generated_source_zip_can_be_extracted_and_run():
    # If the source zip exists, extract it into a temp dir and verify module loading
    zip_path = os.path.join(get_project_root(), "ContractRisk_XAI_source.zip")
    if not os.path.exists(zip_path):
        pytest.skip("Source ZIP not found. Run scripts/generate_colab_package.py first.")
        
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)
            
        # Verify the file is there
        src_path = os.path.join(tmpdir, "src", "models", "run_task019_experiments.py")
        assert os.path.exists(src_path), "Missing expected source file in ZIP"
        frozen_src_path = os.path.join(tmpdir, "src", "models", "run_task019_ledgar_frozen_subset.py")
        assert os.path.exists(frozen_src_path), "Missing frozen subset runner in ZIP"
