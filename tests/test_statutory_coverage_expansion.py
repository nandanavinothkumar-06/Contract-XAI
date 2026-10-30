"""
Task 041 Test Suite: Statutory Coverage Expansion, Artifact Ingestion,
Text Extraction, Granular Comparison, and Epistemic Invariant Verification.

Verifies:
1. Acquisition & Registration:
   - Approved-host allowlist enforcement and SSRF / unsafe redirect blocking.
   - Air-gapped manual registration with provenance persistence.
   - Version collision branching preventing silent overwrites.
   - Format validation, magic bytes (%PDF-), oversized payload rejection, and path traversal defense.
2. Digital Text Extraction:
   - Native pypdf extraction, page and character count recording.
   - Detection of empty/malformed documents and preservation of extraction warnings.
   - Explicit tracking of extraction method (native vs OCR fallback).
3. Structural Section Comparison:
   - Verbatim exact matches, normalized matches, genuine text differences (unified diffs).
   - Detection of sections present in reference artifact but omitted from snapshot.
   - Preservation of existing Task 040/040A comparison scopes (ICA and DPDP).
   - Independent reproducibility of stored comparison reports across all four remaining sources.
4. Epistemic Invariants & Defensible Status:
   - Curated snapshot sections matching reference cannot upgrade entire statute to VERIFIED_OFFICIAL.
   - Partial section concordance yields PARTIALLY_VERIFIED.
   - 100% section concordance yields CONTENT_MATCH_VERIFIED scoped strictly to the curated extract.
   - Checksum matching alone does NOT prove official authenticity or currentness.
   - Currentness remains CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT.
   - Legal applicability remains strictly REQUIRES_ADVOCATE_DETERMINATION.
5. Coverage Reporting:
   - Corpus coverage calculated dynamically from actual ground truth records (5.91%, 40/677 sections).
   - Category A-F boundaries, omitted central sections, state amendments, and case law exclusions disclosed.
6. RBAC & Security:
   - SUPERVISING_LAWYER role enforcement on artifact endpoints; rejection of CLIENT/LAWYER/AUDITOR.
"""

import os
import re
import json
import hashlib
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from src.legal_sources.acquisition import (
    GazetteArtifactAcquisitionManager,
    DEFAULT_APPROVED_HOSTS,
    safe_join_path,
    sanitize_identifier,
)
from src.legal_sources.extraction import StatutoryTextExtractor
from src.legal_sources.comparison import (
    StatutoryComparisonEngine,
    normalize_comparison_text,
    extract_sections_from_raw_text,
)
from src.legal_sources.verification import LegalSourceVerificationWorkflow
from src.legal_sources.coverage import (
    LegalCoverageModel,
    STATUTORY_CORPUS_GROUND_TRUTH,
)
from src.legal_sources.provenance import (
    VerificationStatus,
    SourceCompletenessStatus,
    CurrentnessStatus,
    CommencementStatus,
)


def _render_test_pdf(title: str, sections: list) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    c.drawString(72, y, "THE GAZETTE OF INDIA")
    y -= 25
    c.drawString(72, y, title)
    y -= 30
    for sec_num, heading, body in sections:
        c.drawString(72, y, f"Section {sec_num}. {heading}.—")
        y -= 18
        for word in body.split():
            c.drawString(84, y, word)
            y -= 14
            if y < 72:
                c.showPage()
                y = 750
        y -= 15
        if y < 72:
            c.showPage()
            y = 750
    c.save()
    return buffer.getvalue()


# ============================================================================
# 1. ACQUISITION AND REGISTRATION TESTS
# ============================================================================

