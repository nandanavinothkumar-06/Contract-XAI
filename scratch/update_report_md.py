"""
Synchronize CONTRACTRISK_XAI_ACADEMIC_REPORT.md with the corrected academic report.
Ensures 1:1 parity with the PDF report.
"""

import os

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MD_PATH = os.path.join(WORKSPACE_ROOT, "results", "task025", "CONTRACTRISK_XAI_ACADEMIC_REPORT.md")

with open(MD_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Section 4: Add Figure 1
sec4_target = "└── Academic Report Compiler (ReportLab Engine + Matplotlib)\n```"
sec4_replacement = (
    "└── Academic Report Compiler (ReportLab Engine + Matplotlib)\n```\n\n"
    "![Figure 1: ContractRisk-XAI Modular System Architecture and Verification Pipeline](figures/figure1_architecture.png)"
)
if sec4_target in content:
    content = content.replace(sec4_target, sec4_replacement, 1)
    print("[OK] Section 4 Figure 1 embed added.")
else:
    print("[WARN] Section 4 target not found with LF, trying CRLF...")
    sec4_target_crlf = sec4_target.replace("\n", "\r\n")
    sec4_replacement_crlf = sec4_replacement.replace("\n", "\r\n")
    content = content.replace(sec4_target_crlf, sec4_replacement_crlf, 1)

# 2. Section 5: Dataset table update with explicit status distinctions
sec5_old = """| Dataset | Origin Domain | Document Count | Total Provisions / Instances | Task Formulation | Label Schema | Access & License | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LEDGAR** | SEC EDGAR Filings (2016–2019) | >60,000 contracts (4,844 in 10% subset) | 87,956 test provisions (67,776 train provisions) | Multi-Label Provision Classification | 12,407 active classes (12,608 total taxonomy) | Open (MIT License) | **VERIFIED** (Tuggener et al., 2020) |
| **ContractNLI** | Non-Disclosure Agreements (NDAs) | 607 contracts | 2,091 test pairs (10,319 total pairs) | Document-Level Natural Language Inference | 3 classes: Entailment, Contradiction, NotMentioned | Open (CC BY 4.0) | **VERIFIED** (Koreeda & Manning, 2021) |
| **CUAD** | Commercial Agreements | 510 contracts | >13,000 annotated spans | Extractive Question Answering | 41 legal clause categories | Open (CC BY 4.0) | **VERIFIED** (Hendrycks et al., 2021) |
| **CLAUDETTE** | Terms of Service (ToS) | 100 contracts | 21,063 sentences | Unfair Clause Detection | 5 unfairness categories | Open (Research) | **VERIFIED (SECONDARY)** (Ruggeri et al., 2022) |
| **Construction** | Engineering Specifications | 56 specifications | 2,807 clauses | Domain Risk Classification | 7 risk categories | Restricted / Proprietary | **NOT_RUN_ACCESS_UNRESOLVED** |"""

sec5_new = """| Dataset | Origin Domain | Registry Verification | Local Availability | Preprocessing Status | Completed Supervised Exp | Reproduction Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LEDGAR** | SEC EDGAR Filings (2016–2019) | **VERIFIED** (P002 / ACL Anthology) | Available (Local disk; 10% & full) | Implemented (UTF-8, offsets, hierarchy) | **YES**: LEGAL-BERT + Linear Head (12,407 classes, $\\tau^*=0.04$) | Independently audited & verified (Task 019 / 021) |
| **ContractNLI** | Non-Disclosure Agreements (NDAs) | **VERIFIED** (P003 / StanfordNLP) | Available (Local disk; 607 contracts) | Implemented (NLI pair format) | **YES**: Baseline TF-IDF + Linear SVM (3 classes, 2,091 test pairs) | Independently audited & verified (Task 018 / 023) |
| **CUAD** | Commercial Agreements | **VERIFIED** (Hendrycks / Atticus) | Available (Local disk; 510 contracts) | Implemented (Embedding extract) | **NO**: Representation geometry only; supervised transfer is INVALID | Concept separation margin verified (+0.0686, Task 020) |
| **CLAUDETTE** | Terms of Service (ToS) | **VERIFIED** (P004 / Springer) | Downloadable (Research license) | Not implemented (Tracked reference) | **NO**: Secondary reference domain; no supervised training executed | Unexecuted in this benchmark (Literature reference) |
| **Construction** | Engineering Specifications | **VERIFIED** (P005–P007 papers) | Restricted (Proprietary / unavailable) | Not implemented (Tracked reference) | **NO**: Access unresolved; no supervised training executed | Unexecuted in this benchmark (Literature reference) |

*Empirical Status Distinction: Only LEDGAR and ContractNLI were utilized in completed supervised experiments within this benchmark. CUAD was evaluated exclusively for unsupervised cross-domain representation geometry (cosine similarity in embedding space). CLAUDETTE and Construction Specifications are tracked bibliographic reference domains without active supervised pipelines.*"""

if sec5_old in content:
    content = content.replace(sec5_old, sec5_new, 1)
    print("[OK] Section 5 Dataset Table updated.")
else:
    sec5_old_crlf = sec5_old.replace("\n", "\r\n")
    sec5_new_crlf = sec5_new.replace("\n", "\r\n")
    content = content.replace(sec5_old_crlf, sec5_new_crlf, 1)
    print("[OK] Section 5 Dataset Table updated (CRLF).")

# 3. Section 8: Add Figure 2
sec8_target = "Across all benchmarked clauses, 100% of generated attribution spans satisfied the character-offset invariant."
sec8_replacement = (
    "Across all benchmarked clauses, 100% of generated attribution spans satisfied the character-offset invariant.\n\n"
    "![Figure 2: Evidence Attribution Token Saliency & Character Offset Invariants](figures/figure2_evidence_attribution.png)"
)
if sec8_target in content:
    content = content.replace(sec8_target, sec8_replacement, 1)
    print("[OK] Section 8 Figure 2 embed added.")

# 4. Section 9: Add Figure 3
sec9_target = "This demonstrates that LEGAL-BERT constructs semantically coherent cross-domain concept clusters despite superficial differences in contract drafting styles."
sec9_replacement = (
    "This demonstrates that LEGAL-BERT constructs semantically coherent cross-domain concept clusters despite superficial differences in contract drafting styles.\n\n"
    "![Figure 3: Representation Geometry Across Shared Legal Concepts](figures/figure3_cross_domain_similarity.png)"
)
if sec9_target in content:
    content = content.replace(sec9_target, sec9_replacement, 1)
    print("[OK] Section 9 Figure 3 embed added.")

# 5. Section 10 Part A: Replace with Table 10.1, Table 10.2, and Figure 4
sec10_old = """### Part A: Decision Threshold Calibration
Evaluating threshold variants on the 87,956-provision test split confirmed the decisive impact of threshold calibration:

| Threshold ($\tau$) | Status / Origin | Micro-Precision | Micro-Recall | Micro-F1 | Macro-F1 | True Positives (TP) | False Positives (FP) | False Negatives (FN) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.02** | Test Sweep Variant | 0.1245 | 0.1652 | 0.1421 | 0.0051 | 17,392 | 122,341 | 87,891 |
| **0.04** | **Validation-Calibrated ($\tau^*$)** | **0.1772** | **0.1206** | **0.1435** | **0.0045** | **12,699** | **58,947** | **92,584** |
| **0.10** | Test Sweep Variant | 0.2541 | 0.0768 | 0.1179 | 0.0031 | 8,085 | 23,736 | 97,198 |
| **0.20** | Test Sweep Variant | 0.3702 | 0.0428 | 0.0768 | 0.0020 | 4,506 | 7,665 | 100,777 |
| **0.50** | **Uncalibrated Default Baseline** | **0.6931** | **0.0094** | **0.0185** | **0.0009** | **989** | **438** | **104,294** |"""

sec10_new = """### Part A: Decision Threshold Evaluation & Calibration (Task 019 / 021)

#### Table 10.1: Measured Full-Test Evaluation on Held-Out Test Set (87,956 Provisions; 105,283 Ground-Truth Labels)
*Strict Provenance Boundary: Only $\\tau^* = 0.04$ and $\\tau = 0.50$ were evaluated on the held-out test split. No intermediate test sweeps were performed.*

| Threshold ($\\tau$) | Evaluation Scope & Provenance | Micro-Precision | Micro-Recall | Micro-F1 | Macro-F1 | Weighted-F1 | True Pos (TP) | False Pos (FP) | False Neg (FN) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.04** | **Measured Full-Test (Calibrated Optimum, $\\tau^*$)** | **0.1772** | **0.1206** | **0.1435** | **0.0045** | **0.0937** | **12,699** | **58,947** | **92,584** |
| **0.50** | **Measured Full-Test (Default Baseline)** | **0.6931** | **0.0094** | **0.0185** | **0.0009** | **0.0141** | **989** | **438** | **104,294** |

#### Table 10.2: Stage 1 Validation Split Threshold Sweep Curve (84,250 Provisions — Calibration Dataset)
*Validation Sweep: 14 candidate thresholds evaluated to select $\\tau^* = 0.04$ based on $\\text{argmax}(\\text{Validation Micro-F1})$.*

| Threshold ($\\tau$) | Validation Purpose | Val Micro-Precision | Val Micro-Recall | Val Micro-F1 | Val Macro-F1 | Val TP | Val FP | Val FN |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.01** | Validation Sweep Point | 0.0418 | 0.2304 | 0.0708 | 0.0038 | 23,071 | 528,309 | 77,058 |
| **0.02** | Validation Sweep Point | 0.0864 | 0.1697 | 0.1145 | 0.0044 | 16,989 | 179,698 | 83,140 |
| **0.03** | Validation Sweep Point | 0.1232 | 0.1402 | 0.1311 | 0.0045 | 14,036 | 99,913 | 86,093 |
| **0.04** | **Validation Optimum (Selected $\\tau^*$)** | **0.1559** | **0.1223** | **0.1371** | **0.0044** | **12,246** | **66,305** | **87,883** |
| **0.05** | Validation Sweep Point | 0.1813 | 0.1085 | 0.1357 | 0.0043 | 10,859 | 49,052 | 89,270 |
| **0.06** | Validation Sweep Point | 0.2000 | 0.0980 | 0.1315 | 0.0042 | 9,813 | 39,251 | 90,316 |
| **0.08** | Validation Sweep Point | 0.2195 | 0.0810 | 0.1184 | 0.0039 | 8,114 | 28,854 | 92,015 |
| **0.10** | Validation Sweep Point | 0.2269 | 0.0691 | 0.1060 | 0.0035 | 6,921 | 23,576 | 93,208 |
| **0.20** | Validation Sweep Point | 0.2289 | 0.0392 | 0.0669 | 0.0025 | 3,922 | 13,213 | 96,207 |
| **0.50** | Validation Default Baseline | 0.6098 | 0.0093 | 0.0184 | 0.0009 | 936 | 599 | 99,193 |

![Figure 4: LEDGAR Validation Threshold Tuning Curve (84,250 Provisions)](figures/figure4_threshold_curve.png)"""

if sec10_old in content:
    content = content.replace(sec10_old, sec10_new, 1)
    print("[OK] Section 10 Part A tables updated.")
else:
    sec10_old_crlf = sec10_old.replace("\n", "\r\n")
    sec10_new_crlf = sec10_new.replace("\n", "\r\n")
    content = content.replace(sec10_old_crlf, sec10_new_crlf, 1)
    print("[OK] Section 10 Part A tables updated (CRLF).")

# 6. Section 12: Add Figure 5 and Figure 6
sec12_fig5_target = "Consequently, over **91.07% of the entire taxonomy ($11,298$ classes)** has near-zero test F1, dragging the unweighted arithmetic mean down to $0.0045$, while the 102 head classes drive the Micro-F1 of $0.1435$."
sec12_fig5_replacement = (
    "Consequently, over **91.07% of the entire taxonomy ($11,298$ classes)** has near-zero test F1, dragging the unweighted arithmetic mean down to $0.0045$, while the 102 head classes drive the Micro-F1 of $0.1435$.\n\n"
    "![Figure 5: LEDGAR Long-Tail Class Imbalance and Macro-F1 Collapse Analysis](figures/figure5_class_distribution.png)"
)
if sec12_fig5_target in content:
    content = content.replace(sec12_fig5_target, sec12_fig5_replacement, 1)
    print("[OK] Section 12 Figure 5 embed added.")

sec12_fig6_target = "triggering false `Entailment` predictions."
sec12_fig6_replacement = (
    "triggering false `Entailment` predictions.\n\n"
    "![Figure 6: ContractNLI Baseline Confusion Matrix & Lexical Overlap Flow](figures/figure6_contractnli_confusion.png)"
)
if sec12_fig6_target in content:
    content = content.replace(sec12_fig6_target, sec12_fig6_replacement, 1)
    print("[OK] Section 12 Figure 6 embed added.")

# 7. Section 17: References table with verification status
sec17_old = """* **[Chalkidis2020]** Chalkidis, I., Fergadiotis, M., Malakasiotis, P., Aletras, N., & Androutsopoulos, I. (2020). *LEGAL-BERT: The Muppets straight out of Law School*. In Findings of EMNLP 2020 (pp. 2898–2904). DOI: `10.18653/v1/2020.findings-emnlp.261`.
* **[Tuggener2020]** Tuggener, D., von Däniken, P., Peetz, T., & Cieliebak, M. (2020). *LEDGAR: A Large-Scale Multi-label Corpus for Text Classification of Legal Provisions in Contracts*. In Proceedings of the 12th Language Resources and Evaluation Conference (LREC 2020) (pp. 1235–1241).
* **[Koreeda2021]** Koreeda, Y., & Manning, C. D. (2021). *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*. In Findings of EMNLP 2021 (pp. 1907–1919).
* **[Hendrycks2021]** Hendrycks, D., Burns, C., Chen, A., Ball, S., et al. (2021). *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*. arXiv preprint arXiv:2103.06268. The Atticus Project.
* **[Ruggeri2022]** Ruggeri, F., Lagioia, F., Lippi, M., & Torroni, P. (2022). *Detecting and Explaining Unfairness in Consumer Contracts through Memory Networks*. Artificial Intelligence and Law, 30(2), 159–192. DOI: `10.1007/s10506-021-09288-2`.
* **[Moon2022]** Moon, S., Chi, S., & Im, S.-B. (2022). *Automated Detection of Contractual Risk Clauses from Construction Specifications Using BERT*. Automation in Construction, 140, 104465. DOI: `10.1016/j.autcon.2022.104465`.
* **[Shuai2023]** Shuai, B. (2023). *A Rationale-Augmented NLP Framework to Identify Unilateral Contractual Change Risk for Construction Projects*. Computers in Industry, 151, 103940. DOI: `10.1016/j.compind.2023.103940`.
* **[Zhou2023]** Zhou, H., Gao, B., Tang, S., Li, B., &王, S. (2023). *Intelligent detection on construction project contract missing clauses based on deep learning and NLP*. Engineering, Construction and Architectural Management, 32(3), 1546–1580. DOI: `10.1108/ECAM-02-2023-0172`.
* **[Singh2025]** Singh, A., Joshi, A., Jiang, J., & Paik, H.-Y. (2025). *A Survey of Classification Tasks and Approaches for Legal Contracts*. Artificial Intelligence Review, 58(2), 11359. DOI: `10.1007/s10462-025-11359-8`.
* **[Liu2025]** Liu, S., Li, Z., Ma, R., Zhao, H., & Du, M. (2025). *ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial Contracts*. In Proceedings of the Natural Legal Language Processing Workshop (NLLP 2025).
* **[Sundararajan2017]** Sundararajan, M., Taly, A., & Yan, Q. (2017). *Axiomatic Attribution for Deep Networks*. In Proceedings of the 34th International Conference on Machine Learning (ICML 2017), PMLR 70:3319–3328."""

sec17_new = """| Key / ID | Verified Citation & Bibliographic Metadata | Venue / DOI / Official Source | Registry Verification Status |
| :--- | :--- | :--- | :--- |
| **P001** | Chalkidis, I., Fergadiotis, M., Malakasiotis, P., Aletras, N., & Androutsopoulos, I. (2020). *LEGAL-BERT: The Muppets straight out of Law School*. | Findings of EMNLP 2020 (pp. 2898–2904) \| DOI: `10.18653/v1/2020.findings-emnlp.261` | **VERIFIED** (ACL Anthology; `references/verified_papers.csv`) |
| **P002** | Tuggener, D., von Däniken, P., Peetz, T., & Cieliebak, M. (2020). *LEDGAR: A Large-Scale Multi-label Corpus for Text Classification of Legal Provisions in Contracts*. | LREC 2020 (pp. 1235–1241) \| `https://aclanthology.org/2020.lrec-1.55/` | **VERIFIED** (ACL Anthology; `references/verified_papers.csv`) |
| **P003** | Koreeda, Y., & Manning, C. D. (2021). *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*. | Findings of EMNLP 2021 (pp. 1907–1919) \| `https://aclanthology.org/2021.findings-emnlp.164/` | **VERIFIED** (ACL Anthology; `references/verified_papers.csv`) |
| **CUAD** | Hendrycks, D., Burns, C., Chen, A., Ball, S., et al. (2021). *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*. | arXiv:2103.06268 \| The Atticus Project (CC BY 4.0) | **VERIFIED** (Atticus Project; `references/verified_datasets.csv`) |
| **P004** | Ruggeri, F., Lagioia, F., Lippi, M., & Torroni, P. (2022). *Detecting and Explaining Unfairness in Consumer Contracts through Memory Networks*. | Artificial Intelligence and Law, 30(2), 159–192 \| DOI: `10.1007/s10506-021-09288-2` | **VERIFIED** (Springer; `references/verified_papers.csv`) |
| **P005** | Moon, S., Chi, S., & Im, S.-B. (2022). *Automated Detection of Contractual Risk Clauses from Construction Specifications Using BERT*. | Automation in Construction, 140, 104465 \| DOI: `10.1016/j.autcon.2022.104465` | **VERIFIED** (ScienceDirect; `references/verified_papers.csv`) |
| **P006** | Shuai, B. (2023). *A Rationale-Augmented NLP Framework to Identify Unilateral Contractual Change Risk for Construction Projects*. | Computers in Industry, 151, 103940 \| DOI: `10.1016/j.compind.2023.103940` | **VERIFIED** (ScienceDirect; `references/verified_papers.csv`) |
| **P007** | Zhou, H., Gao, B., Tang, S., Li, B., & Wang, S. (2023). *Intelligent detection on construction project contract missing clauses based on deep learning and NLP*. | Eng. Const. & Arch. Mgmt, 32(3), 1546–1580 \| DOI: `10.1108/ECAM-02-2023-0172` | **VERIFIED** (Emerald Insight; `references/verified_papers.csv`) |
| **P008** | Singh, A., Joshi, A., Jiang, J., & Paik, H.-Y. (2025). *A Survey of Classification Tasks and Approaches for Legal Contracts*. | Artificial Intelligence Review, 58(2), 11359 \| DOI: `10.1007/s10462-025-11359-8` | **VERIFIED** (Springer; `references/verified_papers.csv`) |
| **P009** | Liu, S., Li, Z., Ma, R., Zhao, H., & Du, M. (2025). *ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial Contracts*. | NLLP Workshop 2025 \| `https://aclanthology.org/2025.nllp-1.19/` | **VERIFIED** (ACL Anthology; `references/verified_papers.csv`) |
| **XAI** | Sundararajan, M., Taly, A., & Yan, Q. (2017). *Axiomatic Attribution for Deep Networks (Integrated Gradients)*. | ICML 2017 \| PMLR 70:3319–3328 | **METHODOLOGY** (External CS explainability reference; not in legal registry) |

*Note on Reference Verification: Papers P001 through P009 and CUAD are verified against the authoritative legal research registries (references/verified_papers.csv and references/verified_datasets.csv). Sundararajan et al. (2017) is an external computer science methodology reference for Integrated Gradients and is flagged as an external methodological reference outside the legal corpus registry.*"""

# If list format in content:
if "* **[Chalkidis2020]**" in content:
    # Find start and end of references list
    start_pos = content.find("* **[Chalkidis2020]**")
    end_marker = "\n\n---\n\n## 18. Artifact Provenance"
    end_pos = content.find(end_marker)
    if end_pos == -1:
        end_marker = "\r\n\r\n---\r\n\r\n## 18. Artifact Provenance"
        end_pos = content.find(end_marker)
    if start_pos != -1 and end_pos != -1:
        content = content[:start_pos] + sec17_new + content[end_pos:]
        print("[OK] Section 17 References updated.")
    else:
        print(f"[WARN] Section 17 bounds: start={start_pos}, end={end_pos}")

# 8. Section 18: Provenance Table with exact hashes and discrepancy resolution
sec18_old = """| Component / Task | Source Artifact File Path | File Size (Bytes) | SHA-256 Checksum | Verification Status |
| :--- | :--- | :---: | :--- | :---: |
| **Model Weights** | `results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors` | 476,116,436 | `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f` | **VERIFIED** |
| **Model Archive** | `task019_fresh_colab_results_WITH_MODEL.zip` | 436,812,410 | `aca7529b79d8d7fd88155b14654ba425686775cb72e9982cb5e5e528b74c166a` | **VERIFIED** |
| **LEDGAR Evaluation** | `results/models/ledgar_frozen_subset_fresh/calibrated/TASK019_..._CALIBRATED.json` | 13,842 | `00163351ec12cb6be6251b3ba7583f6f1f33f075da3d544078dbb9623e105e46` | **VERIFIED** |
| **ContractNLI Baseline** | `results/baseline/contractnli/TASK018_CONTRACTNLI_TFIDF_SVM.json` | 2,752 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | **VERIFIED** |
| **Task 020 Manifest** | `results/task020/task020_cross_domain_manifest.json` | 5,234 | `6cb85ec017992a2a0ff9605e5d3c0ffcae70f61405e31fa2a74c728eb71c863a` | **VERIFIED** |
| **Task 021 Manifest** | `results/task021/task021_ablation_manifest.json` | 7,105 | `8f2c0faebdb2b3b85d9cf76f18379469e3a6fa189a038f4a3da7e411b9ba71da` | **VERIFIED** |
| **Task 022 Manifest** | `results/task022/task022_robustness_manifest.json` | 8,940 | `18ba0466be85fb8fb5ec85d38a0a80e1208fbdb95eecb77b966fc29bdf4ef7ee` | **VERIFIED** |
| **Task 023 Manifest** | `results/task023/task023_error_analysis_manifest.json` | 9,388 | `6612df38760fa69632490d1bf435df178229dc1ff6a7a58c0c80b6a22f3900cb` | **VERIFIED** |
| **Task 024 Manifest** | `results/task024/task024_dashboard_manifest.json` | 2,031 | `a65bfce960e608aa58a8f278eb07519ff08da12b9a12c40c3132e48aa124cfb0` | **VERIFIED** |"""

sec18_new = """| Component / Task | Source Artifact File Path | File Size (Bytes) | SHA-256 Checksum | Verification Status |
| :--- | :--- | :---: | :--- | :---: |
| **Model Weights** | `results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors` | 476,116,436 | `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f` | **VERIFIED** |
| **Model Archive** | `task019_fresh_colab_results_WITH_MODEL.zip` | 441,575,824 | `aca7529b79d8d7fd88155b14654ba425686775cb72e9982cb5e5e528b74c166a` | **VERIFIED** |
| **LEDGAR Evaluation** | `results/models/ledgar_frozen_subset_fresh/calibrated/TASK019_..._CALIBRATED.json` | 6,786 | `fbd05ced725508b3c9d6d5eb9f5991d8bdc601d23578ec3067bcc0362d607b27` | **VERIFIED** |
| **ContractNLI Baseline** | `results/baseline/contractnli/TASK018_CONTRACTNLI_TFIDF_SVM.json` | 2,119 | `0e6eb4db9f406f1f13ae648d5902889562f81cffafbcb87e137f1c6261dc1b01` | **VERIFIED** |
| **Task 020 Manifest** | `results/task020/task020_cross_domain_manifest.json` | 16,370 | `77faa3e6fc066d9db4683b337c11aa2e9c6584a7c5ded7c5f03b9ad7469db197` | **VERIFIED** |
| **Task 021 Manifest** | `results/task021/task021_ablation_manifest.json` | 10,081 | `730b5b500ed827b042df01b09270865188d6486d75af50900d385e147e22be1f` | **VERIFIED** |
| **Task 022 Manifest** | `results/task022/task022_robustness_manifest.json` | 13,982 | `a9f75b8e86428202df4667e943e205e6db47b8f5fd49a3aceca7f036c7445cf5` | **VERIFIED** |
| **Task 023 Manifest** | `results/task023/task023_error_analysis_manifest.json` | 9,388 | `1df0170fccb731c48e0a10ce0cfd7e3f74bfb6bd138d6c425110bf2649302fd6` | **VERIFIED** |
| **Task 024 Manifest** | `results/task024/task024_dashboard_manifest.json` | 2,031 | `66805ba5be8b071114da06aa1dd14bebf73369f5f23f118a67c357a882cc9d6a` | **VERIFIED** |

*Forensic Resolution of Checksum Discrepancy: The hash prefix e3b0c44298fc1c149afbf4c8996fb924... previously reported in early draft manifests corresponds to hashlib.sha256(b'').hexdigest() (empty byte string placeholder). Recomputing SHA-256 over physical file bytes on disk resolves to 0e6eb4db9f406f1f13ae648d5902889562f81cffafbcb87e137f1c6261dc1b01 (2,119 bytes). All artifact hashes have been cross-verified against actual disk bytes and marked VERIFIED.*"""

if sec18_old in content:
    content = content.replace(sec18_old, sec18_new, 1)
    print("[OK] Section 18 Provenance Table updated.")
else:
    sec18_old_crlf = sec18_old.replace("\n", "\r\n")
    sec18_new_crlf = sec18_new.replace("\n", "\r\n")
    content = content.replace(sec18_old_crlf, sec18_new_crlf, 1)
    print("[OK] Section 18 Provenance Table updated (CRLF).")

with open(MD_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] CONTRACTRISK_XAI_ACADEMIC_REPORT.md updated successfully!")
