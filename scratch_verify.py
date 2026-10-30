import os
import hashlib
import zipfile
import pandas as pd
from pathlib import Path
from src.models.run_task019_experiments import get_ledgar_data, get_project_root

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def sha256_bytes(b):
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

print("--- 1. Testing Local get_ledgar_data() ---")
df = get_ledgar_data()

train_df = df[df["split"] == "train"]
val_df = df[df["split"] == "val"]
test_df = df[df["split"] == "test"]

train_contracts = set(train_df["contract_id"].unique())
val_contracts = set(val_df["contract_id"].unique())
test_contracts = set(test_df["contract_id"].unique())

total_contracts = len(set(df["contract_id"].unique()))

all_labels = set()
for labels in df["labels"]:
    all_labels.update(labels)

print(f"Train provisions: {len(train_df)}")
print(f"Validation provisions: {len(val_df)}")
print(f"Test provisions: {len(test_df)}")
print(f"Train contracts: {len(train_contracts)}")
print(f"Validation contracts: {len(val_contracts)}")
print(f"Test contracts: {len(test_contracts)}")
print(f"Total contracts: {total_contracts}")
print(f"Total labels: {len(all_labels)}")
print(f"Train/Val overlap: {len(train_contracts.intersection(val_contracts))}")
print(f"Train/Test overlap: {len(train_contracts.intersection(test_contracts))}")
print(f"Val/Test overlap: {len(val_contracts.intersection(test_contracts))}")

print("\n--- 2. Checking SHAs and Packaged Source ---")
local_path = "src/models/run_task019_experiments.py"
local_sha = sha256_file(local_path)
print(f"Local SHA: {local_sha}")

zip_path = "ContractRisk_XAI_source.zip"
if not os.path.exists(zip_path):
    print(f"ZIP {zip_path} not found!")
else:
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Need to check exactly what path it uses inside the zip
        target_name = None
        for name in z.namelist():
            if name.endswith("run_task019_experiments.py"):
                target_name = name
                break
        if target_name:
            print(f"Found in zip: {target_name}")
            data = z.read(target_name)
            zip_sha = sha256_bytes(data)
            print(f"Packaged SHA: {zip_sha}")
            print(f"Match: {local_sha == zip_sha}")
            
            # Print get_ledgar_data source from zip
            lines = data.decode('utf-8').splitlines()
            in_func = False
            for line in lines:
                if line.startswith("def get_ledgar_data():"):
                    in_func = True
                if in_func:
                    print(line)
                    if line.strip() == "return df" or line.strip() == "return pd.DataFrame(records)":
                        break
        else:
            print("File not found in zip!")
