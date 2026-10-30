"""
SQLAlchemy ORM models for document ingestion, text snapshots, segmented clauses,
persistent cryptographic audit logs, and user identity/RBAC/advocate verification (Task 031).
"""

import datetime
from enum import Enum
from sqlalchemy import (
    Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from src.persistence.database import Base

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class UserRole(str, Enum):
    CLIENT = "CLIENT"
    LAWYER = "LAWYER"
    SUPERVISING_LAWYER = "SUPERVISING_LAWYER"
    AUDITOR = "AUDITOR"

class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"

class AdvocateStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"

class ReviewStatus(str, Enum):
    DOCUMENT_SUBMITTED = "DOCUMENT_SUBMITTED"
    PROCESSING = "PROCESSING"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    AWAITING_LAWYER_ASSIGNMENT = "AWAITING_LAWYER_ASSIGNMENT"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    CLIENT_RESPONSE_RECEIVED = "CLIENT_RESPONSE_RECEIVED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REVIEW_REOPENED = "REVIEW_REOPENED"

class LawyerDecisionType(str, Enum):
    ACCEPT_AI_OBSERVATION = "ACCEPT_AI_OBSERVATION"
    CORRECT_AI_OBSERVATION = "CORRECT_AI_OBSERVATION"
    REJECT_AI_OBSERVATION = "REJECT_AI_OBSERVATION"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    NOT_APPLICABLE_TO_REVIEW = "NOT_APPLICABLE_TO_REVIEW"
    REQUIRES_CLIENT_CLARIFICATION = "REQUIRES_CLIENT_CLARIFICATION"

class FindingOrigin(str, Enum):
    AI_GENERATED = "AI_GENERATED"
    LAWYER_AUTHORED = "LAWYER_AUTHORED"

class EvidenceQualityStatus(str, Enum):
    TRACEABLE = "TRACEABLE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    NO_MATCHING_EVIDENCE = "NO_MATCHING_EVIDENCE"

class CommentVisibility(str, Enum):
    INTERNAL_LAWYER_ONLY = "INTERNAL_LAWYER_ONLY"
    CLIENT_VISIBLE = "CLIENT_VISIBLE"
    CLARIFICATION_REQUEST = "CLARIFICATION_REQUEST"
    CLIENT_RESPONSE = "CLIENT_RESPONSE"

class RevisionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

class ReportStatus(str, Enum):
    DRAFT = "DRAFT"
    FINAL = "FINAL"
    SUPERSEDED = "SUPERSEDED"

class FeedbackStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESPONSE_REQUIRED = "RESPONSE_REQUIRED"
    RESPONDED = "RESPONDED"
    CLOSED = "CLOSED"

class AnnotationStage(str, Enum):
    FULL_RECORD = "FULL_RECORD"
    STAGE_1_PREDICTION = "STAGE_1_PREDICTION"
    STAGE_2_SUPPORT = "STAGE_2_SUPPORT"
    STAGE_3_SUFFICIENCY = "STAGE_3_SUFFICIENCY"
    STAGE_4_SOURCE = "STAGE_4_SOURCE"
    STAGE_5_VERSION = "STAGE_5_VERSION"
    STAGE_6_DISPOSITION = "STAGE_6_DISPOSITION"
    STAGE_7_PEER_INDEPENDENT = "STAGE_7_PEER_INDEPENDENT"
    STAGE_8_ADJUDICATION = "STAGE_8_ADJUDICATION"

class AdjudicationStatus(str, Enum):
    PENDING_SUBMISSIONS = "PENDING_SUBMISSIONS"
    READY_FOR_ADJUDICATION = "READY_FOR_ADJUDICATION"
    CONSENSUS_REACHED = "CONSENSUS_REACHED"
    ADJUDICATED = "ADJUDICATED"


class UserRecord(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)  # UUID
    email = Column(String(255), nullable=False, unique=True, index=True)  # Normalized lowercase
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default=UserRole.CLIENT.value, index=True)
    account_status = Column(String(32), nullable=False, default=AccountStatus.ACTIVE.value, index=True)
    advocate_status = Column(String(32), nullable=False, default=AdvocateStatus.NOT_APPLICABLE.value, index=True)
    full_name = Column(String(255), nullable=False)
    
    # Advocate verification metadata
    bar_enrolment_id = Column(String(128), nullable=True, index=True)
    state_bar_council = Column(String(128), nullable=True)
    year_of_enrolment = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owned_documents = relationship(
        "DocumentRecord",
        foreign_keys="DocumentRecord.owner_id",
        back_populates="owner"
    )
    assigned_documents = relationship(
        "DocumentRecord",
        foreign_keys="DocumentRecord.assigned_lawyer_id",
        back_populates="assigned_lawyer"
    )
    verification_requests = relationship(
        "AdvocateVerificationRecord",
        foreign_keys="AdvocateVerificationRecord.user_id",
        back_populates="applicant",
        cascade="all, delete-orphan"
    )
    assigned_reviews = relationship(
        "ReviewRecord",
        foreign_keys="ReviewRecord.assigned_lawyer_id",
        back_populates="assigned_lawyer"
    )
    generated_reports = relationship(
        "FinalReportRecord",
        foreign_keys="FinalReportRecord.generated_by_id",
        back_populates="generated_by"
    )
    client_feedbacks = relationship(
        "ClientFeedbackRecord",
        foreign_keys="ClientFeedbackRecord.client_id",
        back_populates="client"
    )
    sessions = relationship(
        "UserSessionRecord",
        foreign_keys="UserSessionRecord.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    blinded_annotations = relationship(
        "BlindedAnnotationRecord",
        foreign_keys="BlindedAnnotationRecord.annotator_id",
        back_populates="annotator",
        cascade="all, delete-orphan"
    )
    blinded_adjudications = relationship(
        "BlindedAdjudicationRecord",
        foreign_keys="BlindedAdjudicationRecord.adjudicator_id",
        back_populates="adjudicator"
    )


