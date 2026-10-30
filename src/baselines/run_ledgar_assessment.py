import os
import json
import time
import psutil
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

def assess_ledgar():
    print("Reading LEDGAR metadata for split and feasibility analysis...")
    t0 = time.time()
    contracts = []
    labels = []
    sample_texts = []
    total_provs = 0
    all_label_set = set()

    with open("data/raw/ledgar/extracted/LEDGAR_2016-2019_clean.jsonl", "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            total_provs += 1
            d = json.loads(line)
            src = d.get("source", "")
            lbls = d.get("label", [])
            contracts.append(src)
            labels.append(lbls)
            for l in lbls:
                all_label_set.add(l)
            if idx < 1000:
                sample_texts.append(d.get("provision", ""))

    print(f"Read {total_provs} provisions in {time.time()-t0:.2f}s")
    print(f"Total distinct labels: {len(all_label_set)}")
    
    unique_contracts = len(set(contracts))
    print(f"Total distinct contracts: {unique_contracts}")

    df = pd.DataFrame({
        "id": list(range(total_provs)),
        "contract_id": contracts
    })

    # Group-aware split by contract_id: 80% train, 10% val, 10% test
    gss_test = GroupShuffleSplit(n_splits=1, test_size=0.1, random_state=42)
    train_val_idx, test_idx = next(gss_test.split(df, groups=df["contract_id"]))
    
    train_val_df = df.iloc[train_val_idx]
    test_df = df.iloc[test_idx]

    gss_val = GroupShuffleSplit(n_splits=1, test_size=0.1111, random_state=42)  # ~10% of total
    train_idx, val_idx = next(gss_val.split(train_val_df, groups=train_val_df["contract_id"]))
    
    train_df = train_val_df.iloc[train_idx]
    val_df = train_val_df.iloc[val_idx]

    # Check leakage
    train_contracts = set(train_df["contract_id"])
    val_contracts = set(val_df["contract_id"])
    test_contracts = set(test_df["contract_id"])

    train_val_leak = len(train_contracts.intersection(val_contracts))
    train_test_leak = len(train_contracts.intersection(test_contracts))
    val_test_leak = len(val_contracts.intersection(test_contracts))

    print(f"Train provisions: {len(train_df)}, contracts: {len(train_contracts)}")
    print(f"Val provisions: {len(val_df)}, contracts: {len(val_contracts)}")
    print(f"Test provisions: {len(test_df)}, contracts: {len(test_contracts)}")
    print(f"Contract leakage: train-val={train_val_leak}, train-test={train_test_leak}, val-test={val_test_leak}")

    # Resource assessment
    mem = psutil.virtual_memory()
    print(f"Available RAM: {mem.available / (1024**3):.2f} GB / {mem.total / (1024**3):.2f} GB")
    print(f"CPU count: {psutil.cpu_count(logical=True)} logical cores")

    # Timing benchmark for 1 binary classifier on 1,000 samples
    vec = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), min_df=2)
    X_sample = vec.fit_transform(sample_texts)
    y_sample = [1 if "governing laws" in labels[i] else 0 for i in range(1000)]
    
    t_clf = time.time()
    clf = LogisticRegression(max_iter=100)
    clf.fit(X_sample, y_sample)
    single_fit_time = time.time() - t_clf
    
    # Linear projection to train set (677k samples is ~677x larger)
    est_single_fit_on_train = single_fit_time * (len(train_df) / 1000.0) * 0.1 # optimistic sublinear scaling
    est_total_hours = (len(all_label_set) * max(est_single_fit_on_train, 2.0)) / 3600.0
    
    print(f"Benchmark single classifier fit on 1k sample: {single_fit_time:.4f}s")
    print(f"Estimated training time for all 12,608 OVR binary classifiers on {len(train_df)} train provisions: ~{est_total_hours:.1f} hours")

    return {
        "total_provisions": total_provs,
        "distinct_labels": len(all_label_set),
        "distinct_contracts": unique_contracts,
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
        "leakage": {
            "train_val": train_val_leak,
            "train_test": train_test_leak,
            "val_test": val_test_leak
        },
        "available_ram_gb": round(mem.available / (1024**3), 2),
        "total_ram_gb": round(mem.total / (1024**3), 2),
        "cpu_cores": psutil.cpu_count(logical=True),
        "estimated_hours": round(est_total_hours, 1)
    }

if __name__ == "__main__":
    assess_ledgar()
