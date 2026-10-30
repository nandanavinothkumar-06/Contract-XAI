"""
Unit tests for Model Commercial Agreement Provenance and Quarantine Schemas (Strategy A, Step 1).

Covers:
1. Valid ModelAgreementProvenanceRecord creation and serialization.
2. SHA-256 digest format validation (64-character lowercase hex).
3. 1-indexed PDF page range validation (start >= 1, end >= start).
4. Strict forbidden extra fields (ConfigDict(extra="forbid")).
5. ComponentType enum enforcement.
6. Structured QuarantineEntry creation across all QuarantineReasonCode values.
7. Quarantine span integrity (char_end >= char_start, utf8_byte_end >= utf8_byte_start).
8. Distinction between Python character offsets and UTF-8 byte offsets.
9. DocumentValidator helper methods (validate_sha256_hex, validate_page_range, etc.).
10. Truncation inspection: does NOT flag missing terminal punctuation alone.
11. Truncation inspection: flags genuine structural defects (dangling hyphens, unclosed brackets).
"""

import pytest
from pydantic import ValidationError

from src.ingestion.schema import (
    ComponentType,
    OffsetSemantics,
    ModelAgreementProvenanceRecord,
    QuarantineReasonCode,
    QuarantineEntry,
)
from src.ingestion.validator import DocumentValidator


# =============================================================================
# SYNTHETIC TEST FIXTURES
# =============================================================================

VALID_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
VALID_COMPONENT_SHA256 = "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"

SAMPLE_PROVENANCE_DICT = {
    "document_id": "DOE-GOODS-2022-GCC",
    "template_family_id": "MACRO-FAM-DOE-PPD",
    "issuing_agency": "Procurement Policy Division, Department of Expenditure, Ministry of Finance",
    "source_pdf_sha256": VALID_SHA256,
    "source_page_range": (45, 98),
    "component_type": "GCC",
    "source_manual_title": "Manual for Procurement of Goods",
    "manual_edition_date": "June 2022",
    "source_landing_url": "https://doe.gov.in/manuals",
    "source_file_url": "https://doe.gov.in/files/manuals_documents/Goods.pdf",
    "component_sha256": VALID_COMPONENT_SHA256,
    "metadata": {"procurement_category": "GOODS", "chapter_reference": "Annexure 4"}
}


# =============================================================================
# 1. PROVENANCE RECORD VALIDATION
# =============================================================================

def test_valid_provenance_record_creation():
    record = ModelAgreementProvenanceRecord(**SAMPLE_PROVENANCE_DICT)
    assert record.document_id == "DOE-GOODS-2022-GCC"
    assert record.template_family_id == "MACRO-FAM-DOE-PPD"
    assert record.component_type == ComponentType.GCC
    assert record.source_page_range == (45, 98)
    assert record.source_pdf_sha256 == VALID_SHA256
    assert record.metadata["procurement_category"] == "GOODS"


def test_provenance_sha256_validation():
    # Valid lowercase hex succeeds
    record = ModelAgreementProvenanceRecord(
        **{**SAMPLE_PROVENANCE_DICT, "source_pdf_sha256": "a" * 64}
    )
    assert record.source_pdf_sha256 == "a" * 64

    # Uppercase hex is normalized to lowercase
    record_upper = ModelAgreementProvenanceRecord(
        **{**SAMPLE_PROVENANCE_DICT, "source_pdf_sha256": "A" * 64}
    )
    assert record_upper.source_pdf_sha256 == "a" * 64

    # Short hash raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ModelAgreementProvenanceRecord(
            **{**SAMPLE_PROVENANCE_DICT, "source_pdf_sha256": "abcdef1234"}
        )
    assert "64 lowercase hexadecimal" in str(exc.value)

    # Non-hex characters raise ValidationError
    with pytest.raises(ValidationError) as exc:
        ModelAgreementProvenanceRecord(
            **{**SAMPLE_PROVENANCE_DICT, "source_pdf_sha256": "z" * 64}
        )
    assert "64 lowercase hexadecimal" in str(exc.value)


def test_provenance_page_range_validation():
    # Valid range succeeds
    record = ModelAgreementProvenanceRecord(
        **{**SAMPLE_PROVENANCE_DICT, "source_page_range": (1, 50)}
    )
    assert record.source_page_range == (1, 50)

    # Single-page range (start == end) succeeds
    record_single = ModelAgreementProvenanceRecord(
        **{**SAMPLE_PROVENANCE_DICT, "source_page_range": (12, 12)}
    )
    assert record_single.source_page_range == (12, 12)

    # Inverted range (start > end) raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ModelAgreementProvenanceRecord(
            **{**SAMPLE_PROVENANCE_DICT, "source_page_range": (50, 10)}
        )
    assert "cannot be less than start_page" in str(exc.value)

    # 0-indexed page (start < 1) raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ModelAgreementProvenanceRecord(
            **{**SAMPLE_PROVENANCE_DICT, "source_page_range": (0, 10)}
        )
    assert "start_page must be >= 1" in str(exc.value)


