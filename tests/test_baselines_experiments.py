import pandas as pd
from src.baselines.experiments import BaselineExperiment

def test_baseline_experiment_not_applicable():
    config = {
        'dataset': 'CUAD',
        'task': 'SPAN_EXTRACTION',
        'model': 'TFIDF_LOGISTIC_REGRESSION',
        'is_test_fixture': True
    }
    exp = BaselineExperiment(config)
    res = exp.run(pd.DataFrame({'text': ['A'], 'label': [1], 'group': ['G1']}), 'text', 'label', 'group')
    assert res['status'] == 'NOT_APPLICABLE'

def test_baseline_experiment_run():
    config = {
        'dataset': 'TEST',
        'task': 'CLASSIFICATION',
        'model': 'TFIDF_LOGISTIC_REGRESSION',
        'random_state': 42,
        'is_test_fixture': True
    }
    exp = BaselineExperiment(config)
    
    df = pd.DataFrame({
        'text': ['This is good', 'This is bad', 'Another good one', 'A terrible one'],
        'label': [1, 0, 1, 0],
        'group': ['G1', 'G2', 'G3', 'G4']
    })
    
    res = exp.run(df, 'text', 'label', 'group')
    assert res['status'] == 'COMPLETED'
    assert 'metrics' in res
    assert 'macro_f1' in res['metrics']
    
def test_baseline_experiment_multilabel():
    config = {
        'dataset': 'TEST',
        'task': 'MULTI_LABEL_PROVISION_CLASSIFICATION',
        'model': 'TFIDF_OVR_LOGISTIC_REGRESSION',
        'random_state': 42,
        'is_test_fixture': True
    }
    exp = BaselineExperiment(config)
    
    df = pd.DataFrame({
        'text': ['Confidentiality and IP', 'Termination', 'IP and Term', 'Confidentiality'],
        'label': [['Conf', 'IP'], ['Term'], ['IP', 'Term'], ['Conf']],
        'group': ['G1', 'G2', 'G3', 'G4']
    })
    
    res = exp.run(df, 'text', 'label', 'group')
    assert res['status'] == 'COMPLETED'
    assert 'micro_f1' in res['metrics']

def test_genuine_baseline_results():
    import os, json
    manifest_path = "results/baseline/baseline_experiment_manifest.json"
    assert os.path.exists(manifest_path), "baseline_experiment_manifest.json must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_records"] >= 4
    
    exp_ids = {e["experiment_id"] for e in data["experiments"]}
    assert "TASK018_CONTRACTNLI_TFIDF_LR" in exp_ids
    assert "TASK018_CONTRACTNLI_TFIDF_SVM" in exp_ids
    assert "TASK018_CUAD_BASELINES" in exp_ids
    assert "TASK018_LEDGAR_TFIDF_OVR_LR" in exp_ids

    # Verify best ContractNLI model
    svm_file = "results/baseline/contractnli/TASK018_CONTRACTNLI_TFIDF_SVM.json"
    assert os.path.exists(svm_file)
    with open(svm_file, "r", encoding="utf-8") as f:
        svm_res = json.load(f)
    assert svm_res["status"] == "COMPLETED"
    assert svm_res["test_metrics"]["accuracy"] > 0.60
    assert svm_res["test_metrics"]["macro_f1"] > 0.50
    assert svm_res["is_test_fixture"] is False

    # Verify accounting
    acc = data["experiment_accounting"]
    assert acc["actual_ml_experiments_completed"] == 4
    assert acc["actual_ml_experiments_failed"] == 0
    assert acc["not_applicable"] == 3
    assert acc["feasibility_assessments"] == 2


