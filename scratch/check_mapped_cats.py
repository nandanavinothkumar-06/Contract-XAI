import json
import numpy as np

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"
with open(f"{model_dir}/label_mapping.json", "r") as f:
    lm = json.load(f)

l2i = lm.get("label2id", {})
i2l = lm.get("id2label", {})

# Check how screening._build_label_mapping maps labels:
mapping = {}
for name, idx in l2i.items():
    lower = name.lower()
    idx_int = int(idx)
    if "indemn" in lower:
        mapping[idx_int] = ("INDEMNIFICATION", name)
    elif "limitation of liability" in lower or "limit of liability" in lower or "limitations of liability" in lower:
        mapping[idx_int] = ("LIMITATION_OF_LIABILITY", name)
    elif "termination" in lower:
        mapping[idx_int] = ("TERMINATION_CONVENIENCE", name)
    elif "arbitrat" in lower:
        mapping[idx_int] = ("ARBITRATION_EXCLUSIVE_JURISDICTION", name)
    elif "governing law" in lower or "jurisdiction" in lower:
        mapping[idx_int] = ("GOVERNING_LAW_DISPUTE", name)
    elif "confidential" in lower:
        mapping[idx_int] = ("CONFIDENTIALITY_UNILATERAL", name)
    elif "non-compete" in lower or "noncompetition" in lower:
        mapping[idx_int] = ("NON_COMPETE_RESTRAINT", name)
    elif "severability" in lower:
        mapping[idx_int] = ("SEVERABILITY_RESTRAINT", name)

print(f"Total mapped indices in label_mapping: {len(mapping)}")
from collections import Counter
counts = Counter(cat for cat, raw in mapping.values())
for cat, cnt in counts.items():
    print(f"  {cat}: {cnt} LEDGAR labels")

# Look at labels that contain 'liability' that weren't captured by 'limitation of liability'
print("\nLabels containing 'liability' not mapped:")
for name, idx in l2i.items():
    lower = name.lower()
    if "liability" in lower and int(idx) not in mapping:
        print(f"  idx {idx}: {name}")
