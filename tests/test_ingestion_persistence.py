"""
Unit and integration test suite for Document Ingestion, OCR Fallback, and Relational Persistence (Task 030).
Covers all 18 requirements:
1. Successful TXT ingestion.
2. Successful DOCX ingestion.
3. Successful text-based PDF extraction.
4. Scanned-PDF OCR fallback when dependencies are available.
5. Clear failure when required OCR dependencies are unavailable.
6. Unsupported file formats.
7. Empty and malformed documents.
8. File-size and resource-limit enforcement.
9. SHA-256 checksum correctness.
10. Safe temporary-file cleanup.
11. Correct extraction metadata.
12. Correct preprocessing and segmentation integration.
13. Character-offset integrity where supported.
14. Database persistence and transaction rollback.
15. Foreign-key and relational-integrity checks.
16. Retry behavior and duplicate-ingestion protection.
17. Audit-event generation and tamper-evident hash chaining.
18. Preservation of existing research artifacts.
"""

import os
import io
import shutil
import tempfile
import hashlib
import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.config import IngestionConfig
from src.ingestion.schema import (
    DocumentFormat, ExtractionMethod, IngestionStatus,
    ValidationResult, ExtractionResult,
    ModelAgreementProvenanceRecord, ComponentType,
)
from src.ingestion.validator import DocumentValidator
from src.ingestion.storage import DocumentStorageManager
from src.ingestion.parsers.txt_parser import TxtParser
from src.ingestion.parsers.docx_parser import DocxParser
from src.ingestion.parsers.pdf_parser import PdfParser
from src.ingestion.parsers.ocr_engine import OcrEngine
from src.ingestion.pipeline import IngestionPipeline

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    DocumentRecord, ExtractedTextSnapshot, SegmentRecord, AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.audit.integrity import AuditVerifier
from src.audit.provenance import IntegrityStatus

# =========================================================================
# TEST FIXTURES
# =========================================================================

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="contractrisk_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def test_db_engine():
    # In-memory SQLite for isolated transactional testing
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def test_config(temp_dir):
    return IngestionConfig(
        storage_root=os.path.join(temp_dir, "storage"),
        temp_dir=os.path.join(temp_dir, "temp"),
        max_file_size_bytes=500_000,
        max_pages_pdf=20,
        min_chars_per_page_pdf=30,
        ocr_enabled=True
    )

@pytest.fixture
def test_pipeline(test_config, test_db_engine):
    return IngestionPipeline(config=test_config, db_engine=test_db_engine)

def create_synthetic_txt() -> bytes:
    return (
        "CONSULTING SERVICES AGREEMENT\n\n"
        "1. Services and Deliverables.\n"
        "The Consultant shall perform strategic advisory services as described in Exhibit A.\n\n"
        "2. Confidentiality.\n"
        "Each party agrees to preserve the confidentiality of all proprietary information disclosed hereunder.\n\n"
        "3. Governing Law.\n"
        "This Agreement shall be governed by and construed in accordance with the laws of India.\n"
    ).encode("utf-8")

def create_synthetic_docx() -> bytes:
    import docx
    doc = docx.Document()
    doc.add_heading("NON-DISCLOSURE AGREEMENT", level=0)
    doc.add_paragraph("1. Definition of Confidential Information. Confidential Information includes all technical data.")
    doc.add_paragraph("2. Non-Use and Non-Disclosure. The recipient agrees not to disclose proprietary data.")
    
    # Add a sample contract table
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Party A"
    table.cell(0, 1).text = "Alpha Enterprises Pvt Ltd"
    table.cell(1, 0).text = "Party B"
    table.cell(1, 1).text = "Beta Technologies Ltd"
    
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def create_synthetic_pdf(text: str = None, pages: int = 1) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    content = text or (
        "COMMERCIAL LEASE AGREEMENT\n\n"
        "1. Demised Premises. Landlord leases to Tenant the commercial property situated in Bengaluru.\n"
        "2. Rent. Tenant shall pay monthly rent in advance on or before the fifth day of each calendar month.\n"
        "3. Dispute Resolution. Any dispute shall be referred to arbitration in accordance with Indian law."
    )
    for p in range(pages):
        c.drawString(72, 700, f"Page {p+1} - Contract Document")
        y = 650
        for line in content.split("\n"):
            if line.strip():
                c.drawString(72, y, line)
                y -= 20
        c.showPage()
    c.save()
    return buf.getvalue()

