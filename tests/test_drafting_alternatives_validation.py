"""
Unit tests for Drafting Alternative Validator (Strategy A, Step 2).

Covers:
1. Valid sibling alternatives pass consistency validation.
2. Inconsistent sibling metadata (parent section, document ID, template family) is rejected.
3. Groups with fewer than 2 alternatives are rejected.
4. Valid active configuration with exactly one option per group passes.
5. Multiple active options in the same alternative group are rejected (conflict).
6. Missing active option for expected mandatory group is rejected.
7. Candidate finding proposed on inactive alternative is rejected.
8. Candidate finding proposed on active alternative or standard clause passes.
"""

import pytest
from pydantic import ValidationError

from src.candidates.alternative_validator import (
    DraftingAlternativeMetadata,
    ContractConfiguration,
    AlternativeValidator,
)


# =============================================================================
# SYNTHETIC TEST FIXTURES
# =============================================================================

OPT_A = DraftingAlternativeMetadata(
    alternative_id="GCC-24.2#OPT-A",
    alternative_group_id="ALT-GCC-24.2-DISPUTE-RESOLUTION",
    parent_section_id="GCC-24.2",
    document_id="DOE-GOODS-2022-GCC",
    template_family_id="MACRO-FAM-DOE-PPD",
    selection_instruction="Select Option A for institutional arbitration.",
    clause_text="Disputes shall be settled under ICA Institutional Rules."
)

OPT_B = DraftingAlternativeMetadata(
    alternative_id="GCC-24.2#OPT-B",
    alternative_group_id="ALT-GCC-24.2-DISPUTE-RESOLUTION",
    parent_section_id="GCC-24.2",
    document_id="DOE-GOODS-2022-GCC",
    template_family_id="MACRO-FAM-DOE-PPD",
    selection_instruction="Select Option B for ad-hoc arbitration.",
    clause_text="Disputes shall be settled by an ad-hoc tribunal of three arbitrators."
)

SEC_10_OPT_1 = DraftingAlternativeMetadata(
    alternative_id="SCC-10.1#OPT-1",
    alternative_group_id="ALT-SCC-10.1-PAYMENT-TERMS",
    parent_section_id="SCC-10.1",
    document_id="DOE-GOODS-2022-GCC",
    template_family_id="MACRO-FAM-DOE-PPD",
    selection_instruction="Select Option 1 for milestone payments.",
    clause_text="Payment will be disbursed in milestone tranches."
)

SEC_10_OPT_2 = DraftingAlternativeMetadata(
    alternative_id="SCC-10.1#OPT-2",
    alternative_group_id="ALT-SCC-10.1-PAYMENT-TERMS",
    parent_section_id="SCC-10.1",
    document_id="DOE-GOODS-2022-GCC",
    template_family_id="MACRO-FAM-DOE-PPD",
    selection_instruction="Select Option 2 for lump-sum upon acceptance.",
    clause_text="Payment will be disbursed 100% upon final acceptance."
)


# =============================================================================
# 1. SIBLING ALTERNATIVE VALIDATION
# =============================================================================

def test_valid_sibling_alternatives_pass():
    val = AlternativeValidator()
    is_valid, errors = val.validate_sibling_alternatives([OPT_A, OPT_B])
    assert is_valid is True
    assert len(errors) == 0


def test_sibling_mismatched_parent_section_rejected():
    val = AlternativeValidator()
    mismatched_b = OPT_B.model_copy(update={"parent_section_id": "GCC-99.9"})
    is_valid, errors = val.validate_sibling_alternatives([OPT_A, mismatched_b])
    assert is_valid is False
    assert any("Mismatched parent_section_id" in err for err in errors)


def test_sibling_mismatched_document_id_rejected():
    val = AlternativeValidator()
    mismatched_b = OPT_B.model_copy(update={"document_id": "DIFFERENT-DOC-ID"})
    is_valid, errors = val.validate_sibling_alternatives([OPT_A, mismatched_b])
    assert is_valid is False
    assert any("Mismatched document_id" in err for err in errors)


def test_sibling_mismatched_template_family_rejected():
    val = AlternativeValidator()
    mismatched_b = OPT_B.model_copy(update={"template_family_id": "DIFFERENT-FAMILY"})
    is_valid, errors = val.validate_sibling_alternatives([OPT_A, mismatched_b])
    assert is_valid is False
    assert any("Mismatched template_family_id" in err for err in errors)


