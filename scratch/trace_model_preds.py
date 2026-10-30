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

clauses = [
    ("Governing Law", "This Agreement shall be governed by the laws of India. The courts of New Delhi shall have exclusive jurisdiction."),
    ("Indemnification", "The Contractor shall indemnify and hold harmless the Client against third-party claims, liabilities, damages, and reasonable expenses."),
    ("Limitation of Liability", "Neither party shall be liable for indirect or consequential damages, except where otherwise provided in this Agreement."),
    ("Confidentiality", "Each party shall protect confidential information received from the other party and shall not disclose it without authorization.")
]

for title, text in clauses:
    preds, probs, truncs = predict(wrapper, [text])
    p = probs[0]
    top_indices = np.argsort(p)[::-1][:10]
    print(f"\n==================================================")
    print(f"CLAUSE: {title}")
    print(f"TEXT: {text}")
    print("--- TOP 10 OVERALL LABELS ---")
    for idx in top_indices:
        label_name = i2l.get(idx, f"LABEL_{idx}")
        prob = p[idx]
        print(f"  idx {idx:5d}: prob={prob:.5f} | {label_name}")
