"""
Offline Policy Comparison Script: Confidence-Only Baseline vs. Evidence-Aware Policy.

Evaluates and compares:
1. POLICY A: Confidence-Only Baseline sweeping continuous thresholds tau_conf in [0.0, 1.0].
2. POLICY B: Evidence-Aware Policy formalizing the five-tier decision cascade.

Evaluates both policies on the exact same synthetic candidate pool using the
prespecified evaluation harness in `src/evaluation/abstention_eval.py`.

STRICT SCIENTIFIC AND ETHICAL SAFEGUARDS:
- Uses ONLY synthetic CandidateFindingRecord fixtures and mock reference decisions.
- All outputs explicitly state:
  "SYNTHETIC ENGINEERING VALIDATION — NOT REAL-CONTRACT EVIDENCE"
- No claims of legal correctness, model accuracy, or research superiority.
"""

import os
import sys
import json
import csv
import argparse
from typing import List, Dict, Any, Optional, Tuple

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.candidates.schema import (
    CandidateFindingRecord,
    LabelMappingStatus,
)
from src.evaluation.abstention_eval import (
    PolicyAction,
    ReferenceDecision,
    PolicyEvaluationSummary,
    CoverageMatchingResult,
    evaluate_policy,
    compare_policies_at_matched_coverage,
)
from src.abstention.evidence_policy import (
    EvidenceAwarePolicy,
    EvidenceAwarePolicyConfig,
    EvidencePolicyDecision,
)
from src.evaluation.synthetic_candidates import (
    SyntheticEvaluationDataset,
    generate_synthetic_candidate_pool,
    SYNTHETIC_DATA_DISCLAIMER,
)


def evaluate_confidence_baseline(
    candidate: CandidateFindingRecord,
    tau_conf: float,
) -> PolicyAction:
    """
    Evaluates a candidate finding under the confidence-only baseline.

    Operational Rules:
    1. Assessability Safety Gate: Missing identifiers or empty text route to REVIEW_REQUIRED.
    2. Label Space Safety Gate: Unsupported model label mappings (e.g. unmapped SEC classes)
       must NOT be automatically accepted regardless of confidence -> WITHHOLD.
    3. Confidence Threshold: If confidence_value >= tau_conf -> ACCEPT; else WITHHOLD.
    """
    # 1. Assessability Safety Gate
    if not candidate.candidate_finding_id or not candidate.clause_text or not candidate.clause_text.strip():
        return PolicyAction.REVIEW_REQUIRED

    # 2. Label Space Safety Gate
    if candidate.label_mapping_status == LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING or \
       candidate.prediction_category.startswith("UNMAPPED_"):
        return PolicyAction.WITHHOLD

    # 3. Threshold check
    if candidate.confidence_value >= tau_conf:
        return PolicyAction.ACCEPT
    else:
        return PolicyAction.WITHHOLD


def run_confidence_threshold_sweep(
    dataset: SyntheticEvaluationDataset,
    thresholds: List[float],
) -> List[Tuple[float, PolicyEvaluationSummary]]:
    """
    Executes a continuous sweep over confidence thresholds for the baseline policy.
    """
    sweep_results: List[Tuple[float, PolicyEvaluationSummary]] = []

    for tau in thresholds:
        baseline_actions: Dict[str, PolicyAction] = {}
        for cand in dataset.candidates:
            action = evaluate_confidence_baseline(cand, tau)
            baseline_actions[cand.candidate_finding_id] = action

        policy_id = f"confidence_baseline_tau_{tau:.2f}"
        summary = evaluate_policy(
            policy_id=policy_id,
            candidates=dataset.candidates,
            reference_annotations=dataset.reference_annotations,
            policy_decisions=baseline_actions,
        )
        sweep_results.append((tau, summary))

    return sweep_results


