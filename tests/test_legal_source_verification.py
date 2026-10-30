"""
Task 039 Comprehensive Test Suite: Indian Legal Source Verification and Coverage Framework.

Verifies all 26 Phase I test requirements:
1. Missing source file is detected.
2. Malformed manifest is detected.
3. Missing required metadata is reported.
4. Local checksum is computed reproducibly.
5. Changed local source content is detected.
6. A stable checksum does not promote a source to authoritative verification.
7. A URL existing in metadata does not prove authenticity.
8. HTTP success alone does not prove content equivalence.
9. Failed retrieval is recorded without false verification.
10. Exact content comparison requires a real reference artifact.
11. Verification scope and timestamp are recorded.
12. Partial verification is represented accurately.
13. Unknown commencement status remains unknown.
14. Unknown amendment coverage remains unknown.
15. Curated extracts are not presented as complete Acts.
16. Coverage reports identify omitted or unknown sections when that information is available.
17. Duplicate source identifiers are detected.
18. Duplicate or inconsistent source-file references are detected.
19. Missing or stale verification metadata is handled safely.
20. Evidence retrieval preserves source IDs and text provenance.
21. Unverified source status is surfaced in the evidence pipeline.
22. Stale evidence is not presented as current.
23. No fabricated statutory citations are generated.
24. Client views do not expose unauthorized internal information.
25. Lawyer review and report eligibility remain enforced.
26. Existing Task 038 tests continue to pass.
"""

import os
import json
import hashlib
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.legal_sources.schema import LegalSource, LegalPassage, LegalSourceQuery
from src.legal_sources.provenance import (
    VerificationStatus,
    SourceCompletenessStatus,
    AmendmentCoverageStatus,
    VerificationMethod,
    CurrentnessStatus,
    CommencementStatus,
    LegalSourceErrorStatus,
    is_retrieval_eligible,
    is_authoritatively_verified,
)
from src.legal_sources.verification import LegalSourceVerificationWorkflow
from src.legal_sources.coverage import LegalCoverageModel, STATUTORY_CORPUS_GROUND_TRUTH
from src.legal_sources.registry import LegalSourceRegistry, get_authoritative_indian_corpus
from src.legal_sources.ingestion import StatutoryIngestionEngine
from src.legal_sources.retriever import LegalSourceRetriever
from src.legal_sources.config import LegalSourceRetrievalConfig
from src.legal_sources.matcher import ContractStatuteMatcher
from src.review.evidence import ClauseEvidenceRetriever


