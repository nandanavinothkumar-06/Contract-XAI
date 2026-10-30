"""
Partition Isolation Validator for Strategy A (RDR-002).

Enforces:
1. Zero cross-partition leakage of template families:
   Families(Validation) ∩ Families(Test) == ∅.
2. MACRO-FAM-DOE-PPD allocation locking:
   Must reside exclusively in Validation/Development; prohibited from Test.
3. Sub-family leakage protection:
   Related DoE sub-families (Goods, Services, Consultancy) cannot be split across partitions.
4. Sibling alternative co-location:
   All alternatives within the same alternative_group_id must reside in the same partition.
"""

from typing import List, Dict, Any, Set, Tuple, Optional
from pydantic import BaseModel, Field


class PartitionValidationResult(BaseModel):
    is_valid: bool
    validation_families: Set[str] = Field(default_factory=set)
    test_families: Set[str] = Field(default_factory=set)
    leaked_families: Set[str] = Field(default_factory=set)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PartitionIsolationValidator:
    """
    Validates that contract evaluation partitions preserve template-family isolation
    and adhere to Strategy A governance rules.
    """
    DOE_MACRO_FAMILY = "MACRO-FAM-DOE-PPD"

    # Known uncollapsed DoE sub-family prefixes or identifiers
    DOE_RELATED_IDENTIFIERS = {
        "MACRO-FAM-DOE-PPD",
        "FAM-DOE-GOODS",
        "FAM-DOE-SERVICES",
        "FAM-DOE-NONCONSULTANCY",
        "FAM-DOE-CONSULTANCY",
        "DOE-GOODS",
        "DOE-NCS",
        "DOE-CS",
    }

    @staticmethod
    def extract_family_id(item: Any) -> Optional[str]:
        """Extracts template_family_id from dict, Pydantic model, or object."""
        if isinstance(item, dict):
            return item.get("template_family_id")
        if hasattr(item, "template_family_id"):
            return getattr(item, "template_family_id")
        return None

    def validate_partition_splits(
        self,
        validation_items: List[Any],
        test_items: List[Any],
        allow_doe_in_test: bool = False,
    ) -> PartitionValidationResult:
        """
        Validates partition isolation across validation and test sets.
        """
        errors = []
        warnings = []

        val_families = {
            self.extract_family_id(it) for it in validation_items if self.extract_family_id(it) is not None
        }
        test_families = {
            self.extract_family_id(it) for it in test_items if self.extract_family_id(it) is not None
        }

        # 1. Zero cross-partition leakage invariant
        leaked_families = val_families.intersection(test_families)
        if leaked_families:
            errors.append(
                f"Cross-partition template family leakage detected: {sorted(list(leaked_families))} "
                "present in both Validation and Test splits."
            )

        # 2. MACRO-FAM-DOE-PPD must NOT be in Test partition (feasibility pilot invariant)
        if not allow_doe_in_test and self.DOE_MACRO_FAMILY in test_families:
            errors.append(
                f"Policy Violation: '{self.DOE_MACRO_FAMILY}' is allocated to Test partition. "
                "Per RDR-002, DoE macro-family must be allocated exclusively to Validation/Development."
            )

        # 3. Check for related DoE sub-families split across partitions
        val_doe = val_families.intersection(self.DOE_RELATED_IDENTIFIERS)
        test_doe = test_families.intersection(self.DOE_RELATED_IDENTIFIERS)
        if val_doe and test_doe:
            errors.append(
                f"Sub-family leakage: Related DoE template families split across partitions "
                f"(Validation: {sorted(list(val_doe))}, Test: {sorted(list(test_doe))}). "
                "Per RDR-002, all DoE templates must collapse into MACRO-FAM-DOE-PPD and remain co-located."
            )

        is_valid = len(errors) == 0

        return PartitionValidationResult(
            is_valid=is_valid,
            validation_families=val_families,
            test_families=test_families,
            leaked_families=leaked_families,
            errors=errors,
            warnings=warnings,
        )

    def validate_sibling_alternative_partitions(
        self,
        validation_alternatives: List[Any],
        test_alternatives: List[Any],
    ) -> Tuple[bool, List[str]]:
        """
        Verifies that mutually exclusive clause alternatives belonging to the same
        alternative_group_id never cross partitions.
        """
        errors = []

        def get_group_id(it):
            if isinstance(it, dict):
                return it.get("alternative_group_id")
            return getattr(it, "alternative_group_id", None)

        val_groups = {get_group_id(it) for it in validation_alternatives if get_group_id(it) is not None}
        test_groups = {get_group_id(it) for it in test_alternatives if get_group_id(it) is not None}

        leaked_groups = val_groups.intersection(test_groups)
        if leaked_groups:
            errors.append(
                f"Alternative Group Leakage: Alternatives belonging to group(s) {sorted(list(leaked_groups))} "
                "are split across Validation and Test partitions. All sibling alternatives must remain co-located."
            )

        return len(errors) == 0, errors
