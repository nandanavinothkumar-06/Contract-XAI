# TASK 021 — Ablation Studies: Empirical Evaluation Report

**Project**: ContractRisk-XAI  
**Task ID**: 021  
**Task Name**: Run ablation  
**Execution Timestamp**: 2026-10-13T23:55:00+05:30  
**Status**: ✅ COMPLETED  
**Manifest Path**: [`results/task021/task021_ablation_manifest.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/task021/task021_ablation_manifest.json)  
**Test Suite**: [`tests/test_ablation.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_ablation.py) (10/10 tests passed)  

---

## 1. Executive Summary & Objective

The objective of **Task 021** is to empirically measure the isolated contribution, necessity, and failure modes of the four core architectural components of the ContractRisk-XAI system:
1. **Decision Threshold Calibration**: Impact of probability thresholding on extreme multi-label classification.
2. **Cross-Clause Context Strategies**: Trade-offs between isolated provisions and sequential/hierarchical context.
3. **Relationship Graph Topology**: Contribution of structural hierarchy, sequential flow, and cross-references.
4. **Evidence Attribution & Span Aggregation**: Utility of contiguous span aggregation versus raw token saliency.

In accordance with strict research integrity constraints:
- **Zero Retraining**: All ablations used existing frozen weights and deterministic feature pipelines.
- **Zero Test Recalibration**: The calibrated threshold $\tau^* = 0.04$ was fixed from validation data; test set sweeps were executed strictly for sensitivity analysis.
- **Strict Boundary Invariance**: Zero cross-document or cross-partition leakage was permitted in context or graph structures.
- **Disjoint Category Isolation**: No synthetic label projections or artificial task alignments were introduced.

---

## 2. Model & Environmental Provenance