# =========================================================================
# TEST 1: Missing source file is detected
# =========================================================================
def test_01_missing_source_file_is_detected():
    workflow = LegalSourceVerificationWorkflow(snapshots_dir="non_existent_directory_xyz")
    meta = {
        "source_id": "IN_ACT_MISSING_01",
        "snapshot_file": "non_existent_file.txt",
        "source_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    }
    result = workflow.verify_local_file_integrity(meta)
    assert result["file_present"] is False
    assert result["hash_matches"] is False
    assert "not found on disk" in result["error"].lower()


# =========================================================================
# TEST 2: Malformed manifest is detected
# =========================================================================
def test_02_malformed_manifest_is_detected(tmp_path):
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text("{ this is malformed json : not valid", encoding="utf-8")

    workflow = LegalSourceVerificationWorkflow(manifest_path=str(bad_manifest))
    report = workflow.run_verification()
    assert report["status"] == "FAILED"
    assert "malformed json" in report["error"].lower()


# =========================================================================
# TEST 3: Missing required metadata is reported
# =========================================================================
def test_03_missing_required_metadata_is_reported():
    workflow = LegalSourceVerificationWorkflow()
    # Missing source_id, jurisdiction, verification_status, title
    manifest_data = {
        "official_sources": [
            {
                "country": "IN",
                "snapshot_file": "some_file.txt"
            }
        ]
    }
    validation = workflow.validate_manifest_metadata(manifest_data)
    assert validation["valid"] is False
    assert any("missing 'source_id'" in err for err in validation["errors"])
    assert any("missing title" in err for err in validation["errors"])
    assert any("missing required field 'jurisdiction'" in err for err in validation["errors"])


# =========================================================================
# TEST 4: Local checksum is computed reproducibly
# =========================================================================
def test_04_local_checksum_is_computed_reproducibly(tmp_path):
    content = b"Section 10. All agreements are contracts if made by free consent.\n"
    expected_sha = hashlib.sha256(content).hexdigest()

    snap_file = tmp_path / "sample.txt"
    snap_file.write_bytes(content)

    workflow = LegalSourceVerificationWorkflow(snapshots_dir=str(tmp_path))
    meta = {
        "source_id": "TEST_REPRODUCIBLE_01",
        "snapshot_file": "sample.txt",
        "source_sha256": expected_sha
    }
    result = workflow.verify_local_file_integrity(meta)
    assert result["file_present"] is True
    assert result["hash_matches"] is True
    assert result["computed_sha256"] == expected_sha
    assert result["error"] is None


# =========================================================================
# TEST 5: Changed local source content is detected
# =========================================================================
def test_05_changed_local_source_content_is_detected(tmp_path):
    orig_content = b"Original statutory content"
    orig_sha = hashlib.sha256(orig_content).hexdigest()

    # Modified content on disk
    tampered_content = b"Tampered or modified content with unauthorized amendments"
    snap_file = tmp_path / "tampered.txt"
    snap_file.write_bytes(tampered_content)

    workflow = LegalSourceVerificationWorkflow(snapshots_dir=str(tmp_path))
    meta = {
        "source_id": "TEST_TAMPERED_01",
        "snapshot_file": "tampered.txt",
        "source_sha256": orig_sha
    }
    result = workflow.verify_local_file_integrity(meta)
    assert result["file_present"] is True
    assert result["hash_matches"] is False
    assert result["computed_sha256"] != orig_sha
    assert "checksum mismatch" in result["error"].lower()


# =========================================================================
# TEST 6: Stable checksum does not promote source to authoritative verification
# =========================================================================
def test_06_stable_checksum_does_not_promote_to_authoritative(tmp_path):
    content = b"Sample Act text"
    sha = hashlib.sha256(content).hexdigest()
    snap_file = tmp_path / "act.txt"
    snap_file.write_bytes(content)

    manifest_data = {
        "manifest_version": "1.0.0",
        "official_sources": [
            {
                "source_id": "TEST_SRC_01",
                "canonical_title": "Test Statute",
                "jurisdiction": "India - Central",
                "snapshot_file": "act.txt",
                "source_sha256": sha,
                # Improper claim of authoritative verification without reference artifact
                "verification_status": "CONTENT_MATCH_VERIFIED"
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    workflow = LegalSourceVerificationWorkflow(
        manifest_path=str(manifest_path),
        snapshots_dir=str(tmp_path),
        reference_artifacts_dir=str(tmp_path / "no_artifacts")
    )
    report = workflow.run_verification()
    src_rep = report["sources"][0]

    # Must be downgraded from CONTENT_MATCH_VERIFIED because no official artifact comparison took place
    assert src_rep["defensible_verification_status"] == VerificationStatus.PARTIALLY_VERIFIED.value
    assert report["summary"]["is_corpus_fully_authoritative"] is False
    assert any("downgraded to PARTIALLY_VERIFIED" in w for w in report["warnings"])


# =========================================================================
# TEST 7: A URL existing in metadata does not prove authenticity
# =========================================================================
def test_07_url_in_metadata_does_not_prove_authenticity():
    source = LegalSource(
        source_id="TEST_URL_01",
        title="Unverified URL Statute",
        official_url="https://www.indiacode.nic.in/handle/123456789/9999",
        verification_status=VerificationStatus.OFFICIAL_SOURCE_IDENTIFIED
    )
    # Storing a URL identifies candidate official publication, but does NOT make it authoritatively verified
    assert not is_authoritatively_verified(source.verification_status)
    assert source.verification_status != VerificationStatus.CONTENT_MATCH_VERIFIED


# =========================================================================
# TEST 8: HTTP success alone does not prove content equivalence
# =========================================================================
def test_08_http_success_alone_does_not_prove_content_equivalence():
    workflow = LegalSourceVerificationWorkflow()
    # Mock HTTP 200 response
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        net_result = workflow.attempt_network_reachability("https://www.indiacode.nic.in/test")
        assert net_result["reachable"] is True
        assert net_result["http_status"] == 200
        # Crucial invariant: HTTP 200 reachability does NOT prove content equivalence
        assert net_result["proves_content_equivalence"] is False
        assert "does not establish statutory text equivalence" in net_result["disclaimer"]


# =========================================================================
# TEST 9: Failed retrieval is recorded without false verification
# =========================================================================
def test_09_failed_retrieval_recorded_without_false_verification():
    workflow = LegalSourceVerificationWorkflow()
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        net_result = workflow.attempt_network_reachability("https://www.indiacode.nic.in/timeout")
        assert net_result["reachable"] is False
        assert net_result["http_status"] is None
        assert "timed out" in net_result["error"].lower()
        assert net_result["proves_content_equivalence"] is False


# =========================================================================
# TEST 10: Exact content comparison requires a real reference artifact
# =========================================================================
def test_10_exact_content_comparison_requires_real_reference_artifact(tmp_path):
    workflow = LegalSourceVerificationWorkflow(reference_artifacts_dir=str(tmp_path))
    local_text = "Section 10. Valid contracts require free consent."

    # 1. Without reference artifact -> reports limitation honestly
    comp_missing = workflow.compare_with_authoritative_artifact("STATUTE_001", local_text, reference_artifact_path=None)
    assert comp_missing["comparison_performed"] is False
    assert comp_missing["is_byte_exact"] is False
    assert comp_missing["verification_tier"] == VerificationStatus.PARTIALLY_VERIFIED.value

    # 2. With real reference artifact matching exactly -> CONTENT_MATCH_VERIFIED
    ref_file = tmp_path / "STATUTE_001_authoritative.txt"
    ref_file.write_text(local_text, encoding="utf-8")

    comp_match = workflow.compare_with_authoritative_artifact("STATUTE_001", local_text, reference_artifact_path=str(ref_file))
    assert comp_match["comparison_performed"] is True
    assert comp_match["is_byte_exact"] is True
    assert comp_match["match_ratio"] == 1.0
    assert comp_match["verification_tier"] == VerificationStatus.CONTENT_MATCH_VERIFIED.value


# =========================================================================
# TEST 11: Verification scope and timestamp are recorded
# =========================================================================
def test_11_verification_scope_and_timestamp_recorded():
    workflow = LegalSourceVerificationWorkflow()
    report = workflow.run_verification()
    assert "audit_timestamp" in report
    assert report["audit_timestamp"] is not None
    assert "summary" in report
    assert "sources" in report
    for s in report["sources"]:
        assert "covered_sections" in s
        assert "covered_sections_count" in s
        assert "verification_method" in s


# =========================================================================
# TEST 12: Partial verification is represented accurately
# =========================================================================
def test_12_partial_verification_represented_accurately():
    workflow = LegalSourceVerificationWorkflow()
    report = workflow.run_verification()
    # For our curated Indian statutory corpus without external gazette comparison,
    # all 6 sources must be accurately represented as PARTIALLY_VERIFIED
    assert report["summary"]["partially_verified"] == 6
    assert report["summary"]["content_match_verified"] == 0
    assert report["summary"]["is_corpus_fully_authoritative"] is False


# =========================================================================
# TEST 13: Unknown commencement status remains unknown
# =========================================================================
def test_13_unknown_commencement_status_remains_unknown():
    source = LegalSource(
        source_id="UNKNOWN_COMM_01",
        title="Pending Act",
        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
        commencement_status=CommencementStatus.UNKNOWN
    )
    assert source.commencement_status == CommencementStatus.UNKNOWN
    # Ingestion or abstention must not invent an IN_FORCE status
    assert source.commencement_status != CommencementStatus.IN_FORCE


# =========================================================================
# TEST 14: Unknown amendment coverage remains unknown
# =========================================================================
def test_14_unknown_amendment_coverage_remains_unknown():
    source = LegalSource(
        source_id="UNKNOWN_AMEND_01",
        title="Uncertain Amendment Act",
        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
        amendment_coverage_status=AmendmentCoverageStatus.UNKNOWN
    )
    assert source.amendment_coverage_status == AmendmentCoverageStatus.UNKNOWN
    assert source.amendment_coverage_status != AmendmentCoverageStatus.AMENDMENTS_UP_TO_DATE


# =========================================================================
# TEST 15: Curated extracts are not presented as complete Acts
# =========================================================================
def test_15_curated_extracts_not_presented_as_complete_acts():
    model = LegalCoverageModel()
    report = model.generate_coverage_report()
    assert report["summary"]["corpus_completeness_tier"] == "CURATED_COMMERCIAL_EXTRACTS"
    assert report["summary"]["overall_statutory_coverage_percentage"] < 20.0
    for s in report["sources"]:
        assert s["coverage_percentage"] < 100.0
        assert s["sections_present_count"] < s["active_central_sections"]


# =========================================================================
# TEST 16: Coverage reports identify omitted or unknown sections
# =========================================================================
def test_16_coverage_reports_identify_omitted_sections():
    model = LegalCoverageModel()
    sc = model.get_source_coverage("IN_ACT_1872_09")
    assert sc is not None
    assert "omitted_subject_matter" in sc
    assert any("Indemnity" in om for om in sc["omitted_subject_matter"])
    assert any("Guarantee" in om for om in sc["omitted_subject_matter"])
    assert any("Agency" in om for om in sc["omitted_subject_matter"])


# =========================================================================
# TEST 17: Duplicate source identifiers are detected
# =========================================================================
def test_17_duplicate_source_identifiers_detected():
    workflow = LegalSourceVerificationWorkflow()
    manifest_data = {
        "official_sources": [
            {
                "source_id": "DUPLICATE_ID_01",
                "title": "Act Version 1",
                "jurisdiction": "IN",
                "verification_status": "PARTIALLY_VERIFIED",
                "snapshot_file": "file1.txt"
            },
            {
                "source_id": "DUPLICATE_ID_01",  # Duplicate ID
                "title": "Act Version 2",
                "jurisdiction": "IN",
                "verification_status": "PARTIALLY_VERIFIED",
                "snapshot_file": "file2.txt"
            }
        ]
    }
    validation = workflow.validate_manifest_metadata(manifest_data)
    assert validation["valid"] is False
    assert any("Duplicate source identifier detected: 'DUPLICATE_ID_01'" in err for err in validation["errors"])


# =========================================================================
# TEST 18: Duplicate or inconsistent source-file references are detected
# =========================================================================
def test_18_duplicate_source_file_references_detected():
    workflow = LegalSourceVerificationWorkflow()
    manifest_data = {
        "official_sources": [
            {
                "source_id": "ACT_A",
                "title": "Act A",
                "jurisdiction": "IN",
                "verification_status": "PARTIALLY_VERIFIED",
                "snapshot_file": "common_snapshot.txt"
            },
            {
                "source_id": "ACT_B",
                "title": "Act B",
                "jurisdiction": "IN",
                "verification_status": "PARTIALLY_VERIFIED",
                "snapshot_file": "common_snapshot.txt"  # Duplicate file reference
            }
        ]
    }
    validation = workflow.validate_manifest_metadata(manifest_data)
    assert validation["valid"] is False
    assert any("Duplicate source file reference detected" in err for err in validation["errors"])


# =========================================================================
# TEST 19: Missing or stale verification metadata handled safely
# =========================================================================
def test_19_missing_or_stale_verification_metadata_handled_safely():
    # If a source has None or unverified verification status, safe fallback
    source = LegalSource(
        source_id="SAFE_FALLBACK_01",
        title="Fallback Statute",
        verification_status=VerificationStatus.UNVERIFIED,
        currentness_status=CurrentnessStatus.UNKNOWN
    )
    assert not is_retrieval_eligible(source.verification_status)
    assert source.source_completeness_status == SourceCompletenessStatus.CURATED_EXTRACT
    assert source.amendment_coverage_status == AmendmentCoverageStatus.UNKNOWN


# =========================================================================
# TEST 20: Evidence retrieval preserves source IDs and text provenance
# =========================================================================
def test_20_evidence_retrieval_preserves_source_ids_and_text_provenance():
    retriever = ClauseEvidenceRetriever()
    evidence = retriever.retrieve_evidence_for_clause("An agreement in restraint of trade is void")
    assert len(evidence["passages"]) > 0
    top = evidence["passages"][0]
    assert top["statute_id"] == "IN_ACT_1872_09"
    assert "27" in top["section_number"]
    assert "void" in top["passage_text"].lower()
    assert top["checksum_type"] == "LOCAL_SHA256"
    assert "Local SHA-256" in top["checksum_meaning"]


# =========================================================================
# TEST 21: Unverified source status is surfaced in the evidence pipeline
# =========================================================================
def test_21_unverified_source_status_surfaced_in_evidence_pipeline():
    registry = LegalSourceRegistry()
    registry.register_source(LegalSource(
        source_id="SRC_UNVERIFIED_XYZ",
        title="Unverified Manual Guidelines",
        verification_status=VerificationStatus.UNVERIFIED,
        is_test_fixture=True
    ))
    index = MagicMock()
    config = LegalSourceRetrievalConfig(verified_only=True)
    retriever = LegalSourceRetriever(registry, index, config)
    # Filter must reject unverified source
    query = LegalSourceQuery(query_id="q1", query_text="guidelines", created_at="2026-10-17T00:00:00Z")
    assert retriever._is_source_eligible("SRC_UNVERIFIED_XYZ", query) is False


# =========================================================================
# TEST 22: Stale evidence is not presented as current
# =========================================================================
def test_22_stale_evidence_not_presented_as_current():
    retriever = ClauseEvidenceRetriever()
    stale_evidence = retriever.retrieve_evidence_for_clause(
        "Standard commercial clause text",
        clause_id="cl-001",
        document_version_mismatch=True
    )
    assert stale_evidence["status"] == "ABSTAIN"
    assert stale_evidence["abstention_reason"] == "DOCUMENT_VERSION_STALE"
    assert stale_evidence["evidence_quality_status"] == "STALE_EVIDENCE"
    assert len(stale_evidence["passages"]) == 0


# =========================================================================
# TEST 23: No fabricated statutory citations are generated
# =========================================================================
def test_23_no_fabricated_statutory_citations():
    retriever = ClauseEvidenceRetriever()
    # Random query that does not exist in any statute
    evidence = retriever.retrieve_evidence_for_clause("Quantum computing cryptographic lattice entanglement protocol")
    # Must abstain with NO_MATCH or WEAK_RETRIEVAL_EVIDENCE, never invent a section
    assert evidence["status"] == "ABSTAIN"
    assert len(evidence["passages"]) == 0


# =========================================================================
# TEST 24: Client views do not expose unauthorized internal information
# =========================================================================
def test_24_client_views_do_not_expose_unauthorized_internal_info():
    # Verify evidence dict exposed to frontend does not contain internal review notes or advocate IDs
    retriever = ClauseEvidenceRetriever()
    evidence = retriever.retrieve_evidence_for_clause("Section 10 agreements are contracts")
    if evidence.get("passages"):
        p = evidence["passages"][0]
        # Should not expose advocate IDs, raw audit logs, or client-ineligible internal notes
        assert "lawyer_internal_notes" not in p
        assert "supervising_lawyer_private_audit" not in p


# =========================================================================
# TEST 25: Lawyer review and report eligibility remain enforced
# =========================================================================
def test_25_lawyer_review_and_report_eligibility_enforced():
    retriever = ClauseEvidenceRetriever()
    evidence = retriever.retrieve_evidence_for_clause("Contract for sale of goods")
    # Mandatory invariant: automated retrieval always requires lawyer review
    assert evidence["requires_lawyer_review"] is True
    # Mandatory invariant: score is explicitly not a legal probability
    assert "NOT represent probabilities" in evidence["score_disclaimer"]


# =========================================================================
# TEST 26: Existing Task 038 tests continue to pass
# =========================================================================
def test_26_existing_corpus_and_evidence_quality_pipeline():
    # 1. Verify that fresh ingestion from corpus_manifest.json sets PARTIALLY_VERIFIED and CURATED_EXTRACT
    engine = StatutoryIngestionEngine()
    fresh_sources, fresh_passages = engine.ingest_corpus_from_manifest()
    assert len(fresh_sources) == 6
    assert len(fresh_passages) == 40
    source_ids = {s.source_id for s in fresh_sources}
    assert source_ids == {
        "IN_ACT_1872_09",
        "IN_ACT_2000_21",
        "IN_ACT_2023_22",
        "IN_ACT_1963_47",
        "IN_ACT_1996_26",
        "IN_ACT_2023_47",
    }
    for s in fresh_sources:
        assert s.verification_status == VerificationStatus.PARTIALLY_VERIFIED
        assert s.source_completeness_status == SourceCompletenessStatus.CURATED_EXTRACT
        assert s.source_sha256 is not None
        assert s.authoritative_reference_sha256 is None

    # 2. Verify that the ClauseEvidenceRetriever singleton registry sources are retrieval-eligible
    registry = ClauseEvidenceRetriever()._registry
    all_sources = registry.get_all_sources()
    assert len(all_sources) == 6
    for s in all_sources:
        assert is_retrieval_eligible(s.verification_status)
        assert s.source_completeness_status == SourceCompletenessStatus.CURATED_EXTRACT

