"""
Persistence package exports.
"""

from src.persistence.database import (
    Base, create_db_engine, get_engine, get_session_factory,
    get_db_session, init_db, drop_db, get_database_url
)
from src.persistence.models import (
    DocumentRecord, ExtractedTextSnapshot, SegmentRecord, IngestionJob, AuditEventRecord,
    UserRecord, AdvocateVerificationRecord, UserRole, AccountStatus, AdvocateStatus,
    ReviewRecord, ReviewStateTransitionRecord, ClauseFindingRecord, ReviewCommentRecord,
    DocumentRevisionRecord, ReviewStatus, LawyerDecisionType, FindingOrigin,
    CommentVisibility, RevisionStatus,
    ReportStatus, FeedbackStatus, FinalReportRecord, ClientFeedbackRecord, FeedbackResponseRecord,
    UserSessionRecord,
    AnnotationStage, AdjudicationStatus, BlindedAnnotationRecord, BlindedAdjudicationRecord
)
from src.persistence.repository import DocumentRepository

__all__ = [
    "Base",
    "create_db_engine",
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "init_db",
    "drop_db",
    "get_database_url",
    "DocumentRecord",
    "ExtractedTextSnapshot",
    "SegmentRecord",
    "IngestionJob",
    "AuditEventRecord",
    "UserRecord",
    "UserSessionRecord",
    "AdvocateVerificationRecord",
    "UserRole",
    "AccountStatus",
    "AdvocateStatus",
    "ReviewRecord",
    "ReviewStateTransitionRecord",
    "ClauseFindingRecord",
    "ReviewCommentRecord",
    "DocumentRevisionRecord",
    "ReviewStatus",
    "LawyerDecisionType",
    "FindingOrigin",
    "CommentVisibility",
    "RevisionStatus",
    "ReportStatus",
    "FeedbackStatus",
    "FinalReportRecord",
    "ClientFeedbackRecord",
    "FeedbackResponseRecord",
    "AnnotationStage",
    "AdjudicationStatus",
    "BlindedAnnotationRecord",
    "BlindedAdjudicationRecord",
    "DocumentRepository",
]
