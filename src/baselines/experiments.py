import pandas as pd
from typing import Dict, Any
import hashlib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer
from .features import get_tfidf_vectorizer
from .classifiers import get_classifier
from .splitting import group_aware_split
from .leakage import check_leakage
from .metrics import calculate_metrics
from .results import save_experiment_result

class BaselineExperiment:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.dataset = config.get('dataset', 'unknown')
        self.task = config.get('task', 'unknown')
        self.model_name = config.get('model', 'unknown')
        self.seed = config.get('random_state', 42)
        self.exp_id = self._generate_id()
        
    def _generate_id(self) -> str:
        s = f"{self.dataset}_{self.task}_{self.model_name}_{self.seed}"
        return hashlib.md5(s.encode()).hexdigest()[:12]
        
    def run(self, df: pd.DataFrame, text_col: str, label_col: str, group_col: str):
        res = {
            "experiment_id": self.exp_id,
            "dataset": self.dataset,
            "task": self.task,
            "model": self.model_name,
            "feature_type": "TF-IDF",
            "parameters": self.config,
            "seed": self.seed,
            "status": "IN_PROGRESS"
        }
        
        if self.task == "SPAN_EXTRACTION":
            res["status"] = "NOT_APPLICABLE"
            res["note"] = "CUAD is primarily a contract-review QA/span-extraction task; the classification baselines implemented in TASK 007 are not directly comparable."
            save_experiment_result(res, is_test_fixture=self.config.get('is_test_fixture', False))
            return res
            
        if self.dataset == "CLAUDETTE":
            res["status"] = "NOT_RUN_LICENSE_UNRESOLVED"
            save_experiment_result(res, is_test_fixture=self.config.get('is_test_fixture', False))
            return res
            
        if df.empty:
            res["status"] = "NOT_RUN_DATA_UNAVAILABLE"
            save_experiment_result(res, is_test_fixture=self.config.get('is_test_fixture', False))
            return res
            
        try:
            train, val, test = group_aware_split(df, group_col, random_state=self.seed)
            has_leakage, leak_details = check_leakage(train, val, test, group_col, text_col)
            
            if has_leakage:
                res["status"] = "FAILED_LEAKAGE_CHECK"
                res["error"] = f"Data leakage detected: {leak_details}"
                save_experiment_result(res, is_test_fixture=self.config.get('is_test_fixture', False))
                return res
                
            res["n_train"] = len(train)
            res["n_validation"] = len(val)
            res["n_test"] = len(test)
            
            X_train = train[text_col].tolist()
            y_train = train[label_col].tolist()
            X_test = test[text_col].tolist()
            y_test = test[label_col].tolist()
            
            is_multilabel = isinstance(y_train[0], list) or isinstance(y_train[0], tuple)
            
            if is_multilabel:
                mlb = MultiLabelBinarizer()
                y_train = mlb.fit_transform(y_train)
                y_test = mlb.transform(y_test)
                
            pipeline = Pipeline([
                ('tfidf', get_tfidf_vectorizer(self.config.get('tfidf_config', {}))),
                ('clf', get_classifier(self.model_name, self.config))
            ])
            
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)
            
            metrics = calculate_metrics(y_test, y_pred, is_multilabel)
            res["metrics"] = metrics
            res["status"] = "COMPLETED"
            
        except Exception as e:
            res["status"] = "FAILED"
            res["error"] = str(e)
            
        save_experiment_result(res, is_test_fixture=self.config.get('is_test_fixture', False))
        return res
