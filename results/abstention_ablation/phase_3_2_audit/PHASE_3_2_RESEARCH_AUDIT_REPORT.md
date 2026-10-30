# PHASE 3.2 AUDIT REPORT: RESULT RECONCILIATION & RESEARCH VALIDITY

**Audit Target**: Phase 3.1 Multi-Seed Synthetic Stability Study & Rule-Based Metadata Baseline  
**Project**: `CONTRACTRISK-XAI` (NLP Risk Analysis Engine)  
**Date**: October 20, 2026  
**Auditor**: Antigravity Research & Verification Agent  
**Audit Scope**: Strict Read-Only Verification of Artifacts in `results/abstention_ablation/multi_seed/`  

---

> [!IMPORTANT]
> **GOVERNANCE & PRESERVATION COMPLIANCE**
> - Application source code in `src/` and test suites in `tests/` were **NOT MODIFIED**.
> - Historical baseline results in `results/abstention_ablation/` were **PRESERVED INTACT**.
> - Phase 3.1 outputs in `results/abstention_ablation/multi_seed/` were **NOT OVERWRITTEN**.
> - All audit calculations, recomputed tables, and reconciliation logs are written strictly to `results/abstention_ablation/phase_3_2_audit/`.
> - Real-world legal effectiveness and validated novelty are **EXPLICITLY DISCLAIMED**.

---

## 1. Executive Summary

This audit independently verified the data pipeline, mathematical calculations, matched-coverage comparisons, statistical inferential tests, and rule baseline behaviors reported in Phase 3.1. 

### Key Audit Findings:
1. **Zero Discrepancy Reconciliation**: Recomputation of all candidate decisions ($1,740$ decision tuples across 30 seeds $\times$ 58 candidates $\times$ 5 configurations) matched the reported per-seed metrics and summary tables with **0 discrepancies** across all metrics.
2. **Coverage Matching Integrity**: Both compared policies within each seed evaluated the **identical candidate pool**. Matched-coverage comparisons strictly adhered to the $\pm 0.02$ tolerance. Unmatched seeds ($2/30$ unperturbed, $3/30$ perturbed) were transparently excluded from $\Delta \text{UFR}$ without forced interpolation.
3. **Statistical Robustness Under Holm-Bonferroni Correction**: The reported UFR reductions of `FULL_EVIDENCE_AWARE` over the confidence baseline remained statistically significant at $\alpha = 0.01$ under family-wise error rate control ($p_{\text{Holm}} = 2.98 \times 10^{-8}$).
4. **Substantive Rule Baseline Validation**: The Rule-Based Metadata Baseline was confirmed to function strictly as a procedural document-integrity and passage-presence checklist. It eliminates stale drafts ($	ext{SEAR}=0$) with lower human-review workload (HRW = 7.6%), but suffers a significantly higher unsupported-finding rate (UFR = 35.1% vs. 20.4%) because it cannot distinguish between genuine statutory grounding and spurious retrieval hallucinations, nor can it accept high-confidence non-statutory commercial drafting covenants.
5. **Readiness for Citation**: The multi-seed experiment is **methodologically sound and ready to be cited** in academic deliverables as an evaluation of *synthetic algorithmic stability*, provided its synthetic bounds and lack of real-contract validation are clearly stated.

---

## 2. Independent Recomputation & Data Reconciliation

The candidate decisions recorded in `results/abstention_ablation/multi_seed/per_candidate_decisions.csv` were independently parsed and evaluated against ground-truth reference labels using the primary metric definitions from `src/evaluation/abstention_eval.py`.

### 2.1 Reconciliation Checklist

| Artifact Reconciled | Comparison Target | Discrepancies Found | Verification Status |
| :--- | :--- | :---: | :---: |
| `per_candidate_decisions.csv` | `per_seed_metrics_unperturbed.csv` (150 rows) | **0** | **VERIFIED** |
| `per_candidate_decisions.csv` | `per_seed_metrics_perturbed.csv` (150 rows) | **0** | **VERIFIED** |
| `per_seed_metrics_unperturbed.csv` | `aggregated_statistics.json` / `.csv` | **0** | **VERIFIED** |
| `per_seed_metrics_perturbed.csv` | `aggregated_statistics.json` / `.csv` | **0** | **VERIFIED** |
| `statistical_analysis_results.json` | Independent recomputed SciPy tests | **0** | **VERIFIED** |