def test_01_manual_registration_persists_full_provenance(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))
    pdf_bytes = _render_test_pdf("TEST ACT 2026", [("1", "Short title", "This Act may be called Test Act 2026.")])
    
    reg = mgr.register_manual_artifact(
        source_id="IN_ACT_2000_21",
        file_bytes=pdf_bytes,
        filename="original.pdf",
        publication_id="test_pub_001",
        issuing_authority="Ministry of Electronics and Information Technology",
        publication_title="Test IT Act Official Reference",
        publication_date="2000-06-09",
        source_url="https://www.indiacode.nic.in/handle/123456789/1999",
        advocate_reviewer_notes="Verified by senior advocate audit"
    )

    assert reg["success"] is True
    assert reg["acquisition_status"] == "MANUAL_REGISTERED_VERIFIED_CHECKSUM"
    assert reg["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert os.path.exists(reg["artifact_path"])
    assert os.path.exists(reg["metadata_path"])

    with open(reg["metadata_path"], "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["source_id"] == "IN_ACT_2000_21"
    assert meta["issuing_authority"] == "Ministry of Electronics and Information Technology"
    assert meta["verification_notes"] == "Verified by senior advocate audit"


def test_02_version_collision_branching_prevents_silent_overwrites(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))
    pdf1 = _render_test_pdf("ACT V1", [("1", "Title", "Version 1")])
    pdf2 = _render_test_pdf("ACT V2", [("1", "Title", "Version 2")])

    reg1 = mgr.register_manual_artifact(
        source_id="IN_ACT_1963_47",
        file_bytes=pdf1,
        filename="original.pdf",
        publication_id="pub_sra_01"
    )
    reg2 = mgr.register_manual_artifact(
        source_id="IN_ACT_1963_47",
        file_bytes=pdf2,
        filename="original.pdf",
        publication_id="pub_sra_01"
    )

    assert reg1["artifact_path"] != reg2["artifact_path"]
    assert os.path.exists(reg1["artifact_path"])
    assert os.path.exists(reg2["artifact_path"])
    with open(reg1["artifact_path"], "rb") as f:
        assert f.read() == pdf1
    with open(reg2["artifact_path"], "rb") as f:
        assert f.read() == pdf2


def test_03_invalid_file_signature_rejected(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path))
    fake_bytes = b"This is plain text pretending to be a PDF"
    res = mgr.register_manual_artifact(
        source_id="IN_ACT_1996_26",
        file_bytes=fake_bytes,
        filename="fake.pdf",
        publication_id="pub_bad_sig"
    )
    assert res["success"] is False
    assert "Format signature check failed" in res["error"]


def test_04_oversized_payload_rejected(tmp_path):
    mgr = GazetteArtifactAcquisitionManager(base_storage_dir=str(tmp_path), max_download_size_bytes=1000)
    pdf_bytes = _render_test_pdf("BIG ACT", [("1", "Title", "A" * 1500)])
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
            source_id="IN_ACT_2023_47",
            url="https://egazette.gov.in/big.pdf",
            publication_id="oversized_test"
        )
        assert res["success"] is False
        assert "exceeds maximum allowed size" in res["error"].lower() or "exceeded maximum" in res["error"].lower()


def test_05_path_traversal_sanitization():
    with pytest.raises(ValueError, match="Invalid or unsafe identifier"):
        sanitize_identifier("../../etc/passwd")
    with pytest.raises(ValueError, match="Invalid or unsafe identifier"):
        sanitize_identifier("IN_ACT_2000_21/../../sneaky")
    with pytest.raises(ValueError, match="Path traversal detected"):
        safe_join_path("data/legal_sources", "../../etc/passwd")


def test_06_online_disallowed_hosts_and_ip_checks():
    mgr = GazetteArtifactAcquisitionManager()
    is_safe, msg = mgr.is_url_allowed("https://malicious-unofficial-statute.com/act.pdf")
    assert is_safe is False
    assert "not in approved" in msg.lower()

    is_safe, msg = mgr.is_url_allowed("http://192.168.1.1/internal_gazette.pdf")
    assert is_safe is False

    is_safe, msg = mgr.is_url_allowed("https://www.indiacode.nic.in/handle/123456789/1999")
    assert is_safe is True


# ============================================================================
# 2. DIGITAL TEXT EXTRACTION TESTS
# ============================================================================