class AdvocateVerificationRecord(Base):
    __tablename__ = "advocate_verifications"

    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bar_enrolment_id = Column(String(128), nullable=False)
    state_bar_council = Column(String(128), nullable=False)
    year_of_enrolment = Column(Integer, nullable=False)
    
    status = Column(String(32), nullable=False, default=AdvocateStatus.PENDING_VERIFICATION.value, index=True)
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_rationale = Column(Text, nullable=True)
    evidence_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    applicant = relationship("UserRecord", foreign_keys=[user_id], back_populates="verification_requests")
    reviewer = relationship("UserRecord", foreign_keys=[reviewer_id])


class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)  # UUID
    file_sha256 = Column(String(64), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    sanitized_filename = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=False)
    document_format = Column(String(32), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    
    # Multi-tenant and lawyer assignment foreign keys (nullable for backwards compatibility)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_lawyer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    status = Column(String(32), nullable=False, default="RECEIVED", index=True)
    extraction_method = Column(String(64), nullable=True)
    page_count = Column(Integer, default=1)
    char_count = Column(Integer, default=0)
    ocr_applied = Column(Boolean, default=False)
    
    warnings_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owner = relationship("UserRecord", foreign_keys=[owner_id], back_populates="owned_documents")
    assigned_lawyer = relationship("UserRecord", foreign_keys=[assigned_lawyer_id], back_populates="assigned_documents")
    
    text_snapshots = relationship("ExtractedTextSnapshot", back_populates="document", cascade="all, delete-orphan")
    segments = relationship("SegmentRecord", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("IngestionJob", back_populates="document", cascade="all, delete-orphan")
    audit_events = relationship("AuditEventRecord", back_populates="document", cascade="all, delete-orphan")
    reviews = relationship("ReviewRecord", back_populates="document", cascade="all, delete-orphan")
    revisions = relationship("DocumentRevisionRecord", back_populates="document", cascade="all, delete-orphan")
    reports = relationship("FinalReportRecord", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_sha256_status", "file_sha256", "status"),
        Index("ix_documents_owner_status", "owner_id", "status"),
    )


class ExtractedTextSnapshot(Base):
    __tablename__ = "extracted_text_snapshots"

    id = Column(String(36), primary_key=True)  # UUID
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False)
    text_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    document = relationship("DocumentRecord", back_populates="text_snapshots")


class SegmentRecord(Base):
    __tablename__ = "segmented_clauses"

    id = Column(String(36), primary_key=True)  # UUID
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_id = Column(String(64), nullable=False, index=True)  # Segment ID from SegmentationPipeline
    parent_segment_id = Column(String(64), nullable=True)
    segment_type = Column(String(64), nullable=False)  # CLAUSE, SECTION_HEADING, etc.
    
    text = Column(Text, nullable=False)
    original_start = Column(Integer, nullable=False)
    original_end = Column(Integer, nullable=False)
    
    heading = Column(String(255), nullable=True)
    numbering = Column(String(64), nullable=True)
    level = Column(Integer, default=0)
    sequence = Column(Integer, default=0)
    path = Column(String(255), default="")
    metadata_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)

    document = relationship("DocumentRecord", back_populates="segments")

    __table_args__ = (
        Index("ix_segments_doc_seq", "document_id", "sequence"),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True)  # UUID
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    job_status = Column(String(32), nullable=False, default="PENDING")
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_details = Column(Text, nullable=True)

    document = relationship("DocumentRecord", back_populates="jobs")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True)  # UUID
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    timestamp = Column(String(64), nullable=False)
    actor_type = Column(String(32), nullable=False)
    
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    document = relationship("DocumentRecord", back_populates="audit_events")


