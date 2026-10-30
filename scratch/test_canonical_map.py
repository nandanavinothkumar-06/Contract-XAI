import json
import os

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"
with open(os.path.join(model_dir, "label_mapping.json"), "r") as f:
    lm = json.load(f)

l2i = lm.get("label2id", {})
i2l = lm.get("id2label", {})

# Exact canonical dictionary mapping specific LEDGAR label names to Indian commercial risk categories
CANONICAL_LEDGAR_TAXONOMY_MAP = {
    # 1. GOVERNING_LAW_DISPUTE
    "governing laws": "GOVERNING_LAW_DISPUTE",
    "governing law: jurisdiction": "GOVERNING_LAW_DISPUTE",
    "submission to jurisdiction": "GOVERNING_LAW_DISPUTE",
    "jurisdiction": "GOVERNING_LAW_DISPUTE",
    "applicable law": "GOVERNING_LAW_DISPUTE",
    "choice of law": "GOVERNING_LAW_DISPUTE",

    # 2. INDEMNIFICATION
    "indemnity": "INDEMNIFICATION",
    "indemnification - general": "INDEMNIFICATION",
    "indemnification": "INDEMNIFICATION",
    "indemnifications": "INDEMNIFICATION",
    "additional indemnification": "INDEMNIFICATION",
    "additional indemnity": "INDEMNIFICATION",

    # 3. LIMITATION_OF_LIABILITY
    "limitation of liability": "LIMITATION_OF_LIABILITY",
    "limitation on liability": "LIMITATION_OF_LIABILITY",
    "limitations of liability": "LIMITATION_OF_LIABILITY",
    "limitations on liability": "LIMITATION_OF_LIABILITY",
    "limitation of consequential damages": "LIMITATION_OF_LIABILITY",
    "limitation of damages": "LIMITATION_OF_LIABILITY",
    "limits of liability": "LIMITATION_OF_LIABILITY",
    "liability limitations": "LIMITATION_OF_LIABILITY",

    # 4. CONFIDENTIALITY_UNILATERAL
    "confidentiality": "CONFIDENTIALITY_UNILATERAL",
    "confidential information": "CONFIDENTIALITY_UNILATERAL",
    "confidential terms": "CONFIDENTIALITY_UNILATERAL",
    "confidential": "CONFIDENTIALITY_UNILATERAL",
    "confidential agreement": "CONFIDENTIALITY_UNILATERAL",
    "confidentiality agreements": "CONFIDENTIALITY_UNILATERAL",

    # 5. TERMINATION_CONVENIENCE
    "termination for convenience": "TERMINATION_CONVENIENCE",
    "termination": "TERMINATION_CONVENIENCE",
    "termination by company": "TERMINATION_CONVENIENCE",
    "termination by company without cause": "TERMINATION_CONVENIENCE",
    "terminations": "TERMINATION_CONVENIENCE",

    # 6. ARBITRATION_EXCLUSIVE_JURISDICTION
    "arbitration": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "arbitration procedures": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "arbitration of disputes": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "arbitration agreements": "ARBITRATION_EXCLUSIVE_JURISDICTION",
    "agreement to arbitrate": "ARBITRATION_EXCLUSIVE_JURISDICTION",

    # 7. SEVERABILITY_RESTRAINT
    "severability": "SEVERABILITY_RESTRAINT",
    "severability clause": "SEVERABILITY_RESTRAINT",
    "severability of provisions": "SEVERABILITY_RESTRAINT",

    # 8. NON_COMPETE_RESTRAINT
    "non-compete agreements": "NON_COMPETE_RESTRAINT",
    "non-competition agreements": "NON_COMPETE_RESTRAINT",
    "non-competition covenants": "NON_COMPETE_RESTRAINT",
}

mapped_indices = {}
for name, cat in CANONICAL_LEDGAR_TAXONOMY_MAP.items():
    if name in l2i:
        mapped_indices[int(l2i[name])] = (cat, name)

print(f"Mapped indices count: {len(mapped_indices)}")
for idx, (cat, name) in sorted(mapped_indices.items()):
    print(f"  idx {idx:5d} -> {cat}: {repr(name)}")
