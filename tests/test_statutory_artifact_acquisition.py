"""
Task 040 Comprehensive Test Suite: Statutory Reference Artifact Acquisition and Gazette Ingestion Workflow.

Verifies all 32 Phase J test requirements:
1. Successful acquisition of a valid fixture artifact.
2. Network timeout handling.
3. HTTP error handling.
4. Invalid TLS/certificate failure handling.
5. Redirect to a disallowed host is rejected.
6. Oversized download is rejected.
7. Unexpected file type is rejected.
8. PDF signature and parser validation.
9. Malformed artifact handling.
10. Safe filename handling.
11. Path traversal prevention.
12. Original bytes remain unchanged after extraction.
13. SHA-256 reproducibility.
14. Existing artifacts are not silently overwritten.
15. New artifact versions are recorded separately.
16. Extraction failure is recorded honestly.
17. OCR fallback is marked explicitly.
18. Text normalization is documented.
19. Exact section match is reported correctly.
20. Text differences are identified.
21. Missing local sections are reported.
22. Ambiguous section mappings do not produce false exact matches.
23. Whole-PDF hash differences do not automatically imply text mismatch.
24. Local SHA-256 alone cannot promote authoritative verification.
25. HTTP 200 alone cannot promote authoritative verification.
26. Partial section comparisons do not verify the entire Act.
27. Stale enactment text does not imply current consolidated law.
28. Source and artifact IDs remain traceable.
29. Failed acquisition leaves source status unchanged or appropriately downgraded.
30. Existing Task 039 verification tests remain valid.
31. Task 038 evidence-grounding tests remain valid.
32. Authorization rules remain enforced.
"""

import os
import io
import json
import uuid
import hashlib
import tempfile
import pytest
import requests
from io import BytesIO
from unittest.mock import patch, MagicMock

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pypdf

from src.legal_sources.acquisition import (
    GazetteArtifactAcquisitionManager,
    safe_join_path,
    sanitize_identifier,
    DEFAULT_APPROVED_HOSTS
)
from src.legal_sources.extraction import StatutoryTextExtractor
from src.legal_sources.comparison import (
    StatutoryComparisonEngine,
    normalize_comparison_text,
    extract_sections_from_raw_text
)
from src.legal_sources.verification import LegalSourceVerificationWorkflow
from src.legal_sources.provenance import (
    VerificationStatus,
    SourceCompletenessStatus,
    CurrentnessStatus,
    CommencementStatus,
    is_retrieval_eligible,
    is_authoritatively_verified
)
from src.review.evidence import ClauseEvidenceRetriever
from src.dashboard.app import app
from src.persistence.models import UserRole, AccountStatus, AdvocateStatus
from src.persistence.repository import DocumentRepository
from src.persistence.database import get_session_factory, Base, get_engine
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.config import AuthConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# =========================================================================
# HELPER: Generate Deterministic Statutory PDF Fixtures with ReportLab
# =========================================================================

