"""
Pydantic schemas and serialization models for Task 034 Final Reports and Client Feedback.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

STATUTORY_CORPUS_NOTICE = (
    "STATUTORY COVERAGE LIMITATION NOTICE: The Indian statutory citations in this report "
    "are grounded in a limited, curated set of statutory extracts (specifically covering selected "
    "provisions from Indian Contract Act, 1872; Information Technology Act, 2000; "
    "Digital Personal Data Protection Act, 2023; Specific Relief Act, 1963; "
    "Arbitration and Conciliation Act, 1996; and Bharatiya Sakshya Adhiniyam, 2023). "
    "These extracts do NOT represent complete Acts, nor does this report represent an exhaustive legal "
    "search of all applicable Central Acts, State amendments, delegated legislation, commencement notifications, "
    "or latest judicial precedents."
)

SCORE_RETRIEVAL_DISCLAIMER = (
    "Lexical BM25 and token-overlap retrieval scores reflect semantic and lexical relevance within "
    "the indexed statutory extracts. They do NOT represent a probability of legal validity, "
    "binding statutory effect, or judicial enforceability."
)

MANDATORY_LEGAL_DISCLAIMER = (
    "LEGAL NOTICE AND LIMITATION OF LIABILITY: ContractRisk-XAI is an AI-assisted legal decision-support system "
    "operating under mandatory human advocate oversight. This report reflects the professional assessment of the "
    "assigned advocate and the evidence retrieved at the time of review. This report does not certify legal compliance, "
    "guarantee statutory enforceability, or replace independent legal counsel. The ultimate legal responsibility "
    "remains with the reviewing advocate and the executing parties."
)

class StatutoryReferenceItem(BaseModel):
    act_name: str
    section: str
    title: Optional[str] = None
    excerpt: str
    source_id: str
    snapshot_version: str
    commencement_date: Optional[str] = None
    score_semantics_disclaimer: str = SCORE_RETRIEVAL_DISCLAIMER
    retrieval_caveat: Optional[str] = None


class ReviewedFindingItem(BaseModel):
    finding_id: str
    segment_id: str
    clause_heading: Optional[str] = None
    clause_numbering: Optional[str] = None
    clause_text_excerpt: str
    finding_origin: str  # AI_GENERATED vs LAWYER_AUTHORED
    risk_label: Optional[str] = None
    ai_confidence_score: Optional[str] = None
    ai_observation: Optional[str] = None
    lawyer_decision: str  # ACCEPT, CORRECT, REJECT_AI_OBSERVATION, etc.
    lawyer_decision_label: str
    lawyer_rationale: str
    statutory_references: List[StatutoryReferenceItem] = []
    is_clarification_flagged: bool = False
    is_ai_observation_rejected: bool = False


class ReportMetadata(BaseModel):
    report_id: str
    report_number: str
    report_version: int
    status: str
    is_final: bool
    document_id: str
    document_version: int
    original_filename: str
    file_sha256: str
    review_id: str
    review_completed_at: Optional[str] = None
    assigned_lawyer_id: Optional[str] = None
    assigned_lawyer_name: str
    assigned_lawyer_email: str
    bar_enrolment_id: Optional[str] = None
    state_bar_council: Optional[str] = None
    generated_at: str
    content_sha256: str
    pdf_storage_path: Optional[str] = None
    pdf_sha256: Optional[str] = None
    superseded_at: Optional[str] = None
    superseded_by_id: Optional[str] = None
    supersession_reason: Optional[str] = None


class ExecutiveSummaryData(BaseModel):
    contract_description: str
    scope_of_review: str
    key_findings_summary: str
    total_findings_count: int
    accepted_ai_findings_count: int
    corrected_findings_count: int
    rejected_ai_findings_count: int
    lawyer_authored_findings_count: int
    outstanding_limitations: Optional[str] = None
    unresolved_questions: Optional[str] = None
    further_client_action_required: bool = False


class FinalReportPayload(BaseModel):
    metadata: ReportMetadata
    executive_summary: ExecutiveSummaryData
    findings: List[ReviewedFindingItem]
    disclaimer_and_limitations: str = MANDATORY_LEGAL_DISCLAIMER
    statutory_corpus_notice: str = STATUTORY_CORPUS_NOTICE


class FeedbackSubmitRequest(BaseModel):
    overall_satisfaction: int = Field(..., ge=1, le=5, description="1 to 5 satisfaction rating")
    clarity_rating: int = Field(..., ge=1, le=5, description="1 to 5 clarity rating")
    usefulness_rating: int = Field(..., ge=1, le=5, description="1 to 5 usefulness rating")
    needs_clarification: bool = False
    follow_up_requested: bool = False
    client_comments: Optional[str] = None


class FeedbackResponseRequest(BaseModel):
    response_text: str = Field(..., min_length=1)
    is_client_visible: bool = True
    internal_notes: Optional[str] = None


class FeedbackStatusUpdateRequest(BaseModel):
    status: str