def test_single_alternative_in_group_rejected():
    val = AlternativeValidator()
    # Group with only 1 option cannot be mutually exclusive
    is_valid, errors = val.validate_sibling_alternatives([OPT_A])
    assert is_valid is False
    assert any("contains only 1 alternative(s)" in err for err in errors)


def test_duplicate_alternative_id_rejected():
    val = AlternativeValidator()
    duplicate_a = OPT_A.model_copy()
    is_valid, errors = val.validate_sibling_alternatives([OPT_A, duplicate_a])
    assert is_valid is False
    assert any("Duplicate alternative_id" in err for err in errors)


# =============================================================================
# 2. ACTIVE CONFIGURATION VALIDATION
# =============================================================================

def test_valid_active_configuration_passes():
    val = AlternativeValidator()
    # Exactly one alternative active per group: OPT_A from dispute group, SEC_10_OPT_1 from payment group
    active_alts = [OPT_A, SEC_10_OPT_1]
    expected_groups = {
        "ALT-GCC-24.2-DISPUTE-RESOLUTION",
        "ALT-SCC-10.1-PAYMENT-TERMS"
    }

    is_valid, errors = val.validate_active_configuration(active_alts, expected_groups=expected_groups)
    assert is_valid is True
    assert len(errors) == 0


def test_multiple_active_alternatives_in_same_group_rejected():
    val = AlternativeValidator()
    # Conflict: Both OPT_A and OPT_B active simultaneously in the same contract instance
    conflicting_active = [OPT_A, OPT_B]

    is_valid, errors = val.validate_active_configuration(conflicting_active)
    assert is_valid is False
    assert any("Mutual Exclusion Conflict" in err for err in errors)
    assert any("has 2 active alternatives" in err for err in errors)


def test_missing_active_alternative_for_mandatory_group_rejected():
    val = AlternativeValidator()
    # Only dispute option selected; payment group omitted
    active_alts = [OPT_A]
    expected_groups = {
        "ALT-GCC-24.2-DISPUTE-RESOLUTION",
        "ALT-SCC-10.1-PAYMENT-TERMS"
    }

    is_valid, errors = val.validate_active_configuration(active_alts, expected_groups=expected_groups)
    assert is_valid is False
    assert any("Missing Active Alternative" in err for err in errors)
    assert any("ALT-SCC-10.1-PAYMENT-TERMS" in err for err in errors)


# =============================================================================
# 3. CANDIDATE FINDING CLAUSE ACTIVATION VALIDATION
# =============================================================================

def test_candidate_clause_activation_validation():
    val = AlternativeValidator()

    active_config = ContractConfiguration(
        configuration_id="CONFIG-001",
        contract_id="CONTRACT-DOE-GOODS-01",
        document_id="DOE-GOODS-2022-GCC",
        template_family_id="MACRO-FAM-DOE-PPD",
        active_clause_ids=["GCC-01.1", "GCC-24.2#OPT-A", "SCC-10.1#OPT-1"],
        active_alternatives={
            "ALT-GCC-24.2-DISPUTE-RESOLUTION": "GCC-24.2#OPT-A",
            "ALT-SCC-10.1-PAYMENT-TERMS": "SCC-10.1#OPT-1"
        }
    )

    all_alts = [OPT_A, OPT_B, SEC_10_OPT_1, SEC_10_OPT_2]

    # Valid candidates targeting active clauses
    valid_candidates = ["GCC-01.1", "GCC-24.2#OPT-A"]
    is_valid, errors = val.validate_candidate_clause_activation(
        valid_candidates, active_config, all_alts
    )
    assert is_valid is True
    assert len(errors) == 0

    # Invalid candidate targeting inactive alternative (OPT_B)
    invalid_candidates = ["GCC-01.1", "GCC-24.2#OPT-B"]
    is_valid, errors = val.validate_candidate_clause_activation(
        invalid_candidates, active_config, all_alts
    )
    assert is_valid is False
    assert any("Invalid Candidate Target: Clause 'GCC-24.2#OPT-B' is an inactive alternative" in err for err in errors)
