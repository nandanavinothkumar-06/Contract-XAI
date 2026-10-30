import pytest
from src.adapters.schema import DatasetRecord, TaskType, EvidenceSpan
from src.preprocessing.pipeline import PreprocessingPipeline
from src.segmentation.pipeline import SegmentationPipeline

def test_evidence_overlap():
    text = (
        "1. Confidentiality\n\n"
        "The Receiving Party shall protect Confidential Information.\n\n"
        "2. Termination\n\n"
        "Either party may terminate."
    )
    
    ev1 = EvidenceSpan(start=text.find("The Receiving Party"), end=text.find("Information.") + len("Information."), text="The Receiving Party shall protect Confidential Information.", source_field="text")
    
    rec = DatasetRecord.model_construct(
        record_id="1", source_dataset="TEST", source_document_id="doc1", contract_id=None, clause_id=None,
        text=text, task=TaskType.QA_SPAN_EXTRACTION, original_label="Label", normalized_label=None,
        evidence=[ev1], rationale=None, domain=None, language=None, annotation_source=None, source_reference=None,
        license_status=None, access_status=None, metadata={"is_test_fixture": True}
    )
    p_rec = PreprocessingPipeline().preprocess_record(rec)
    
    doc = SegmentationPipeline().segment_record(p_rec)
    
    assert len(doc.evidence_associations) == 1
    # Evidence 1 falls in segment 0 (clause 1.)
    assert doc.segments[0].segment_id in doc.evidence_associations[0].overlapping_segment_ids

def test_coverage_calculation():
    text = "   \n\n1. First clause.\n\n    \n\n2. Second clause.  \n"
    # full text length is 54
    # The segments should cover the non-whitespace blocks.
    rec = DatasetRecord.model_construct(
        record_id="1", source_dataset="TEST", source_document_id="doc1", contract_id=None, clause_id=None,
        text=text, task=TaskType.QA_SPAN_EXTRACTION, original_label="Label", normalized_label=None,
        evidence=[], rationale=None, domain=None, language=None, annotation_source=None, source_reference=None,
        license_status=None, access_status=None, metadata={"is_test_fixture": True}
    )
    p_rec = PreprocessingPipeline().preprocess_record(rec)
    doc = SegmentationPipeline().segment_record(p_rec)
    
    # 54 total length.
    # Segment 1: "1. First clause." -> 16 chars
    # Segment 2: "2. Second clause." -> 17 chars
    # Total covered: 33 chars.
    # 33 / 54 = 0.61 > 0.5. No LOW_COVERAGE flag.
    assert "LOW_COVERAGE" not in doc.quality_flags