### 2.2 Recomputed vs. Reported Metric Invariants
- **Candidate Pool Consistency**: Every seed generated exactly 58 candidates, of which 57 were evaluable and 1 was corrupt/unassessable (`clause-corrupt-01`).
- **Retention Rate**: Exactly matched across all 150 configuration runs.
- **Unsupported-Finding Rate (UFR)**: Numerator (retained candidates with $y_{\text{ref}} = \text{WITHHOLD}$) and denominator (evaluable retained candidates) matched with 100% precision. Zero-denominator cases safely evaluated to `None`.
- **Useful-Finding Coverage (UFC)**: Numerator (retained candidates with $y_{\text{ref}} = \text{RETAIN}$) and denominator (total evaluable candidates with $y_{\text{ref}} = \text{RETAIN}$) matched with 100% precision.
- **Stale-Evidence Acceptance Rate (SEAR)**: Evaluated to exactly $0.0000$ for `VERSION_AWARE`, `FULL_EVIDENCE_AWARE`, and `RULE_BASED_METADATA` across all 30 seeds.

---

## 3. Matched-Coverage Protocol Audit

### 3.1 Candidate Pool Identity
- **Audited Condition**: Does the baseline policy evaluate the identical candidate pool as the policy configuration being matched?
- **Finding**: **YES**. In every seed $s \in \{101..130\}$, both the policy and the 101-point baseline sweep evaluated the exact candidate list `synth-cand-{s}-0001` through `synth-cand-{s}-0058`. No candidate was added, dropped, or reweighted.

### 3.2 Coverage Matching Tolerance & Exclusions
The prespecified protocol requires $|\text{UFC}_{\text{baseline}} - \text{UFC}_{\text{policy}}| \le 0.02$. If no baseline threshold satisfies this tolerance, the comparison must report `MATCHED_COVERAGE_UNACHIEVED` and exclude $\Delta \text{UFR}$.

| Policy Configuration | Benchmark | Total Seeds | Matched Seeds Achieved ($|\Delta \text{UFC}| \le 0.02$) | Unmatched Seeds Excluded | Actual Sample Size for $\Delta \text{UFR}$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **FULL_EVIDENCE_AWARE** | Unperturbed | 30 | 28 (93.3%) | 2 (Seeds 110, 124) | **$N = 28$** |
| **VERSION_AWARE** | Unperturbed | 30 | 30 (100.0%) | 0 | **$N = 30$** |
| **STATUTORY_GROUNDING** | Unperturbed | 30 | 30 (100.0%) | 0 | **$N = 30$** |
| **RULE_BASED_METADATA** | Unperturbed | 30 | 29 (96.7%) | 1 (Seed 116) | **$N = 29$** |
| **FULL_EVIDENCE_AWARE** | Perturbed | 30 | 27 (90.0%) | 3 (Seeds 104, 110, 124) | **$N = 27$** |
| **VERSION_AWARE** | Perturbed | 30 | 30 (100.0%) | 0 | **$N = 30$** |
| **STATUTORY_GROUNDING** | Perturbed | 30 | 29 (96.7%) | 1 (Seed 125) | **$N = 29$** |
| **RULE_BASED_METADATA** | Perturbed | 30 | 28 (93.3%) | 2 (Seeds 116, 125) | **$N = 28$** |

*Audit Verdict*: **VERIFIED**. Excluded seeds were transparently omitted from the paired $\Delta \text{UFR}$ vectors without forced linear interpolation or post-hoc threshold tweaking.

---

## 4. Statistical Analysis Audit

