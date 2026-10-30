import sys
sys.path.insert(0, '.')
import json
from src.persistence.database import get_db_session
from src.persistence.models import ReviewRecord, DocumentRecord, SegmentRecord, ClauseFindingRecord

with get_db_session() as sess:
    rev = sess.query(ReviewRecord).filter_by(id='28976229-2dff-434a-9c9e-6449399f4a78').first()
    print('Review:', rev.id, rev.status, rev.document_id, rev.created_at, rev.updated_at)
    doc = sess.query(DocumentRecord).filter_by(id=rev.document_id).first()
    print('Doc:', doc.id, doc.original_filename, doc.created_at)
    
    segs = sess.query(SegmentRecord).filter_by(document_id=doc.id).order_by(SegmentRecord.sequence).all()
    print(f'Segments for doc {doc.id} ({len(segs)}):')
    for s in segs:
        print(f'  Seg UUID: {s.id}, Seg ID: {s.segment_id}, Seq: {s.sequence}, Text: {repr(s.text[:80])}')

    findings = sess.query(ClauseFindingRecord).filter_by(review_id=rev.id).all()
    print(f'\nFindings for review {rev.id} ({len(findings)}):')
    for f in findings:
        seg = sess.query(SegmentRecord).filter_by(document_id=doc.id, segment_id=f.segment_id).first()
        print(f'\nFinding: {f.id}')
        print(f'  Created at: {f.created_at}, Updated at: {f.updated_at}')
        print(f'  Segment ID: {f.segment_id}')
        print(f'  Segment text: {repr(seg.text) if seg else None}')
        print(f'  Risk label: {f.risk_label}')
        print(f'  Score: {f.ai_confidence_score}')
        print(f'  AI Observation: {f.ai_observation.encode("ascii", "replace").decode()}')
        if f.ai_metadata_json:
            meta = json.loads(f.ai_metadata_json)
            print(f'  Metadata: raw_model_label={meta.get("raw_model_label")}, raw_confidence={meta.get("raw_confidence")}, policy_action={meta.get("policy_action")}')
