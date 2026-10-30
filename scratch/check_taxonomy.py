import json
import os

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"

with open(os.path.join(model_dir, "config.json"), "r") as f:
    cfg = json.load(f)
id2label = cfg.get("id2label", {})
label2id = cfg.get("label2id", {})
print("config.json id2label count:", len(id2label))
print("config.json label2id count:", len(label2id))

with open(os.path.join(model_dir, "label_mapping.json"), "r") as f:
    lm = json.load(f)
print("label_mapping.json keys:", list(lm.keys()))
lm_l2i = lm.get("label2id", {})
lm_i2l = lm.get("id2label", {})
print("label_mapping.json label2id count:", len(lm_l2i))
print("label_mapping.json id2label count:", len(lm_i2l))

# Print first 20 id2label
sample_ids = list(id2label.items())[:15]
print("\nSample config id2label:")
for k, v in sample_ids:
    print(f"  {k}: {v}")

# Look for governing law, indemnification, confidentiality, limitation of liability in id2label
print("\nSearching for categories in id2label:")
for k, v in id2label.items():
    v_lower = v.lower()
    if any(term in v_lower for term in ["governing law", "confidential", "liability", "indemn", "arbitrat", "termination"]):
        print(f"  id {k}: {v}")