def find_best_matched_baseline(
    sweep_results: List[Tuple[float, PolicyEvaluationSummary]],
    evid_summary: PolicyEvaluationSummary,
    tolerance: float = 0.02,
) -> Tuple[Optional[float], Optional[PolicyEvaluationSummary], CoverageMatchingResult]:
    """
    Locates the best baseline operating point that matches the evidence-aware policy's
    Useful-Finding Coverage (UFC) within the prespecified tolerance of ±0.02.

    Tie-Breaking Protocol:
    1. Primary key: Minimum absolute difference |UFC_baseline - UFC_evid|.
    2. Deterministic tie-breaker: Higher confidence threshold tau_conf (conservative thresholding).
    """
    evid_ufc = evid_summary.ufc
    if evid_ufc is None:
        unachieved = compare_policies_at_matched_coverage(
            eval_a=sweep_results[0][1],
            eval_b=evid_summary,
            tolerance=tolerance,
        )
        return None, None, unachieved

    eligible_matches: List[Tuple[float, float, float, PolicyEvaluationSummary]] = []

    for tau, summary in sweep_results:
        base_ufc = summary.ufc
        if base_ufc is not None:
            diff = abs(base_ufc - evid_ufc)
            if diff <= tolerance:
                # Store (diff, -tau, tau, summary) for deterministic sorting
                # (-tau breaks ties in favor of higher threshold)
                eligible_matches.append((diff, -tau, tau, summary))

    if not eligible_matches:
        # No threshold achieved matched coverage within tolerance
        unachieved = compare_policies_at_matched_coverage(
            eval_a=sweep_results[0][1],
            eval_b=evid_summary,
            tolerance=tolerance,
        )
        return None, None, unachieved

    # Sort deterministically
    eligible_matches.sort(key=lambda x: (x[0], x[1]))
    best_diff, neg_tau, best_tau, best_summary = eligible_matches[0]

    matching_result = compare_policies_at_matched_coverage(
        eval_a=best_summary,
        eval_b=evid_summary,
        tolerance=tolerance,
    )
    return best_tau, best_summary, matching_result