# =============================================================================
# TASK 033: COLLABORATIVE LAWYER REVIEW WORKBENCH MODELS
# =============================================================================

class ReviewRecord(Base):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True)  # UUID
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version = Column(Integer, default=1, nullable=False)
    status = Column(String(32), nullable=False, default=ReviewStatus.DOCUMENT_SUBMITTED.value, index=True)
    
    assigned_lawyer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    
    completed_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completion_summary = Column(Text, nullable=True)
    outstanding_limitations = Column(Text, nullable=True)
    unresolved_questions = Column(Text, nullable=True)
    further_client_action_required = Column(Boolean, default=False)
    disclaimer_text = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    document = relationship("DocumentRecord", back_populates="reviews")
    assigned_lawyer = relationship("UserRecord", foreign_keys=[assigned_lawyer_id], back_populates="assigned_reviews")
    assigned_by = relationship("UserRecord", foreign_keys=[assigned_by_id])
    completed_by = relationship("UserRecord", foreign_keys=[completed_by_id])
    
    findings = relationship("ClauseFindingRecord", back_populates="review", cascade="all, delete-orphan")
    comments = relationship("ReviewCommentRecord", back_populates="review", cascade="all, delete-orphan")
    revisions = relationship("DocumentRevisionRecord", back_populates="review", cascade="all, delete-orphan")
    transitions = relationship("ReviewStateTransitionRecord", back_populates="review", cascade="all, delete-orphan")
    reports = relationship("FinalReportRecord", back_populates="review", cascade="all, delete-orphan")


class ReviewStateTransitionRecord(Base):
    __tablename__ = "review_state_transitions"

    id = Column(String(36), primary_key=True)  # UUID
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    from_state = Column(String(32), nullable=False)
    to_state = Column(String(32), nullable=False)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    review = relationship("ReviewRecord", back_populates="transitions")
    actor = relationship("UserRecord", foreign_keys=[actor_id])


class ClauseFindingRecord(Base):
    __tablename__ = "clause_findings"

    id = Column(String(36), primary_key=True)  # UUID
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_id = Column(String(64), nullable=False, index=True)  # Links to SegmentRecord.segment_id
    document_version = Column(Integer, default=1, nullable=False)
    
    finding_origin = Column(String(32), nullable=False, default=FindingOrigin.AI_GENERATED.value)  # AI_GENERATED vs LAWYER_AUTHORED
    risk_label = Column(String(64), nullable=True)
    ai_confidence_score = Column(String(32), nullable=True)
    ai_observation = Column(Text, nullable=True)
    
    decision = Column(String(32), nullable=True)  # LawyerDecisionType
    lawyer_rationale = Column(Text, nullable=True)
    lawyer_notes = Column(Text, nullable=True)
    
    statutory_evidence_json = Column(Text, nullable=True)  # Serialized list/dict of retrieved legal evidence
    ai_metadata_json = Column(Text, nullable=True)  # Serialized model identity, version, raw logits, calibrated threshold, disclaimer
    model_attribution_json = Column(Text, nullable=True)  # Serialized Gradient X Input token attribution spans & research warning
    evidence_quality_status = Column(String(32), nullable=True, default=EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value)
    is_disclosed_to_client = Column(Boolean, default=False, nullable=False)
    
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    review = relationship("ReviewRecord", back_populates="findings")
    document = relationship("DocumentRecord")
    author = relationship("UserRecord", foreign_keys=[author_id])


