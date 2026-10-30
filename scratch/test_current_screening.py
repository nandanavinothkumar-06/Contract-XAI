import sys
sys.path.insert(0, '.')
import json

from src.review.screening import ContractScreeningService

svc = ContractScreeningService()

clauses = [
    ("Governing Law", "This Agreement shall be governed by the laws of India. The courts of New Delhi shall have exclusive jurisdiction."),
    ("Indemnification", "The Contractor shall indemnify and hold harmless the Client against third-party claims, liabilities, damages, and reasonable expenses."),
    ("Limitation of Liability", "Neither party shall be liable for indirect or consequential damages, except where otherwise provided in this Agreement."),
    ("Confidentiality", "Each party shall protect confidential information received from the other party and shall not disclose it without authorization.")
]

print("=== TESTING SCREEN_CLAUSE BEHAVIOR ===")
for title, text in clauses:
    res = svc.screen_clause(
        clause_text=text,
        clause_id=f"seg_{title.lower().replace(' ', '_')}",
        document_id="doc_test_1",
        document_version=1
    )
    print(f"\n[{title}]")
    print(f"  Risk Label: {res['risk_label']}")
    print(f"  Score: {res['ai_confidence_score']}")
    print(f"  Policy Action: {res['policy_action']}")
    print(f"  Policy Reason: {res['policy_reason_code']}")
    attr = json.loads(res['model_attribution_json']) if res['model_attribution_json'] else None
    print(f"  Has Attribution: {attr is not None} (Spans: {len(attr['attributed_spans']) if attr else 0})")
    print(f"  Evidence Quality: {res['evidence_quality_status']}")