def test_provenance_strict_forbidden_extra_fields():
    # Extra field raises ValidationError due to extra="forbid"
    with pytest.raises(ValidationError) as exc:
        ModelAgreementProvenanceRecord(
            **{**SAMPLE_PROVENANCE_DICT, "unauthorized_extra_field": "injected_value"}
        )
    assert "extra_forbidden" in str(exc.value)


def test_provenance_component_type_enum():
    for comp in ["GCC", "SCC", "CONTRACT_FORM", "SLA_SCHEDULE", "OPERATIVE_COVENANT", "OTHER"]:
        rec = ModelAgreementProvenanceRecord(**{**SAMPLE_PROVENANCE_DICT, "component_type": comp})
        assert rec.component_type.value == comp

    with pytest.raises(ValidationError):
        ModelAgreementProvenanceRecord(**{**SAMPLE_PROVENANCE_DICT, "component_type": "INVALID_COMPONENT"})


def test_provenance_empty_strings_rejected():
    with pytest.raises(ValidationError):
        ModelAgreementProvenanceRecord(**{**SAMPLE_PROVENANCE_DICT, "document_id": "   "})

    with pytest.raises(ValidationError):
        ModelAgreementProvenanceRecord(**{**SAMPLE_PROVENANCE_DICT, "template_family_id": ""})


# =============================================================================
# 2. QUARANTINE ENTRY VALIDATION
# =============================================================================

def test_quarantine_entry_creation_all_reasons():
    reasons = [
        QuarantineReasonCode.TRUNCATED_TEXT,
        QuarantineReasonCode.DANGLING_SCHEDULE_REFERENCE,
        QuarantineReasonCode.UNRESOLVED_ALTERNATIVE_OPTION,
        QuarantineReasonCode.EMBEDDED_DRAFTING_GUIDANCE,
        QuarantineReasonCode.BOUNDARY_AMBIGUITY,
        QuarantineReasonCode.UNRESOLVED_TABLE_STRUCTURE,
        QuarantineReasonCode.UNSPECIFIED_EXTRACTION_DEFECT,
    ]
    for reason in reasons:
        entry = QuarantineEntry(
            quarantine_id=f"QUAR-{reason.value}-001",
            document_id="DOE-GOODS-2022-GCC",
            clause_id="GCC-14.2",
            reason_code=reason,
            description="Synthetic description of quarantine condition",
            flagged_text_snippet="...synthetic clause fragment...",
            source_page=48
        )
        assert entry.reason_code == reason
        assert entry.resolution_status == "PENDING_REVIEW"
        assert entry.offset_semantics == OffsetSemantics.PYTHON_CHAR_OFFSETS


def test_quarantine_span_validation():
    # Valid spans succeed
    entry = QuarantineEntry(
        quarantine_id="QUAR-001",
        document_id="DOE-NCS-2025-SLA",
        reason_code=QuarantineReasonCode.BOUNDARY_AMBIGUITY,
        description="Ambiguous table header boundary",
        char_start=100,
        char_end=250,
        utf8_byte_start=120,
        utf8_byte_end=280
    )
    assert entry.char_start == 100
    assert entry.char_end == 250
    assert entry.utf8_byte_start == 120
    assert entry.utf8_byte_end == 280

    # Inverted char span raises ValidationError
    with pytest.raises(ValidationError) as exc:
        QuarantineEntry(
            quarantine_id="QUAR-002",
            document_id="DOE-NCS-2025-SLA",
            reason_code=QuarantineReasonCode.BOUNDARY_AMBIGUITY,
            description="Inverted char boundary",
            char_start=250,
            char_end=100
        )
    assert "char_end (100) cannot be less than char_start (250)" in str(exc.value)

    # Inverted byte span raises ValidationError
    with pytest.raises(ValidationError) as exc:
        QuarantineEntry(
            quarantine_id="QUAR-003",
            document_id="DOE-NCS-2025-SLA",
            reason_code=QuarantineReasonCode.BOUNDARY_AMBIGUITY,
            description="Inverted byte boundary",
            utf8_byte_start=300,
            utf8_byte_end=150
        )
    assert "utf8_byte_end (150) cannot be less than utf8_byte_start (300)" in str(exc.value)