def test_07_native_pdf_text_extraction(tmp_path):
    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    pdf_bytes = _render_test_pdf("IT ACT EXTRACT", [
        ("4", "Legal recognition of electronic records", "Where any law provides that information shall be in writing...")
    ])
    pdf_path = tmp_path / "test_it.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    res = extractor.extract_from_artifact(
        artifact_path=str(pdf_path),
        source_id="IN_ACT_2000_21",
        publication_id="pub_extract_01"
    )

    assert res["success"] is True
    assert res["ocr_used"] is False
    assert res["page_count"] >= 1
    assert res["char_count"] > 20
    assert os.path.exists(res["extracted_text_path"])
    with open(res["extracted_text_path"], "r", encoding="utf-8") as f:
        txt = f.read()
    assert "Section 4. Legal recognition of electronic records" in txt


def test_08_empty_and_corrupt_documents_fail_safely(tmp_path):
    extractor = StatutoryTextExtractor(base_extracted_dir=str(tmp_path / "extracted"))
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    res = extractor.extract_from_artifact(
        artifact_path=str(empty_file),
        source_id="IN_ACT_1963_47",
        publication_id="pub_empty"
    )
    assert res["success"] is False
    assert "empty" in res["error"].lower() or "not found" in res["error"].lower()


# ============================================================================
# 3. STATUTORY COMPARISON ENGINE TESTS
# ============================================================================

def test_09_exact_and_normalized_match_detection():
    t1 = "Section 10. What agreements are contracts.—All agreements are contracts if they are made by free consent."
    t2 = "Section 10. What agreements are contracts.- All agreements are contracts if they are made by free consent."
    assert normalize_comparison_text(t1) == normalize_comparison_text(t2)


def test_10_genuine_text_difference_with_diff_generation(tmp_path):
    comparator = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comp"))
    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(
        "Section 10. Specific performance in respect of contracts.—The specific performance of a contract shall be enforced.\n"
        "[Note: Substituted by the Specific Relief (Amendment) Act, 2018 (Act 18 of 2018), w.e.f. 1-10-2018.]",
        encoding="utf-8"
    )
    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(
        "Section 10. Specific performance in respect of contracts.—The specific performance of a contract shall be enforced.",
        encoding="utf-8"
    )

    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_1963_47",
        snapshot_file_path=str(snap_file),
        reference_text_path=str(ref_file)
    )

    assert res["report"]["summary"]["concordance_percentage"] == 0.0
    assert res["report"]["summary"]["textual_differences"] == 1
    assert res["defensible_status"] == VerificationStatus.VERIFICATION_FAILED.value
    diff_lines = res["report"]["sections"][0]["diff"]
    assert any("[Note: Substituted by" in line for line in diff_lines)


def test_11_detection_of_omitted_central_sections(tmp_path):
    comparator = StatutoryComparisonEngine(base_comparisons_dir=str(tmp_path / "comp"))
    snap_file = tmp_path / "snap.txt"
    snap_file.write_text(
        "Section 7. Arbitration agreement.—In this Part, arbitration agreement means an agreement.\n\n"
        "Section 8. Power to refer parties to arbitration.—A judicial authority shall refer.",
        encoding="utf-8"
    )
    ref_file = tmp_path / "ref.txt"
    ref_file.write_text(
        "Section 2. Definitions.—In this Part, unless the context otherwise requires...\n\n"
        "Section 7. Arbitration agreement.—In this Part, arbitration agreement means an agreement.\n\n"
        "Section 8. Power to refer parties to arbitration.—A judicial authority shall refer.\n\n"
        "Section 11. Appointment of arbitrators.—A person of any nationality may be an arbitrator.",
        encoding="utf-8"
    )

    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_1996_26",
        snapshot_file_path=str(snap_file),
        reference_text_path=str(ref_file)
    )

    assert res["report"]["summary"]["concordance_percentage"] == 100.0
    assert res["report"]["summary"]["sections_in_reference_omitted_from_snapshot_count"] == 2
    assert "2" in res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]
    assert "11" in res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]
    assert res["defensible_status"] == VerificationStatus.CONTENT_MATCH_VERIFIED.value


# ============================================================================
# 4. REPRODUCIBILITY OF ALL FOUR REMAINING STATUTES + PRESERVATION OF PRIOR SCOPES
# ============================================================================