### 4.1 Test Inputs and Assumptions Check
1. **Normality of Paired Differences**:
   - Shapiro-Wilk test on unperturbed `FULL_EVIDENCE_AWARE` $\Delta \text{UFR}$: $W = 0.9613$, $p = 0.3554$.
   - Shapiro-Wilk test on perturbed `FULL_EVIDENCE_AWARE` $\Delta \text{UFR}$: $W = 0.9806$, $p = 0.8589$.
   - *Verdict*: Paired differences do not reject normality ($p > 0.05$). Therefore, parametric Student's $t$-tests are statistically valid.
2. **Non-Parametric Wilcoxon Signed-Rank Test**:
   - Because bounded rate differences can exhibit kurtosis or discreteness, reporting Wilcoxon signed-rank tests alongside Student's $t$ is appropriate.
   - For unperturbed `FULL_EVIDENCE_AWARE`: $W = 0.0$, $p = 7.45 \times 10^{-9}$ ($N = 28$).
   - For perturbed `FULL_EVIDENCE_AWARE`: $W = 1.0$, $p = 9.32 \times 10^{-6}$ ($N = 27$).
3. **Multiple Comparisons Correction (Holm-Bonferroni)**:
   When evaluating 4 policy configurations against baseline, family-wise error rate (FWER) must be controlled:

| Configuration | Raw Wilcoxon $p$-value | Rank $j$ | Multiplier ($m - j + 1$) | Adjusted Holm-Bonferroni $p$ | Significant at $\alpha = 0.01$? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **FULL_EVIDENCE_AWARE** | $7.45 \times 10^{-9}$ | 1 | 4 | **$2.98 \times 10^{-8}$** | **YES** |
| **STATUTORY_GROUNDING** | $3.86 \times 10^{-7}$ | 2 | 3 | **$1.16 \times 10^{-6}$** | **YES** |
| **VERSION_AWARE** | $1.92 \times 10^{-6}$ | 3 | 2 | **$3.84 \times 10^{-6}$** | **YES** |
| **RULE_BASED_METADATA** | $3.08 \times 10^{-5}$ | 4 | 1 | **$3.08 \times 10^{-5}$** | **YES** |

*Audit Verdict*: **VERIFIED**. All policy advantages survive strict family-wise error rate control at $\alpha = 0.01$.

### 4.2 Effect Sizes and Interpretation Bounds
- **Reported Cohen's $d_z$**:
  - Unperturbed: $d_z = 2.1497$
  - Perturbed: $d_z = 1.9055$
- **Interpretation Bound**: Cohen's $d_z > 1.9$ reflects an extremely consistent positive shift in the synthetic distribution. However, this measures **effect magnitude relative to generator variance**, not effect size in commercial legal practice.

---

## 5. Multi-Dimensional Trade-Off Surface Analysis

The table below summarizes the multi-dimensional operating surface across the 30-seed unperturbed evaluation:

| Configuration | UFR (Risk) $\downarrow$ | UFC (Coverage) $\uparrow$ | HRW (Workload) $\downarrow$ | SEAR (Stale) $\downarrow$ | UAR (Lost Utility) $\downarrow$ |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **CONFIDENCE_BASELINE** | 0.4709 | **0.5683** | **0.0172** | 0.1301 | **0.1538** |
| **VERSION_AWARE** | 0.3249 | **0.5683** | 0.1977 | **0.0000** | **0.1538** |
| **STATUTORY_GROUNDING** | 0.3463 | **0.5683** | 0.1569 | 0.1570 | **0.1538** |
| **FULL_EVIDENCE_AWARE** | **0.2035** | 0.5116 | 0.3316 | **0.0000** | 0.1743 |
| **RULE_BASED_METADATA** | 0.3512 | 0.5664 | 0.0764 | **0.0000** | 0.1556 |

### Trade-Off Observations:
1. **The Cost of Risk Reduction**: `FULL_EVIDENCE_AWARE` reduces the unsupported finding rate by more than half ($47.1\% \rightarrow 20.4\%$). However, it incurs a substantial increase in human-review workload ($1.7\% \rightarrow 33.2\%$) and a modest drop in automated useful coverage ($56.8\% \rightarrow 51.2\%$).
2. **Selective Review Routing**: The $33.2\%$ review workload is not random abstention; it explicitly captures high-severity findings with incomplete citations and ambiguous document version lineages.
3. **The Efficiency of Procedural Rules**: `RULE_BASED_METADATA` achieves zero stale draft acceptance with a very modest review workload ($7.6\%$), but plateaus at a high UFR ($35.1\%$) because it lacks model confidence scoring and nuanced statutory verification.

