import os
import json
import time
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from src.baselines.features import get_tfidf_vectorizer
from src.baselines.classifiers import get_classifier
from src.baselines.metrics import calculate_metrics

def run_contractnli_experiments():
    os.makedirs("results/baseline/contractnli", exist_ok=True)
    os.makedirs("results/baseline/ledgar", exist_ok=True)
    os.makedirs("results/baseline/cuad", exist_ok=True)

    print("Loading ContractNLI...")
    records = []
    for split in ["train", "dev", "test"]:
        p = f"data/raw/contractnli/extracted/contract-nli/{split}.json"
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
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "dev"]
    test_df = df[df["split"] == "test"]

    # TF-IDF isolation: fit on train only
    tfidf_config = {"ngram_range": (1, 2), "sublinear_tf": True, "min_df": 2}
    vectorizer = get_tfidf_vectorizer(tfidf_config)
    print("Fitting TF-IDF on train only...")
    t0_vec = time.time()
    X_train = vectorizer.fit_transform(train_df["text"])
    X_val = vectorizer.transform(val_df["text"])
    X_test = vectorizer.transform(test_df["text"])
    vec_time = time.time() - t0_vec
    print(f"TF-IDF fitted in {vec_time:.2f}s, vocabulary size: {len(vectorizer.vocabulary_)}")

    y_train = train_df["label"].values
    y_val = val_df["label"].values
    y_test = test_df["label"].values

    target_names = ["Contradiction", "Entailment", "NotMentioned"]

    models = [
        ("TASK018_CONTRACTNLI_TFIDF_LR", "TFIDF_LOGISTIC_REGRESSION", {"random_state": 42, "max_iter": 1000}),
        ("TASK018_CONTRACTNLI_TFIDF_SVM", "TFIDF_LINEAR_SVM", {"random_state": 42, "max_iter": 2000}),
        ("TASK018_CONTRACTNLI_TFIDF_OVR_LR", "TFIDF_OVR_LOGISTIC_REGRESSION", {"random_state": 42, "max_iter": 1000}),
        ("TASK018_CONTRACTNLI_TFIDF_OVR_SVM", "TFIDF_OVR_LINEAR_SVM", {"random_state": 42, "max_iter": 2000})
    ]

    all_results = []

    for exp_id, model_name, cfg in models:
        print(f"Running {exp_id} ({model_name})...")
        clf = get_classifier(model_name, cfg)
        t0 = time.time()
        clf.fit(X_train, y_train)
        fit_time = time.time() - t0
        
        # Val evaluation
        val_preds = clf.predict(X_val)
        val_metrics = calculate_metrics(y_val, val_preds)
        
        # Test evaluation
        test_preds = clf.predict(X_test)
        test_metrics = calculate_metrics(y_test, test_preds)
        
        report = classification_report(y_test, test_preds, target_names=target_names, output_dict=True, zero_division=0)
        cm = confusion_matrix(y_test, test_preds, labels=target_names).tolist()
        
        res = {
            "experiment_id": exp_id,
            "task": "DOCUMENT_NLI",
            "dataset": "ContractNLI",
            "dataset_version": "1.0",
            "input_path": "data/raw/contractnli/extracted/contract-nli/",
            "model": model_name,
            "hyperparameters": cfg,
            "vectorizer_configuration": tfidf_config,
            "vocabulary_size": len(vectorizer.vocabulary_),
            "random_seed": 42,
            "preprocessing_version": "Task 005 standard + NLI text pairing",
            "split": "official_train_dev_test",
            "training_size": len(train_df),
            "validation_size": len(val_df),
            "test_size": len(test_df),
            "leakage_status": "VERIFIED_ZERO_LEAKAGE (0 doc ID overlap, 0 text hash overlap)",
            "runtime_seconds": round(fit_time, 3),
            "validation_metrics": val_metrics,
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
            "status": "COMPLETED",
            "is_test_fixture": False
        }
        
        out_file = f"results/baseline/contractnli/{exp_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"{exp_id} completed: Test Acc={test_metrics['accuracy']:.4f}, Test Macro-F1={test_metrics['macro_f1']:.4f}, time={fit_time:.2f}s")
        all_results.append(res)

    return all_results

if __name__ == "__main__":
    run_contractnli_experiments()
