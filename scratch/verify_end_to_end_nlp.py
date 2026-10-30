"""
Verification Script for CONTRACTRISK-XAI Core NLP Workflow.
Executes the actual workflow using the user's exact synthetic contract.
"""

import os
import json
import logging
from src.persistence.database import init_db, get_db_session
from src.persistence.models import (
    UserRecord, DocumentRecord, SegmentRecord, ReviewRecord,
    ClauseFindingRecord, FindingOrigin
)
from src.ingestion.pipeline import IngestionPipeline
from src.review.service import ReviewService
from src.review.screening import get_contract_screening_service

def run_verification():
    init_db()
    
    contract_text = """MASTER SERVICES AGREEMENT

1. Governing Law:
This Agreement shall be governed by the laws of India. The courts of
New Delhi shall have exclusive jurisdiction.

2. Indemnification:
The Contractor shall indemnify and hold harmless the Client against
third-party claims, liabilities, damages, and reasonable expenses.

3. Limitation of Liability:
Neither party shall be liable for indirect or consequential damages,
except where otherwise provided in this Agreement.

4. Confidentiality:
Each party shall protect confidential information received from the
other party and shall not disclose it without authorization."""

    with get_db_session() as session:
        user = session.query(UserRecord).filter_by(email="advocate@legal.in").first()
        if not user:
            user = session.query(UserRecord).first()
        print(f"Executing as user: {user.email} (Role: {user.role})")

        # Step 1: Ingestion (Upload, Extraction, Preprocessing, Segmentation)
        pipeline = IngestionPipeline()
        ingest_res = pipeline.ingest_document(
            file_bytes=contract_text.encode("utf-8"),
            original_filename="synthetic_msa_verification.txt",
            owner_id=user.id,
            session=session
        )
        doc_id = ingest_res.document_id
        print(f"Ingestion complete: Doc ID={doc_id}, Segments count={ingest_res.segment_count}")

        # Step 2: Review Initiation
        review_svc = ReviewService(session)
        review = review_svc.initiate_review(doc_id, actor_user=user)
        print(f"Review initiated: Review ID={review.id}, Status={review.status}")

        # Step 3: Real NLP Screening
        screening_svc = get_contract_screening_service()
        screening_result = screening_svc.screen_review(review.id, session=session)
        session.commit()
        print(f"Screening complete: Segments screened={screening_result['segments_screened']}, Findings={screening_result['findings_count']}")

        # Step 4: Verification of Persisted Findings and Exact Outputs
        findings = session.query(ClauseFindingRecord).filter_by(review_id=review.id).all()
        doc = session.query(DocumentRecord).filter_by(id=doc_id).first()
        segments = session.query(SegmentRecord).filter_by(document_id=doc_id).order_by(SegmentRecord.sequence).all()

        print("\n======================= VERIFICATION AUDIT =======================")
        print(f"Total Segments in DB: {len(segments)}")
        print(f"Total Clause Findings in DB: {len(findings)}")

        total_explanation_spans = 0
        total_statutory_passages = 0
        decisions_summary = []

        for seg in segments:
            print(f"\n--- Segment {seg.sequence}: [{seg.segment_id}] ---")
            print(f"Text Snippet: {repr(seg.text[:70])}...")
            print(f"Character Offsets: ({seg.original_start}, {seg.original_end})")
            
            # Find associated finding
            finding = next((f for f in findings if f.segment_id == seg.segment_id), None)
            if not finding:
                print("No finding generated (e.g. short heading/title)")
                continue

            print(f"Finding ID: {finding.id}")
            print(f"Origin: {finding.finding_origin}")
            print(f"Predicted Risk Label: {finding.risk_label}")
            print(f"AI Confidence Score: {finding.ai_confidence_score}")
            print(f"Client Disclosed: {finding.is_disclosed_to_client}")

            # Verify AI Metadata & Preserved Model Label
            meta = json.loads(finding.ai_metadata_json)
            print(f"Raw Model Label: {meta.get('raw_model_label')} (Index: {meta.get('raw_model_index')})")
            print(f"Model Name: {meta.get('model_name')}")
            print(f"Calibrated Threshold: {meta.get('calibrated_threshold')}")
            print(f"Policy Action: {meta.get('policy_action')}")
            print(f"Policy Reason: {meta.get('policy_reason_code')}")
            decisions_summary.append({
                "segment_id": seg.segment_id,
                "label": finding.risk_label,
                "score": finding.ai_confidence_score,
                "action": meta.get("policy_action"),
                "reason": meta.get("policy_reason_code")
            })

            # Verify Gradient x Input Attribution
            if finding.model_attribution_json:
                attr = json.loads(finding.model_attribution_json)
                spans = attr.get("attributed_spans", [])
                total_explanation_spans += len(spans)
                print(f"Explainability Method: {attr.get('method')}")
                print(f"Attributed Spans Count: {len(spans)}")
                for sp in spans:
                    # Verify offset match against clause text
                    s_text = sp.get("text")
                    s_start = sp.get("source_start")
                    s_end = sp.get("source_end")
                    exact_substr = seg.text[s_start:s_end]
                    match_exact = (s_text in seg.text)
                    print(f"  Span: '{s_text}' (score: {sp.get('raw_score'):.4f}, offsets: {s_start}-{s_end}) -> In clause: {match_exact}")

            # Verify Statutory Evidence (BM25)
            if finding.statutory_evidence_json:
                ev = json.loads(finding.statutory_evidence_json)
                passages = ev.get("passages", [])
                total_statutory_passages += len(passages)
                print(f"Statutory Evidence Quality: {finding.evidence_quality_status}")
                print(f"Retrieved Passages: {len(passages)}")
                for p in passages:
                    print(f"  Statute: {p.get('source_act')}, Sec {p.get('section_number')}, Score: {p.get('ranking_score')} ({p.get('retrieval_method')})")

        print("\n======================= SUMMARY TOTALS =======================")
        print(f"Segments Processed: {len(segments)}")
        print(f"Predictions Produced: {len(findings)}")
        print(f"Explanation Spans Generated: {total_explanation_spans}")
        print(f"Statutory Passages Retrieved: {total_statutory_passages}")
        print(f"Findings Persisted: {len(findings)}")
        print("Decisions:")
        for d in decisions_summary:
            print(f"  - {d['label']}: Score={d['score']}, Action={d['action']}, Reason={d['reason']}")

if __name__ == "__main__":
    run_verification()