def test_12_reproducibility_of_it_act_comparison():
    comparator = StatutoryComparisonEngine()
    snap_path = "data/legal_sources/snapshots/IN_ACT_2000_21.txt"
    ref_path = "data/legal_sources/extracted_text/IN_ACT_2000_21/indiacode_2000_1999/extracted.txt"
    assert os.path.exists(snap_path)
    assert os.path.exists(ref_path)

    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_2000_21",
        snapshot_file_path=snap_path,
        reference_text_path=ref_path
    )
    assert res["report"]["summary"]["sections_in_snapshot"] == 6
    assert res["report"]["summary"]["concordance_percentage"] == 66.67
    assert res["defensible_status"] == VerificationStatus.PARTIALLY_VERIFIED.value
    # Sections 1, 4, 10A, 72A matched
    assert set(res["report"]["verification_outcome"]["verified_scope"]) == {"1", "4", "10A", "72A"}
    # Sections 43A and 66A contain editorial researcher notes and differ
    assert set(res["report"]["verification_outcome"]["unverified_scope"]) == {"43A", "66A"}
    # Omitted central sections identified
    assert set(res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]) == {"2", "85"}


def test_13_reproducibility_of_specific_relief_act_comparison():
    comparator = StatutoryComparisonEngine()
    snap_path = "data/legal_sources/snapshots/IN_ACT_1963_47.txt"
    ref_path = "data/legal_sources/extracted_text/IN_ACT_1963_47/indiacode_1963_1583/extracted.txt"
    assert os.path.exists(snap_path)
    assert os.path.exists(ref_path)

    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_1963_47",
        snapshot_file_path=snap_path,
        reference_text_path=ref_path
    )
    assert res["report"]["summary"]["sections_in_snapshot"] == 6
    assert res["report"]["summary"]["concordance_percentage"] == 83.33
    assert res["defensible_status"] == VerificationStatus.PARTIALLY_VERIFIED.value
    # Sections 1, 14, 14A, 16, 20A matched
    assert set(res["report"]["verification_outcome"]["verified_scope"]) == {"1", "14", "14A", "16", "20A"}
    # Section 10 contains 2018 amendment editorial note and differs
    assert set(res["report"]["verification_outcome"]["unverified_scope"]) == {"10"}
    # Omitted central sections identified
    assert set(res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]) == {"2", "20B"}


def test_14_reproducibility_of_arbitration_act_comparison():
    comparator = StatutoryComparisonEngine()
    snap_path = "data/legal_sources/snapshots/IN_ACT_1996_26.txt"
    ref_path = "data/legal_sources/extracted_text/IN_ACT_1996_26/indiacode_1996_1978/extracted.txt"
    assert os.path.exists(snap_path)
    assert os.path.exists(ref_path)

    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_1996_26",
        snapshot_file_path=snap_path,
        reference_text_path=ref_path
    )
    assert res["report"]["summary"]["sections_in_snapshot"] == 6
    assert res["report"]["summary"]["concordance_percentage"] == 100.0
    assert res["defensible_status"] == VerificationStatus.CONTENT_MATCH_VERIFIED.value
    # All 6 curated sections match official enactment text
    assert set(res["report"]["verification_outcome"]["verified_scope"]) == {"1", "7", "8", "9", "16", "34"}
    assert len(res["report"]["verification_outcome"]["unverified_scope"]) == 0
    # Omitted central sections identified
    assert set(res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]) == {"2", "11"}


def test_15_reproducibility_of_bsa_comparison():
    comparator = StatutoryComparisonEngine()
    snap_path = "data/legal_sources/snapshots/IN_ACT_2023_47.txt"
    ref_path = "data/legal_sources/extracted_text/IN_ACT_2023_47/egazette_2023_250882/extracted.txt"
    assert os.path.exists(snap_path)
    assert os.path.exists(ref_path)

    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_2023_47",
        snapshot_file_path=snap_path,
        reference_text_path=ref_path
    )
    assert res["report"]["summary"]["sections_in_snapshot"] == 3
    assert res["report"]["summary"]["concordance_percentage"] == 66.67
    assert res["defensible_status"] == VerificationStatus.PARTIALLY_VERIFIED.value
    # Sections 61, 63 matched
    assert set(res["report"]["verification_outcome"]["verified_scope"]) == {"61", "63"}
    # Section 1 contains commencement note and differs
    assert set(res["report"]["verification_outcome"]["unverified_scope"]) == {"1"}
    # Omitted central sections identified
    assert set(res["report"]["summary"]["sections_in_reference_omitted_from_snapshot"]) == {"2", "62"}


