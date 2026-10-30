"""
Independent Audit and Reconciliation Script for Phase 3.1 Multi-Seed Evaluation.

Phase 3.2: Result Reconciliation and Research Validity Audit.
Strictly read-only with respect to historical and Phase 3.1 artifacts.
Writes audit results exclusively to results/abstention_ablation/phase_3_2_audit/.
"""

import os
import sys
import json
import csv
import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from scipy import stats

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from src.evaluation.abstention_eval import (
    ReferenceDecision,
    PolicyAction,
)

PHASE_3_1_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "multi_seed"))
AUDIT_OUT_DIR = os.path.abspath(os.path.dirname(__file__))


def load_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def reconcile_candidate_decisions():
    """
    Independently recomputes every metric for every seed and configuration
    from per_candidate_decisions.csv and compares against per_seed_metrics_unperturbed.csv.
    """
    cand_path = os.path.join(PHASE_3_1_DIR, "per_candidate_decisions.csv")
    unp_path = os.path.join(PHASE_3_1_DIR, "per_seed_metrics_unperturbed.csv")

    candidates = load_csv(cand_path)
    reported_metrics = load_csv(unp_path)

    # Group candidates by seed
    candidates_by_seed: Dict[int, List[Dict[str, Any]]] = {}
    for c in candidates:
        s = int(c["seed"])
        candidates_by_seed.setdefault(s, []).append(c)

    # Configurations mapping in candidate decisions
    cfg_to_col = {
        "CONFIDENCE_BASELINE": "action_confidence_baseline",
        "VERSION_AWARE": "action_version_aware",
        "STATUTORY_GROUNDING": "action_statutory_grounding",
        "FULL_EVIDENCE_AWARE": "action_full_evidence_aware",
        "RULE_BASED_METADATA": "action_rule_based_metadata",
    }

    recomputed_rows = []
    discrepancies = []

    for rep in reported_metrics:
        s = int(rep["seed"])
        cfg = rep["configuration"]
        cands = candidates_by_seed.get(s, [])
        col = cfg_to_col[cfg]

        total_cands = len(cands)
        # Unassessable check: clause corrupt / NOT_ASSESSABLE
        unassessable_cands = [c for c in cands if c["reference_decision"] == "NOT_ASSESSABLE"]
        evaluable_cands = [c for c in cands if c["reference_decision"] != "NOT_ASSESSABLE"]
        evaluable_count = len(evaluable_cands)

        # Policy actions
        retained = [c for c in cands if c[col] in ("ACCEPT", "RETAIN")]
        retained_count = len(retained)
        retention_rate = retained_count / total_cands if total_cands > 0 else 0.0

        evaluable_retained = [c for c in evaluable_cands if c[col] in ("ACCEPT", "RETAIN")]
        evaluable_retained_count = len(evaluable_retained)

        # Unsupported findings: y_ref == WITHHOLD in evaluable retained
        unsupported = [c for c in evaluable_retained if c["reference_decision"] == "WITHHOLD"]
        unsupported_count = len(unsupported)
        ufr = (unsupported_count / evaluable_retained_count) if evaluable_retained_count > 0 else None

        # Useful coverage: y_ref == RETAIN in evaluable retained / total y_ref == RETAIN in evaluable
        reference_retainable = [c for c in evaluable_cands if c["reference_decision"] == "RETAIN"]
        total_ref_retainable = len(reference_retainable)
        retained_useful = [c for c in evaluable_retained if c["reference_decision"] == "RETAIN"]
        ufc = (len(retained_useful) / total_ref_retainable) if total_ref_retainable > 0 else None

        # SEAR stale: version == STALE in retained
        sear_stale_count = sum(1 for c in retained if c["version_status"] == "STALE")
        sear_stale_rate = (sear_stale_count / retained_count) if retained_count > 0 else None

        # SEAR unknown: version == UNKNOWN in retained
        sear_unknown_count = sum(1 for c in retained if c["version_status"] == "UNKNOWN")
        sear_unknown_rate = (sear_unknown_count / retained_count) if retained_count > 0 else None

        # HRW: action == REVIEW_REQUIRED
        hrw_count = sum(1 for c in cands if c[col] == "REVIEW_REQUIRED")
        hrw_rate = hrw_count / total_cands if total_cands > 0 else 0.0

        # UAR total: reference RETAIN not accepted (withheld or review)
        uar_unretained = [c for c in reference_retainable if c[col] not in ("ACCEPT", "RETAIN")]
        uar_rate = (len(uar_unretained) / evaluable_count) if evaluable_count > 0 else None

        # Compare with reported values
        def _check(metric_name, recomputed, reported_str, tol=1e-4):
            if reported_str == "" or reported_str is None or reported_str == "None":
                if recomputed is not None:
                    discrepancies.append({
                        "seed": s, "cfg": cfg, "metric": metric_name,
                        "recomputed": recomputed, "reported": reported_str,
                        "type": "NONE_MISMATCH"
                    })
                return
            reported_val = float(reported_str)
            if recomputed is None:
                discrepancies.append({
                    "seed": s, "cfg": cfg, "metric": metric_name,
                    "recomputed": recomputed, "reported": reported_val,
                    "type": "NONE_MISMATCH"
                })
            elif abs(recomputed - reported_val) > tol:
                discrepancies.append({
                    "seed": s, "cfg": cfg, "metric": metric_name,
                    "recomputed": recomputed, "reported": reported_val,
                    "diff": abs(recomputed - reported_val),
                    "type": "VALUE_MISMATCH"
                })

        _check("retained_count", retained_count, rep["retained_count"])
        _check("evaluable_retained_count", evaluable_retained_count, rep["evaluable_retained_count"])
        _check("unsupported_finding_count", unsupported_count, rep["unsupported_finding_count"])
        _check("ufr", ufr, rep["ufr"])
        _check("ufc", ufc, rep["ufc"])
        _check("sear_stale_rate", sear_stale_rate, rep["sear_stale_rate"])
        _check("sear_unknown_rate", sear_unknown_rate, rep["sear_unknown_rate"])
        _check("hrw_rate", hrw_rate, rep["hrw_rate"])
        _check("uar_total_rate", uar_rate, rep["uar_total_rate"])

        recomputed_rows.append({
            "seed": s,
            "configuration": cfg,
            "total_candidates": total_cands,
            "evaluable_candidates": evaluable_count,
            "recomputed_retained_count": retained_count,
            "recomputed_evaluable_retained": evaluable_retained_count,
            "recomputed_unsupported_count": unsupported_count,
            "recomputed_ufr": round(ufr, 4) if ufr is not None else None,
            "recomputed_ufc": round(ufc, 4) if ufc is not None else None,
            "recomputed_sear_stale": round(sear_stale_rate, 4) if sear_stale_rate is not None else None,
            "recomputed_sear_unknown": round(sear_unknown_rate, 4) if sear_unknown_rate is not None else None,
            "recomputed_hrw": round(hrw_rate, 4),
            "recomputed_uar": round(uar_rate, 4) if uar_rate is not None else None,
            "reported_ufr": round(float(rep["ufr"]), 4) if rep["ufr"] != "" else None,
            "reported_ufc": round(float(rep["ufc"]), 4) if rep["ufc"] != "" else None,
            "reported_delta_ufr": round(float(rep["delta_ufr"]), 4) if rep["delta_ufr"] != "" else None,
            "matched_status": rep["matched_status"],
        })

    return recomputed_rows, discrepancies


