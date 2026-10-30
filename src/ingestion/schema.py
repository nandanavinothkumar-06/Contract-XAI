"""
Data models and enumeration schemas for document ingestion and extraction.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import re
from pydantic import BaseModel, Field, ConfigDict, field_validator

class DocumentFormat(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"
    UNSUPPORTED = "UNSUPPORTED"

class ExtractionMethod(str, Enum):
    TEXT_EXTRACTOR_PDF = "TEXT_EXTRACTOR_PDF"
    OCR_FALLBACK_PDF = "OCR_FALLBACK_PDF"
    DOCX_PARSER = "DOCX_PARSER"
    TXT_DECODER = "TXT_DECODER"
    UNKNOWN = "UNKNOWN"

class IngestionStatus(str, Enum):
    RECEIVED = "RECEIVED"
    EXTRACTED = "EXTRACTED"
    PREPROCESSED = "PREPROCESSED"
    SEGMENTED = "SEGMENTED"
    FAILED = "FAILED"

class ValidationResult(BaseModel):
    is_valid: bool
    format: DocumentFormat
    mime_type: str
    file_size_bytes: int
    file_sha256: str
    original_filename: str
    sanitized_filename: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class ExtractionResult(BaseModel):
    document_id: str
    extraction_method: ExtractionMethod
    raw_text: str
    page_count: int = 1
    char_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    ocr_applied: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class IngestionResult(BaseModel):
    document_id: str
    status: IngestionStatus
    validation: ValidationResult
    extraction: Optional[ExtractionResult] = None
    dataset_record_id: Optional[str] = None
    preprocessed_status: Optional[str] = None
    segment_count: int = 0
    storage_path: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    model_agreement_provenance: Optional["ModelAgreementProvenanceRecord"] = None


# =============================================================================
# STRATEGY A: MODEL COMMERCIAL AGREEMENT PROVENANCE & QUARANTINE SCHEMAS (RDR-002)
# =============================================================================

class ComponentType(str, Enum):
    """
    Standard commercial contract component type within public-sector procurement models.
    """
    GCC = "GCC"
    SCC = "SCC"
    CONTRACT_FORM = "CONTRACT_FORM"
    SLA_SCHEDULE = "SLA_SCHEDULE"
    OPERATIVE_COVENANT = "OPERATIVE_COVENANT"
    OTHER = "OTHER"


class OffsetSemantics(str, Enum):
    """
    Explicit specification of offset coordinate space.
    Python Unicode code-point character indices (Python len/slice) MUST NOT be
    conflated with UTF-8 encoded byte offsets.
    """
    PYTHON_CHAR_OFFSETS = "PYTHON_CHAR_OFFSETS"
    UTF8_BYTE_OFFSETS = "UTF8_BYTE_OFFSETS"


class ModelAgreementProvenanceRecord(BaseModel):
    """
    Provenance-preserving metadata for public-sector model commercial agreement components.
    Adheres strictly to Strategy A research decisions (RDR-002).
    """
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(
        ...,
        min_length=1,
        description="Canonical unique identifier for the source document (e.g. 'DOE-GOODS-2022-GCC')."
    )
    template_family_id: str = Field(
        ...,
        min_length=1,
        description="Macro-family identifier enforcing partition isolation (e.g. 'MACRO-FAM-DOE-PPD')."
    )
    issuing_agency: str = Field(
        ...,
        min_length=1,
        description="Official sovereign issuing body (e.g. 'Procurement Policy Division, Department of Expenditure, Ministry of Finance')."
    )
    source_pdf_sha256: str = Field(
        ...,
        description="64-character lowercase hexadecimal SHA-256 digest of the source PDF."
    )
    source_page_range: Tuple[int, int] = Field(
        ...,
        description="1-indexed physical PDF page range [start_page, end_page] where start_page <= end_page."
    )
    component_type: ComponentType = Field(
        ...,
        description="Contract component classification (GCC, SCC, CONTRACT_FORM, SLA_SCHEDULE, OPERATIVE_COVENANT)."
    )
    source_manual_title: Optional[str] = Field(
        default=None,
        description="Exact published manual title."
    )
    manual_edition_date: Optional[str] = Field(
        default=None,
        description="Official publication or revision date string."
    )
    source_landing_url: Optional[str] = Field(
        default=None,
        description="Official departmental landing page URL."
    )
    source_file_url: Optional[str] = Field(
        default=None,
        description="Direct endpoint URL for the source file."
    )
    component_sha256: Optional[str] = Field(
        default=None,
        description="Optional 64-character SHA-256 digest of the extracted raw component text."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary provenance-related attributes."
    )

    @field_validator("document_id", "template_family_id", "issuing_agency")
    @classmethod
    def validate_non_empty_stripped(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or purely whitespace.")
        return s

    @field_validator("source_pdf_sha256", "component_sha256")
    @classmethod
    def validate_sha256_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", v):
            raise ValueError(f"SHA-256 digest must be exactly 64 lowercase hexadecimal characters; received '{v}'")
        return v

    @field_validator("source_page_range")
    @classmethod
    def validate_page_range(cls, v: Tuple[int, int]) -> Tuple[int, int]:
        if len(v) != 2:
            raise ValueError("source_page_range must be a 2-tuple [start_page, end_page].")
        start, end = v
        if start < 1:
            raise ValueError(f"start_page must be >= 1 (1-indexed); received {start}.")
        if end < start:
            raise ValueError(f"end_page ({end}) cannot be less than start_page ({start}).")
        return v


class QuarantineReasonCode(str, Enum):
    """
    Explicit, auditable reason codes for quarantining corrupt, ambiguous,
    or incomplete contract clause text from the candidate generation pool.
    """
    TRUNCATED_TEXT = "TRUNCATED_TEXT"
    DANGLING_SCHEDULE_REFERENCE = "DANGLING_SCHEDULE_REFERENCE"
    UNRESOLVED_ALTERNATIVE_OPTION = "UNRESOLVED_ALTERNATIVE_OPTION"
    EMBEDDED_DRAFTING_GUIDANCE = "EMBEDDED_DRAFTING_GUIDANCE"
    BOUNDARY_AMBIGUITY = "BOUNDARY_AMBIGUITY"
    UNRESOLVED_TABLE_STRUCTURE = "UNRESOLVED_TABLE_STRUCTURE"
    UNSPECIFIED_EXTRACTION_DEFECT = "UNSPECIFIED_EXTRACTION_DEFECT"


class QuarantineEntry(BaseModel):
    """
    Structured audit record for an incomplete or ambiguous clause routed to quarantine.
    Guarantees that corrupt or incomplete elements are flagged and quarantined rather than
    silently ingested into candidate generation.
    """
    model_config = ConfigDict(extra="forbid")

    quarantine_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this quarantine event."
    )
    document_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the source document."
    )
    clause_id: Optional[str] = Field(
        default=None,
        description="Identifier of the specific clause segment, if known."
    )
    reason_code: QuarantineReasonCode = Field(
        ...,
        description="Standardized, auditable reason code for quarantine."
    )
    description: str = Field(
        ...,
        min_length=5,
        description="Detailed explanation of the boundary defect, ambiguity, or missing reference."
    )
    flagged_text_snippet: Optional[str] = Field(
        default=None,
        description="Verbatim excerpt of the problematic text."
    )
    char_start: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-indexed Python character start offset in the extracted component text."
    )
    char_end: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-indexed Python character end offset in the extracted component text."
    )
    utf8_byte_start: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-indexed UTF-8 byte start offset in the raw encoded text stream."
    )
    utf8_byte_end: Optional[int] = Field(
        default=None,
        ge=0,
        description="0-indexed UTF-8 byte end offset in the raw encoded text stream."
    )
    offset_semantics: OffsetSemantics = Field(
        default=OffsetSemantics.PYTHON_CHAR_OFFSETS,
        description="Explicitly documents whether active span coordinates represent Python characters or UTF-8 bytes."
    )
    source_page: Optional[int] = Field(
        default=None,
        ge=1,
        description="Physical 1-indexed PDF page where the defect occurs."
    )
    resolution_status: str = Field(
        default="PENDING_REVIEW",
        description="Operational resolution status ('PENDING_REVIEW', 'RESOLVED_EXCLUDED', 'RESOLVED_REPAIRED')."
    )
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the quarantine action."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary diagnostic or reviewer metadata."
    )

    @field_validator("quarantine_id", "document_id", "description")
    @classmethod
    def validate_non_empty_stripped(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or purely whitespace.")
        return s

    @field_validator("char_end")
    @classmethod
    def validate_char_spans(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None and "char_start" in info.data and info.data["char_start"] is not None:
            if v < info.data["char_start"]:
                raise ValueError(f"char_end ({v}) cannot be less than char_start ({info.data['char_start']}).")
        return v

    @field_validator("utf8_byte_end")
    @classmethod
    def validate_byte_spans(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None and "utf8_byte_start" in info.data and info.data["utf8_byte_start"] is not None:
            if v < info.data["utf8_byte_start"]:
                raise ValueError(f"utf8_byte_end ({v}) cannot be less than utf8_byte_start ({info.data['utf8_byte_start']}).")
        return v