def test_offset_semantics_distinction():
    # Synthetic string with multi-byte characters:
    # "₹" = 3 bytes in UTF-8
    # "—" (em-dash) = 3 bytes in UTF-8
    text = "Fee: ₹500 — Paid"
    char_len = len(text)                  # 16 characters
    utf8_byte_len = len(text.encode("utf-8")) # 20 bytes

    assert char_len == 16
    assert utf8_byte_len == 20
    assert char_len != utf8_byte_len

    # QuarantineEntry explicitly records both coordinates without conflation
    entry = QuarantineEntry(
        quarantine_id="QUAR-OFFSETS-001",
        document_id="DOE-CS-2025-LUMPSUM",
        reason_code=QuarantineReasonCode.TRUNCATED_TEXT,
        description="Truncated after currency symbol",
        flagged_text_snippet=text,
        char_start=0,
        char_end=char_len,
        utf8_byte_start=0,
        utf8_byte_end=utf8_byte_len,
        offset_semantics=OffsetSemantics.PYTHON_CHAR_OFFSETS
    )
    assert entry.char_end == 16
    assert entry.utf8_byte_end == 20
    assert entry.offset_semantics == OffsetSemantics.PYTHON_CHAR_OFFSETS


# =============================================================================
# 3. DOCUMENT VALIDATOR PROVENANCE METHODS
# =============================================================================

def test_document_validator_sha256_hex():
    val = DocumentValidator()
    assert val.validate_sha256_hex(VALID_SHA256) is True
    assert val.validate_sha256_hex(VALID_SHA256.upper()) is True
    assert val.validate_sha256_hex("short_hash") is False
    assert val.validate_sha256_hex("z" * 64) is False
    assert val.validate_sha256_hex(None) is False


def test_document_validator_page_range():
    val = DocumentValidator()
    is_valid, errors = val.validate_page_range(1, 10, max_pages=300)
    assert is_valid is True
    assert len(errors) == 0

    is_valid, errors = val.validate_page_range(0, 10)
    assert is_valid is False
    assert "start_page must be >= 1" in errors[0]

    is_valid, errors = val.validate_page_range(15, 10)
    assert is_valid is False
    assert "cannot be less than start_page" in errors[0]

    is_valid, errors = val.validate_page_range(1, 350, max_pages=300)
    assert is_valid is False
    assert "exceeds allowed limit" in errors[0]


def test_document_validator_model_agreement_provenance():
    val = DocumentValidator()
    rec, errors = val.validate_model_agreement_provenance(SAMPLE_PROVENANCE_DICT)
    assert rec is not None
    assert len(errors) == 0
    assert rec.document_id == "DOE-GOODS-2022-GCC"

    bad_dict = {**SAMPLE_PROVENANCE_DICT, "source_page_range": (100, 20)}
    rec_bad, errors_bad = val.validate_model_agreement_provenance(bad_dict)
    assert rec_bad is None
    assert len(errors_bad) > 0


def test_document_validator_quarantine_entry():
    val = DocumentValidator()
    entry_dict = {
        "quarantine_id": "Q-001",
        "document_id": "DOE-GOODS-2022-GCC",
        "reason_code": "EMBEDDED_DRAFTING_GUIDANCE",
        "description": "Embedded guidance note found in clause text",
        "flagged_text_snippet": "[Note for Procuring Entity: specify warranty period]"
    }
    entry, errors = val.validate_quarantine_entry(entry_dict)
    assert entry is not None
    assert len(errors) == 0
    assert entry.reason_code == QuarantineReasonCode.EMBEDDED_DRAFTING_GUIDANCE


# =============================================================================
# 4. TRUNCATION INDICATOR INSPECTION (RDR-002 RULES)
# =============================================================================

def test_truncation_inspection_does_not_flag_missing_terminal_punctuation_alone():
    val = DocumentValidator()

    # Clause heading without terminal punctuation is normal legal drafting
    heading = "Clause 14. Limitation of Liability and Indemnities"
    is_suspect, reasons = val.assess_truncation_indicators(heading)
    assert is_suspect is False
    assert len(reasons) == 0

    # Sub-clause list item ending without period
    subclause = "(b) Liquidated damages for delayed delivery of goods and components"
    is_suspect, reasons = val.assess_truncation_indicators(subclause)
    assert is_suspect is False
    assert len(reasons) == 0


def test_truncation_inspection_flags_genuine_structural_defects():
    val = DocumentValidator()

    # Trailing hyphenated word break
    dangling_hyphen = "The Supplier shall indemnify and hold harmless the Purchas-"
    is_suspect, reasons = val.assess_truncation_indicators(dangling_hyphen)
    assert is_suspect is True
    assert any("unfinished word break" in r for r in reasons)

    # Trailing dangling operator
    dangling_operator = "Total liability shall equal the contract price +"
    is_suspect, reasons = val.assess_truncation_indicators(dangling_operator)
    assert is_suspect is True
    assert any("dangling operator" in r for r in reasons)

    # Unclosed bracket
    unclosed_bracket = "Delivery shall take place at [Insert designated storage location"
    is_suspect, reasons = val.assess_truncation_indicators(unclosed_bracket)
    assert is_suspect is True
    assert any("unclosed bracket" in r for r in reasons)
