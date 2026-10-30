import json
import os
from collections import defaultdict

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"
with open(f"{model_dir}/label_mapping.json", "r") as f:
    lm = json.load(f)

l2i = lm.get("label2id", {})
i2l = lm.get("id2label", {})

print(f"Total labels in taxonomy: {len(l2i)}")

# Look for exact or canonical contract headings in LEDGAR
target_headings = [
    "governing law",
    "governing laws",
    "applicable law",
    "choice of law",
    "jurisdiction",
    "submission to jurisdiction",
    "indemnification",
    "indemnity",
    "limitation of liability",
    "limitation on liability",
    "limitations of liability",
    "limitations on liability",
    "liability",
    "confidentiality",
    "confidential information",
    "termination",
    "termination for convenience",
    "arbitration",
    "non-competition",
    "non-compete",
    "severability"
]

print("\nDirect matches in LEDGAR taxonomy:")
for h in target_headings:
    if h in l2i:
        print(f"  EXACT MATCH: '{h}' -> idx {l2i[h]}")
    else:
        # Check partial
        matches = [k for k in l2i.keys() if k.lower() == h]
        if matches:
            print(f"  CASE MATCH: '{matches[0]}' -> idx {l2i[matches[0]]}")

print("\nAll LEDGAR labels starting with target words:")
for prefix in ["governing law", "limitation", "confidential", "indemn", "arbitrat", "severab", "terminat", "non-comp"]:
    matching = [(k, l2i[k]) for k in l2i.keys() if k.lower().startswith(prefix)]
    print(f"\nPrefix '{prefix}' ({len(matching)} labels):")
    for k, idx in matching[:10]:
        print(f"  idx {idx:5d}: {repr(k)}")
