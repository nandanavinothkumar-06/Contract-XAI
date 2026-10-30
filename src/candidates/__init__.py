"""
Candidate Generation and Provenance Subsystem for CONTRACTRISK-XAI.
"""

from src.candidates.schema import (
    CandidateFindingRecord,
    ConfidenceSemantics,
    CandidateOrigin,
    VersionConsistencyStatus,
    LabelMappingStatus,
    DuplicateFindingEntry,
)
from src.candidates.deduplication import (
    compute_deduplication_key,
    deduplicate_candidates,
    normalize_finding_text,
)
from src.candidates.pipeline import (
    CandidateGenerationPipeline,
    generate_deterministic_finding_id,
    VALID_INDIAN_RISK_CATEGORIES,
)
from src.candidates.alternative_validator import (
    DraftingAlternativeMetadata,
    ContractConfiguration,
    AlternativeValidator,
)

__all__ = [
    "CandidateFindingRecord",
    "ConfidenceSemantics",
    "CandidateOrigin",
    "VersionConsistencyStatus",
    "LabelMappingStatus",
    "DuplicateFindingEntry",
    "compute_deduplication_key",
    "deduplicate_candidates",
    "normalize_finding_text",
    "CandidateGenerationPipeline",
    "generate_deterministic_finding_id",
    "VALID_INDIAN_RISK_CATEGORIES",
    "DraftingAlternativeMetadata",
    "ContractConfiguration",
    "AlternativeValidator",
]

