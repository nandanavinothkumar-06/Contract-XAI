import json
import os

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"

with open(os.path.join(model_dir, "label_mapping.json"), "r") as f:
    lm = json.load(f)

l2i = lm.get("label2id", {})
i2l = lm.get("id2label", {})

print("Sample 10 items from label2id in label_mapping.json:")
for k in list(l2i.keys())[:10]:
    print(f"  {repr(k)}: {l2i[k]}")

print("\nSample 10 items from id2label in label_mapping.json:")
for k in list(i2l.keys())[:10]:
    print(f"  {repr(k)}: {repr(i2l[k])}")

# Search for relevant terms in label2id
print("\nSearching terms in label2id:")
for term in ["governing law", "confidential", "liability", "indemn", "arbitrat", "termination"]:
    matches = [(k, v) for k, v in l2i.items() if term in k.lower()]
    print(f"Term '{term}': {len(matches)} matches")
    for m in matches[:3]:
        print(f"  {m[0]}: {m[1]}")
