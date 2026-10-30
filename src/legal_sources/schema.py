from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from src.legal_sources.provenance import (
    VerificationStatus,
    SourceCompletenessStatus,
    AmendmentCoverageStatus,
    VerificationMethod,
    SourceType,
    RetrievalMethod,
    LegalSourceErrorStatus,
    JurisdictionLevel,
    CurrentnessStatus,
    CommencementStatus,
)

class LegalSource(BaseModel):
    source_id: str
    canonical_title: Optional[str] = None
    title: str = ""
    short_title: Optional[str] = None
    act_number: Optional[str] = None
    jurisdiction: str = "India - Central"
    jurisdiction_level: JurisdictionLevel = JurisdictionLevel.UNKNOWN
    country: str = "IN"
    instrument_type: Optional[str] = None
    source_type: SourceType = SourceType.STATUTE
    issuing_authority: Optional[str] = None
    publisher: str = "Government of India"
    authoritative_source_url: Optional[str] = None
    official_url: Optional[str] = None
    source_file: Optional[str] = None
    source_snapshot_path: Optional[str] = None
    source_format: str = "txt"
    source_language: str = "en"
    language: str = "en"
    source_scope: Optional[str] = None
    covered_sections_or_provisions: List[str] = Field(default_factory=list)
    publication_or_version_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_verified_at: Optional[str] = None
    verification_status: VerificationStatus
    verification_method: Optional[VerificationMethod] = None
    verification_notes: Optional[str] = None
    source_sha256: Optional[str] = None
    content_checksum_sha256: Optional[str] = None
    authoritative_reference_sha256: Optional[str] = None
    source_completeness_status: SourceCompletenessStatus = SourceCompletenessStatus.CURATED_EXTRACT
    amendment_coverage_status: AmendmentCoverageStatus = AmendmentCoverageStatus.UNKNOWN
    commencement_status: CommencementStatus = CommencementStatus.UNKNOWN
    applicability_limitations: Optional[str] = None
    reviewer_status: Optional[str] = None
    reviewer_notes: Optional[str] = None
    currentness_status: CurrentnessStatus = CurrentnessStatus.UNKNOWN
    effective_date: Optional[str] = None
    enactment_date: Optional[str] = None
    commencement_date: Optional[str] = None
    retrieved_at: Optional[str] = None
    version_identifier: Optional[str] = None
    reviewed_by_human: bool = False
    reviewer_id: Optional[str] = None
    review_timestamp: Optional[str] = None
    extraction_method: Optional[str] = None
    extraction_warnings: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    enabled: bool = True
    is_test_fixture: bool = False

    @model_validator(mode="before")
    @classmethod
    def sync_backward_compatible_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Title sync
            if not values.get("canonical_title") and values.get("title"):
                values["canonical_title"] = values["title"]
            elif not values.get("title") and values.get("canonical_title"):
                values["title"] = values["canonical_title"]

            # Publisher / Issuing Authority sync
            if not values.get("issuing_authority") and values.get("publisher"):
                values["issuing_authority"] = values["publisher"]
            elif not values.get("publisher") and values.get("issuing_authority"):
                values["publisher"] = values["issuing_authority"]

            # Official URL sync
            if not values.get("authoritative_source_url") and values.get("official_url"):
                values["authoritative_source_url"] = values["official_url"]
            elif not values.get("official_url") and values.get("authoritative_source_url"):
                values["official_url"] = values["authoritative_source_url"]

            # Source file / snapshot path sync
            file_val = values.get("source_file") or values.get("snapshot_file") or values.get("source_snapshot_path")
            if file_val:
                if not values.get("source_file"):
                    values["source_file"] = file_val
                if not values.get("source_snapshot_path"):
                    values["source_snapshot_path"] = file_val

            # Language sync
            if not values.get("source_language") and values.get("language"):
                values["source_language"] = values["language"]
            elif not values.get("language") and values.get("source_language"):
                values["language"] = values["source_language"]

            # Dates sync
            if not values.get("publication_or_version_date"):
                values["publication_or_version_date"] = values.get("enactment_date") or values.get("version_identifier")
            if not values.get("effective_from"):
                values["effective_from"] = values.get("commencement_date") or values.get("effective_date")
            if not values.get("effective_date") and values.get("effective_from"):
                values["effective_date"] = values["effective_from"]

            # Checksum sync
            sha_val = values.get("source_sha256") or values.get("content_checksum_sha256")
            if sha_val:
                values["source_sha256"] = sha_val
                values["content_checksum_sha256"] = sha_val

            # Notes sync
            if not values.get("verification_notes") and values.get("notes"):
                values["verification_notes"] = values["notes"]
            elif not values.get("notes") and values.get("verification_notes"):
                values["notes"] = values["verification_notes"]

            # Instrument type sync
            if not values.get("instrument_type"):
                st = values.get("source_type")
                values["instrument_type"] = st.value if hasattr(st, "value") else str(st or "STATUTE")

            # Reviewer status sync
            if not values.get("reviewer_status"):
                if values.get("reviewed_by_human"):
                    values["reviewer_status"] = "ADVOCATE_REVIEWED"
                else:
                    values["reviewer_status"] = "PENDING_REVIEW"
        return values