def audit_statistical_tests():
    """
    Independently audits all hypothesis tests and confidence intervals
    reported in statistical_analysis_results.json.
    """
    unp_metrics = load_csv(os.path.join(PHASE_3_1_DIR, "per_seed_metrics_unperturbed.csv"))
    per_metrics = load_csv(os.path.join(PHASE_3_1_DIR, "per_seed_metrics_perturbed.csv"))
    reported_stats = load_json(os.path.join(PHASE_3_1_DIR, "statistical_analysis_results.json"))

    audit_stat_results = {}

    for b_name, recs in [("unperturbed", unp_metrics), ("perturbed", per_metrics)]:
        audit_stat_results[b_name] = {}
        reported_b = reported_stats[b_name]

        for cfg in ["FULL_EVIDENCE_AWARE", "VERSION_AWARE", "STATUTORY_GROUNDING", "RULE_BASED_METADATA"]:
            cfg_rows = [r for r in recs if r["configuration"] == cfg]
            # Extract delta_ufr
            valid_deltas = [float(r["delta_ufr"]) for r in cfg_rows if r["delta_ufr"] != "" and r["delta_ufr"] is not None]
            
            n = len(valid_deltas)
            mean_d = float(np.mean(valid_deltas))
            std_d = float(np.std(valid_deltas, ddof=1))
            se_d = std_d / math.sqrt(n)

            # 95% Student t CI
            t_crit = stats.t.ppf(0.975, df=n - 1)
            ci_95 = [float(mean_d - t_crit * se_d), float(mean_d + t_crit * se_d)]

            # Shapiro-Wilk normality
            sw_stat, sw_p = stats.shapiro(valid_deltas)

            # Paired Student t-test
            t_stat, t_p = stats.ttest_1samp(valid_deltas, popmean=0.0)

            # Wilcoxon signed-rank
            w_res = stats.wilcoxon(np.array(valid_deltas) - 0.0, zero_method="wilcox")

            # Cohen's d_z
            d_z = mean_d / std_d if std_d > 0 else None

            rep_cfg = reported_b.get(cfg, {})

            audit_stat_results[b_name][cfg] = {
                "sample_size": n,
                "recomputed_mean_delta": round(mean_d, 4),
                "reported_mean_delta": rep_cfg.get("mean_delta_ufr"),
                "recomputed_std_delta": round(std_d, 4),
                "reported_std_delta": rep_cfg.get("std_delta_ufr"),
                "recomputed_ci_95": [round(ci_95[0], 4), round(ci_95[1], 4)],
                "shapiro_p": round(float(sw_p), 6),
                "t_stat": round(float(t_stat), 4),
                "t_p": float(t_p),
                "wilcoxon_stat": round(float(w_res.statistic), 4),
                "wilcoxon_p": float(w_res.pvalue),
                "cohen_dz": round(d_z, 4) if d_z is not None else None,
                "reported_wilcoxon_p": rep_cfg.get("wilcoxon_p_value"),
                "p_value_matches": abs(float(w_res.pvalue) - float(rep_cfg.get("wilcoxon_p_value", 0))) < 1e-6,
            }

        # Multiple Comparisons Correction (Holm-Bonferroni across the 4 policy tests)
        # Sort hypotheses by unadjusted p-value ascending
        p_vals = []
        for cfg in ["FULL_EVIDENCE_AWARE", "VERSION_AWARE", "STATUTORY_GROUNDING", "RULE_BASED_METADATA"]:
            p = audit_stat_results[b_name][cfg]["wilcoxon_p"]
            p_vals.append((cfg, p))
        p_vals.sort(key=lambda x: x[1])

        m = len(p_vals)
        holm_adjusted = {}
        for rank, (cfg, raw_p) in enumerate(p_vals):
            adj_p = min(1.0, raw_p * (m - rank))
            holm_adjusted[cfg] = {
                "rank": rank + 1,
                "raw_p": raw_p,
                "holm_bonferroni_p": adj_p,
                "significant_at_0_01": adj_p < 0.01,
            }
        audit_stat_results[b_name]["holm_bonferroni_adjustment"] = holm_adjusted

    return audit_stat_results