class ReviewCommentRecord(Base):
    __tablename__ = "review_comments"

    id = Column(String(36), primary_key=True)  # UUID
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_id = Column(String(64), nullable=True, index=True)
    finding_id = Column(String(36), ForeignKey("clause_findings.id", ondelete="SET NULL"), nullable=True)
    
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    author_role = Column(String(32), nullable=False)
    author_name = Column(String(255), nullable=False)
    
    visibility = Column(String(32), nullable=False, default=CommentVisibility.INTERNAL_LAWYER_ONLY.value)
    comment_text = Column(Text, nullable=False)
    parent_comment_id = Column(String(36), ForeignKey("review_comments.id", ondelete="SET NULL"), nullable=True)
    
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    review = relationship("ReviewRecord", back_populates="comments")
    author = relationship("UserRecord", foreign_keys=[author_id])
    finding = relationship("ClauseFindingRecord")
    parent = relationship("ReviewCommentRecord", remote_side=[id])
    resolved_by = relationship("UserRecord", foreign_keys=[resolved_by_id])


class DocumentRevisionRecord(Base):
    __tablename__ = "document_revisions"

    id = Column(String(36), primary_key=True)  # UUID
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    
    revision_status = Column(String(32), nullable=False, default=RevisionStatus.PROPOSED.value)  # PROPOSED, ACCEPTED, REJECTED, SUPERSEDED
    original_file_sha256 = Column(String(64), nullable=False)
    revised_text = Column(Text, nullable=False)
    revised_text_sha256 = Column(String(64), nullable=False)
    
    diff_summary = Column(Text, nullable=True)
    change_reason = Column(Text, nullable=True)
    
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    decided_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    document = relationship("DocumentRecord", back_populates="revisions")
    review = relationship("ReviewRecord", back_populates="revisions")
    author = relationship("UserRecord", foreign_keys=[author_id])
    decided_by = relationship("UserRecord", foreign_keys=[decided_by_id])


# =============================================================================
# TASK 034: FINAL LAWYER-REVIEWED REPORTS AND CLIENT FEEDBACK MODELS
# =============================================================================