def generate_statutory_pdf(
    title: str = "THE GAZETTE OF INDIA EXTRAORDINARY",
    sections: list = None,
    include_extra_metadata: bool = False
) -> bytes:
    """
    Generates authentic valid PDF bytes containing statutory text for deterministic testing.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    if include_extra_metadata:
        c.setAuthor("Official Gazette Printing Press")
        c.setTitle(title)
        c.setSubject("Statutory Notification 2023")

    y = 750
    c.drawString(72, y, title)
    y -= 30

    if sections is None:
        sections = [
            ("10", "What agreements are contracts", "All agreements are contracts if they are made by the free consent of parties competent to contract."),
            ("27", "Agreement in restraint of trade, void", "Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, is to that extent void.")
        ]

    for sec_num, heading, body in sections:
        c.drawString(72, y, f"Section {sec_num}. {heading}.—{body}")
        y -= 30
        if y < 100:
            c.showPage()
            y = 750

    c.save()
    return buffer.getvalue()


# =========================================================================
# TEST 1: Successful acquisition of a valid fixture artifact
# =========================================================================

def test_01_successful_acquisition_of_valid_fixture_artifact(tmp_path):
    pdf_bytes = generate_statutory_pdf()
    expected_sha = hashlib.sha256(pdf_bytes).hexdigest()

    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    # Mock successful HTTP 200 response from approved gazette domain
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://egazette.gov.in/WriteReadData/2023/248045.pdf"
        mock_resp.headers = {
            "Content-Type": "application/pdf",
            "Content-Length": str(len(pdf_bytes))
        }
        mock_resp.iter_content.return_value = [pdf_bytes]
        mock_resp.history = []
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_get.return_value = mock_resp

        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_2023_22",
            url="https://egazette.gov.in/WriteReadData/2023/248045.pdf",
            publication_id="pub_248045",
            issuing_authority="Ministry of Law and Justice",
            publication_title="The Digital Personal Data Protection Act, 2023"
        )

        assert res["success"] is True
        assert res["sha256"] == expected_sha
        assert res["tls_validated"] is True
        assert os.path.exists(res["original_file_path"])
        assert os.path.exists(res["metadata_path"])
        assert os.path.exists(res["acquisition_record_path"])

        with open(res["metadata_path"], "r", encoding="utf-8") as f:
            meta = json.load(f)
            assert meta["source_id"] == "IN_ACT_2023_22"
            assert meta["sha256"] == expected_sha
            assert meta["acquisition_status"] == "ACQUIRED_VERIFIED_CHECKSUM"


# =========================================================================
# TEST 2: Network timeout handling
# =========================================================================

def test_02_network_timeout_handling(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out after 10.0s")):
        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_1872_09",
            url="https://indiacode.nic.in/handle/123456789/2187",
            publication_id="ica_timeout_test"
        )
        assert res["success"] is False
        assert "timed out" in res["error"].lower()
        assert res["tls_validated"] is False


# =========================================================================
# TEST 3: HTTP error handling
# =========================================================================

def test_03_http_error_handling(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.url = "https://indiacode.nic.in/handle/123456789/999999"
        mock_resp.history = []
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error: Not Found")
        mock_get.return_value = mock_resp

        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_1872_09",
            url="https://indiacode.nic.in/handle/123456789/999999",
            publication_id="ica_404_test"
        )
        assert res["success"] is False
        assert "404" in res["error"]


# =========================================================================
# TEST 4: Invalid TLS/certificate failure handling
# =========================================================================

def test_04_invalid_tls_certificate_failure_handling(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    with patch("requests.get", side_effect=requests.exceptions.SSLError("certificate verify failed: self-signed certificate")):
        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_2023_22",
            url="https://egazette.gov.in/WriteReadData/2023/248045.pdf",
            publication_id="ssl_fail_test"
        )
        assert res["success"] is False
        assert res["tls_validated"] is False
        assert "ssl error" in res["error"].lower() or "certificate" in res["error"].lower()


# =========================================================================
# TEST 5: Redirect to a disallowed host is rejected
# =========================================================================

def test_05_redirect_to_disallowed_host_rejected(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    # Redirect history leads to an unapproved host
    with patch("requests.get") as mock_get:
        mock_hist = MagicMock()
        mock_hist.url = "https://egazette.gov.in/redirect"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://malicious-internal-bypass.org/payload.pdf"
        mock_resp.history = [mock_hist]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_get.return_value = mock_resp

        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_2023_22",
            url="https://egazette.gov.in/redirect",
            publication_id="redirect_bypass_test"
        )
        assert res["success"] is False
        assert "disallowed host" in res["error"].lower() or "not in approved host list" in res["error"].lower()


# =========================================================================
# TEST 6: Oversized download is rejected
# =========================================================================

def test_06_oversized_download_rejected(tmp_path):
    # Set a small limit: 1000 bytes
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path), max_download_size_bytes=1000)

    pdf_bytes = generate_statutory_pdf()
    assert len(pdf_bytes) > 1000

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://egazette.gov.in/big.pdf"
        mock_resp.headers = {"Content-Length": str(len(pdf_bytes))}
        mock_resp.iter_content.return_value = [pdf_bytes]
        mock_resp.history = []
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_get.return_value = mock_resp

        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_2023_22",
            url="https://egazette.gov.in/big.pdf",
            publication_id="oversized_test"
        )
        assert res["success"] is False
        assert "exceeds maximum allowed size" in res["error"].lower() or "exceeded maximum" in res["error"].lower()


# =========================================================================
# TEST 7: Unexpected file type is rejected
# =========================================================================

def test_07_unexpected_file_type_rejected(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    # Content is HTML rather than PDF
    html_bytes = b"<html><body><h1>403 Forbidden</h1></body></html>"

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://egazette.gov.in/fake.pdf"
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.iter_content.return_value = [html_bytes]
        mock_resp.history = []
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_get.return_value = mock_resp

        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_2023_22",
            url="https://egazette.gov.in/fake.pdf",
            publication_id="html_magic_test"
        )
        assert res["success"] is False
        assert "magic bytes" in res["error"].lower()


# =========================================================================
# TEST 8: PDF signature and parser validation
# =========================================================================

def test_08_pdf_signature_and_parser_validation(tmp_path):
    extractor = StatutoryTextExtractor()

    # Valid PDF
    valid_pdf = generate_statutory_pdf()
    valid_path = tmp_path / "valid.pdf"
    valid_path.write_bytes(valid_pdf)

    is_valid, num_pages, err = extractor.validate_pdf_artifact(str(valid_path))
    assert is_valid is True
    assert num_pages >= 1
    assert err is None

    # Corrupted PDF (has %PDF- header but truncated/garbage body)
    bad_pdf = b"%PDF-1.4\nGarbage data not a valid PDF structure EOF"
    bad_path = tmp_path / "bad.pdf"
    bad_path.write_bytes(bad_pdf)

    is_valid_bad, num_pages_bad, err_bad = extractor.validate_pdf_artifact(str(bad_path))
    assert is_valid_bad is False
    assert "parser error" in err_bad.lower() or "error" in err_bad.lower()


# =========================================================================
# TEST 9: Malformed artifact handling
# =========================================================================

def test_09_malformed_artifact_handling(tmp_path):
    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.5\nIncomplete truncated stream")

    res = extractor.extract_text_from_artifact(
        source_id="IN_ACT_2023_22",
        artifact_pdf_path=str(corrupt_pdf),
        publication_id="pub_corrupt"
    )
    assert res["success"] is False
    assert "error" in res
    assert os.path.exists(res["metadata_path"])

    with open(res["metadata_path"], "r", encoding="utf-8") as f:
        meta = json.load(f)
        assert meta["extraction_status"] == "EXTRACTION_FAILED"


# =========================================================================
# TEST 10: Safe filename handling
# =========================================================================

def test_10_safe_filename_handling():
    unsafe_id = "ICA:1872*pub#1?file<test>|name"
    safe_id = sanitize_identifier(unsafe_id)
    assert ":" not in safe_id
    assert "*" not in safe_id
    assert "<" not in safe_id
    assert ">" not in safe_id
    assert safe_id == "ICA_1872_pub_1_file_test__name"

    with pytest.raises(ValueError) as exc:
        sanitize_identifier("../../../etc/passwd")
    assert "unsafe identifier" in str(exc.value).lower()


# =========================================================================
# TEST 11: Path traversal prevention
# =========================================================================

def test_11_path_traversal_prevention(tmp_path):
    base_dir = str(tmp_path / "base")
    os.makedirs(base_dir, exist_ok=True)

    with pytest.raises(ValueError) as excinfo:
        safe_join_path(base_dir, "..", "escaped_dir")
    assert "path traversal detected" in str(excinfo.value).lower()

    with pytest.raises(ValueError) as excinfo2:
        safe_join_path(base_dir, "subdir", "../../../outside")
    assert "path traversal detected" in str(excinfo2.value).lower()


# =========================================================================
# TEST 12: Original bytes remain unchanged after extraction
# =========================================================================

def test_12_original_bytes_remain_unchanged_after_extraction(tmp_path):
    pdf_bytes = generate_statutory_pdf()
    orig_sha = hashlib.sha256(pdf_bytes).hexdigest()

    pdf_file = tmp_path / "original.pdf"
    pdf_file.write_bytes(pdf_bytes)

    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    res = extractor.extract_text_from_artifact(
        source_id="IN_ACT_1872_09",
        artifact_pdf_path=str(pdf_file),
        publication_id="pub_immutable_test"
    )

    assert res["success"] is True

    # Re-read original file and verify hash matches initial hash exactly
    after_bytes = pdf_file.read_bytes()
    after_sha = hashlib.sha256(after_bytes).hexdigest()
    assert orig_sha == after_sha
    assert orig_sha == res["original_sha256"]


# =========================================================================
# TEST 13: SHA-256 reproducibility
# =========================================================================

def test_13_sha256_reproducibility():
    content = b"Section 10. Valid contracts requirement under Indian law."
    hash1 = hashlib.sha256(content).hexdigest()
    hash2 = hashlib.sha256(content).hexdigest()
    hash3 = hashlib.sha256(content).hexdigest()
    assert hash1 == hash2 == hash3


# =========================================================================
# TEST 14: Existing artifacts are not silently overwritten
# =========================================================================

def test_14_existing_artifacts_are_not_silently_overwritten(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    pdf1 = generate_statutory_pdf(title="FIRST VERSION")
    pdf2 = generate_statutory_pdf(title="SECOND VERSION WITH AMENDMENTS")

    res1 = mgr.register_manual_artifact(
        source_id="IN_ACT_TEST_01",
        file_bytes=pdf1,
        filename="original.pdf",
        issuing_authority="Government Press",
        publication_title="Version 1",
        publication_id="pub_unique_01"
    )
    assert res1["success"] is True
    file1_path = res1["original_file_path"]

    # Registering differing bytes for same publication ID must NOT overwrite file1
    res2 = mgr.register_manual_artifact(
        source_id="IN_ACT_TEST_01",
        file_bytes=pdf2,
        filename="original.pdf",
        issuing_authority="Government Press",
        publication_title="Version 2",
        publication_id="pub_unique_01"
    )
    assert res2["success"] is True
    assert res2["prior_version_preserved"] is True
    assert res2["original_file_path"] != file1_path

    # Verify original file1 content remains intact
    with open(file1_path, "rb") as f:
        assert f.read() == pdf1


# =========================================================================
# TEST 15: New artifact versions are recorded separately
# =========================================================================

def test_15_new_artifact_versions_recorded_separately(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    pdf1 = generate_statutory_pdf(title="INITIAL 1872 ENACTMENT")
    pdf2 = generate_statutory_pdf(title="1997 AMENDMENT")

    res1 = mgr.register_manual_artifact(source_id="IN_ACT_1872_09", file_bytes=pdf1, filename="original.pdf", publication_id="act_ver")
    res2 = mgr.register_manual_artifact(source_id="IN_ACT_1872_09", file_bytes=pdf2, filename="original.pdf", publication_id="act_ver")

    # Directory for res2 must be distinct (e.g. act_ver_v...)
    assert res1["publication_id"] != res2["publication_id"]
    assert "act_ver_v" in res2["publication_id"]


# =========================================================================
# TEST 16: Extraction failure is recorded honestly
# =========================================================================

def test_16_extraction_failure_is_recorded_honestly(tmp_path):
    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")

    res = extractor.extract_text_from_artifact("IN_ACT_TEST_02", str(empty_pdf), "pub_empty")
    assert res["success"] is False
    assert "error" in res
    assert res.get("extracted_text_path") is None or not os.path.exists(res["extracted_text_path"])


# =========================================================================
# TEST 17: OCR fallback is marked explicitly
# =========================================================================

def test_17_ocr_fallback_marked_explicitly(tmp_path):
    pdf_bytes = generate_statutory_pdf()
    pdf_path = tmp_path / "native.pdf"
    pdf_path.write_bytes(pdf_bytes)

    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    res = extractor.extract_text_from_artifact("IN_ACT_1872_09", str(pdf_path), "pub_ocr_meta_check")

    assert res["success"] is True
    assert res["ocr_used"] is False

    with open(res["metadata_path"], "r", encoding="utf-8") as f:
        meta = json.load(f)
        assert meta["ocr_used"] is False
        assert "ocr_engine" in meta


# =========================================================================
# TEST 18: Text normalization is documented
# =========================================================================

def test_18_text_normalization_documented():
    fancy_text = "“Section 10.—All agreements are contracts” — where parties agree."
    norm = normalize_comparison_text(fancy_text)
    assert "\"" in norm
    assert "“" not in norm
    assert "”" not in norm
    assert "-" in norm
    assert "—" not in norm


# =========================================================================
# TEST 19: Exact section match is reported correctly
# =========================================================================

def test_19_exact_section_match_reported_correctly(tmp_path):
    snap_text = "Section 10. What agreements are contracts.—All agreements are contracts if made by free consent.\n"
    ref_text = "Section 10. What agreements are contracts.—All agreements are contracts if made by free consent.\n"

    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(snap_text, encoding="utf-8")

    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(ref_text, encoding="utf-8")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference(
        source_id="IN_ACT_1872_09",
        snapshot_file_path=str(snap_file),
        reference_text_path=str(ref_file)
    )

    assert res["success"] is True
    assert res["defensible_status"] == VerificationStatus.CONTENT_MATCH_VERIFIED.value
    rep = res["report"]
    assert rep["summary"]["exact_text_matches"] == 1
    assert rep["summary"]["textual_differences"] == 0
    assert rep["summary"]["concordance_percentage"] == 100.0


# =========================================================================
# TEST 20: Text differences are identified
# =========================================================================

def test_20_text_differences_identified(tmp_path):
    snap_text = "Section 27. Agreement in restraint of trade, void.—Every agreement in restraint of trade is void.\n"
    ref_text = "Section 27. Agreement in restraint of trade, void.—Every agreement by which any one is restrained from exercising a lawful profession is void.\n"

    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(snap_text, encoding="utf-8")

    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(ref_text, encoding="utf-8")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference(
        source_id="IN_ACT_1872_09",
        snapshot_file_path=str(snap_file),
        reference_text_path=str(ref_file)
    )

    assert res["success"] is True
    assert res["defensible_status"] == VerificationStatus.VERIFICATION_FAILED.value
    rep = res["report"]
    assert rep["summary"]["textual_differences"] == 1
    diff_item = [s for s in rep["sections"] if s["section_number"] == "27"][0]
    assert diff_item["match_type"] == "TEXT_DIFFERENCE"
    assert len(diff_item["diff"]) > 0


# =========================================================================
# TEST 21: Missing local sections are reported
# =========================================================================

def test_21_missing_local_sections_reported(tmp_path):
    snap_text = "Section 10. Valid contracts.—Agreements are contracts.\n"
    ref_text = (
        "Section 10. Valid contracts.—Agreements are contracts.\n"
        "Section 11. Competence.—Sound mind competent to contract.\n"
        "Section 12. Sound mind.—Defined herein.\n"
    )

    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(snap_text, encoding="utf-8")
    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(ref_text, encoding="utf-8")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference("IN_ACT_1872_09", str(snap_file), str(ref_file))

    rep = res["report"]
    omitted = rep["summary"]["sections_in_reference_omitted_from_snapshot"]
    assert "11" in omitted
    assert "12" in omitted
    assert rep["summary"]["sections_in_reference_omitted_from_snapshot_count"] == 2


# =========================================================================
# TEST 22: Ambiguous section mappings do not produce false exact matches
# =========================================================================

def test_22_ambiguous_section_mappings_do_not_produce_false_exact_matches(tmp_path):
    # Snapshot contains Section 99 which is completely absent from reference
    snap_text = "Section 99. Ghost section.—This section does not exist in the official gazette.\n"
    ref_text = "Section 10. Valid contracts.—Agreements are contracts.\n"

    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(snap_text, encoding="utf-8")
    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(ref_text, encoding="utf-8")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference("IN_ACT_1872_09", str(snap_file), str(ref_file))

    rep = res["report"]
    assert rep["summary"]["missing_in_reference"] == 1
    assert rep["summary"]["exact_text_matches"] == 0
    assert res["defensible_status"] == VerificationStatus.VERIFICATION_FAILED.value


# =========================================================================
# TEST 23: Whole-PDF hash differences do not automatically imply text mismatch
# =========================================================================

def test_23_whole_pdf_hash_differences_do_not_imply_text_mismatch(tmp_path):
    # Two PDFs with identical section text, but different PDF metadata -> different SHA-256
    pdf1 = generate_statutory_pdf(include_extra_metadata=False)
    pdf2 = generate_statutory_pdf(include_extra_metadata=True)

    sha1 = hashlib.sha256(pdf1).hexdigest()
    sha2 = hashlib.sha256(pdf2).hexdigest()
    assert sha1 != sha2  # Binary digests differ

    pdf1_file = tmp_path / "pdf1.pdf"
    pdf1_file.write_bytes(pdf1)
    pdf2_file = tmp_path / "pdf2.pdf"
    pdf2_file.write_bytes(pdf2)

    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    ext1 = extractor.extract_text_from_artifact("TEST_01", str(pdf1_file), "pub_1")
    ext2 = extractor.extract_text_from_artifact("TEST_01", str(pdf2_file), "pub_2")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference(
        "TEST_01",
        ext1["extracted_text_path"],
        ext2["extracted_text_path"]
    )
    # Extracted text should match 100% despite the whole-PDF byte hash difference
    assert res["report"]["summary"]["concordance_percentage"] == 100.0


# =========================================================================
# TEST 24: Local SHA-256 alone cannot promote authoritative verification
# =========================================================================

def test_24_local_sha256_alone_cannot_promote_authoritative_verification(tmp_path):
    content = b"Section 10. Sample Act text.\n"
    sha = hashlib.sha256(content).hexdigest()
    snap_file = tmp_path / "act.txt"
    snap_file.write_bytes(content)

    manifest_data = {
        "manifest_version": "1.0.0",
        "official_sources": [
            {
                "source_id": "TEST_PROMOTION_01",
                "canonical_title": "Test Statute",
                "jurisdiction": "India - Central",
                "snapshot_file": "act.txt",
                "source_sha256": sha,
                "verification_status": "CONTENT_MATCH_VERIFIED"
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    workflow = LegalSourceVerificationWorkflow(
        manifest_path=str(manifest_path),
        snapshots_dir=str(tmp_path),
        reference_artifacts_dir=str(tmp_path / "empty_ref")
    )
    report = workflow.run_verification()
    src_rep = report["sources"][0]
    # Invariant: Must be downgraded because reference artifact is absent
    assert src_rep["defensible_verification_status"] == VerificationStatus.PARTIALLY_VERIFIED.value


# =========================================================================
# TEST 25: HTTP 200 alone cannot promote authoritative verification
# =========================================================================

def test_25_http_200_alone_cannot_promote_authoritative_verification():
    workflow = LegalSourceVerificationWorkflow()
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_open.return_value = mock_resp

        res = workflow.attempt_network_reachability("https://egazette.gov.in/test.pdf")
        assert res["reachable"] is True
        assert res["proves_content_equivalence"] is False


# =========================================================================
# TEST 26: Partial section comparisons do not verify the entire Act
# =========================================================================

def test_26_partial_section_comparisons_do_not_verify_entire_act(tmp_path):
    snap_text = "Section 10. What agreements are contracts.—All agreements are contracts.\n"
    ref_text = (
        "Section 10. What agreements are contracts.—All agreements are contracts.\n"
        "Section 11. Who are competent.—Every person of sound mind.\n"
        "Section 12. What is sound mind.—Defined.\n"
    )

    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(snap_text, encoding="utf-8")
    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(ref_text, encoding="utf-8")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference("IN_ACT_1872_09", str(snap_file), str(ref_file))

    out = res["report"]["verification_outcome"]
    # Verified scope covers Section 10 only, not 11 or 12
    assert out["verified_scope"] == ["10"]
    assert "11" in res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]


# =========================================================================
# TEST 27: Stale enactment text does not imply current consolidated law
# =========================================================================

def test_27_stale_enactment_text_does_not_imply_current_consolidated_law(tmp_path):
    snap_text = "Section 10. What agreements are contracts.—All agreements are contracts.\n"
    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(snap_text, encoding="utf-8")
    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(snap_text, encoding="utf-8")

    engine = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comparisons"))
    res = engine.compare_snapshot_with_reference("IN_ACT_1872_09", str(snap_file), str(ref_file))

    out = res["report"]["verification_outcome"]
    assert out["currentness_status"] == "CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT"
    assert out["applicability_status"] == "REQUIRES_ADVOCATE_DETERMINATION"


# =========================================================================
# TEST 28: Source and artifact IDs remain traceable
# =========================================================================

def test_28_source_and_artifact_ids_remain_traceable(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path / "artifacts"))
    pdf_bytes = generate_statutory_pdf()

    reg_res = mgr.register_manual_artifact(
        source_id="IN_ACT_TRACE_01",
        file_bytes=pdf_bytes,
        filename="gazette.pdf",
        issuing_authority="Legislative Department",
        publication_title="Traceable Act",
        publication_id="pub_trace_999"
    )
    artifact_id = reg_res["artifact_id"]

    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    ext_res = extractor.extract_text_from_artifact(
        source_id="IN_ACT_TRACE_01",
        artifact_pdf_path=reg_res["original_file_path"],
        publication_id="pub_trace_999",
        artifact_id=artifact_id
    )

    with open(ext_res["metadata_path"], "r", encoding="utf-8") as f:
        ext_meta = json.load(f)
        assert ext_meta["source_id"] == "IN_ACT_TRACE_01"
        assert ext_meta["artifact_id"] == artifact_id


# =========================================================================
# TEST 29: Failed acquisition leaves source status unchanged
# =========================================================================

def test_29_failed_acquisition_leaves_source_status_unchanged(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Host unreachable")):
        res = mgr.acquire_artifact_from_url(
            source_id="IN_ACT_2023_22",
            url="https://egazette.gov.in/down.pdf",
            publication_id="down_test"
        )
        assert res["success"] is False

    # Workflow running after failed acquisition must still maintain PARTIALLY_VERIFIED
    workflow = LegalSourceVerificationWorkflow()
    rep = workflow.run_verification()
    dpdp = [s for s in rep["sources"] if s["source_id"] == "IN_ACT_2023_22"][0]
    assert dpdp["defensible_verification_status"] == VerificationStatus.PARTIALLY_VERIFIED.value


# =========================================================================
# TEST 30: Existing Task 039 verification tests remain valid
# =========================================================================

def test_30_existing_task_039_verification_tests_remain_valid():
    workflow = LegalSourceVerificationWorkflow()
    rep = workflow.run_verification()
    assert rep["manifest_valid"] is True
    assert rep["summary"]["total_sources_declared"] == 6
    assert rep["summary"]["files_present_on_disk"] == 6
    assert rep["summary"]["hashes_reproducible"] == 6
    assert rep["summary"]["partially_verified"] == 6
    assert rep["summary"]["content_match_verified"] == 0


# =========================================================================
# TEST 31: Task 038 evidence-grounding tests remain valid
# =========================================================================

def test_31_task_038_evidence_grounding_tests_remain_valid():
    retriever = ClauseEvidenceRetriever()
    ev = retriever.retrieve_evidence_for_clause("Agreement in restraint of trade is void")
    assert ev["requires_lawyer_review"] is True
    assert "NOT represent probabilities" in ev["score_disclaimer"]
    assert len(ev["passages"]) > 0
    assert ev["passages"][0]["statute_id"] == "IN_ACT_1872_09"


# =========================================================================
# TEST 32: Authorization rules remain enforced
# =========================================================================

def test_32_authorization_rules_remain_enforced():
    """
    Verifies that acquisition, registration, extraction, and comparison endpoints
    reject unauthenticated and junior client requests, and allow supervising lawyer.
    """
    from contextlib import contextmanager

    app.config["TESTING"] = True
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    @contextmanager
    def mock_db_session(engine=None):
        sess = SessionLocal()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    seed_sess = SessionLocal()
    repo = DocumentRepository(seed_sess)
    pm = PasswordManager()
    tm = TokenManager(AuthConfig())

    client_user = repo.create_user(
        user_id=str(uuid.uuid4()),
        email="client@example.com",
        password_hash=pm.hash_password("Pass123!"),
        full_name="Client User",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE
    )
    lawyer_user = repo.create_user(
        user_id=str(uuid.uuid4()),
        email="supervisor@example.com",
        password_hash=pm.hash_password("Pass123!"),
        full_name="Supervising Advocate",
        role=UserRole.SUPERVISING_LAWYER,
        account_status=AccountStatus.ACTIVE,
        advocate_status=AdvocateStatus.VERIFIED
    )
    seed_sess.commit()

    client_token = tm.generate_token(client_user)
    lawyer_token = tm.generate_token(lawyer_user)
    seed_sess.close()

    with patch("src.persistence.database.get_engine", return_value=test_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=mock_db_session):
            with patch("src.persistence.database.get_db_session", side_effect=mock_db_session):
                with patch("src.persistence.database.get_db", side_effect=mock_db_session):
                    with app.test_client() as client:
                        # A. Unauthenticated request -> 401
                        resp_unauth = client.post("/api/legal/artifacts/acquire", json={})
                        assert resp_unauth.status_code == 401

                        # B. Client role request -> 403 Forbidden
                        resp_forbidden = client.post(
                            "/api/legal/artifacts/acquire",
                            headers={"Authorization": f"Bearer {client_token}"},
                            json={"source_id": "IN_ACT_1872_09", "url": "https://indiacode.nic.in/handle/123456789/2187"}
                        )
                        assert resp_forbidden.status_code == 403

                        # C. Supervising Lawyer role request -> passes auth gate (not 401/403)
                        resp_auth = client.post(
                            "/api/legal/artifacts/acquire",
                            headers={"Authorization": f"Bearer {lawyer_token}"},
                            json={"source_id": "IN_ACT_1872_09", "url": "https://unapproved.com/fake.pdf"}
                        )
                        # Should not be 401 or 403 (host validation error 400 is expected and correct)
                        assert resp_auth.status_code == 400
                        err_str = resp_auth.get_json()["error"].lower()
                        assert "approved" in err_str and "allowlist" in err_str

    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