class LegalPassage(BaseModel):
    passage_id: str
    source_id: str
    legal_document_id: str
    statute_title: Optional[str] = None
    section_identifier: Optional[str] = None
    section_number: Optional[str] = None
    subsection_identifier: Optional[str] = None
    heading: Optional[str] = None
    passage_text: str
    normalized_text: Optional[str] = None
    passage_start: Optional[int] = None
    passage_end: Optional[int] = None
    passage_checksum_sha256: Optional[str] = None
    citation_string: Optional[str] = None
    currentness_status: CurrentnessStatus = CurrentnessStatus.UNKNOWN
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    commencement_status: CommencementStatus = CommencementStatus.UNKNOWN
    extraction_warnings: List[str] = Field(default_factory=list)
    is_test_fixture: bool = False

class LegalSourceQuery(BaseModel):
    query_id: str
    query_text: str
    source_document_id: Optional[str] = None
    clause_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    jurisdiction_level: Optional[JurisdictionLevel] = None
    country: Optional[str] = None
    source_types: Optional[List[SourceType]] = None
    domain: Optional[str] = None
    requested_top_k: int = 5
    minimum_score: Optional[float] = None
    exact_section_filter: Optional[str] = None
    created_at: str
    configuration_version: str = "1.0.0"

class LegalSourceRetrievalResult(BaseModel):
    result_id: str
    query_id: str
    source_id: str
    source_title: str
    source_type: SourceType
    jurisdiction: str
    jurisdiction_level: JurisdictionLevel
    verification_status: VerificationStatus
    currentness_status: CurrentnessStatus
    legal_document_id: str
    section_identifier: Optional[str] = None
    section_number: Optional[str] = None
    subsection_identifier: Optional[str] = None
    heading: Optional[str] = None
    passage_text: str
    passage_start: Optional[int] = None
    passage_end: Optional[int] = None
    similarity_score: float
    rank: int
    retrieval_method: RetrievalMethod
    official_url: Optional[str] = None
    effective_date: Optional[str] = None
    version_identifier: Optional[str] = None
    retrieved_at: Optional[str] = None
    citation_string: Optional[str] = None
    commencement_status: Optional[CommencementStatus] = None
    score_explanation: Optional[str] = None
    contract_source_document_id: Optional[str] = None
    contract_clause_id: Optional[str] = None
    reviewed_by_human: bool = True
    is_test_fixture: bool = False

class RetrievedLegalEvidence(BaseModel):
    evidence_id: str
    clause_id: Optional[str] = None
    clause_text: str
    status: str  # "EVIDENCE_FOUND" or "ABSTAIN"
    passages: List[LegalSourceRetrievalResult] = Field(default_factory=list)
    abstention_reason: Optional[LegalSourceErrorStatus] = None
    requires_lawyer_review: bool = True
    disclaimer: str = (
        "Retrieved statutory passages represent potentially relevant legal references "
        "for independent human legal review. This automated retrieval does not constitute "
        "definitive legal advice, statutory interpretation, or a determination of clause "
        "validity or enforceability."
    )
    evaluated_at: str

