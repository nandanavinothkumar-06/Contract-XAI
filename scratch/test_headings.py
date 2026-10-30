import sys
sys.path.insert(0, '.')
import json
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

test_clauses = [
    ("Governing Law with Heading", "1. Governing Law:\nThis Agreement shall be governed by the laws of India. The courts of New Delhi shall have exclusive jurisdiction."),
    ("Indemnification with Heading", "2. Indemnification:\nThe Contractor shall indemnify and hold harmless the Client against third-party claims, liabilities, damages, and reasonable expenses."),
    ("Limitation of Liability with Heading", "3. Limitation of Liability:\nNeither party shall be liable for indirect or consequential damages, except where otherwise provided in this Agreement."),
    ("Confidentiality with Heading", "4. Confidentiality:\nEach party shall protect confidential information received from the other party and shall not disclose it without authorization."),
    ("Standard LEDGAR Confidentiality", "CONFIDENTIALITY. The parties agree to hold all Confidential Information in strict confidence and not to disclose such Confidential Information to any third party."),
    ("Standard LEDGAR Limitation on Liability", "LIMITATION ON LIABILITY. IN NO EVENT SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, SPECIAL, INCIDENTAL, CONSEQUENTIAL OR PUNITIVE DAMAGES.")
]

for title, text in test_clauses:
    preds, probs, truncs = predict(wrapper, [text])
    p = probs[0]
    top_indices = np.argsort(p)[::-1][:5]
    print(f"\n==================================================")
    print(f"{title}")
    for idx in top_indices:
        label_name = i2l.get(idx, f"LABEL_{idx}")
        prob = p[idx]
        print(f"  idx {idx:5d}: prob={prob:.5f} | {label_name}")