def test_16_preservation_of_task_040_ica_and_dpdp_scopes():
    comparator = StatutoryComparisonEngine()
    # 1. ICA 1872
    ica_snap = "data/legal_sources/snapshots/IN_ACT_1872_09.txt"
    ica_ref = "data/legal_sources/extracted_text/IN_ACT_1872_09/indiacode_1872_2187/extracted.txt"
    ica_res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_1872_09",
        snapshot_file_path=ica_snap,
        reference_text_path=ica_ref
    )
    assert ica_res["report"]["summary"]["concordance_percentage"] == 100.0
    assert ica_res["defensible_status"] == VerificationStatus.CONTENT_MATCH_VERIFIED.value
    assert len(ica_res["report"]["verification_outcome"]["verified_scope"]) == 11

    # 2. DPDP 2023
    dpdp_snap = "data/legal_sources/snapshots/IN_ACT_2023_22.txt"
    dpdp_ref = "data/legal_sources/extracted_text/IN_ACT_2023_22/egazette_2023_248045/extracted.txt"
    dpdp_res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_2023_22",
        snapshot_file_path=dpdp_snap,
        reference_text_path=dpdp_ref
    )
    assert dpdp_res["report"]["summary"]["concordance_percentage"] == 100.0
    assert dpdp_res["defensible_status"] == VerificationStatus.CONTENT_MATCH_VERIFIED.value
    assert len(dpdp_res["report"]["verification_outcome"]["verified_scope"]) == 8


# ============================================================================
# 5. EPISTEMIC BOUNDARIES AND VERIFICATION STATUS INVARIANTS
# ============================================================================

