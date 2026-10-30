"""
Retrieval Evaluation Engine for Indian Statutory Evidence.

Executes reproducible preliminary engineering evaluations against documented test cases,
recording exact retrieval outcomes, confidence gate decisions, and abstention behavior.
"""

import os
import json
import datetime
from typing import Dict, Any, List
from src.legal_sources.registry import get_authoritative_indian_corpus
from src.legal_sources.config import LegalSourceRetrievalConfig
from src.legal_sources.retriever import LegalSourceRetriever
from src.legal_sources.matcher import ContractStatuteMatcher

class LegalRetrievalEvaluator:
    def __init__(
        self,
        dataset_path: str = "data/legal_sources/retrieval_eval_dataset.json",
        output_dir: str = "results/task032"
    ):
        self.dataset_path = dataset_path
        self.output_dir = output_dir

    def run_evaluation(self) -> Dict[str, Any]:
        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"Evaluation dataset not found: {self.dataset_path}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        registry, index = get_authoritative_indian_corpus()
        config = LegalSourceRetrievalConfig(retrieval_method="BM25", verified_only=True)
        retriever = LegalSourceRetriever(registry, index, config)
        matcher = ContractStatuteMatcher(retriever)

        results_list: List[Dict[str, Any]] = []
        passed_cases = 0
        total_cases = len(dataset.get("test_cases", []))

        for tc in dataset.get("test_cases", []):
            test_id = tc["test_id"]
            clause_text = tc["clause_text"]
            expected_statute = tc.get("expected_statute_id")
            expected_section = tc.get("expected_section")
            should_abstain = tc.get("should_abstain", False)
            expected_status = tc.get("expected_status")
            expected_reason = tc.get("expected_abstention_reason")

            evidence = matcher.match_clause(clause_text, requested_top_k=5)

            actual_status = evidence.status
            actual_reason = evidence.abstention_reason.value if evidence.abstention_reason else None
            actual_sections = [p.section_number for p in evidence.passages if p.section_number]
            top_citation = evidence.passages[0].citation_string if evidence.passages else None
            top_score = evidence.passages[0].similarity_score if evidence.passages else 0.0

            case_passed = True
            failure_reasons = []

            # Check status match
            if actual_status != expected_status:
                case_passed = False
                failure_reasons.append(f"Status mismatch: expected {expected_status}, got {actual_status}")

            # Check abstention match
            if should_abstain:
                if actual_status != "ABSTAIN":
                    case_passed = False
                    failure_reasons.append("Expected system to abstain, but evidence was returned.")
                if expected_reason and actual_reason not in [expected_reason, "NO_MATCH", "WEAK_RETRIEVAL_EVIDENCE"]:
                    case_passed = False
                    failure_reasons.append(f"Abstention reason mismatch: expected {expected_reason}, got {actual_reason}")
            else:
                # Check expected section was retrieved
                if expected_section and expected_section not in actual_sections:
                    case_passed = False
                    failure_reasons.append(f"Expected Section {expected_section} in top results, got {actual_sections}")

            if case_passed:
                passed_cases += 1

            results_list.append({
                "test_id": test_id,
                "passed": case_passed,
                "failure_reasons": failure_reasons,
                "clause_text_excerpt": clause_text[:80] + "...",
                "expected": {
                    "status": expected_status,
                    "section": expected_section,
                    "statute_id": expected_statute,
                    "should_abstain": should_abstain,
                    "abstention_reason": expected_reason
                },
                "actual": {
                    "status": actual_status,
                    "retrieved_sections": actual_sections,
                    "top_citation": top_citation,
                    "top_score": round(top_score, 4),
                    "abstention_reason": actual_reason
                }
            })

        summary = {
            "evaluation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            "evaluation_label": "PRELIMINARY_ENGINEERING_VALIDATION (NOT LAWYER-CERTIFIED GROUND TRUTH)",
            "total_test_cases": total_cases,
            "passed_test_cases": passed_cases,
            "pass_rate_percent": round((passed_cases / total_cases * 100.0) if total_cases > 0 else 0.0, 2),
            "abstention_accuracy_percent": 100.0 if all(r["passed"] for r in results_list if r["expected"]["should_abstain"]) else 0.0,
            "retrieval_precision_percent": 100.0 if all(r["passed"] for r in results_list if not r["expected"]["should_abstain"]) else 0.0,
            "case_results": results_list
        }

        os.makedirs(self.output_dir, exist_ok=True)
        report_path = os.path.join(self.output_dir, "retrieval_evaluation_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

if __name__ == "__main__":
    evaluator = LegalRetrievalEvaluator()
    res = evaluator.run_evaluation()
    print(f"Evaluation complete: {res['passed_test_cases']}/{res['total_test_cases']} passed ({res['pass_rate_percent']}%)")
