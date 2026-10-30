import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from src.evaluation.synthetic_candidates import generate_synthetic_candidate_pool, generate_perturbed_candidate_pool
from scripts.evaluate_abstention_ablation import (
    build_ablation_policy_instances,
    evaluate_confidence_baseline,
    run_confidence_threshold_sweep,
    find_best_matched_baseline,
)
from src.evaluation.abstention_eval import (
    evaluate_policy,
    PolicyAction,
    ReferenceDecision,
)

# Load saved summary
saved_summary = json.load(open('results/abstention_ablation/ablation_metrics_summary.json', 'r', encoding='utf-8'))

results = {}

for bench_name, get_pool in [
    ('unperturbed_benchmark', lambda: generate_synthetic_candidate_pool(seed=42, num_contracts=15, additional_random_count=45)),
    ('perturbed_benchmark', lambda: generate_perturbed_candidate_pool(seed=42, num_contracts=15, additional_random_count=45, perturbation_rate=0.20)),
]:
    print('=' * 40, bench_name, '=' * 40)
    ds = get_pool()
    cands = ds.candidates
    refs = ds.reference_annotations
    print(f"Total candidates: {len(cands)}, Reference annotations count: {len(refs)}")

    cand_ids = [c.candidate_finding_id for c in cands]
    assert len(set(cand_ids)) == len(cand_ids), "Duplicate candidate IDs!"

    policies = build_ablation_policy_instances(threshold=0.50)
    baseline_actions = {c.candidate_finding_id: evaluate_confidence_baseline(c, tau_conf=0.50) for c in cands}

    all_configs = {'CONFIDENCE_BASELINE': baseline_actions}
    for name, pol in policies.items():
        all_configs[name] = {
            c.candidate_finding_id: pol.evaluate_candidate(
                c,
                explicit_severity=ds.explicit_severities.get(c.candidate_finding_id)
            ).policy_action
            for c in cands
        }

    for name, acts in all_configs.items():
        assert list(acts.keys()) == cand_ids, f"Candidate ID mismatch in {name}"

    thresholds = [round(i * 0.01, 4) for i in range(101)]
    sweep = run_confidence_threshold_sweep(ds, thresholds)

    results[bench_name] = {}

    for name, acts in all_configs.items():
        print(f"\n--- Configuration: {name} ---")
        total = len(cands)
        unassessable_ids = {c.candidate_finding_id for c in cands if refs[c.candidate_finding_id] == ReferenceDecision.NOT_ASSESSABLE}
        evaluable_cands = [c for c in cands if c.candidate_finding_id not in unassessable_ids]

        accepted = [c for c in cands if acts[c.candidate_finding_id] in (PolicyAction.ACCEPT, PolicyAction.RETAIN)]
        withheld = [c for c in cands if acts[c.candidate_finding_id] == PolicyAction.WITHHOLD]
        review = [c for c in cands if acts[c.candidate_finding_id] == PolicyAction.REVIEW_REQUIRED]

        evaluable_retained = [c for c in accepted if c.candidate_finding_id not in unassessable_ids]

        retainable_ref = [c for c in evaluable_cands if refs[c.candidate_finding_id] == ReferenceDecision.RETAIN]
        retained_useful = [c for c in evaluable_retained if refs[c.candidate_finding_id] == ReferenceDecision.RETAIN]
        ufc = len(retained_useful) / len(retainable_ref) if retainable_ref else None

        unsupported = [c for c in evaluable_retained if refs[c.candidate_finding_id] == ReferenceDecision.WITHHOLD]
        ufr = len(unsupported) / len(evaluable_retained) if evaluable_retained else None

        discrepancies = [c for c in evaluable_retained if refs[c.candidate_finding_id] == ReferenceDecision.HUMAN_REVIEW_REQUIRED]
        discrepancy_rate = len(discrepancies) / len(evaluable_retained) if evaluable_retained else None

        uar_withheld = [c for c in withheld if c.candidate_finding_id in [r.candidate_finding_id for r in retainable_ref]]
        uar_review = [c for c in review if c.candidate_finding_id in [r.candidate_finding_id for r in retainable_ref]]
        uar_total = (len(uar_withheld) + len(uar_review)) / len(evaluable_cands) if evaluable_cands else None
        uar_withheld_rate = len(uar_withheld) / len(evaluable_cands) if evaluable_cands else None
        uar_review_rate = len(uar_review) / len(evaluable_cands) if evaluable_cands else None

        sear_stale = [c for c in accepted if c.version_consistency_status == 'STALE']
        sear_unknown = [c for c in accepted if c.version_consistency_status == 'UNKNOWN']
        sear_stale_rate = len(sear_stale) / len(accepted) if accepted else None
        sear_unknown_rate = len(sear_unknown) / len(accepted) if accepted else None

        hrw_rate = len(review) / total

        print(f"  Total Candidates: {total}, Evaluable: {len(evaluable_cands)}, Unassessable: {len(unassessable_ids)}")
        print(f"  Actions: Accepted={len(accepted)} ({len(accepted)/total:.2%}), Withheld={len(withheld)}, Review={len(review)}")
        print(f"  UFC (Useful Coverage): {len(retained_useful)} / {len(retainable_ref)} = {ufc:.4f}" if ufc is not None else "  UFC: None")
        print(f"  UFR (Unsupported Rate): {len(unsupported)} / {len(evaluable_retained)} = {ufr:.4f}" if ufr is not None else "  UFR: None")
        print(f"  Safety Discrepancies (Review retained): {len(discrepancies)} / {len(evaluable_retained)} = {discrepancy_rate:.4f}" if discrepancy_rate is not None else "  Discrepancies: None")
        print(f"  UAR (Unnecessary Abstention): ({len(uar_withheld)} withheld + {len(uar_review)} review) / {len(evaluable_cands)} = {uar_total:.4f}" if uar_total is not None else "  UAR: None")
        print(f"  SEAR Stale: {len(sear_stale)} / {len(accepted)} = {sear_stale_rate:.4f}" if sear_stale_rate is not None else "  SEAR Stale: None")
        print(f"  SEAR Unknown: {len(sear_unknown)} / {len(accepted)} = {sear_unknown_rate:.4f}" if sear_unknown_rate is not None else "  SEAR Unknown: None")
        print(f"  HRW Rate: {len(review)} / {total} = {hrw_rate:.4f}")

        # Best matched baseline check
        eval_summary = evaluate_policy(
            policy_id="temp",
            candidates=cands,
            reference_annotations=refs,
            policy_decisions=acts,
        )
        best_tau, best_base_sum, match_res = find_best_matched_baseline(
            sweep_results=sweep,
            evid_summary=eval_summary,
            tolerance=0.02,
        )
        print(f"  Matched Baseline: tau={best_tau}, status={match_res.status}, tolerance={match_res.tolerance}")
        if match_res.status == "MATCHED_COVERAGE_ACHIEVED":
            print(f"    Coverage Diff: {match_res.coverage_difference:.4f}")
            print(f"    Baseline UFR: {match_res.policy_a_ufr:.4f}, Policy UFR: {match_res.policy_b_ufr:.4f}, Delta-UFR: {match_res.delta_ufr:.4f}")

        # Verification against saved summary
        saved_c = saved_summary[bench_name]['config_summaries'][name]
        assert saved_c['total_candidates'] == total
        assert saved_c['evaluable_candidates'] == len(evaluable_cands)
        assert saved_c['retained_count'] == len(accepted)
        assert round(saved_c['ufc'], 4) == round(ufc, 4)
        assert round(saved_c['ufr'], 4) == round(ufr, 4)
        assert round(saved_c['hrw_rate'], 4) == round(hrw_rate, 4)
        if sear_stale_rate is not None:
            assert round(saved_c['sear_stale_rate'], 4) == round(sear_stale_rate, 4)

        results[bench_name][name] = {
            "total": total,
            "evaluable": len(evaluable_cands),
            "unassessable": len(unassessable_ids),
            "accepted": len(accepted),
            "withheld": len(withheld),
            "review": len(review),
            "evaluable_retained": len(evaluable_retained),
            "retainable_ref": len(retainable_ref),
            "retained_useful": len(retained_useful),
            "unsupported": len(unsupported),
            "discrepancies": len(discrepancies),
            "ufc": ufc,
            "ufr": ufr,
            "uar_total": uar_total,
            "sear_stale": sear_stale_rate,
            "sear_unknown": sear_unknown_rate,
            "hrw": hrw_rate,
            "best_matched_tau": best_tau,
            "matching_status": match_res.status,
            "coverage_diff": match_res.coverage_difference,
            "delta_ufr": match_res.delta_ufr,
        }

print("\n" + "=" * 80)
print("ALL CALCULATIONS VERIFIED SUCCESSFULLY AGAINST RAW CANDIDATE RECORDS!")
print("=" * 80)
