"""
Publication-Readiness Analysis and Sensitivity Audit for Phase 3.3.

Audits matched-coverage pairing, excluded seeds sensitivity, statistical tests,
and metric reconciliation.
Writes outputs strictly to results/abstention_ablation/phase_3_3_publication_audit/.
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

PHASE_3_1_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "multi_seed"))
OUT_DIR = os.path.abspath(os.path.dirname(__file__))


def load_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def perform_publication_audit():
    os.makedirs(OUT_DIR, exist_ok=True)
    unp_rows = load_csv(os.path.join(PHASE_3_1_DIR, "per_seed_metrics_unperturbed.csv"))
    per_rows = load_csv(os.path.join(PHASE_3_1_DIR, "per_seed_metrics_perturbed.csv"))

    audit_data = {}

    for b_name, rows in [("unperturbed", unp_rows), ("perturbed", per_rows)]:
        b_audit = {}
        cfgs = ["FULL_EVIDENCE_AWARE", "VERSION_AWARE", "STATUTORY_GROUNDING", "RULE_BASED_METADATA"]

        for cfg in cfgs:
            cfg_rows = [r for r in rows if r["configuration"] == cfg]
            
            included_seeds = []
            excluded_seeds = []
            paired_records = []

            for r in cfg_rows:
                s = int(r["seed"])
                status = r["matched_status"]
                diff = float(r["matched_coverage_difference"]) if r["matched_coverage_difference"] != "" else None
                delta = float(r["delta_ufr"]) if r["delta_ufr"] != "" else None
                base_ufr = float(r["baseline_ufr"]) if r["baseline_ufr"] != "" else None
                pol_ufr = float(r["ufr"]) if r["ufr"] != "" else None
                pol_ufc = float(r["ufc"]) if r["ufc"] != "" else None
                base_tau = float(r["matched_baseline_tau"]) if r["matched_baseline_tau"] != "" else None

                if status == "MATCHED_COVERAGE_ACHIEVED" and delta is not None:
                    included_seeds.append(s)
                    paired_records.append({
                        "seed": s,
                        "policy_ufc": pol_ufc,
                        "matched_baseline_tau": base_tau,
                        "coverage_difference": diff,
                        "baseline_ufr": base_ufr,
                        "policy_ufr": pol_ufr,
                        "paired_delta_ufr": delta,
                    })
                else:
                    excluded_seeds.append({
                        "seed": s,
                        "status": status,
                        "coverage_difference": diff,
                        "policy_ufc": pol_ufc,
                        "reason": f"Coverage difference ({diff}) exceeded prespecified tolerance of 0.02" if diff else "No matched point"
                    })

            # Calculate paired descriptive statistics
            deltas = [p["paired_delta_ufr"] for p in paired_records]
            n = len(deltas)
            mean_d = float(np.mean(deltas))
            std_d = float(np.std(deltas, ddof=1)) if n > 1 else 0.0
            median_d = float(np.median(deltas))
            q25, q75 = float(np.percentile(deltas, 25)), float(np.percentile(deltas, 75))
            
            # 95% Student-t CI
            t_crit = stats.t.ppf(0.975, df=n - 1)
            se_d = std_d / math.sqrt(n)
            ci_95 = [float(mean_d - t_crit * se_d), float(mean_d + t_crit * se_d)]

            # Bootstrap 95% CI (10,000 iterations)
            np.random.seed(42)
            boot_means = [np.mean(np.random.choice(deltas, size=n, replace=True)) for _ in range(10000)]
            boot_ci_95 = [float(np.percentile(boot_means, 2.5)), float(np.percentile(boot_means, 97.5))]

            # Tests
            t_stat, t_p = stats.ttest_1samp(deltas, popmean=0.0)
            w_res = stats.wilcoxon(deltas, zero_method="wilcox")
            w_stat = float(w_res.statistic)
            w_p = float(w_res.pvalue)
            cohen_dz = mean_d / std_d if std_d > 0 else None

            b_audit[cfg] = {
                "total_seeds": len(cfg_rows),
                "matched_sample_size": n,
                "included_seeds": included_seeds,
                "excluded_count": len(excluded_seeds),
                "excluded_seeds": excluded_seeds,
                "paired_delta_ufr_records": paired_records,
                "mean_delta_ufr": round(mean_d, 4),
                "std_delta_ufr": round(std_d, 4),
                "median_delta_ufr": round(median_d, 4),
                "iqr_25_75": [round(q25, 4), round(q75, 4)],
                "student_t_ci_95": [round(ci_95[0], 4), round(ci_95[1], 4)],
                "bootstrap_ci_95": [round(boot_ci_95[0], 4), round(boot_ci_95[1], 4)],
                "t_statistic": round(float(t_stat), 4),
                "t_p_value": float(t_p),
                "wilcoxon_statistic": round(w_stat, 4),
                "wilcoxon_p_value": w_p,
                "cohen_dz": round(cohen_dz, 4) if cohen_dz is not None else None,
            }

        # Sensitivity Analysis: What if excluded seeds had Delta UFR = 0 (worst-case attrition)?
        full_p = b_audit["FULL_EVIDENCE_AWARE"]
        imputed_worst_case_deltas = [p["paired_delta_ufr"] for p in full_p["paired_delta_ufr_records"]] + [0.0] * full_p["excluded_count"]
        w_imp = stats.wilcoxon(imputed_worst_case_deltas, zero_method="wilcox")
        t_imp = stats.ttest_1samp(imputed_worst_case_deltas, popmean=0.0)

        b_audit["FULL_EVIDENCE_AWARE_SENSITIVITY"] = {
            "imputed_sample_size": len(imputed_worst_case_deltas),
            "worst_case_imputed_mean_delta": round(float(np.mean(imputed_worst_case_deltas)), 4),
            "worst_case_t_statistic": round(float(t_imp.statistic), 4),
            "worst_case_t_p_value": float(t_imp.pvalue),
            "worst_case_wilcoxon_p_value": float(w_imp.pvalue),
            "conclusion_altered": bool(w_imp.pvalue > 0.01),
        }

        audit_data[b_name] = b_audit

    # Save detailed JSON
    json_path = os.path.join(OUT_DIR, "publication_reconciliation_tables.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    # Save CSV of all paired delta-UFR records
    csv_path = os.path.join(OUT_DIR, "paired_matched_coverage_reconciliation.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "benchmark", "configuration", "seed", "policy_ufc", "matched_baseline_tau",
            "coverage_difference", "baseline_ufr", "policy_ufr", "paired_delta_ufr"
        ])
        for b_name, b_cfgs in audit_data.items():
            for cfg in ["FULL_EVIDENCE_AWARE", "VERSION_AWARE", "STATUTORY_GROUNDING", "RULE_BASED_METADATA"]:
                for rec in b_cfgs[cfg]["paired_delta_ufr_records"]:
                    writer.writerow([
                        b_name, cfg, rec["seed"], rec["policy_ufc"], rec["matched_baseline_tau"],
                        rec["coverage_difference"], rec["baseline_ufr"], rec["policy_ufr"], rec["paired_delta_ufr"]
                    ])

    print("Phase 3.3 Publication Audit Reconciliation complete. Artifacts saved in:", OUT_DIR)
    return audit_data


if __name__ == "__main__":
    perform_publication_audit()
