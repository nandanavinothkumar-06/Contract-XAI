"""
Drafting Alternative Validator for Strategy A (RDR-002).

Enforces:
1. Sibling consistency across parent section, document ID, and template family ID.
2. Invariant: Exactly one active option per alternative group in any contract configuration.
3. Candidate finding origin check: candidates must only be proposed for active clauses.
"""

from typing import List, Dict, Any, Set, Tuple, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class DraftingAlternativeMetadata(BaseModel):
    """
    Metadata representation of a mutually exclusive contract clause alternative.
    """
    model_config = ConfigDict(extra="forbid")

    alternative_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this specific clause alternative (e.g. 'GCC-24.2#OPT-A')."
    )
    alternative_group_id: str = Field(
        ...,
        min_length=1,
        description="Common identifier grouping mutually exclusive alternatives (e.g. 'ALT-GCC-24.2-DISPUTE-RES')."
    )
    parent_section_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the common parent contract section (e.g. 'GCC-24.2')."
    )
    document_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the parent source document (e.g. 'DOE-GOODS-2022-GCC')."
    )
    template_family_id: str = Field(
        ...,
        min_length=1,
        description="Macro-family identifier (e.g. 'MACRO-FAM-DOE-PPD')."
    )
    is_drafting_alternative: bool = Field(
        default=True,
        description="Flag denoting that this clause is a mutually exclusive option."
    )
    selection_instruction: Optional[str] = Field(
        default=None,
        description="Optional instructional text for procuring entity."
    )
    clause_text: Optional[str] = Field(
        default=None,
        description="Optional text of the alternative clause."
    )

    @field_validator("alternative_id", "alternative_group_id", "parent_section_id", "document_id", "template_family_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or purely whitespace.")
        return s


class ContractConfiguration(BaseModel):
    """
    Instantiated contract configuration representing an evaluable document configuration.
    """
    model_config = ConfigDict(extra="forbid")

    configuration_id: str = Field(..., min_length=1)
    contract_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    template_family_id: str = Field(..., min_length=1)
    active_clause_ids: List[str] = Field(default_factory=list)
    # Mapping from alternative_group_id -> active alternative_id
    active_alternatives: Dict[str, str] = Field(default_factory=dict)


class AlternativeValidator:
    """
    Validates drafting alternatives and contract configuration invariants.
    """

    @staticmethod
    def validate_sibling_alternatives(
        alternatives: List[DraftingAlternativeMetadata]
    ) -> Tuple[bool, List[str]]:
        """
        Validates that all alternatives belonging to the same group share identical
        provenance, section IDs, and unique alternative IDs.
        """
        errors = []
        if not alternatives:
            errors.append("Alternative list cannot be empty")
            return False, errors

        groups: Dict[str, List[DraftingAlternativeMetadata]] = {}
        for alt in alternatives:
            groups.setdefault(alt.alternative_group_id, []).append(alt)

        for group_id, alts in groups.items():
            if len(alts) < 2:
                errors.append(
                    f"Group '{group_id}' contains only {len(alts)} alternative(s). "
                    "Mutually exclusive alternative groups must contain at least 2 distinct options."
                )

            first = alts[0]
            alt_ids_seen = set()

            for alt in alts:
                # Unique alternative IDs within group
                if alt.alternative_id in alt_ids_seen:
                    errors.append(
                        f"Duplicate alternative_id '{alt.alternative_id}' within group '{group_id}'"
                    )
                alt_ids_seen.add(alt.alternative_id)

                # Lineage consistency
                if alt.parent_section_id != first.parent_section_id:
                    errors.append(
                        f"Mismatched parent_section_id in group '{group_id}': "
                        f"'{alt.parent_section_id}' vs expected '{first.parent_section_id}'"
                    )
                if alt.document_id != first.document_id:
                    errors.append(
                        f"Mismatched document_id in group '{group_id}': "
                        f"'{alt.document_id}' vs expected '{first.document_id}'"
                    )
                if alt.template_family_id != first.template_family_id:
                    errors.append(
                        f"Mismatched template_family_id in group '{group_id}': "
                        f"'{alt.template_family_id}' vs expected '{first.template_family_id}'"
                    )

        return len(errors) == 0, errors

    @staticmethod
    def validate_active_configuration(
        active_alternatives: List[DraftingAlternativeMetadata],
        expected_groups: Optional[Set[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Enforces the Strategy A invariant: exactly one active option per alternative group.
        """
        errors = []
        group_counts: Dict[str, List[str]] = {}

        for alt in active_alternatives:
            group_counts.setdefault(alt.alternative_group_id, []).append(alt.alternative_id)

        # Check for multiple active options in the same group (CONFLICT)
        for group_id, alt_ids in group_counts.items():
            if len(alt_ids) > 1:
                errors.append(
                    f"Mutual Exclusion Conflict: Group '{group_id}' has {len(alt_ids)} active alternatives: "
                    f"{alt_ids}. Exactly one active alternative is permitted per contract configuration."
                )

        # Check for missing active options if expected_groups is provided
        if expected_groups:
            active_group_ids = set(group_counts.keys())
            missing_groups = expected_groups - active_group_ids
            if missing_groups:
                errors.append(
                    f"Missing Active Alternative: Expected active option for group(s) "
                    f"{sorted(list(missing_groups))}, but none was selected."
                )

        return len(errors) == 0, errors

    @staticmethod
    def validate_candidate_clause_activation(
        candidate_clause_ids: List[str],
        active_config: ContractConfiguration,
        all_alternatives: List[DraftingAlternativeMetadata]
    ) -> Tuple[bool, List[str]]:
        """
        Verifies that candidate findings are proposed ONLY on active clauses.
        If a candidate is proposed on an inactive alternative option, it is rejected.
        """
        errors = []
        alt_to_group = {alt.alternative_id: alt.alternative_group_id for alt in all_alternatives}
        active_alt_ids = set(active_config.active_alternatives.values())

        for cid in candidate_clause_ids:
            if cid in alt_to_group:
                # It is an alternative option
                if cid not in active_alt_ids:
                    group_id = alt_to_group[cid]
                    active_for_group = active_config.active_alternatives.get(group_id, "NONE")
                    errors.append(
                        f"Invalid Candidate Target: Clause '{cid}' is an inactive alternative in group '{group_id}' "
                        f"(Active alternative is '{active_for_group}'). Candidates cannot be evaluated on inactive options."
                    )

        return len(errors) == 0, errors
