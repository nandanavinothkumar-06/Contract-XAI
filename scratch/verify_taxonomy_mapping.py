import json

model_dir = "results/models/ledgar_frozen_subset_fresh/final_model"
with open(f"{model_dir}/label_mapping.json", "r") as f:
    lm = json.load(f)

l2i = lm.get("label2id", {})
i2l = lm.get("id2label", {})

canonical_taxonomy = {
    "GOVERNING_LAW_DISPUTE": [
        "governing laws",
        "governing law: jurisdiction",
        "submission to jurisdiction",
        "jurisdiction",
        "applicable law",
        "choice of law"
    ],
    "INDEMNIFICATION": [
        "indemnity",
        "indemnification - general",
        "indemnification",
        "indemnifications"
    ],
    "LIMITATION_OF_LIABILITY": [
        "limitation of liability",
        "limitation on liability",
        "limitations of liability",
        "limitations on liability",
        "limitation of consequential damages",
        "limitation of damages",
        "limits of liability",
        "liability limitations"
    ],
    "CONFIDENTIALITY_UNILATERAL": [
        "confidentiality",
        "confidential information",
        "confidential terms",
        "confidential"
    ],
    "TERMINATION_CONVENIENCE": [
        "termination for convenience",
        "termination",
        "termination by company",
        "termination by company without cause"
    ],
    "ARBITRATION_EXCLUSIVE_JURISDICTION": [
        "arbitration",
        "arbitration procedures",
        "arbitration of disputes",
        "arbitration agreements"
    ],
    "SEVERABILITY_RESTRAINT": [
        "severability",
        "severability clause",
        "severability of provisions"
    ],
    "NON_COMPETE_RESTRAINT": [
        "non-compete agreements",
        "non-competition agreements",
        "non-competition covenants"
    ]
}

print("=== CANONICAL TAXONOMY INDEX VERIFICATION ===")
verified_mapping = {}
for category, label_list in canonical_taxonomy.items():
    found = []
    for lbl in label_list:
        if lbl in l2i:
            idx = int(l2i[lbl])
            verified_mapping[idx] = (category, lbl)
            found.append((idx, lbl))
    print(f"\n{category} ({len(found)} verified canonical indices):")
    for idx, lbl in found:
        print(f"  idx {idx:5d} -> exact saved label: {repr(lbl)}")
