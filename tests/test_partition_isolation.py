"""
Unit tests for Partition Isolation Validator (Strategy A, Step 2).

Covers:
1. Disjoint, non-leaking template families pass validation.
2. Direct cross-partition template family leakage is detected and rejected.
3. MACRO-FAM-DOE-PPD allocated to Test split is rejected (feasibility pilot invariant).
4. Related DoE sub-families split across partitions (e.g. Goods in Val, Services in Test) rejected.
5. Sibling alternatives crossing partitions are detected and rejected.
6. Robust family ID extraction across dicts, Pydantic objects, and custom items.
"""

import pytest
from src.evaluation.partition_validator import (
    PartitionIsolationValidator,
    PartitionValidationResult,
)


# =============================================================================
# SYNTHETIC TEST FIXTURES
# =============================================================================

SAMPLE_VALIDATION_ITEMS = [
    {"contract_id": "C-01", "template_family_id": "MACRO-FAM-DOE-PPD"},
    {"contract_id": "C-02", "template_family_id": "MACRO-FAM-DOE-PPD"},
    {"contract_id": "C-03", "template_family_id": "MACRO-FAM-NITI-BUS"},
]

SAMPLE_TEST_ITEMS = [
    {"contract_id": "C-04", "template_family_id": "MACRO-FAM-DEA-CONCESSION"},
    {"contract_id": "C-05", "template_family_id": "MACRO-FAM-MOHUA-MSI"},
]


# =============================================================================
# TESTS
# =============================================================================

def test_clean_partition_split_succeeds():
    validator = PartitionIsolationValidator()
    result = validator.validate_partition_splits(SAMPLE_VALIDATION_ITEMS, SAMPLE_TEST_ITEMS)
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert len(result.leaked_families) == 0
    assert "MACRO-FAM-DOE-PPD" in result.validation_families
    assert "MACRO-FAM-DEA-CONCESSION" in result.test_families


def test_direct_cross_partition_leakage_detected():
    validator = PartitionIsolationValidator()
    # Contaminate test split with MACRO-FAM-NITI-BUS (present in validation)
    contaminated_test = SAMPLE_TEST_ITEMS + [
        {"contract_id": "C-06", "template_family_id": "MACRO-FAM-NITI-BUS"}
    ]
    result = validator.validate_partition_splits(SAMPLE_VALIDATION_ITEMS, contaminated_test)
    assert result.is_valid is False
    assert "MACRO-FAM-NITI-BUS" in result.leaked_families
    assert any("Cross-partition template family leakage detected" in err for err in result.errors)


def test_doe_macro_family_in_test_rejected():
    validator = PartitionIsolationValidator()
    # Attempting to allocate MACRO-FAM-DOE-PPD to test split
    invalid_test = [
        {"contract_id": "C-07", "template_family_id": "MACRO-FAM-DOE-PPD"}
    ]
    result = validator.validate_partition_splits(
        [{"contract_id": "C-08", "template_family_id": "MACRO-FAM-NITI-BUS"}],
        invalid_test
    )
    assert result.is_valid is False
    assert any("Policy Violation: 'MACRO-FAM-DOE-PPD' is allocated to Test partition" in err for err in result.errors)


def test_related_doe_subfamilies_split_across_partitions_rejected():
    validator = PartitionIsolationValidator()
    # Simulating an uncollapsed split attempt: Goods in Val, Services in Test
    uncollapsed_val = [{"contract_id": "C-09", "template_family_id": "FAM-DOE-GOODS"}]
    uncollapsed_test = [{"contract_id": "C-10", "template_family_id": "FAM-DOE-SERVICES"}]

    result = validator.validate_partition_splits(uncollapsed_val, uncollapsed_test)
    assert result.is_valid is False
    assert any("Sub-family leakage: Related DoE template families split across partitions" in err for err in result.errors)


def test_sibling_alternatives_crossing_partitions_rejected():
    validator = PartitionIsolationValidator()

    # Option A in Validation, Option B in Test for the same alternative group
    val_alts = [{"alternative_id": "GCC-24.2#OPT-A", "alternative_group_id": "ALT-GCC-24.2-DISPUTE"}]
    test_alts = [{"alternative_id": "GCC-24.2#OPT-B", "alternative_group_id": "ALT-GCC-24.2-DISPUTE"}]

    is_valid, errors = validator.validate_sibling_alternative_partitions(val_alts, test_alts)
    assert is_valid is False
    assert any("Alternative Group Leakage" in err for err in errors)


def test_sibling_alternatives_co_located_succeeds():
    validator = PartitionIsolationValidator()

    # Both Option A and Option B co-located in Validation
    val_alts = [
        {"alternative_id": "GCC-24.2#OPT-A", "alternative_group_id": "ALT-GCC-24.2-DISPUTE"},
        {"alternative_id": "GCC-24.2#OPT-B", "alternative_group_id": "ALT-GCC-24.2-DISPUTE"},
    ]
    test_alts = [
        {"alternative_id": "CONC-18.1#OPT-1", "alternative_group_id": "ALT-CONC-18.1-ARBITRATION"}
    ]

    is_valid, errors = validator.validate_sibling_alternative_partitions(val_alts, test_alts)
    assert is_valid is True
    assert len(errors) == 0


def test_family_id_extraction_support():
    validator = PartitionIsolationValidator()

    # Dict
    assert validator.extract_family_id({"template_family_id": "FAM-1"}) == "FAM-1"

    # Object with attribute
    class DummyItem:
        template_family_id = "FAM-2"
    assert validator.extract_family_id(DummyItem()) == "FAM-2"

    # Missing attribute
    assert validator.extract_family_id(object()) is None
