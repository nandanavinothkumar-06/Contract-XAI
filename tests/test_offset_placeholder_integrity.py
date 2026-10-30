"""
Unit tests for Extraction Offset & Literal-Placeholder Integrity Verifier (Strategy A, Step 3).

Covers:
1. Python Unicode character index slicing (raw_text[start:end] == expected).
2. Multi-byte Unicode handling (currency ₹, em-dashes —, Indic scripts).
3. Offset boundary conditions (empty, full-range, out-of-bounds, inverted, negative).
4. Whitespace normalization offset drift detection.
5. Literal placeholder detection across all Policy A categories.
6. Literal placeholder preservation enforcement (flags synthetic replacement as Policy A violation).
7. Missing terminal punctuation treated as WARNING only (valid=True).
8. External schedule reference treated as WARNING only (valid=True).
9. Structural truncation (hyphenated breaks, dangling operators, unclosed brackets) triggers ERROR (valid=False).
"""

import pytest
from src.preprocessing.offset_verifier import (
    OffsetAndPlaceholderVerifier,
    OffsetVerificationStatus,
    PlaceholderCategory,
    PlaceholderOccurrence,
    VerificationReport,
)


# =============================================================================
# SYNTHETIC TEST FIXTURES
# =============================================================================

SAMPLE_ASCII_TEXT = (
    "14. Limitation of Liability. The total aggregate liability of the Contractor "
    "under this Agreement shall not exceed [INR 50,00,000]."
)

SAMPLE_UNICODE_TEXT = (
    "शुल्क: ₹50,000/- (भारतीय संविदा अधिनियम 1872) — धारा 73 के अधीन। "
    "The Supplier [Insert Name of Supplier] shall pay liquidated damages."
)


# =============================================================================
# 1. CHARACTER OFFSET SLICING (PYTHON UNICODE INDICES)
# =============================================================================

def test_exact_character_offset_slice_ascii():
    expected_slice = "Limitation of Liability"
    start = SAMPLE_ASCII_TEXT.index(expected_slice)
    end = start + len(expected_slice)

    report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        SAMPLE_ASCII_TEXT, start, end, expected_slice
    )
    assert report.is_valid is True
    assert report.status == OffsetVerificationStatus.VERIFIED_EXACT
    assert report.slice_matches is True
    assert report.extracted_slice == expected_slice


def test_exact_character_offset_slice_multibyte_unicode():
    # Slicing the currency symbol and Hindi phrase using Python character indices
    expected_slice = "₹50,000/- (भारतीय संविदा अधिनियम 1872)"
    start = SAMPLE_UNICODE_TEXT.index(expected_slice)
    end = start + len(expected_slice)

    report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        SAMPLE_UNICODE_TEXT, start, end, expected_slice
    )
    assert report.is_valid is True
    assert report.status == OffsetVerificationStatus.VERIFIED_EXACT
    assert report.slice_matches is True
    assert report.extracted_slice == expected_slice


def test_byte_offset_confusion_detection():
    # In SAMPLE_UNICODE_TEXT, multi-byte characters cause byte lengths to diverge from char lengths:
    # "₹" = 3 bytes, "—" = 3 bytes, Devanagari chars = 3 bytes each.
    raw_bytes = SAMPLE_UNICODE_TEXT.encode("utf-8")
    target_substring = "₹50,000"

    # Find the byte position
    byte_start = raw_bytes.find(target_substring.encode("utf-8"))
    byte_end = byte_start + len(target_substring.encode("utf-8"))

    # If caller mistakenly passes byte offsets into character slicer:
    report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        SAMPLE_UNICODE_TEXT, byte_start, byte_end, target_substring
    )
    # Character slice at byte offsets must fail text match
    assert report.is_valid is False
    assert report.status == OffsetVerificationStatus.MISMATCH_TEXT
    # Verifier must detect the byte-offset confusion
    assert any("Offset Encoding Confusion Detected" in err for err in report.errors)


# =============================================================================
# 2. BOUNDARY CONDITIONS & INVALID OFFSETS
# =============================================================================

def test_offset_boundary_conditions():
    text = "Contract Agreement"

    # Full text slice
    full_report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        text, 0, len(text), text
    )
    assert full_report.is_valid is True
    assert full_report.status == OffsetVerificationStatus.VERIFIED_EXACT

    # Empty slice (start == end)
    empty_report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        text, 5, 5, ""
    )
    assert empty_report.is_valid is True
    assert empty_report.status == OffsetVerificationStatus.VERIFIED_EXACT

    # Out of bounds (end > len)
    oob_report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        text, 0, len(text) + 10, text
    )
    assert oob_report.is_valid is False
    assert oob_report.status == OffsetVerificationStatus.OUT_OF_BOUNDS

    # Inverted offsets (end < start)
    inverted_report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        text, 10, 5, "Agreement"
    )
    assert inverted_report.is_valid is False
    assert inverted_report.status == OffsetVerificationStatus.INVERTED_OFFSETS

    # Negative offset
    neg_report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        text, -1, 5, "Contract"
    )
    assert neg_report.is_valid is False
    assert neg_report.status == OffsetVerificationStatus.OUT_OF_BOUNDS

    # Non-integer offsets
    non_int_report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        text, "0", 5, "Contract"
    )
    assert non_int_report.is_valid is False
    assert non_int_report.status == OffsetVerificationStatus.NON_INTEGER_OFFSETS