def test_17_partial_match_cannot_upgrade_entire_act_to_verified():
    with open("data/legal_sources/corpus_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # In the manifest, all 6 sources must remain PARTIALLY_VERIFIED because the snapshot is a CURATED_EXTRACT
    for src in manifest["official_sources"]:
        assert src["verification_status"] == VerificationStatus.PARTIALLY_VERIFIED.value
        assert src["source_completeness_status"] == SourceCompletenessStatus.CURATED_EXTRACT.value


def test_18_matching_checksum_alone_cannot_prove_official_authenticity():
    workflow = LegalSourceVerificationWorkflow()
    with open("data/legal_sources/corpus_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    src = manifest["official_sources"][0]
    check = workflow.verify_local_file_integrity(src)
    assert check["hash_matches"] is True
    # hash_matches proves byte integrity of stored file, not that the statute is 100% complete or current
    assert src["verification_status"] != VerificationStatus.VERIFIED_OFFICIAL.value


def test_19_currentness_remains_unverified_pending_amendment_audit():
    comparator = StatutoryComparisonEngine()
    res = comparator.compare_snapshot_with_reference(
        source_id="IN_ACT_1996_26",
        snapshot_file_path="data/legal_sources/snapshots/IN_ACT_1996_26.txt",
        reference_text_path="data/legal_sources/extracted_text/IN_ACT_1996_26/indiacode_1996_1978/extracted.txt"
    )
    # Even on 100% concordance, currentness is explicitly unverified pending amendment audit
    assert res["report"]["verification_outcome"]["currentness_status"] == "CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT"
    assert res["report"]["verification_outcome"]["applicability_status"] == "REQUIRES_ADVOCATE_DETERMINATION"


# ============================================================================
# 6. COVERAGE REPORTING INVARIANTS
# ============================================================================

def test_20_coverage_model_metrics_calculated_dynamically():
    model = LegalCoverageModel()
    report = model.generate_coverage_report()
    summary = report["summary"]

    assert summary["total_acts_represented"] == 6
    assert summary["total_sections_in_curated_corpus"] == 40
    assert summary["total_active_central_sections"] == 677
    assert summary["overall_statutory_coverage_percentage"] == 5.91
    assert summary["omitted_central_sections_count"] == 637
    assert summary["corpus_completeness_tier"] == "CURATED_COMMERCIAL_EXTRACTS"


def test_21_disclosures_of_missing_state_amendments_and_case_law():
    model = LegalCoverageModel()
    report = model.generate_coverage_report()
    categories = report["categories"]

    assert "state_amendments" in categories["category_e_missing_or_unresolved_coverage"]
    assert categories["category_e_missing_or_unresolved_coverage"]["state_amendments"] == "EXCLUDED"
    assert categories["category_e_missing_or_unresolved_coverage"]["subordinate_rules"] == "EXCLUDED"
    assert "Shreya Singhal" in categories["category_e_missing_or_unresolved_coverage"]["case_law"]
    assert "Retrieval similarity" in categories["category_f_applicability_not_determined"]["rule"]


# ============================================================================
# 7. SECURITY & RBAC ENFORCEMENT
# ============================================================================

def test_22_supervisor_role_enforced_on_artifact_routes():
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.dashboard.app import app
    from src.persistence.models import UserRecord, UserRole, AccountStatus, AdvocateStatus
    from src.persistence.database import Base
    from src.auth.token import TokenManager
    from src.auth.config import AuthConfig

    app.config["TESTING"] = True
    test_client = app.test_client()

    from contextlib import contextmanager
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)

    @contextmanager
    def mock_db_session():
        sess = TestingSession()
        try:
            yield sess
        finally:
            sess.close()

    seed_sess = TestingSession()
    client_user = UserRecord(
        id=str(uuid.uuid4()),
        email="client_task041@example.com",
        password_hash="mock_hash",
        full_name="Client Test",
        role=UserRole.CLIENT.value,
        account_status=AccountStatus.ACTIVE.value
    )
    lawyer_user = UserRecord(
        id=str(uuid.uuid4()),
        email="lawyer_task041@example.com",
        password_hash="mock_hash",
        full_name="Lawyer Test",
        role=UserRole.LAWYER.value,
        account_status=AccountStatus.ACTIVE.value
    )
    auditor_user = UserRecord(
        id=str(uuid.uuid4()),
        email="auditor_task041@example.com",
        password_hash="mock_hash",
        full_name="Auditor Test",
        role=UserRole.AUDITOR.value,
        account_status=AccountStatus.ACTIVE.value
    )
    seed_sess.add_all([client_user, lawyer_user, auditor_user])
    seed_sess.commit()

    tm = TokenManager(AuthConfig())
    client_token = tm.generate_token(client_user)
    lawyer_token = tm.generate_token(lawyer_user)
    auditor_token = tm.generate_token(auditor_user)
    seed_sess.close()

    with patch("src.persistence.database.get_engine", return_value=test_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=mock_db_session):
            with patch("src.persistence.database.get_db_session", side_effect=mock_db_session):
                with patch("src.persistence.database.get_db", side_effect=mock_db_session):
                    # A. Unauthenticated request -> 401
                    resp = test_client.post("/api/legal/artifacts/acquire", json={"source_id": "IN_ACT_2000_21"})
                    assert resp.status_code == 401

                    # B. Ordinary LAWYER role -> 403 Forbidden
                    resp = test_client.post(
                        "/api/legal/artifacts/acquire",
                        headers={"Authorization": f"Bearer {lawyer_token}"},
                        json={"source_id": "IN_ACT_2000_21"}
                    )
                    assert resp.status_code == 403

                    # C. CLIENT role -> 403 Forbidden
                    resp = test_client.post(
                        "/api/legal/artifacts/register",
                        headers={"Authorization": f"Bearer {client_token}"},
                        json={"source_id": "IN_ACT_2000_21"}
                    )
                    assert resp.status_code == 403

                    # D. AUDITOR role -> 403 Forbidden
                    resp = test_client.post(
                        "/api/legal/artifacts/compare",
                        headers={"Authorization": f"Bearer {auditor_token}"},
                        json={"source_id": "IN_ACT_2000_21"}
                    )
                    assert resp.status_code == 403

    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
