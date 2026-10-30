import sys
sys.path.insert(0, '.')
import json
import torch
import numpy as np

from src.models.legalbert import LegalBertWrapper
from src.models.config import LegalBertConfig
from src.models.prediction import predict

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"
with open(f"{model_dir}/label_mapping.json", "r") as f:
    lm = json.load(f)
i2l = {int(k): v for k, v in lm.get("id2label", {}).items()}
l2i = {k: int(v) for k, v in lm.get("label2id", {}).items()}

config = LegalBertConfig(
    model_name="ledgar-legalbert-frozen",
    model_family="legal-bert",
    model_checkpoint=model_dir,
    tokenizer_name=model_dir,
    num_labels=len(i2l),
    classification_mode="multilabel",
    multilabel_threshold=0.04
)
wrapper = LegalBertWrapper(config)

text_lol = "Neither party shall be liable for indirect or consequential damages, except where otherwise provided in this Agreement."
preds, probs, truncs = predict(wrapper, [text_lol])
p = probs[0]

print("--- Probabilities for Liability related labels ---")
for idx in [5978, 6035, 5873, 5879, 5874, 6078, 4741]:
    print(f"  idx {idx:5d} ({i2l[idx]}): prob = {p[idx]:.5f}")

text_conf = "Each party shall protect confidential information received from the other party and shall not disclose it without authorization."
preds_c, probs_c, truncs_c = predict(wrapper, [text_conf])
p_c = probs_c[0]

print("\n--- Probabilities for Confidentiality related labels ---")
conf_indices = [idx for name, idx in l2i.items() if "confidential" in name.lower()]
print(f"Total confidential labels: {len(conf_indices)}")
top_conf = sorted([(idx, p_c[idx], i2l[idx]) for idx in conf_indices], key=lambda x: x[1], reverse=True)[:5]
for idx, prob, name in top_conf:
    print(f"  idx {idx:5d} ({name}): prob = {prob:.5f}")
print(f"  idx 4741 ({i2l[4741]}): prob = {p_c[4741]:.5f}")