- **Physical Model Weights**: [`results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors)
- **Model Weights SHA-256**: `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f`
- **Output Dimension**: 12,407 classes
- **Base Encoder**: `nlpaueb/legal-bert-base-uncased` (frozen, 109.5M params)
- **Classification Head**: Trainable linear layer ($768 \rightarrow 12,407$, 9.5M params)
- **Evaluation Runner**: [`src/evaluation/run_task021_ablation.py`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/evaluation/run_task021_ablation.py)

---

## 3. Experiment A — Decision Threshold Calibration Ablation

### Background & Failure Mode
In extreme multi-label text classification (12,407 classes), standard uncalibrated models employ a fixed sigmoid threshold $\tau = 0.50$. Because the linear classification head is trained over a frozen encoder on an imbalanced 10% contract subset, the uncalibrated model outputs low raw probabilities across sparse tail classes.

### Empirical Sweep Across Operating Thresholds ($\tau$)

#### Full Corpus Test Split (87,956 provisions, 105,283 positive labels):
| Threshold ($\tau$) | Status / Role | Micro-Precision | Micro-Recall | Micro-F1 | Macro-F1 | Weighted-F1 | True Positives | False Positives | False Negatives |
|---|---|---|---|---|---|---|---|---|---|
| **$\tau = 0.02$** | High Recall Variant | 0.0982 | 0.1685 | 0.1241 | 0.0044 | 0.0812 | 17,740 | 162,880 | 87,543 |
| **$\tau^* = 0.04$** | **Calibrated Optimum** | **0.1772** | **0.1206** | **0.1435** | **0.0045** | **0.0937** | **12,699** | **58,947** | **92,584** |
| **$\tau = 0.10$** | Moderate Precision | 0.2315 | 0.0682 | 0.1054 | 0.0035 | 0.0689 | 7,180 | 23,830 | 98,103 |
| **$\tau = 0.20$** | High Precision Variant | 0.2351 | 0.0389 | 0.0667 | 0.0025 | 0.0452 | 4,095 | 13,322 | 101,188 |
| **$\tau = 0.50$** | **Uncalibrated Baseline** | **0.6931** | **0.0094** | **0.0185** | **0.0009** | **0.0141** | **989** | **438** | **104,294** |

#### Empirical Test Sample Sweep ($N = 200$ test provisions):
- $\tau = 0.02$: Micro-P: 0.1014 | Micro-R: 0.3013 | Micro-F1: 0.1509 | TP: 94 | FP: 833 | FN: 218
- $\tau^* = 0.04$: Micro-P: 0.1642 | Micro-R: 0.1827 | **Micro-F1: 0.1728** | TP: 57 | FP: 290 | FN: 255
- $\tau = 0.10$: Micro-P: 0.2115 | Micro-R: 0.0609 | Micro-F1: 0.0927 | TP: 19 | FP: 71 | FN: 293
- $\tau = 0.20$: Micro-P: 0.2500 | Micro-R: 0.0321 | Micro-F1: 0.0562 | TP: 10 | FP: 30 | FN: 302
- $\tau = 0.50$: Micro-P: 0.6000 | Micro-R: 0.0096 | Micro-F1: 0.0165 | TP: 3 | FP: 2 | FN: 309

### Findings
1. **Severe Suppression at Baseline**: At $\tau = 0.50$, the model misses **99.06%** of true positives ($104,294$ false negatives).
2. **Optimal Trade-off**: Validation calibration to $\tau^* = 0.04$ boosts true positive yield by **12.83$\times$** ($12,699$ vs $989$), increasing Micro-F1 from **0.0185** to **0.1435** (**+675.7% relative gain**).
3. **Diminishing Returns Below 0.04**: Dropping threshold to $\tau = 0.02$ causes false positives to explode ($162,880$ FP), reducing precision from $17.72\%$ to $9.82\%$ and Micro-F1 to $0.1241$.

---

## 4. Experiment B — Cross-Clause Context Strategy Ablation

### Objective
Isolate the representation impact and budget behavior when augmenting target contract clauses with neighboring or hierarchical clauses using [`ContextBuilder`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/context/builder.py).

### Quantitative Results on Multi-Clause Commercial Agreement
| Strategy | Description | Components | Text Length | Cosine Sim to Isolated | Representation Drift | Latency (ms) | Target Truncated? | Budget Compliant? |
|---|---|---|---|---|---|---|---|---|
| `NONE` | Target clause only (Ablated) | 1 | 148 chars | **1.0000** | 0.0000 | 1.71 ms | ❌ No (Preserved) | ✅ Yes |
| `PREVIOUS_NEXT` | Preceding + Target + Next | 3 | 430 chars | **0.8270** | 0.1730 | 0.80 ms | ❌ No (Preserved) | ✅ Yes |
| `WINDOW` | Sliding window ($k=2$) | 5 | 732 chars | **0.8438** | 0.1562 | 0.83 ms | ❌ No (Preserved) | ✅ Yes |
| `PARENT_CHILD` | Heading + Target clause | 2 | 183 chars | **0.8720** | 0.1280 | 0.45 ms | ❌ No (Preserved) | ✅ Yes |

### Invariant & Safety Verifications
- **Target Preservation Invariant**: `target_truncated == False` verified across 100% of evaluations.
- **Context Budget**: All 4 strategies remained strictly within the 512-token limit.
- **Cross-Document Leakage**: Injecting multi-document segments triggered immediate `ValueError("Cross-document context leakage detected.")` as required.

### Findings
1. `PARENT_CHILD` achieves the most conservative representation shift ($\text{Sim} = 0.8720$, drift $0.1280$) while providing essential structural context (article/section headers).
2. Sequential strategies (`PREVIOUS_NEXT` and `WINDOW`) induce higher contextual modulation ($\text{Sim} \approx 0.82 - 0.84$) by introducing neighboring clause semantics into the [CLS] representation.

---

## 5. Experiment C — Relationship Graph Topology Ablation

### Objective
Measure structural connectivity, reachability, and cross-reference resolution when graph edge types are systematically removed using [`GraphBuilder`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/graph/builder.py).

### Topological Comparison
| Topology Variant | Edges Retained | Node Count | Edge Count | Edge Density | Reachability (%) | Resolved Cross-Refs | Resolution Rate | Boundary Violations |
|---|---|---|---|---|---|---|---|---|
| `FULL_GRAPH` | Hierarchy + Sequence + Citations | 7 | 24 | **0.5714** | **100.0%** | **3 / 3** | **100.0%** | **0** |
| `HIERARCHICAL_ONLY` | `CONTAINS`, `PARENT_OF` | 7 | 8 | **0.1905** | **9.52%** | 0 / 3 | 0.0% | **0** |
| `SEQUENTIAL_ONLY` | `PRECEDES`, `FOLLOWS` | 7 | 12 | **0.2857** | **100.0%** | 0 / 3 | 0.0% | **0** |
| `DISJOINT_NODES` | None (Isolated clauses) | 7 | 0 | **0.0000** | **0.00%** | 0 / 3 | 0.0% | **0** |

### Findings
1. **Critical Role of Cross-References**: In legal contracts where risk definitions span multiple sections (e.g., *"pursuant to Section 4.1"*), `FULL_GRAPH` connects disjoint sections, achieving 100% cross-reference resolution.
2. **Hierarchy Alone is Insufficient**: Ablating sequential and cross-reference edges (`HIERARCHICAL_ONLY`) collapses reachability to **9.52%**, restricting visibility solely to immediate parent-child pairs.
3. **Zero Boundary Violations**: In all variants, cross-document edge leakage was strictly prevented (0 cross-document edges).

---

## 6. Experiment D — Evidence Attribution & Span Aggregation Ablation

### Objective
Compare contiguous span aggregation against raw token saliency and signed attributions using [`EvidenceExtractor`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/evidence/extractor.py).

### Method Comparison
| Attribution Variant | Mechanism | Offset Invariant Verified? | Average Gini Sparsity | Average Latency / Clause | Qualitative Human Utility |
|---|---|---|---|---|---|
| `SPAN_AGGREGATED` | Gradient $\times$ Input + Contiguous Span Merging | ✅ **100% Exact Match** | **0.1041** | 216.65 ms | **High**: Emits coherent legal phrases (*"Delaware"*, *"terminate this"*, *"indemnify and hold harmless"*). |
| `RAW_TOKENS` | Unmerged individual subwords | ✅ **100% Exact Match** | **0.1041** | 169.56 ms | **Moderate**: Produces fragmented subword tokens (*"Dela"*, *"##ware"*, *"term"*, *"##inate"*). |
| `SIGNED_GRADIENT` | Directional signed gradient weights | ✅ **100% Exact Match** | **0.1041** | 166.72 ms | **Moderate**: Distinguishes inhibitory versus excitatory tokens. |
| `UNWEIGHTED_SPAN` | Equal-weight baseline spans | ✅ **100% Exact Match** | **0.0000** | 162.57 ms | **Poor**: Loses token saliency concentration entirely. |

### Findings
1. **Phrase Coherence**: Contiguous span aggregation converts subword gradient spikes into readable legal rationales without sacrificing token-level character offset guarantees.
2. **Strict Invariant Guarantee**: `clause[source_start:source_end] == span.text` held across 100% of tested clauses and methods.

---

## 7. Architectural Comparison: Baselines vs. Full Model vs. Ablations

| Model / Architecture | Task / Corpus | Primary Evaluation Metric | Result | Role / Finding |
|---|---|---|---|---|
| **TF-IDF + Linear SVC** | ContractNLI (3-class NLI) | Test Accuracy / Macro-F1 | 65.57% / 0.5844 | Task 018 Baseline: Effective on document-level classification with few classes. |
| **TF-IDF + One-vs-Rest** | LEDGAR (12,608 classes) | Resource Feasibility | `RESOURCE_LIMITATION` | Task 018 Baseline: Infeasible on CPU due to 12,608 independent estimators. |
| **LEGAL-BERT (Uncalibrated $\tau = 0.50$)** | LEDGAR (12,407 classes) | Test Micro-F1 | **0.0185** | Ablated Baseline: Extreme true positive suppression ($989$ TP). |
| **LEGAL-BERT (Calibrated $\tau^* = 0.04$)** | LEDGAR (12,407 classes) | Test Micro-F1 | **0.1435** | **Full Proposed System**: +675.7% gain over uncalibrated baseline ($12,699$ TP). |
| **LEGAL-BERT + `NONE` Context** | Multi-Clause Segmentation | Target Representation Drift | 0.0000 (Purity) | Ablated Context: Pure isolated clause, zero surrounding grounding. |
| **LEGAL-BERT + `PARENT_CHILD`** | Multi-Clause Segmentation | Target Representation Drift | 0.1280 (Controlled) | **Proposed Context**: Retains structural heading with 100% budget compliance. |
| **Relationship Graph (`DISJOINT`)** | Multi-Clause AST | Reachability / Ref Resolution | 0.0% / 0.0% | Ablated Graph: Disjoint clauses cannot resolve cross-references. |
| **Relationship Graph (`FULL_GRAPH`)** | Multi-Clause AST | Reachability / Ref Resolution | **100.0% / 100.0%** | **Proposed Graph**: Resolves cross-clause citations across articles. |

---

## 8. Acceptance Criteria Checklist (10/10 Verified)

| # | Acceptance Criterion | Verification Method | Status |
|---|---|---|---|
| 1 | Threshold ablation evaluated across $\{0.02, 0.04, 0.10, 0.20, 0.50\}$ | `test_1_threshold_ablation_sweep` | ✅ PASSED |
| 2 | Calibrated threshold $\tau^* = 0.04$ preserved from validation split | `test_2_calibrated_threshold_preservation` | ✅ PASSED |
| 3 | Context strategies (`NONE`, `PREVIOUS_NEXT`, `WINDOW`, `PARENT_CHILD`) evaluated | `test_3_context_ablation_strategies` | ✅ PASSED |
| 4 | Context target preservation invariant (`target_truncated == False`) verified | `test_4_context_target_preservation_invariant` | ✅ PASSED |
| 5 | Context representation drift measured and bounded | `test_5_context_representation_drift` | ✅ PASSED |
| 6 | Graph topologies (`FULL`, `HIERARCHICAL`, `SEQUENTIAL`, `DISJOINT`) evaluated | `test_6_graph_topology_ablation_variants` | ✅ PASSED |
| 7 | Zero cross-document graph edge leakage enforced | `test_7_graph_zero_cross_document_leakage` | ✅ PASSED |
| 8 | Evidence attribution variants evaluated with Gini sparsity | `test_8_evidence_attribution_ablation` | ✅ PASSED |
| 9 | Character offset invariants verified with 100% precision | `test_9_evidence_character_offset_invariants` | ✅ PASSED |
| 10 | Deterministic manifest generated and validated against model weights | `test_10_ablation_manifest_integrity` | ✅ PASSED |

---

## 9. Limitations & Boundary Conditions

1. **Threshold Specificity**: $\tau^* = 0.04$ was calibrated specifically for the 10% subset frozen-encoder architecture on LEDGAR; it should not be assumed optimal for fully fine-tuned models or different label spaces.
2. **Context Window Limits**: `WINDOW` and `PREVIOUS_NEXT` strategies risk displacing structural headings when contract provisions are unusually long (>250 tokens), whereas `PARENT_CHILD` prioritizes structural anchors.
3. **Graph Dependency on Regex Heuristics**: Cross-reference resolution relies on formal citation numbering (e.g., *"Section 4.1"*); informal references (e.g., *"as described above"*) require semantic coreference resolution.
4. **Attribution Non-Equivalence**: High gradient attribution scores indicate token sensitivity in the neural network; they do not establish causal legal necessity or judicial validity.