def create_scanned_synthetic_pdf() -> bytes:
    """Creates a PDF with no text strings (pure empty pages/scanned representation)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Draw geometric rectangles without any font/text operators
    c.rect(50, 50, 500, 700, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()

# =========================================================================
# TESTS
# =========================================================================

def test_01_successful_txt_ingestion(test_pipeline):
    """1. Successful TXT ingestion."""
    txt_bytes = create_synthetic_txt()
    result = test_pipeline.ingest_document(txt_bytes, "consulting_agreement.txt")
    
    assert result.status == IngestionStatus.SEGMENTED
    assert result.validation.format == DocumentFormat.TXT
    assert result.extraction.extraction_method == ExtractionMethod.TXT_DECODER
    assert "Consulting Services Agreement" in result.extraction.raw_text.title()
    assert result.segment_count >= 3
    assert result.storage_path is not None
    assert os.path.exists(result.storage_path)

def test_02_successful_docx_ingestion(test_pipeline):
    """2. Successful DOCX ingestion."""
    docx_bytes = create_synthetic_docx()
    result = test_pipeline.ingest_document(docx_bytes, "nda_contract.docx")
    
    assert result.status == IngestionStatus.SEGMENTED
    assert result.validation.format == DocumentFormat.DOCX
    assert result.extraction.extraction_method == ExtractionMethod.DOCX_PARSER
    assert "Definition of Confidential Information" in result.extraction.raw_text
    assert "Alpha Enterprises Pvt Ltd" in result.extraction.raw_text
    assert result.segment_count >= 2

def test_03_successful_pdf_text_extraction(test_pipeline):
    """3. Successful text-based PDF extraction."""
    pdf_bytes = create_synthetic_pdf(pages=2)
    result = test_pipeline.ingest_document(pdf_bytes, "commercial_lease.pdf")
    
    assert result.status == IngestionStatus.SEGMENTED
    assert result.validation.format == DocumentFormat.PDF
    assert result.extraction.extraction_method == ExtractionMethod.TEXT_EXTRACTOR_PDF
    assert result.extraction.ocr_applied is False
    assert result.extraction.page_count == 2
    assert "Demised Premises" in result.extraction.raw_text
    assert result.segment_count >= 2

def test_04_scanned_pdf_ocr_fallback_when_available(test_pipeline):
    """4. Scanned-PDF OCR fallback when dependencies are available."""
    scanned_pdf = create_scanned_synthetic_pdf()
    
    # Mock OCR engine to simulate successful OCR extraction
    with patch.object(test_pipeline.ocr_engine, "check_availability", return_value=(True, None)):
        with patch.object(
            test_pipeline.ocr_engine,
            "extract_text_from_pdf_images",
            return_value=("1. Scanned Covenants. The parties agree to the scanned terms.", 1, ["OCR applied"], [])
        ):
            result = test_pipeline.ingest_document(scanned_pdf, "scanned_deed.pdf")
            
            assert result.status == IngestionStatus.SEGMENTED
            assert result.extraction.extraction_method == ExtractionMethod.OCR_FALLBACK_PDF
            assert result.extraction.ocr_applied is True
            assert "Scanned Covenants" in result.extraction.raw_text
            assert any("OCR" in w for w in result.warnings)

def test_05_clear_failure_when_ocr_dependencies_unavailable(test_pipeline):
    """5. Clear failure when required OCR dependencies are unavailable."""
    scanned_pdf = create_scanned_synthetic_pdf()
    
    # Simulate missing OCR engine
    with patch.object(
        test_pipeline.ocr_engine,
        "check_availability",
        return_value=(False, "OCR_DEPENDENCIES_UNAVAILABLE: Tesseract OCR engine executable not found on system PATH.")
    ):
        result = test_pipeline.ingest_document(scanned_pdf, "scanned_mortgage.pdf")
        
        assert result.status == IngestionStatus.FAILED
        assert any("OCR_DEPENDENCIES_UNAVAILABLE" in err for err in result.errors)
        assert result.segment_count == 0

def test_06_unsupported_file_formats(test_pipeline):
    """6. Unsupported file formats rejection."""
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
    result = test_pipeline.ingest_document(fake_exe, "malware.exe")
    
    assert result.status == IngestionStatus.FAILED
    assert result.validation.is_valid is False
    assert any("not permitted" in err or "Unsupported" in err for err in result.errors)

def test_07_empty_and_malformed_documents(test_pipeline):
    """7. Empty and malformed documents handling."""
    # 0-byte document
    res_empty = test_pipeline.ingest_document(b"", "empty.txt")
    assert res_empty.status == IngestionStatus.FAILED
    assert any("empty" in err.lower() for err in res_empty.errors)
    
    # Malformed PDF (corrupted header)
    corrupted_pdf = b"%PDF-1.4\nCorrupted binary payload without xref or trailer"
    res_corrupt = test_pipeline.ingest_document(corrupted_pdf, "corrupt.pdf")
    assert res_corrupt.status == IngestionStatus.FAILED

def test_08_file_size_and_resource_limits(test_pipeline):
    """8. File-size and resource-limit enforcement."""
    # Generate bytes exceeding the 500,000 byte limit configured in test_config
    oversized_bytes = b"Oversized contract payload text\n" * 20000  # ~640 KB
    assert len(oversized_bytes) > test_pipeline.config.max_file_size_bytes
    
    result = test_pipeline.ingest_document(oversized_bytes, "oversized.txt")
    assert result.status == IngestionStatus.FAILED
    assert any("exceeds configured limit" in err for err in result.errors)

def test_09_sha256_checksum_correctness(test_pipeline):
    """9. SHA-256 checksum correctness."""
    txt_bytes = create_synthetic_txt()
    expected_sha = hashlib.sha256(txt_bytes).hexdigest()
    
    result = test_pipeline.ingest_document(txt_bytes, "checksum_test.txt")
    assert result.validation.file_sha256 == expected_sha
    
    # Query database to confirm persisted checksum matches exactly
    factory = get_session_factory(test_pipeline.db_engine)
    with factory() as sess:
        repo = DocumentRepository(sess)
        doc = repo.get_document_by_id(result.document_id)
        assert doc is not None
        assert doc.file_sha256 == expected_sha

def test_10_safe_temporary_file_cleanup(test_config, temp_dir):
    """10. Safe temporary-file cleanup."""
    storage = DocumentStorageManager(test_config)
    temp_file = storage.create_temp_file()
    assert os.path.exists(temp_file)
    
    storage.cleanup_path(temp_file)
    assert not os.path.exists(temp_file)

def test_11_correct_extraction_metadata(test_pipeline):
    """11. Correct extraction metadata recording."""
    pdf_bytes = create_synthetic_pdf(pages=3)
    result = test_pipeline.ingest_document(pdf_bytes, "three_page_contract.pdf")
    
    assert result.extraction.page_count == 3
    assert result.extraction.char_count == len(result.extraction.raw_text)
    assert result.extraction.extraction_method == ExtractionMethod.TEXT_EXTRACTOR_PDF
    assert result.extraction.ocr_applied is False
    assert "avg_chars_per_page" in result.extraction.metadata

def test_12_preprocessing_and_segmentation_integration(test_pipeline):
    """12. Correct preprocessing and segmentation integration."""
    txt_bytes = create_synthetic_txt()
    result = test_pipeline.ingest_document(txt_bytes, "integration_agreement.txt")
    
    assert result.status == IngestionStatus.SEGMENTED
    assert result.dataset_record_id is not None
    assert result.preprocessed_status == "SUCCESS"
    assert result.segment_count >= 3
    
    # Verify segments in DB
    factory = get_session_factory(test_pipeline.db_engine)
    with factory() as sess:
        doc = sess.query(DocumentRecord).filter(DocumentRecord.id == result.document_id).first()
        assert len(doc.segments) == result.segment_count
        clause_types = [s.segment_type for s in doc.segments]
        assert any(t in ("CLAUSE", "SECTION_HEADING", "DOCUMENT_TITLE") for t in clause_types)

def test_13_character_offset_integrity(test_pipeline):
    """13. Character-offset integrity where supported."""
    txt_bytes = create_synthetic_txt()
    result = test_pipeline.ingest_document(txt_bytes, "offsets_test.txt")
    
    raw_text = result.extraction.raw_text
    factory = get_session_factory(test_pipeline.db_engine)
    with factory() as sess:
        doc = sess.query(DocumentRecord).filter(DocumentRecord.id == result.document_id).first()
        for seg in doc.segments:
            # Sliced substring from raw text using segment coordinates must match segment text
            span_from_source = raw_text[seg.original_start:seg.original_end]
            assert span_from_source == seg.text, (
                f"Offset mismatch for segment {seg.segment_id}: "
                f"expected '{seg.text}', got '{span_from_source}'"
            )

def test_14_database_persistence_and_transaction_rollback(test_pipeline):
    """14. Database persistence and transaction rollback."""
    txt_bytes = create_synthetic_txt()
    
    # Ingest document successfully
    res = test_pipeline.ingest_document(txt_bytes, "commit_test.txt")
    assert res.status == IngestionStatus.SEGMENTED
    
    # Verify transaction rollback on error
    factory = get_session_factory(test_pipeline.db_engine)
    with pytest.raises(Exception):
        with factory() as sess:
            repo = DocumentRepository(sess)
            repo.update_document_status(res.document_id, IngestionStatus.FAILED)
            # Force an integrity error by violating primary key unique constraint
            duplicate_doc = DocumentRecord(
                id=res.document_id,
                file_sha256="dummy_sha",
                original_filename="dup.txt",
                sanitized_filename="dup.txt",
                mime_type="text/plain",
                document_format="TXT",
                file_size_bytes=100,
                storage_path="/tmp/dup"
            )
            sess.add(duplicate_doc)
            sess.flush()
            
    # Check that previous status was NOT changed due to transaction rollback
    with factory() as sess:
        repo = DocumentRepository(sess)
        doc = repo.get_document_by_id(res.document_id)
        assert doc.status == IngestionStatus.SEGMENTED.value

def test_15_foreign_key_and_relational_integrity(test_pipeline):
    """15. Foreign-key and relational-integrity checks."""
    docx_bytes = create_synthetic_docx()
    res = test_pipeline.ingest_document(docx_bytes, "relational_test.docx")
    
    factory = get_session_factory(test_pipeline.db_engine)
    with factory() as sess:
        doc = sess.query(DocumentRecord).filter(DocumentRecord.id == res.document_id).first()
        assert doc is not None
        assert len(doc.text_snapshots) == 1
        assert len(doc.segments) >= 2
        assert len(doc.audit_events) >= 3
        
        # Verify FK links
        snapshot = doc.text_snapshots[0]
        assert snapshot.document_id == doc.id
        for seg in doc.segments:
            assert seg.document_id == doc.id

def test_16_retry_behavior_and_duplicate_protection(test_pipeline):
    """16. Retry behavior and duplicate-ingestion protection."""
    txt_bytes = create_synthetic_txt()
    
    # First ingestion
    res1 = test_pipeline.ingest_document(txt_bytes, "agreement_v1.txt")
    assert res1.status == IngestionStatus.SEGMENTED
    
    # Duplicate retry with exact same bytes
    res2 = test_pipeline.ingest_document(txt_bytes, "agreement_v1_retry.txt")
    assert res2.status == IngestionStatus.SEGMENTED
    assert res2.document_id == res1.document_id
    assert any("Duplicate" in w for w in res2.warnings)
    
    # Confirm no duplicate rows in database
    factory = get_session_factory(test_pipeline.db_engine)
    with factory() as sess:
        docs = sess.query(DocumentRecord).filter(DocumentRecord.file_sha256 == res1.validation.file_sha256).all()
        assert len(docs) == 1

def test_17_audit_event_generation_and_hash_chain(test_pipeline):
    """17. Audit-event generation and tamper-evident hash chaining."""
    txt_bytes = create_synthetic_txt()
    res = test_pipeline.ingest_document(txt_bytes, "audited_agreement.txt")
    
    # Verify events were captured in audit store
    events = test_pipeline.audit_store.get_all()
    assert len(events) >= 3
    
    event_types = [e.event_type.value for e in events]
    assert "DOCUMENT_INGESTED" in event_types
    assert "PREPROCESSING_COMPLETED" in event_types
    assert "CLAUSE_SEGMENTED" in event_types
    
    # Verify cryptographic hash chain integrity using AuditVerifier
    verifier = AuditVerifier()
    status, err = verifier.verify(test_pipeline.audit_store)
    assert status == IntegrityStatus.VALID
    assert err is None

def test_18_preservation_of_existing_research_artifacts():
    """18. Preservation of existing research artifacts."""
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # 1. Model weights file
    weights_path = os.path.join(
        workspace_root, "results", "models", "ledgar_frozen_subset_fresh", "final_model", "model.safetensors"
    )
    assert os.path.exists(weights_path), f"Physical model weights missing: {weights_path}"
    assert os.path.getsize(weights_path) == 476_116_436
    
    # Verify SHA-256 matches exact historical checksum
    h = hashlib.sha256()
    with open(weights_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    assert h.hexdigest() == "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"
    
    # 2. Academic PDF report
    pdf_path = os.path.join(workspace_root, "results", "task025", "CONTRACTRISK_XAI_ACADEMIC_REPORT.pdf")
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1_000_000


# =============================================================================
# STRATEGY A (STEP 5): MODEL AGREEMENT PROVENANCE INGESTION HOOK TESTS
# =============================================================================

def test_ingest_with_valid_model_agreement_provenance(test_pipeline):
    """
    Ingestion hook: When valid model-agreement provenance is supplied,
    it is validated via DocumentValidator, persisted safely in the audit
    event payload and DatasetRecord metadata, and returned in IngestionResult.
    """
    txt_bytes = create_synthetic_txt()
    prov_data = {
        "document_id": "DOE-GOODS-2022-GCC",
        "template_family_id": "MACRO-FAM-DOE-PPD",
        "issuing_agency": "Procurement Policy Division, Department of Expenditure, Ministry of Finance",
        "source_pdf_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        "source_page_range": (15, 68),
        "component_type": "GCC",
        "source_manual_title": "Manual for Procurement of Goods 2022",
    }

    res = test_pipeline.ingest_document(
        txt_bytes,
        "valid_provenance_doc.txt",
        model_agreement_provenance=prov_data,
    )

    assert res.status == IngestionStatus.SEGMENTED
    assert res.model_agreement_provenance is not None
    assert isinstance(res.model_agreement_provenance, ModelAgreementProvenanceRecord)
    assert res.model_agreement_provenance.document_id == "DOE-GOODS-2022-GCC"
    assert res.model_agreement_provenance.template_family_id == "MACRO-FAM-DOE-PPD"
    assert res.model_agreement_provenance.component_type == ComponentType.GCC

    # Verify audit event captures the provenance metadata in its event payload
    events = test_pipeline.audit_store.get_all()
    ingest_events = [e for e in events if e.event_type.value == "DOCUMENT_INGESTED" and e.source_document_id == res.document_id]
    assert len(ingest_events) == 1
    audit_evt = ingest_events[0]
    assert "model_agreement_provenance" in audit_evt.event_payload
    saved_prov = audit_evt.event_payload["model_agreement_provenance"]
    assert saved_prov["template_family_id"] == "MACRO-FAM-DOE-PPD"
    assert saved_prov["document_id"] == "DOE-GOODS-2022-GCC"


def test_ingest_with_invalid_model_agreement_provenance_rejected(test_pipeline):
    """
    Ingestion hook: When invalid model-agreement provenance metadata is supplied,
    it is rejected with IngestionStatus.FAILED and clear error descriptions.
    """
    txt_bytes = create_synthetic_txt()
    # Invalid: empty issuing_agency and inverted page range
    invalid_prov = {
        "document_id": "DOE-GOODS-2022-GCC",
        "template_family_id": "MACRO-FAM-DOE-PPD",
        "issuing_agency": "   ",  # Fails min_length / non-empty
        "source_pdf_sha256": "not-a-valid-sha256",  # Invalid sha256 format
        "source_page_range": (80, 20),  # Inverted range
        "component_type": "GCC",
    }

    res = test_pipeline.ingest_document(
        txt_bytes,
        "invalid_prov_doc.txt",
        model_agreement_provenance=invalid_prov,
    )

    assert res.status == IngestionStatus.FAILED
    assert len(res.errors) >= 1
    assert any("Invalid model_agreement_provenance" in err for err in res.errors)


def test_ingest_omitted_model_agreement_provenance_preserves_compatibility(test_pipeline):
    """
    Ingestion hook: When model-agreement provenance is omitted (None),
    existing behavior is preserved without error for all existing callers.
    """
    txt_bytes = create_synthetic_txt()
    res = test_pipeline.ingest_document(txt_bytes, "omitted_prov_doc.txt", model_agreement_provenance=None)

    assert res.status == IngestionStatus.SEGMENTED
    assert res.model_agreement_provenance is None
    assert len(res.errors) == 0