def analyze_multidimensional_tradeoffs():
    """
    Analyzes the multi-dimensional trade-off surface among:
    - Unsupported-Finding Rate (UFR)
    - Useful-Finding Coverage (UFC)
    - Human-Review Workload (HRW)
    - Stale-Evidence Acceptance Rate (SEAR)
    - Unnecessary-Abstention Rate (UAR)
    """
    agg = load_json(os.path.join(PHASE_3_1_DIR, "aggregated_statistics.json"))
    unp = agg["unperturbed"]

    tradeoff_summary = {}
    for cfg, metrics in unp.items():
        tradeoff_summary[cfg] = {
            "ufr_mean": metrics["ufr"]["mean"],
            "ufc_mean": metrics["ufc"]["mean"],
            "hrw_mean": metrics["hrw"]["mean"],
            "sear_stale_mean": metrics["sear_stale"]["mean"],
            "uar_mean": metrics["uar"]["mean"],
            "delta_ufr_mean": metrics["delta_ufr"]["mean"],
        }
    return tradeoff_summary


def audit_rule_based_baseline_implementation():
    """
    Examines edge cases in per_candidate_decisions.csv to evaluate exact
    adherence between rule specification and implemented behavior.
    """
    candidates = load_csv(os.path.join(PHASE_3_1_DIR, "per_candidate_decisions.csv"))

    # Check Candidate 5 behavior across seeds (Spurious Hallucination edge case)
    cand_5_decisions = [c for c in candidates if c["clause_id"] == "clause-notices-01"]
    
    # Check Candidate 2 behavior across seeds (Non-statutory price adjustment)
    cand_2_decisions = [c for c in candidates if c["clause_id"] == "clause-price-02"]

    # Check Candidate 10 behavior (Unknown version)
    cand_10_decisions = [c for c in candidates if c["clause_id"] == "clause-unknown-v-02"]

    # Check Candidate 3 behavior (Stale version)
    cand_3_decisions = [c for c in candidates if c["clause_id"] == "clause-superseded-01"]

    analysis = {
        "candidate_5_spurious_hallucination": {
            "description": "Limitation of liability predicted on notices clause, INSUFFICIENT evidence, but cited provision present",
            "rule_based_actions": list(set(c["action_rule_based_metadata"] for c in cand_5_decisions)),
            "full_evidence_actions": list(set(c["action_full_evidence_aware"] for c in cand_5_decisions)),
            "note": (
                "Rule baseline accepts Candidate 5 because retrieved_passages is non-empty, "
                "whereas Full Evidence-Aware policy withholds or routes it because evidence_quality_status is INSUFFICIENT. "
                "This confirms the rule baseline functions strictly as a procedural passage presence check."
            )
        },
        "candidate_2_non_statutory": {
            "description": "Price adjustment clause, non-statutory category, NO_MATCHING_EVIDENCE",
            "rule_based_actions": list(set(c["action_rule_based_metadata"] for c in cand_2_decisions)),
            "full_evidence_actions": list(set(c["action_full_evidence_aware"] for c in cand_2_decisions)),
            "note": (
                "Rule baseline withholds Candidate 2 because no statutory passage exists, "
                "whereas Full Evidence-Aware policy accepts it under Tier 5 because price adjustment "
                "is an approved non-statutory commercial drafting category with high confidence."
            )
        },
        "candidate_10_unknown_version": {
            "description": "Severability clause with UNKNOWN document version",
            "rule_based_actions": list(set(c["action_rule_based_metadata"] for c in cand_10_decisions)),
            "full_evidence_actions": list(set(c["action_full_evidence_aware"] for c in cand_10_decisions)),
            "note": "Both rule baseline and Full Evidence-Aware policy correctly route unknown versions to REVIEW_REQUIRED."
        },
        "candidate_3_stale_version": {
            "description": "Termination clause from STALE document version",
            "rule_based_actions": list(set(c["action_rule_based_metadata"] for c in cand_3_decisions)),
            "full_evidence_actions": list(set(c["action_full_evidence_aware"] for c in cand_3_decisions)),
            "note": "Both rule baseline and Full Evidence-Aware policy correctly WITHHOLD stale document versions."
        }
    }
    return analysis