def export_evaluation_artifacts(
    dataset: SyntheticEvaluationDataset,
    sweep_results: List[Tuple[float, PolicyEvaluationSummary]],
    evid_summary: PolicyEvaluationSummary,
    best_tau: Optional[float],
    best_baseline_summary: Optional[PolicyEvaluationSummary],
    matching_result: CoverageMatchingResult,
    output_dir: str,
) -> Dict[str, str]:
    """
    Exports all evaluation results into reproducible JSONL, CSV, JSON, and Markdown artifacts.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    # 1. JSONL: synthetic_candidate_pool.jsonl
    jsonl_path = os.path.join(output_dir, "synthetic_candidate_pool.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in dataset.candidates:
            cid = c.candidate_finding_id
            row = {
                "candidate": c.model_dump(),
                "reference_decision": dataset.reference_annotations[cid].value,
                "explicit_severity": dataset.explicit_severities.get(cid),
                "disclaimer": SYNTHETIC_DATA_DISCLAIMER,
            }
            f.write(json.dumps(row) + "\n")
    paths["candidate_pool_jsonl"] = jsonl_path

    # 2. CSV: confidence_threshold_sweep.csv
    csv_sweep_path = os.path.join(output_dir, "confidence_threshold_sweep.csv")
    with open(csv_sweep_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "disclaimer",
            "threshold",
            "policy_id",
            "total_candidates",
            "evaluable_candidates",
            "retained_count",
            "retention_rate",
            "evaluable_retained_count",
            "unsupported_finding_count",
            "ufr",
            "total_reference_retainable",
            "retained_useful_count",
            "ufc",
            "human_review_discrepancy_count",
            "human_review_discrepancy_rate",
            "uar_total_rate",
            "sear_stale_rate",
            "sear_unknown_rate",
            "hrw_rate",
            "unassessable_rate",
        ])
        for tau, s in sweep_results:
            writer.writerow([
                "SYNTHETIC",
                f"{tau:.2f}",
                s.policy_id,
                s.total_candidates,
                s.evaluable_candidates,
                s.retained_count,
                f"{s.retention_rate:.4f}",
                s.evaluable_retained_count,
                s.unsupported_finding_count,
                f"{s.ufr:.4f}" if s.ufr is not None else "UNDEFINED",
                s.total_reference_retainable,
                s.retained_useful_count,
                f"{s.ufc:.4f}" if s.ufc is not None else "UNDEFINED",
                s.human_review_discrepancy_count,
                f"{s.human_review_discrepancy_rate:.4f}" if s.human_review_discrepancy_rate is not None else "UNDEFINED",
                f"{s.uar_total_rate:.4f}" if s.uar_total_rate is not None else "UNDEFINED",
                f"{s.sear_stale_rate:.4f}" if s.sear_stale_rate is not None else "UNDEFINED",
                f"{s.sear_unknown_rate:.4f}" if s.sear_unknown_rate is not None else "UNDEFINED",
                f"{s.hrw_rate:.4f}",
                f"{s.unassessable_rate:.4f}",
            ])
    paths["sweep_csv"] = csv_sweep_path

    # 3. CSV: matched_coverage_comparison.csv
    csv_match_path = os.path.join(output_dir, "matched_coverage_comparison.csv")
    with open(csv_match_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "disclaimer",
            "status",
            "tolerance",
            "baseline_threshold",
            "baseline_ufc",
            "evidence_policy_ufc",
            "coverage_difference",
            "baseline_ufr",
            "evidence_policy_ufr",
            "delta_ufr",
            "baseline_uar_total",
            "evidence_policy_uar_total",
            "baseline_sear_stale",
            "evidence_policy_sear_stale",
            "baseline_hrw",
            "evidence_policy_hrw",
            "notes",
        ])
        b_ufr = f"{best_baseline_summary.ufr:.4f}" if (best_baseline_summary and best_baseline_summary.ufr is not None) else "UNDEFINED"
        e_ufr = f"{evid_summary.ufr:.4f}" if evid_summary.ufr is not None else "UNDEFINED"
        b_ufc = f"{best_baseline_summary.ufc:.4f}" if (best_baseline_summary and best_baseline_summary.ufc is not None) else "UNDEFINED"
        e_ufc = f"{evid_summary.ufc:.4f}" if evid_summary.ufc is not None else "UNDEFINED"
        d_ufr = f"{matching_result.delta_ufr:.4f}" if matching_result.delta_ufr is not None else "UNDEFINED"

        writer.writerow([
            "SYNTHETIC",
            matching_result.status,
            matching_result.tolerance,
            f"{best_tau:.2f}" if best_tau is not None else "NONE",
            b_ufc,
            e_ufc,
            f"{matching_result.coverage_difference:.4f}" if matching_result.coverage_difference is not None else "NONE",
            b_ufr,
            e_ufr,
            d_ufr,
            f"{best_baseline_summary.uar_total_rate:.4f}" if (best_baseline_summary and best_baseline_summary.uar_total_rate is not None) else "NONE",
            f"{evid_summary.uar_total_rate:.4f}" if evid_summary.uar_total_rate is not None else "NONE",
            f"{best_baseline_summary.sear_stale_rate:.4f}" if (best_baseline_summary and best_baseline_summary.sear_stale_rate is not None) else "NONE",
            f"{evid_summary.sear_stale_rate:.4f}" if evid_summary.sear_stale_rate is not None else "NONE",
            f"{best_baseline_summary.hrw_rate:.4f}" if best_baseline_summary else "NONE",
            f"{evid_summary.hrw_rate:.4f}",
            matching_result.notes,
        ])
    paths["matched_csv"] = csv_match_path

    # 4. JSON: synthetic_evaluation_summary.json
    json_summary_path = os.path.join(output_dir, "synthetic_evaluation_summary.json")
    summary_data = {
        "disclaimer": SYNTHETIC_DATA_DISCLAIMER,
        "seed": dataset.seed,
        "candidate_count": dataset.total_candidates,
        "unique_contracts": dataset.unique_contracts,
        "threshold_grid_count": len(sweep_results),
        "tolerance": matching_result.tolerance,
        "matching_result": matching_result.model_dump(),
        "evidence_aware_summary": evid_summary.model_dump(),
        "matched_baseline_summary": best_baseline_summary.model_dump() if best_baseline_summary else None,
        "best_baseline_threshold": best_tau,
    }
    with open(json_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    paths["summary_json"] = json_summary_path

    return paths


def execute_offline_comparison(
    seed: int = 42,
    num_contracts: int = 15,
    additional_random: int = 45,
    threshold_step: float = 0.01,
    output_dir: str = "results/synthetic_evaluation",
) -> Dict[str, Any]:
    """
    Main execution pipeline for the offline comparison.
    """
    # 1. Generate Synthetic Candidate Pool
    dataset = generate_synthetic_candidate_pool(
        seed=seed,
        num_contracts=num_contracts,
        additional_random_count=additional_random,
    )

    # 2. Evaluate Evidence-Aware Policy Once
    evid_policy = EvidenceAwarePolicy()
    evid_decisions: Dict[str, PolicyAction] = {}

    for cand in dataset.candidates:
        cid = cand.candidate_finding_id
        sev = dataset.explicit_severities.get(cid)
        dec = evid_policy.evaluate_candidate(cand, explicit_severity=sev)
        evid_decisions[cid] = dec.policy_action

    evid_summary = evaluate_policy(
        policy_id=evid_policy.config.policy_id,
        candidates=dataset.candidates,
        reference_annotations=dataset.reference_annotations,
        policy_decisions=evid_decisions,
    )

    # 3. Sweep Baseline Thresholds
    steps = int(round(1.0 / threshold_step)) + 1
    thresholds = [round(i * threshold_step, 4) for i in range(steps)]
    sweep_results = run_confidence_threshold_sweep(dataset, thresholds)

    # 4. Perform Matched-Coverage Comparison
    best_tau, best_baseline_summary, matching_result = find_best_matched_baseline(
        sweep_results=sweep_results,
        evid_summary=evid_summary,
        tolerance=0.02,
    )

    # 5. Export Output Artifacts
    artifact_paths = export_evaluation_artifacts(
        dataset=dataset,
        sweep_results=sweep_results,
        evid_summary=evid_summary,
        best_tau=best_tau,
        best_baseline_summary=best_baseline_summary,
        matching_result=matching_result,
        output_dir=output_dir,
    )

    return {
        "dataset": dataset,
        "evid_summary": evid_summary,
        "best_tau": best_tau,
        "best_baseline_summary": best_baseline_summary,
        "matching_result": matching_result,
        "artifact_paths": artifact_paths,
        "sweep_count": len(sweep_results),
    }


def main():
    parser = argparse.ArgumentParser(description="Offline Policy Comparison: Confidence Baseline vs. Evidence-Aware Policy")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--num-contracts", type=int, default=15, help="Number of synthetic contracts")
    parser.add_argument("--additional-random", type=int, default=45, help="Number of seeded synthetic candidates")
    parser.add_argument("--step", type=float, default=0.01, help="Threshold grid step size")
    parser.add_argument("--output-dir", type=str, default="results/synthetic_evaluation", help="Output directory")

    args = parser.parse_args()

    print("================================================================================")
    print("CONTRACTRISK-XAI: OFFLINE POLICY COMPARISON (SYNTHETIC ENGINEERING VALIDATION)")
    print(SYNTHETIC_DATA_DISCLAIMER)
    print("================================================================================")
    print(f"Executing with Seed: {args.seed}, Output Dir: {args.output_dir}...")

    results = execute_offline_comparison(
        seed=args.seed,
        num_contracts=args.num_contracts,
        additional_random=args.additional_random,
        threshold_step=args.step,
        output_dir=args.output_dir,
    )

    ev_sum = results["evid_summary"]
    best_base = results["best_baseline_summary"]
    match = results["matching_result"]
    tau = results["best_tau"]

    print("\n--- EVALUATION SUMMARY ---")
    print(f"Total Synthetic Candidates: {results['dataset'].total_candidates}")
    print(f"Unique Synthetic Contracts: {results['dataset'].unique_contracts}")
    print(f"Threshold Grid Evaluated: {results['sweep_count']} points")
    print(f"\n[Evidence-Aware Policy ({ev_sum.policy_id})]")
    print(f"  Retention Rate:  {ev_sum.retention_rate:.4f} ({ev_sum.retained_count}/{ev_sum.total_candidates})")
    print(f"  Useful Coverage: {ev_sum.ufc:.4f}" if ev_sum.ufc is not None else "  Useful Coverage: UNDEFINED")
    print(f"  UFR:             {ev_sum.ufr:.4f}" if ev_sum.ufr is not None else "  UFR:             UNDEFINED")
    print(f"  Human Review HW: {ev_sum.hrw_rate:.4f} ({ev_sum.routed_to_review_count})")
    print(f"  Stale Accept.:   {ev_sum.sear_stale_rate:.4f}" if ev_sum.sear_stale_rate is not None else "  Stale Accept.:   NONE")

    print(f"\n[Matched Baseline (tau = {tau:.2f})]" if tau is not None else "\n[Matched Baseline: NONE]")
    if best_base:
        print(f"  Retention Rate:  {best_base.retention_rate:.4f} ({best_base.retained_count}/{best_base.total_candidates})")
        print(f"  Useful Coverage: {best_base.ufc:.4f}" if best_base.ufc is not None else "  Useful Coverage: UNDEFINED")
        print(f"  UFR:             {best_base.ufr:.4f}" if best_base.ufr is not None else "  UFR:             UNDEFINED")
        print(f"  Human Review HW: {best_base.hrw_rate:.4f} ({best_base.routed_to_review_count})")
        print(f"  Stale Accept.:   {best_base.sear_stale_rate:.4f}" if best_base.sear_stale_rate is not None else "  Stale Accept.:   NONE")

    print(f"\n[Coverage Matching Result: {match.status}]")
    print(f"  Tolerance:       ±{match.tolerance:.2f}")
    print(f"  Coverage Diff:   {match.coverage_difference:.4f}" if match.coverage_difference is not None else "  Coverage Diff:   NONE")
    print(f"  Delta-UFR:       {match.delta_ufr:.4f}" if match.delta_ufr is not None else "  Delta-UFR:       NONE")
    print(f"  Notes:           {match.notes}")

    print("\nGenerated Artifacts:")
    for k, v in results["artifact_paths"].items():
        print(f"  - {k}: {v}")

    print("================================================================================")


if __name__ == "__main__":
    main()
