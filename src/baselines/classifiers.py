"""Baseline classifiers."""
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.multiclass import OneVsRestClassifier

def get_classifier(model_name: str, config: dict = None):
    config = config or {}
    random_state = config.get('random_state', 42)
    class_weight = config.get('class_weight', None)
    
    if model_name == "TFIDF_LOGISTIC_REGRESSION":
        return LogisticRegression(random_state=random_state, class_weight=class_weight, max_iter=1000)
    elif model_name == "TFIDF_LINEAR_SVM":
        return LinearSVC(random_state=random_state, class_weight=class_weight, max_iter=2000, dual=False)
    elif model_name == "TFIDF_OVR_LOGISTIC_REGRESSION":
        base_clf = LogisticRegression(random_state=random_state, class_weight=class_weight, max_iter=1000)
        return OneVsRestClassifier(base_clf)
    elif model_name == "TFIDF_OVR_LINEAR_SVM":
        base_clf = LinearSVC(random_state=random_state, class_weight=class_weight, max_iter=2000, dual=False)
        return OneVsRestClassifier(base_clf)
    else:
        raise ValueError(f"Unknown baseline model: {model_name}")