def test_whitespace_normalization_offset_drift():
    original = "Clause 1.   Scope    of Work."
    # Whitespace normalization collapses multiple spaces
    normalized = "Clause 1. Scope of Work."

    # In original: "Scope" is at indices 12:17
    assert original[12:17] == "Scope"

    # In normalized: indices 12:17 extracts "ope o" (drift!)
    report = OffsetAndPlaceholderVerifier.verify_character_offset_slice(
        normalized, 12, 17, "Scope"
    )
    assert report.is_valid is False
    assert report.status == OffsetVerificationStatus.MISMATCH_TEXT
    assert report.extracted_slice == "ope o"


# =============================================================================
# 3. LITERAL PLACEHOLDER DETECTION & PRESERVATION (POLICY A)
# =============================================================================

def test_placeholder_detection_all_categories():
    contract_text = (
        "Parties: [Insert Name of Procuring Entity] and [Insert Name of Contractor]. "
        "Effective Date: [DD/MM/YYYY] or [Insert Date]. "
        "Contract Value: [INR 50,00,000 (Rupees Fifty Lakhs Only)]. "
        "Arbitration Mode: [Option A: Institutional Arbitration under ICA Rules]. "
        "Proprietary Schedule: [***]. "
        "Authorized Signature: ___________"
    )

    placeholders = OffsetAndPlaceholderVerifier.detect_literal_placeholders(contract_text)
    categories = {p.category for p in placeholders}

    assert PlaceholderCategory.BRACKETED_FIELD in categories
    assert PlaceholderCategory.DATE_PLACEHOLDER in categories
    assert PlaceholderCategory.NUMERICAL_AMOUNT in categories
    assert PlaceholderCategory.DRAFTING_OPTION in categories
    assert PlaceholderCategory.REDACTION_TOKEN in categories
    assert PlaceholderCategory.BLANK_UNDERLINE in categories
    assert len(placeholders) >= 7


def test_placeholder_preservation_success():
    orig = "Warranty shall extend for [Insert 24 Months] from [Insert Acceptance Date]."
    proc = "Warranty shall extend for [Insert 24 Months] from [Insert Acceptance Date]."

    preserved, detected, missing, errors = (
        OffsetAndPlaceholderVerifier.verify_placeholder_preservation(orig, proc)
    )
    assert preserved is True
    assert len(missing) == 0
    assert len(errors) == 0
    assert len(detected) == 2


def test_placeholder_synthetic_replacement_triggers_policy_violation():
    orig = "The Contractor [Insert Name of Contractor] shall pay [INR 5,00,000]."
    # Faulty pipeline injected synthetic entity names instead of preserving placeholders
    corrupt_proc = "The Contractor Acme Infrastructure Ltd shall pay Rs. 500000."

    preserved, detected, missing, errors = (
        OffsetAndPlaceholderVerifier.verify_placeholder_preservation(orig, corrupt_proc)
    )
    assert preserved is False
    assert len(missing) == 2
    assert "[Insert Name of Contractor]" in missing
    assert "[INR 5,00,000]" in missing
    assert any("Policy A Violation" in err for err in errors)


# =============================================================================
# 4. TERMINAL PUNCTUATION & DANGLING REFERENCE CLASSIFICATION
# =============================================================================

def test_missing_terminal_punctuation_treated_as_warning_only():
    heading = "Clause 21. Liquidated Damages and Deduction Schedule"
    is_valid, warnings, errors = (
        OffsetAndPlaceholderVerifier.evaluate_terminal_and_dangling_cues(heading)
    )
    assert is_valid is True
    assert len(errors) == 0
    assert len(warnings) > 0
    assert any("does not conclude with terminal punctuation" in w for w in warnings)

    list_item = "(iv) Compliance with all statutory labour enactments"
    is_valid, warnings, errors = (
        OffsetAndPlaceholderVerifier.evaluate_terminal_and_dangling_cues(list_item)
    )
    assert is_valid is True
    assert len(errors) == 0
    assert len(warnings) > 0


def test_external_schedule_reference_treated_as_warning_only():
    clause = "The service levels and liquidated damages shall be as set forth in Schedule B."
    is_valid, warnings, errors = (
        OffsetAndPlaceholderVerifier.evaluate_terminal_and_dangling_cues(clause)
    )
    assert is_valid is True
    assert len(errors) == 0
    assert len(warnings) > 0
    assert any("external schedule" in w for w in warnings)


def test_genuine_structural_truncation_triggers_errors():
    # Trailing hyphenated word break
    dangling_hyphen = "The contractor shall deliver all materi-"
    is_valid, warnings, errors = (
        OffsetAndPlaceholderVerifier.evaluate_terminal_and_dangling_cues(dangling_hyphen)
    )
    assert is_valid is False
    assert any("incomplete hyphenated word break" in err for err in errors)

    # Trailing dangling operator
    dangling_operator = "Total liability shall equal fee +"
    is_valid, warnings, errors = (
        OffsetAndPlaceholderVerifier.evaluate_terminal_and_dangling_cues(dangling_operator)
    )
    assert is_valid is False
    assert any("dangling operator" in err for err in errors)

    # Unclosed bracket
    unclosed_bracket = "Payment shall be made to [Insert Bank Account"
    is_valid, warnings, errors = (
        OffsetAndPlaceholderVerifier.evaluate_terminal_and_dangling_cues(unclosed_bracket)
    )
    assert is_valid is False
    assert any("unclosed opening bracket" in err for err in errors)