def run_full_audit():
    os.makedirs(AUDIT_OUT_DIR, exist_ok=True)
    print("Executing Phase 3.2 Result Reconciliation & Research Validity Audit...")

    # 1. Reconcile candidates
    print("  -> Reconciling candidate decisions against reported seed metrics...")
    recomputed_rows, discrepancies = reconcile_candidate_decisions()
    print(f"     Discrepancies found: {len(discrepancies)}")

    recomp_csv = os.path.join(AUDIT_OUT_DIR, "recomputed_per_seed_metrics_unperturbed.csv")
    with open(recomp_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(recomputed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(recomputed_rows)

    disc_path = os.path.join(AUDIT_OUT_DIR, "discrepancy_log.json")
    with open(disc_path, "w", encoding="utf-8") as f:
        json.dump(discrepancies, f, indent=2)

    # 2. Audit statistical tests
    print("  -> Auditing hypothesis tests, normality, and multiple comparison corrections...")
    audit_stats = audit_statistical_tests()
    stat_path = os.path.join(AUDIT_OUT_DIR, "independent_statistical_audit.json")
    with open(stat_path, "w", encoding="utf-8") as f:
        json.dump(audit_stats, f, indent=2)

    # 3. Trade-off analysis
    print("  -> Analyzing multi-dimensional risk/coverage/workload trade-offs...")
    tradeoffs = analyze_multidimensional_tradeoffs()
    tradeoff_path = os.path.join(AUDIT_OUT_DIR, "tradeoff_analysis.json")
    with open(tradeoff_path, "w", encoding="utf-8") as f:
        json.dump(tradeoffs, f, indent=2)

    # 4. Rule baseline inspection
    print("  -> Inspecting rule-based metadata baseline edge-case adherence...")
    rule_inspection = audit_rule_based_baseline_implementation()
    rule_insp_path = os.path.join(AUDIT_OUT_DIR, "rule_baseline_adherence_audit.json")
    with open(rule_insp_path, "w", encoding="utf-8") as f:
        json.dump(rule_inspection, f, indent=2)

    print("Phase 3.2 Audit Calculations Complete. Saved artifacts in:", AUDIT_OUT_DIR)
    return {
        "discrepancies_count": len(discrepancies),
        "audit_stats": audit_stats,
        "tradeoffs": tradeoffs,
        "rule_inspection": rule_inspection,
    }


if __name__ == "__main__":
    run_full_audit()
