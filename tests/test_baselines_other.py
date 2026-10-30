import pandas as pd
from src.baselines.features import get_tfidf_vectorizer
from src.baselines.classifiers import get_classifier
from src.baselines.metrics import calculate_metrics
from src.baselines.results import save_experiment_result
from src.baselines.experiments import BaselineExperiment
from sklearn.pipeline import Pipeline
import os
import json

def test_tfidf_feature_generation():
    vectorizer = get_tfidf_vectorizer({'ngram_range': (1, 2)})
    X = vectorizer.fit_transform(["hello world", "world hello"])
    assert X.shape[0] == 2
    
def test_classifiers():
    clf1 = get_classifier("TFIDF_LOGISTIC_REGRESSION")
    assert type(clf1).__name__ == "LogisticRegression"
    
    clf2 = get_classifier("TFIDF_LINEAR_SVM")
    assert type(clf2).__name__ == "LinearSVC"
    
def test_ovr_classifiers():
    clf = get_classifier("TFIDF_OVR_LOGISTIC_REGRESSION")
    assert type(clf).__name__ == "OneVsRestClassifier"
    assert type(clf.estimator).__name__ == "LogisticRegression"
    
def test_metric_calculation():
    y_true = [1, 0, 1]
    y_pred = [1, 0, 0]
    metrics = calculate_metrics(y_true, y_pred, is_multilabel=False)
    assert 'accuracy' in metrics
    assert 'macro_f1' in metrics
    
    y_true_ml = [[1, 0], [0, 1]]
    y_pred_ml = [[1, 0], [1, 1]]
    metrics_ml = calculate_metrics(y_true_ml, y_pred_ml, is_multilabel=True)
    assert 'micro_f1' in metrics_ml
    assert 'hamming_loss' in metrics_ml
    
def test_result_serialization(tmp_path):
    res = {
        "experiment_id": "test_id",
        "dataset": "TEST",
        "metrics": {"macro_f1": 0.9}
    }
    save_experiment_result(res, output_dir=str(tmp_path))
    assert os.path.exists(os.path.join(tmp_path, "test_id.json"))
    assert os.path.exists(os.path.join(tmp_path, "baseline_results.csv"))
    
    with open(os.path.join(tmp_path, "test_id.json"), "r") as f:
        data = json.load(f)
        assert data["experiment_id"] == "test_id"
        assert "timestamp" in data
        
def test_unavailable_handling():
    exp = BaselineExperiment({'dataset': 'CLAUDETTE', 'task': 'CLASSIFICATION', 'model': 'TFIDF_LOGISTIC_REGRESSION'})
    df = pd.DataFrame()
    res = exp.run(df, 'text', 'label', 'group')
    assert res['status'] == 'NOT_RUN_LICENSE_UNRESOLVED'