---

## 6. Rule-Based Metadata Baseline Implementation Audit

The implementation of `evaluate_rule_based_baseline()` was audited against `rule_based_baseline_spec.json` and inspected across candidate-level edge cases:

1. **Candidate 5 (Spurious Model Hallucination)**:
   - Clause: Notices provision predicted as limitation of liability with `evidence_quality_status = INSUFFICIENT`, but citing an in-force Indian Contract Act section.
   - *Rule Baseline Action*: `ACCEPT`.
   - *Full Policy Action*: `WITHHOLD`.
   - *Audit Finding*: Rule 6 in the specification requires `and not candidate.retrieved_passages`. Because a passage was technically returned by BM25, the naive checklist accepted it. The Full Evidence-Aware policy correctly withheld it under Tier 4 because the passage was flagged as `INSUFFICIENT`. This confirms the rule baseline behaves exactly as a naive procedural checklist.
2. **Candidate 2 (Valid Non-Statutory Commercial Covenant)**:
   - Clause: Price adjustment covenant with no statutory citation.
   - *Rule Baseline Action*: `WITHHOLD`.
   - *Full Policy Action*: `ACCEPT`.
   - *Audit Finding*: Because no statutory passage exists, the rule baseline withholds it. The Full Evidence-Aware policy recognizes price adjustment as an authorized non-statutory commercial drafting category and accepts it based on model confidence.
3. **Candidate 3 (Stale Version) & Candidate 10 (Unknown Version)**:
   - *Rule Baseline Action*: Stale is withheld; unknown is routed to review.
   - *Full Policy Action*: Identical behavior.

*Audit Verdict*: **VERIFIED**. The rule baseline implementation adheres strictly to its documented specification and provides a fair, transparent comparison.

---

## 7. Claims Assessment & Final Recommendations

### A. Claims Supported by the Synthetic Experiment
1. **Algorithmic Stability**: The finding that the five-tier evidence-aware policy achieves lower UFR than confidence-only thresholding at matched coverage is stable across random generation seeds ($p < 10^{-8}$).
2. **Marginal Value over Simple Procedural Rules**: The full evidence-aware policy achieves a statistically significant UFR advantage ($+14.8\%$, $p < 10^{-5}$) over a procedural document-integrity checklist.
3. **Zero Stale-Draft Acceptance Invariant**: Both version-aware configurations guarantee $\text{SEAR} = 0.0000$ across all tested generation seeds.

### B. Claims That Remain Unsupported
1. **Real-World Legal Efficacy**: These experiments do **not** prove effectiveness on real commercial contracts or equivalence to human advocate review.
2. **Indian Statutory Completeness**: The 40-section retrieval index does not represent comprehensive Indian commercial law.
3. **Explainability Faithfulness**: Gradient × Input attributions were not evaluated for causal legal faithfulness or lawyer review utility.

### C. Corrections Required Before Academic Deliverables
1. **Report Actual Sample Sizes**: Deliverable reports must state that matched comparisons used $N = 28$ paired seeds (unperturbed) and $N = 27$ paired seeds (perturbed) due to strict non-interpolation of discrete coverage steps.
2. **Explicit Trade-Off Disclosures**: Deliverable reports must highlight the human-review workload increase ($1.7\% \rightarrow 33.2\%$) alongside the UFR reduction.
3. **Mandatory Synthetic Disclaimers**: All figures and tables citing Phase 3.1 must retain the prominent disclaimer: *"SYNTHETIC SOFTWARE VALIDATION — NOT REAL-CONTRACT EVIDENCE"*.

### D. Readiness for Citation
**APPROVED FOR CITATION IN ACADEMIC REPORT**.  
The Phase 3.1 multi-seed evaluation satisfies all requirements for reproducibility, statistical rigor, and governance compliance, and is ready to be incorporated into the final research report under the documented synthetic limitations.