class FinalReportRecord(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True)  # UUID
    report_number = Column(String(64), nullable=False, unique=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version = Column(Integer, default=1, nullable=False)
    report_version = Column(Integer, default=1, nullable=False)
    
    status = Column(String(32), nullable=False, default=ReportStatus.FINAL.value, index=True)
    is_final = Column(Boolean, default=True, nullable=False)
    
    generated_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_at = Column(DateTime, default=utcnow, nullable=False)
    
    title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=True)
    scope_of_review = Column(Text, nullable=True)
    review_outcome_summary = Column(Text, nullable=True)
    outstanding_limitations = Column(Text, nullable=True)
    disclaimer_text = Column(Text, nullable=False)
    statutory_corpus_version = Column(String(64), nullable=True)
    
    # Immutable JSON snapshot of findings, evidence references, and metadata
    report_payload_json = Column(Text, nullable=False)
    content_sha256 = Column(String(64), nullable=False, index=True)
    
    # PDF export artifact details
    pdf_storage_path = Column(String(512), nullable=True)
    pdf_sha256 = Column(String(64), nullable=True)
    pdf_file_size_bytes = Column(Integer, nullable=True)
    pdf_generated_at = Column(DateTime, nullable=True)
    
    # Versioning & Traceability
    superseded_at = Column(DateTime, nullable=True)
    superseded_by_id = Column(String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    supersession_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    document = relationship("DocumentRecord", back_populates="reports")
    review = relationship("ReviewRecord", back_populates="reports")
    generated_by = relationship("UserRecord", foreign_keys=[generated_by_id], back_populates="generated_reports")
    feedback = relationship("ClientFeedbackRecord", back_populates="report", cascade="all, delete-orphan")
    superseded_by = relationship("FinalReportRecord", remote_side=[id])

    __table_args__ = (
        Index("ix_reports_doc_version", "document_id", "document_version", "report_version"),
        Index("ix_reports_review_status", "review_id", "status"),
    )


class ClientFeedbackRecord(Base):
    __tablename__ = "client_feedback"

    id = Column(String(36), primary_key=True)  # UUID
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(String(32), nullable=False, default=FeedbackStatus.SUBMITTED.value, index=True)
    
    overall_satisfaction = Column(Integer, nullable=False)  # 1 to 5
    clarity_rating = Column(Integer, nullable=False)        # 1 to 5
    usefulness_rating = Column(Integer, nullable=False)     # 1 to 5
    
    needs_clarification = Column(Boolean, default=False, nullable=False)
    follow_up_requested = Column(Boolean, default=False, nullable=False)
    client_comments = Column(Text, nullable=True)
    
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    report = relationship("FinalReportRecord", back_populates="feedback")
    document = relationship("DocumentRecord")
    review = relationship("ReviewRecord")
    client = relationship("UserRecord", foreign_keys=[client_id], back_populates="client_feedbacks")
    responses = relationship("FeedbackResponseRecord", back_populates="feedback", cascade="all, delete-orphan")


class FeedbackResponseRecord(Base):
    __tablename__ = "feedback_responses"

    id = Column(String(36), primary_key=True)  # UUID
    feedback_id = Column(String(36), ForeignKey("client_feedback.id", ondelete="CASCADE"), nullable=False, index=True)
    responder_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    responder_role = Column(String(32), nullable=False)
    
    response_text = Column(Text, nullable=False)
    is_client_visible = Column(Boolean, default=True, nullable=False)
    internal_notes = Column(Text, nullable=True)  # Internal notes hidden from client
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    feedback = relationship("ClientFeedbackRecord", back_populates="responses")
    responder = relationship("UserRecord", foreign_keys=[responder_id])


# =============================================================================
# TASK 036: PERSISTENT AUTHENTICATION & SECURE SESSION REGISTRY
# =============================================================================

class UserSessionRecord(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 of session ID / jti
    
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(64), nullable=True)  # LOGOUT, EXPIRED, PASSWORD_CHANGED, ACCOUNT_SUSPENDED
    
    remember_me = Column(Boolean, default=False, nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_activity_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    user = relationship("UserRecord", back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_revoked"),
    )


# =============================================================================
# STRATEGY A: BLINDED ANNOTATION & INDEPENDENT STORAGE MODELS
# =============================================================================

class BlindedAnnotationRecord(Base):
    __tablename__ = "blinded_annotations"

    id = Column(String(36), primary_key=True)  # UUID
    candidate_finding_id = Column(String(64), nullable=False, index=True)
    contract_id = Column(String(64), nullable=False, index=True)
    clause_id = Column(String(64), nullable=False, index=True)
    annotator_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    stage = Column(String(32), nullable=False, default=AnnotationStage.FULL_RECORD.value, index=True)
    version = Column(Integer, default=1, nullable=False)

    is_locked = Column(Boolean, default=False, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    payload_sha256 = Column(String(64), nullable=False, index=True)

    reference_action = Column(String(32), nullable=True)  # RETAIN, WITHHOLD, HUMAN_REVIEW_REQUIRED, NOT_ASSESSABLE
    is_synthetic_fixture = Column(Boolean, default=False, nullable=False)

    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    locked_at = Column(DateTime, nullable=True)

    superseded_by_id = Column(String(36), ForeignKey("blinded_annotations.id", ondelete="SET NULL"), nullable=True)
    supersession_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    annotator = relationship("UserRecord", back_populates="blinded_annotations")
    superseded_by = relationship("BlindedAnnotationRecord", remote_side=[id])

    __table_args__ = (
        Index("ix_blinded_annotation_unique_active", "candidate_finding_id", "annotator_id", "stage", "version", unique=True),
        Index("ix_blinded_annotation_candidate_stage", "candidate_finding_id", "stage", "is_locked"),
    )


class BlindedAdjudicationRecord(Base):
    __tablename__ = "blinded_adjudications"

    id = Column(String(36), primary_key=True)  # UUID
    candidate_finding_id = Column(String(64), nullable=False, unique=True, index=True)
    contract_id = Column(String(64), nullable=False, index=True)
    clause_id = Column(String(64), nullable=False, index=True)

    annotator_1_submission_id = Column(String(36), ForeignKey("blinded_annotations.id", ondelete="SET NULL"), nullable=True)
    annotator_2_submission_id = Column(String(36), ForeignKey("blinded_annotations.id", ondelete="SET NULL"), nullable=True)
    adjudicator_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(32), nullable=False, default=AdjudicationStatus.PENDING_SUBMISSIONS.value, index=True)

    adjudication_payload_json = Column(Text, nullable=True)
    adjudicator_rationale = Column(Text, nullable=True)
    final_disposition = Column(String(32), nullable=True)  # RETAIN, WITHHOLD, HUMAN_REVIEW_REQUIRED, NOT_ASSESSABLE
    payload_sha256 = Column(String(64), nullable=True)

    is_locked = Column(Boolean, default=False, nullable=False, index=True)
    adjudicated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    adjudicator = relationship("UserRecord", back_populates="blinded_adjudications")
    submission_1 = relationship("BlindedAnnotationRecord", foreign_keys=[annotator_1_submission_id])
    submission_2 = relationship("BlindedAnnotationRecord", foreign_keys=[annotator_2_submission_id])

    __table_args__ = (
        Index("ix_blinded_adjudication_status", "candidate_finding_id", "status"),
    )

