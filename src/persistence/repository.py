"""
Repository layer providing transactional database operations, duplicate detection,
and relational integrity management for documents, text snapshots, segments, and audit events.
"""

import json
import uuid
import hashlib
import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.persistence.models import (
    DocumentRecord, ExtractedTextSnapshot, SegmentRecord, IngestionJob, AuditEventRecord,
    UserRecord, AdvocateVerificationRecord, UserRole, AccountStatus, AdvocateStatus,
    ReviewRecord, ReviewStateTransitionRecord, ClauseFindingRecord, ReviewCommentRecord,
    DocumentRevisionRecord, ReviewStatus, LawyerDecisionType, FindingOrigin,
    CommentVisibility, RevisionStatus, EvidenceQualityStatus,
    ReportStatus, FeedbackStatus, FinalReportRecord, ClientFeedbackRecord, FeedbackResponseRecord,
    UserSessionRecord,
    AnnotationStage, AdjudicationStatus, BlindedAnnotationRecord, BlindedAdjudicationRecord
)
from src.segmentation.schema import Segment
from src.audit.schema import AuditEvent

class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_document(
        self,
        document_id: str,
        validation: Any,
        storage_path: str,
        initial_status: Any = "RECEIVED",
        owner_id: Optional[str] = None,
        assigned_lawyer_id: Optional[str] = None
    ) -> DocumentRecord:
        """
        Creates and persists a new DocumentRecord.
        Supports tenant isolation via owner_id and lawyer assignment.
        """
        fmt = validation.format.value if hasattr(validation.format, "value") else str(validation.format)
        st = initial_status.value if hasattr(initial_status, "value") else str(initial_status)
        doc = DocumentRecord(
            id=document_id,
            file_sha256=validation.file_sha256,
            original_filename=validation.original_filename,
            sanitized_filename=validation.sanitized_filename,
            mime_type=validation.mime_type,
            document_format=fmt,
            file_size_bytes=validation.file_size_bytes,
            storage_path=storage_path,
            owner_id=owner_id,
            assigned_lawyer_id=assigned_lawyer_id,
            status=st,
            warnings_json=json.dumps(validation.warnings) if validation.warnings else None,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(doc)
        self.session.flush()
        return doc

    def get_document_by_id(self, document_id: str) -> Optional[DocumentRecord]:
        """Fetches document by internal UUID."""
        return self.session.query(DocumentRecord).filter(DocumentRecord.id == document_id).first()

    def find_duplicate_by_sha256(self, file_sha256: str) -> Optional[DocumentRecord]:
        """
        Checks if an identical file has already been ingested.
        Helps prevent accidental duplicate processing on retries.
        """
        return self.session.query(DocumentRecord).filter(
            DocumentRecord.file_sha256 == file_sha256,
            DocumentRecord.status.in_([
                "RECEIVED",
                "EXTRACTED",
                "PREPROCESSED",
                "SEGMENTED"
            ])
        ).first()

    # =========================================================================
    # USER & ROLE MANAGEMENT
    # =========================================================================

    def create_user(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        full_name: str,
        role: UserRole = UserRole.CLIENT,
        account_status: AccountStatus = AccountStatus.ACTIVE,
        advocate_status: AdvocateStatus = AdvocateStatus.NOT_APPLICABLE,
        bar_enrolment_id: Optional[str] = None,
        state_bar_council: Optional[str] = None,
        year_of_enrolment: Optional[int] = None
    ) -> UserRecord:
        """Creates and persists a new user with strictly normalized email."""
        norm_email = email.strip().lower()
        user = UserRecord(
            id=user_id,
            email=norm_email,
            password_hash=password_hash,
            full_name=full_name.strip(),
            role=role.value if hasattr(role, "value") else str(role),
            account_status=account_status.value if hasattr(account_status, "value") else str(account_status),
            advocate_status=advocate_status.value if hasattr(advocate_status, "value") else str(advocate_status),
            bar_enrolment_id=bar_enrolment_id.strip() if bar_enrolment_id else None,
            state_bar_council=state_bar_council.strip() if state_bar_council else None,
            year_of_enrolment=year_of_enrolment,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(user)
        self.session.flush()
        return user

    def get_user_by_id(self, user_id: str) -> Optional[UserRecord]:
        return self.session.query(UserRecord).filter(UserRecord.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        norm_email = email.strip().lower()
        return self.session.query(UserRecord).filter(UserRecord.email == norm_email).first()

    def update_user_role(self, user_id: str, new_role: UserRole) -> Optional[UserRecord]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        user.role = new_role.value if hasattr(new_role, "value") else str(new_role)
        user.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.flush()
        return user

    def update_user_status(self, user_id: str, new_status: AccountStatus) -> Optional[UserRecord]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        user.account_status = new_status.value if hasattr(new_status, "value") else str(new_status)
        user.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.flush()
        return user

    def update_user_advocate_status(self, user_id: str, new_status: AdvocateStatus) -> Optional[UserRecord]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        user.advocate_status = new_status.value if hasattr(new_status, "value") else str(new_status)
        user.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.flush()
        return user

    # =========================================================================
    # ADVOCATE VERIFICATION WORKFLOW
    # =========================================================================

    def create_advocate_verification_request(
        self,
        request_id: str,
        user_id: str,
        bar_enrolment_id: str,
        state_bar_council: str,
        year_of_enrolment: int,
        evidence_notes: Optional[str] = None
    ) -> AdvocateVerificationRecord:
        """Records an advocate's verification submission."""
        req = AdvocateVerificationRecord(
            id=request_id,
            user_id=user_id,
            bar_enrolment_id=bar_enrolment_id.strip(),
            state_bar_council=state_bar_council.strip(),
            year_of_enrolment=year_of_enrolment,
            status=AdvocateStatus.PENDING_VERIFICATION.value,
            evidence_notes=evidence_notes,
            submitted_at=datetime.datetime.now(datetime.timezone.utc),
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(req)
        # Also update user's advocate_status to PENDING_VERIFICATION and store credentials
        user = self.get_user_by_id(user_id)
        if user:
            user.advocate_status = AdvocateStatus.PENDING_VERIFICATION.value
            user.bar_enrolment_id = bar_enrolment_id.strip()
            user.state_bar_council = state_bar_council.strip()
            user.year_of_enrolment = year_of_enrolment
            user.updated_at = datetime.datetime.now(datetime.timezone.utc)
            
        self.session.flush()
        return req

    def get_advocate_verification_by_id(self, request_id: str) -> Optional[AdvocateVerificationRecord]:
        return self.session.query(AdvocateVerificationRecord).filter(AdvocateVerificationRecord.id == request_id).first()

    def get_pending_advocate_verifications(self) -> List[AdvocateVerificationRecord]:
        return self.session.query(AdvocateVerificationRecord).filter(
            AdvocateVerificationRecord.status == AdvocateStatus.PENDING_VERIFICATION.value
        ).all()

    def decide_advocate_verification(
        self,
        request_id: str,
        reviewer_id: str,
        decision: AdvocateStatus,
        rationale: str
    ) -> Optional[AdvocateVerificationRecord]:
        """Applies a verification decision (VERIFIED or REJECTED) by an authorized reviewer."""
        req = self.get_advocate_verification_by_id(request_id)
        if not req:
            return None
            
        now = datetime.datetime.now(datetime.timezone.utc)
        req.status = decision.value if hasattr(decision, "value") else str(decision)
        req.reviewer_id = reviewer_id
        req.decision_rationale = rationale
        req.decided_at = now
        req.updated_at = now
        
        # Reflect decision on the user's account record
        applicant = self.get_user_by_id(req.user_id)
        if applicant:
            applicant.advocate_status = req.status
            applicant.updated_at = now
            
        self.session.flush()
        return req

    # =========================================================================
    # TASK 036: SECURE SESSION PERSISTENCE & LIFECYCLE
    # =========================================================================

    def create_session(
        self,
        session_id: str,
        user_id: str,
        session_token_hash: str,
        expires_at: datetime.datetime,
        remember_me: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSessionRecord:
        """Persists a new active user session with cryptographic token hash."""
        now = datetime.datetime.now(datetime.timezone.utc)
        sess_rec = UserSessionRecord(
            id=session_id,
            user_id=user_id,
            session_token_hash=session_token_hash,
            is_revoked=False,
            remember_me=remember_me,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
            created_at=now,
            last_activity_at=now,
            expires_at=expires_at
        )
        self.session.add(sess_rec)
        self.session.flush()
        return sess_rec

    def get_session_by_token_hash(self, token_hash: str) -> Optional[UserSessionRecord]:
        """Retrieves session record by the SHA-256 hash of its token/jti."""
        return self.session.query(UserSessionRecord).filter_by(session_token_hash=token_hash).first()

    def update_session_activity(self, session_id: str, new_expires_at: Optional[datetime.datetime] = None) -> None:
        """Updates last_activity_at and optional sliding expires_at."""
        now = datetime.datetime.now(datetime.timezone.utc)
        sess_rec = self.session.query(UserSessionRecord).filter_by(id=session_id).first()
        if sess_rec:
            sess_rec.last_activity_at = now
            if new_expires_at:
                sess_rec.expires_at = new_expires_at
            self.session.flush()

    def revoke_session_by_hash(self, token_hash: str, reason: str = "LOGOUT") -> bool:
        """Revokes a specific session by its token hash."""
        sess_rec = self.session.query(UserSessionRecord).filter_by(session_token_hash=token_hash).first()
        if sess_rec and not sess_rec.is_revoked:
            sess_rec.is_revoked = True
            sess_rec.revoked_at = datetime.datetime.now(datetime.timezone.utc)
            sess_rec.revocation_reason = reason
            self.session.flush()
            return True
        return False

    def revoke_all_user_sessions(self, user_id: str, reason: str = "SECURITY_RESET") -> int:
        """Revokes all active sessions for a user (e.g. after password change or account suspension)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        active_sessions = (
            self.session.query(UserSessionRecord)
            .filter_by(user_id=user_id, is_revoked=False)
            .all()
        )
        count = len(active_sessions)
        for s in active_sessions:
            s.is_revoked = True
            s.revoked_at = now
            s.revocation_reason = reason
        self.session.flush()
        return count

    def get_active_sessions_for_user(self, user_id: str) -> List[UserSessionRecord]:
        """Returns all unexpired, unrevoked sessions for a user."""
        now = datetime.datetime.now(datetime.timezone.utc)
        return (
            self.session.query(UserSessionRecord)
            .filter(
                UserSessionRecord.user_id == user_id,
                UserSessionRecord.is_revoked == False,
                UserSessionRecord.expires_at > now
            )
            .all()
        )

    # =========================================================================
    # CONTRACT ASSIGNMENT & RBAC AUTHORIZATION CHECKS
    # =========================================================================

    def assign_document_to_lawyer(
        self,
        document_id: str,
        lawyer_id: str
    ) -> Optional[DocumentRecord]:
        """Assigns a document to a verified lawyer."""
        doc = self.get_document_by_id(document_id)
        if not doc:
            return None
        lawyer = self.get_user_by_id(lawyer_id)
        if not lawyer or lawyer.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            raise ValueError(f"User {lawyer_id} is not an authorized lawyer")
        if lawyer.advocate_status != AdvocateStatus.VERIFIED.value:
            raise ValueError(f"Lawyer {lawyer_id} is not verified (status={lawyer.advocate_status})")
            
        doc.assigned_lawyer_id = lawyer_id
        doc.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.flush()
        return doc

    def can_user_access_document(
        self,
        user: UserRecord,
        document: DocumentRecord,
        require_full_content: bool = True
    ) -> bool:
        """
        Enforces server-side contract access control:
        - SUPERVISING_LAWYER: full access to all contracts.
        - CLIENT: access only to contracts where owner_id == user.id.
        - LAWYER: access only to contracts where assigned_lawyer_id == user.id AND advocate_status == VERIFIED.
        - AUDITOR: access to metadata only; denied if require_full_content is True.
        """
        if not user or not document:
            return False
            
        # Check active status
        if user.account_status != AccountStatus.ACTIVE.value:
            return False
            
        role = user.role
        
        if role == UserRole.SUPERVISING_LAWYER.value:
            return True
            
        if role == UserRole.CLIENT.value:
            # Client can only access contracts they own
            return document.owner_id == user.id
            
        if role == UserRole.LAWYER.value:
            # Lawyer can only access if assigned AND verified
            if user.advocate_status != AdvocateStatus.VERIFIED.value:
                return False
            return document.assigned_lawyer_id == user.id
            
        if role == UserRole.AUDITOR.value:
            # Auditor can access metadata, but never raw contract contents
            return not require_full_content
            
        return False

    def save_extracted_snapshot(
        self,
        document_id: str,
        raw_text: str
    ) -> ExtractedTextSnapshot:
        """
        Saves an immutable text snapshot of the raw extracted text.
        """
        text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        snapshot = ExtractedTextSnapshot(
            id=str(uuid.uuid4()),
            document_id=document_id,
            raw_text=raw_text,
            char_count=len(raw_text),
            text_sha256=text_hash,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def save_segments(
        self,
        document_id: str,
        segments: List[Segment]
    ) -> List[SegmentRecord]:
        """
        Persists clause segments derived from SegmentationPipeline.
        """
        records = []
        for seq, seg in enumerate(segments):
            rec = SegmentRecord(
                id=str(uuid.uuid4()),
                document_id=document_id,
                segment_id=seg.segment_id,
                parent_segment_id=seg.parent_segment_id,
                segment_type=seg.segment_type.value if hasattr(seg.segment_type, "value") else str(seg.segment_type),
                text=seg.text,
                original_start=seg.original_start,
                original_end=seg.original_end,
                heading=seg.heading,
                numbering=seg.numbering,
                level=seg.level,
                sequence=seq,
                path=seg.path,
                metadata_json=json.dumps(seg.metadata) if seg.metadata else None,
                created_at=datetime.datetime.now(datetime.timezone.utc)
            )
            self.session.add(rec)
            records.append(rec)
            
        self.session.flush()
        return records

    def record_audit_event(
        self,
        audit_event: AuditEvent
    ) -> AuditEventRecord:
        """
        Persists an audit event to the tamper-evident database audit table.
        """
        rec = AuditEventRecord(
            id=str(uuid.uuid4()),
            document_id=audit_event.source_document_id,
            event_id=audit_event.event_id,
            event_type=audit_event.event_type.value if hasattr(audit_event.event_type, "value") else str(audit_event.event_type),
            timestamp=audit_event.timestamp,
            actor_type=audit_event.actor_type.value if hasattr(audit_event.actor_type, "value") else str(audit_event.actor_type),
            previous_event_hash=audit_event.previous_event_hash,
            event_hash=audit_event.event_hash,
            payload_json=json.dumps(audit_event.event_payload),
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(rec)
        self.session.flush()
        return rec

    def get_audit_events_for_document(self, document_id: Optional[str] = None) -> List[AuditEventRecord]:
        """
        Retrieves all audit events for a document, or all events if document_id is None.
        """
        if document_id is not None:
            return self.session.query(AuditEventRecord).filter(AuditEventRecord.document_id == document_id).order_by(AuditEventRecord.created_at.asc()).all()
        return self.session.query(AuditEventRecord).order_by(AuditEventRecord.created_at.asc()).all()

    def update_document_status(
        self,
        document_id: str,
        status: Any,
        extraction_result: Optional[Any] = None,
        error_message: Optional[str] = None
    ) -> Optional[DocumentRecord]:
        """
        Updates document status, extraction metrics, and error state.
        """
        doc = self.get_document_by_id(document_id)
        if not doc:
            return None

        doc.status = status.value if hasattr(status, "value") else str(status)
        doc.updated_at = datetime.datetime.now(datetime.timezone.utc)

        if extraction_result:
            method_val = (
                extraction_result.extraction_method.value
                if hasattr(extraction_result.extraction_method, "value")
                else str(extraction_result.extraction_method)
            )
            doc.extraction_method = method_val
            doc.page_count = extraction_result.page_count
            doc.char_count = extraction_result.char_count
            doc.ocr_applied = extraction_result.ocr_applied
            if extraction_result.warnings:
                existing_warnings = json.loads(doc.warnings_json) if doc.warnings_json else []
                existing_warnings.extend(extraction_result.warnings)
                doc.warnings_json = json.dumps(existing_warnings)
            if extraction_result.errors:
                doc.error_message = "; ".join(extraction_result.errors)

        if error_message:
            doc.error_message = error_message

        self.session.flush()
        return doc

    # =========================================================================
    # TASK 033: REVIEW WORKBENCH OPERATIONS
    # =========================================================================

    def create_review(
        self,
        document_id: str,
        document_version: int = 1,
        initial_status: ReviewStatus = ReviewStatus.DOCUMENT_SUBMITTED
    ) -> ReviewRecord:
        """Creates and persists a new ReviewRecord for a document."""
        st = initial_status.value if hasattr(initial_status, "value") else str(initial_status)
        review = ReviewRecord(
            id=str(uuid.uuid4()),
            document_id=document_id,
            document_version=document_version,
            status=st,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(review)
        self.session.flush()
        return review

    def get_review_by_id(self, review_id: str) -> Optional[ReviewRecord]:
        return self.session.query(ReviewRecord).filter(ReviewRecord.id == review_id).first()

    def get_review_by_document_id(self, document_id: str) -> Optional[ReviewRecord]:
        return self.session.query(ReviewRecord).filter(ReviewRecord.document_id == document_id).order_by(ReviewRecord.created_at.desc()).first()

    def list_reviews(
        self,
        user: Optional[UserRecord] = None,
        status_filter: Optional[str] = None
    ) -> List[ReviewRecord]:
        """
        Lists reviews according to user role and optional status filter.
        - CLIENT: only reviews of documents owned by user.
        - LAWYER: only reviews assigned to lawyer.
        - SUPERVISING_LAWYER / AUDITOR: all reviews.
        """
        query = self.session.query(ReviewRecord).join(DocumentRecord, ReviewRecord.document_id == DocumentRecord.id)

        if user:
            role = user.role
            if role == UserRole.CLIENT.value:
                query = query.filter(DocumentRecord.owner_id == user.id)
            elif role == UserRole.LAWYER.value:
                query = query.filter(ReviewRecord.assigned_lawyer_id == user.id)
            # SUPERVISING_LAWYER & AUDITOR see all

        if status_filter:
            query = query.filter(ReviewRecord.status == status_filter)

        return query.order_by(ReviewRecord.created_at.desc()).all()

    def record_review_transition(
        self,
        review_id: str,
        from_state: str,
        to_state: str,
        actor_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> ReviewStateTransitionRecord:
        """Records an explicit state transition in the review lifecycle."""
        rec = ReviewStateTransitionRecord(
            id=str(uuid.uuid4()),
            review_id=review_id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            reason=reason,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(rec)
        self.session.flush()
        return rec

    def assign_review(
        self,
        review_id: str,
        lawyer_id: str,
        assigned_by_id: str
    ) -> Optional[ReviewRecord]:
        """
        Assigns a review to a verified advocate.
        Also syncs the document's assigned_lawyer_id.
        """
        review = self.get_review_by_id(review_id)
        if not review:
            return None

        now = datetime.datetime.now(datetime.timezone.utc)
        review.assigned_lawyer_id = lawyer_id
        review.assigned_by_id = assigned_by_id
        review.assigned_at = now
        review.status = ReviewStatus.ASSIGNED.value
        review.updated_at = now

        # Update document assignment as well
        doc = self.get_document_by_id(review.document_id)
        if doc:
            doc.assigned_lawyer_id = lawyer_id
            doc.updated_at = now

        self.session.flush()
        return review

    def create_or_update_clause_finding(
        self,
        review_id: str,
        document_id: str,
        segment_id: str,
        decision: Optional[str] = None,
        lawyer_rationale: Optional[str] = None,
        lawyer_notes: Optional[str] = None,
        finding_origin: str = FindingOrigin.AI_GENERATED.value,
        risk_label: Optional[str] = None,
        ai_observation: Optional[str] = None,
        ai_confidence_score: Optional[str] = None,
        statutory_evidence_json: Optional[str] = None,
        ai_metadata_json: Optional[str] = None,
        model_attribution_json: Optional[str] = None,
        evidence_quality_status: Optional[str] = None,
        is_disclosed_to_client: bool = False,
        author_id: Optional[str] = None,
        document_version: int = 1
    ) -> ClauseFindingRecord:
        """
        Creates or updates a clause-level finding and lawyer decision.
        """
        finding = self.session.query(ClauseFindingRecord).filter(
            ClauseFindingRecord.review_id == review_id,
            ClauseFindingRecord.segment_id == segment_id
        ).first()

        now = datetime.datetime.now(datetime.timezone.utc)
        eq_status = evidence_quality_status or EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value

        if not finding:
            finding = ClauseFindingRecord(
                id=str(uuid.uuid4()),
                review_id=review_id,
                document_id=document_id,
                segment_id=segment_id,
                document_version=document_version,
                finding_origin=finding_origin,
                risk_label=risk_label,
                ai_confidence_score=ai_confidence_score,
                ai_observation=ai_observation,
                decision=decision,
                lawyer_rationale=lawyer_rationale,
                lawyer_notes=lawyer_notes,
                statutory_evidence_json=statutory_evidence_json,
                ai_metadata_json=ai_metadata_json,
                model_attribution_json=model_attribution_json,
                evidence_quality_status=eq_status,
                is_disclosed_to_client=is_disclosed_to_client,
                author_id=author_id,
                created_at=now,
                updated_at=now
            )
            self.session.add(finding)
        else:
            if document_version is not None:
                finding.document_version = document_version
            if finding_origin is not None:
                finding.finding_origin = finding_origin
            if decision is not None:
                finding.decision = decision
            if lawyer_rationale is not None:
                finding.lawyer_rationale = lawyer_rationale
            if lawyer_notes is not None:
                finding.lawyer_notes = lawyer_notes
            if risk_label is not None:
                finding.risk_label = risk_label
            if ai_observation is not None:
                finding.ai_observation = ai_observation
            if ai_confidence_score is not None:
                finding.ai_confidence_score = ai_confidence_score
            if statutory_evidence_json is not None:
                finding.statutory_evidence_json = statutory_evidence_json
            if ai_metadata_json is not None:
                finding.ai_metadata_json = ai_metadata_json
            if model_attribution_json is not None or finding_origin == FindingOrigin.AI_GENERATED.value:
                finding.model_attribution_json = model_attribution_json
            if evidence_quality_status is not None:
                finding.evidence_quality_status = evidence_quality_status
            if is_disclosed_to_client is not None:
                finding.is_disclosed_to_client = is_disclosed_to_client
            if author_id is not None:
                finding.author_id = author_id
            finding.updated_at = now

        self.session.flush()
        return finding

    def get_findings_for_review(
        self,
        review_id: str,
        client_view: bool = False
    ) -> List[ClauseFindingRecord]:
        """
        Retrieves findings for a review.
        If client_view is True, excludes undisclosed findings and internal lawyer notes.
        """
        query = self.session.query(ClauseFindingRecord).filter(ClauseFindingRecord.review_id == review_id)
        if client_view:
            query = query.filter(ClauseFindingRecord.is_disclosed_to_client == True)
        return query.order_by(ClauseFindingRecord.created_at.asc()).all()

    def create_comment(
        self,
        review_id: str,
        document_id: str,
        author_id: str,
        author_role: str,
        author_name: str,
        comment_text: str,
        visibility: str = CommentVisibility.INTERNAL_LAWYER_ONLY.value,
        segment_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        parent_comment_id: Optional[str] = None
    ) -> ReviewCommentRecord:
        """Creates a scoped review comment."""
        comment = ReviewCommentRecord(
            id=str(uuid.uuid4()),
            review_id=review_id,
            document_id=document_id,
            segment_id=segment_id,
            finding_id=finding_id,
            author_id=author_id,
            author_role=author_role,
            author_name=author_name,
            visibility=visibility,
            comment_text=comment_text,
            parent_comment_id=parent_comment_id,
            is_resolved=False,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(comment)
        self.session.flush()
        return comment

    def get_comments_for_review(
        self,
        review_id: str,
        client_view: bool = False
    ) -> List[ReviewCommentRecord]:
        """
        Retrieves comments for a review.
        If client_view is True, filters out INTERNAL_LAWYER_ONLY comments.
        """
        query = self.session.query(ReviewCommentRecord).filter(ReviewCommentRecord.review_id == review_id)
        if client_view:
            query = query.filter(
                ReviewCommentRecord.visibility.in_([
                    CommentVisibility.CLIENT_VISIBLE.value,
                    CommentVisibility.CLARIFICATION_REQUEST.value,
                    CommentVisibility.CLIENT_RESPONSE.value
                ])
            )
        return query.order_by(ReviewCommentRecord.created_at.asc()).all()

    def resolve_comment(
        self,
        comment_id: str,
        resolved_by_id: str
    ) -> Optional[ReviewCommentRecord]:
        """Marks a comment thread or clarification request as resolved."""
        comment = self.session.query(ReviewCommentRecord).filter(ReviewCommentRecord.id == comment_id).first()
        if not comment:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        comment.is_resolved = True
        comment.resolved_by_id = resolved_by_id
        comment.resolved_at = now
        comment.updated_at = now
        self.session.flush()
        return comment

    def create_document_revision(
        self,
        document_id: str,
        review_id: str,
        version_number: int,
        original_file_sha256: str,
        revised_text: str,
        author_id: str,
        change_reason: Optional[str] = None,
        diff_summary: Optional[str] = None
    ) -> DocumentRevisionRecord:
        """Creates a versioned document revision, preserving original file immutability."""
        rev_hash = hashlib.sha256(revised_text.encode("utf-8")).hexdigest()
        rev = DocumentRevisionRecord(
            id=str(uuid.uuid4()),
            document_id=document_id,
            review_id=review_id,
            version_number=version_number,
            revision_status=RevisionStatus.PROPOSED.value,
            original_file_sha256=original_file_sha256,
            revised_text=revised_text,
            revised_text_sha256=rev_hash,
            diff_summary=diff_summary,
            change_reason=change_reason,
            author_id=author_id,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(rev)
        self.session.flush()
        return rev

    def get_revisions_for_document(self, document_id: str) -> List[DocumentRevisionRecord]:
        return self.session.query(DocumentRevisionRecord).filter(
            DocumentRevisionRecord.document_id == document_id
        ).order_by(DocumentRevisionRecord.version_number.asc()).all()

    def decide_document_revision(
        self,
        revision_id: str,
        decision: str,
        decided_by_id: str
    ) -> Optional[DocumentRevisionRecord]:
        rev = self.session.query(DocumentRevisionRecord).filter(DocumentRevisionRecord.id == revision_id).first()
        if not rev:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        rev.revision_status = decision
        rev.decided_by_id = decided_by_id
        rev.decided_at = now
        rev.updated_at = now
        self.session.flush()
        return rev

    def complete_review(
        self,
        review_id: str,
        completed_by_id: str,
        completion_summary: Optional[str] = None,
        outstanding_limitations: Optional[str] = None,
        unresolved_questions: Optional[str] = None,
        further_client_action_required: bool = False,
        disclaimer_text: Optional[str] = None
    ) -> Optional[ReviewRecord]:
        review = self.get_review_by_id(review_id)
        if not review:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        review.status = ReviewStatus.REVIEW_COMPLETED.value
        review.completed_by_id = completed_by_id
        review.completed_at = now
        review.completion_summary = completion_summary
        review.outstanding_limitations = outstanding_limitations
        review.unresolved_questions = unresolved_questions
        review.further_client_action_required = further_client_action_required
        review.disclaimer_text = disclaimer_text
        review.updated_at = now
        self.session.flush()
        return review

    def reopen_review(
        self,
        review_id: str,
        actor_id: str,
        reason: str
    ) -> Optional[ReviewRecord]:
        review = self.get_review_by_id(review_id)
        if not review:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        review.status = ReviewStatus.IN_REVIEW.value
        review.updated_at = now
        self.session.flush()
        return review

    def get_eligible_advocates(self) -> List[UserRecord]:
        """Returns verified advocates eligible for assignment."""
        return self.session.query(UserRecord).filter(
            UserRecord.role.in_([UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value]),
            UserRecord.advocate_status == AdvocateStatus.VERIFIED.value,
            UserRecord.account_status == AccountStatus.ACTIVE.value
        ).order_by(UserRecord.full_name.asc()).all()

    # =========================================================================
    # TASK 034: FINAL REPORTS & CLIENT FEEDBACK
    # =========================================================================

    def create_report(
        self,
        report_id: str,
        report_number: str,
        document_id: str,
        review_id: str,
        document_version: int,
        report_version: int,
        title: str,
        disclaimer_text: str,
        report_payload_json: str,
        content_sha256: str,
        generated_by_id: Optional[str] = None,
        status: str = ReportStatus.FINAL.value,
        is_final: bool = True,
        executive_summary: Optional[str] = None,
        scope_of_review: Optional[str] = None,
        review_outcome_summary: Optional[str] = None,
        outstanding_limitations: Optional[str] = None,
        statutory_corpus_version: Optional[str] = None,
        pdf_storage_path: Optional[str] = None,
        pdf_sha256: Optional[str] = None,
        pdf_file_size_bytes: Optional[int] = None
    ) -> FinalReportRecord:
        now = datetime.datetime.now(datetime.timezone.utc)
        report = FinalReportRecord(
            id=report_id,
            report_number=report_number,
            document_id=document_id,
            review_id=review_id,
            document_version=document_version,
            report_version=report_version,
            status=status,
            is_final=is_final,
            generated_by_id=generated_by_id,
            generated_at=now,
            title=title,
            executive_summary=executive_summary,
            scope_of_review=scope_of_review,
            review_outcome_summary=review_outcome_summary,
            outstanding_limitations=outstanding_limitations,
            disclaimer_text=disclaimer_text,
            statutory_corpus_version=statutory_corpus_version,
            report_payload_json=report_payload_json,
            content_sha256=content_sha256,
            pdf_storage_path=pdf_storage_path,
            pdf_sha256=pdf_sha256,
            pdf_file_size_bytes=pdf_file_size_bytes,
            pdf_generated_at=now if pdf_storage_path else None,
            created_at=now,
            updated_at=now
        )
        self.session.add(report)
        self.session.flush()
        return report

    def get_report_by_id(self, report_id: str) -> Optional[FinalReportRecord]:
        return self.session.query(FinalReportRecord).filter(FinalReportRecord.id == report_id).first()

    def get_report_by_number(self, report_number: str) -> Optional[FinalReportRecord]:
        return self.session.query(FinalReportRecord).filter(FinalReportRecord.report_number == report_number).first()

    def get_reports_for_document(self, document_id: str) -> List[FinalReportRecord]:
        return (
            self.session.query(FinalReportRecord)
            .filter(FinalReportRecord.document_id == document_id)
            .order_by(FinalReportRecord.report_version.desc(), FinalReportRecord.created_at.desc())
            .all()
        )

    def get_reports_for_review(self, review_id: str) -> List[FinalReportRecord]:
        return (
            self.session.query(FinalReportRecord)
            .filter(FinalReportRecord.review_id == review_id)
            .order_by(FinalReportRecord.report_version.desc(), FinalReportRecord.created_at.desc())
            .all()
        )

    def get_active_final_report_for_review(self, review_id: str) -> Optional[FinalReportRecord]:
        return (
            self.session.query(FinalReportRecord)
            .filter(
                FinalReportRecord.review_id == review_id,
                FinalReportRecord.status == ReportStatus.FINAL.value,
                FinalReportRecord.is_final == True
            )
            .order_by(FinalReportRecord.report_version.desc())
            .first()
        )

    def supersede_report(
        self,
        report_id: str,
        new_report_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Optional[FinalReportRecord]:
        report = self.get_report_by_id(report_id)
        if not report:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        report.status = ReportStatus.SUPERSEDED.value
        report.superseded_at = now
        report.superseded_by_id = new_report_id
        report.supersession_reason = reason
        report.updated_at = now
        self.session.flush()
        return report

    def update_report_pdf_artifact(
        self,
        report_id: str,
        pdf_path: str,
        pdf_sha256: str,
        file_size: int
    ) -> Optional[FinalReportRecord]:
        report = self.get_report_by_id(report_id)
        if not report:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        report.pdf_storage_path = pdf_path
        report.pdf_sha256 = pdf_sha256
        report.pdf_file_size_bytes = file_size
        report.pdf_generated_at = now
        report.updated_at = now
        self.session.flush()
        return report

    def create_client_feedback(
        self,
        feedback_id: str,
        report_id: str,
        document_id: str,
        review_id: str,
        client_id: str,
        overall_satisfaction: int,
        clarity_rating: int,
        usefulness_rating: int,
        needs_clarification: bool = False,
        follow_up_requested: bool = False,
        client_comments: Optional[str] = None,
        status: str = FeedbackStatus.SUBMITTED.value
    ) -> ClientFeedbackRecord:
        now = datetime.datetime.now(datetime.timezone.utc)
        feedback = ClientFeedbackRecord(
            id=feedback_id,
            report_id=report_id,
            document_id=document_id,
            review_id=review_id,
            client_id=client_id,
            status=status,
            overall_satisfaction=overall_satisfaction,
            clarity_rating=clarity_rating,
            usefulness_rating=usefulness_rating,
            needs_clarification=needs_clarification,
            follow_up_requested=follow_up_requested,
            client_comments=client_comments,
            submitted_at=now,
            updated_at=now
        )
        self.session.add(feedback)
        self.session.flush()
        return feedback

    def get_feedback_by_id(self, feedback_id: str) -> Optional[ClientFeedbackRecord]:
        return self.session.query(ClientFeedbackRecord).filter(ClientFeedbackRecord.id == feedback_id).first()

    def get_feedback_for_report(self, report_id: str) -> List[ClientFeedbackRecord]:
        return (
            self.session.query(ClientFeedbackRecord)
            .filter(ClientFeedbackRecord.report_id == report_id)
            .order_by(ClientFeedbackRecord.submitted_at.desc())
            .all()
        )

    def get_feedback_for_document(self, document_id: str) -> List[ClientFeedbackRecord]:
        return (
            self.session.query(ClientFeedbackRecord)
            .filter(ClientFeedbackRecord.document_id == document_id)
            .order_by(ClientFeedbackRecord.submitted_at.desc())
            .all()
        )

    def get_feedback_for_client(self, client_id: str) -> List[ClientFeedbackRecord]:
        return (
            self.session.query(ClientFeedbackRecord)
            .filter(ClientFeedbackRecord.client_id == client_id)
            .order_by(ClientFeedbackRecord.submitted_at.desc())
            .all()
        )

    def update_feedback_status(
        self,
        feedback_id: str,
        new_status: str
    ) -> Optional[ClientFeedbackRecord]:
        feedback = self.get_feedback_by_id(feedback_id)
        if not feedback:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        feedback.status = new_status
        feedback.updated_at = now
        self.session.flush()
        return feedback

    def add_feedback_response(
        self,
        response_id: str,
        feedback_id: str,
        responder_id: Optional[str],
        responder_role: str,
        response_text: str,
        is_client_visible: bool = True,
        internal_notes: Optional[str] = None
    ) -> FeedbackResponseRecord:
        now = datetime.datetime.now(datetime.timezone.utc)
        resp = FeedbackResponseRecord(
            id=response_id,
            feedback_id=feedback_id,
            responder_id=responder_id,
            responder_role=responder_role,
            response_text=response_text,
            is_client_visible=is_client_visible,
            internal_notes=internal_notes,
            created_at=now,
            updated_at=now
        )
        self.session.add(resp)
        self.session.flush()
        return resp

    # =========================================================================
    # STRATEGY A: BLINDED ANNOTATION & INDEPENDENT STORAGE REPOSITORY METHODS
    # =========================================================================

    def create_blinded_annotation(
        self,
        candidate_finding_id: str,
        contract_id: str,
        clause_id: str,
        annotator_id: str,
        payload_json: str,
        payload_sha256: str,
        stage: str = AnnotationStage.FULL_RECORD.value,
        reference_action: Optional[str] = None,
        is_synthetic_fixture: bool = False,
        version: int = 1
    ) -> BlindedAnnotationRecord:
        """
        Creates an independent blinded annotation record.
        Prevents duplicate active submissions for the same (candidate, annotator, stage, version).
        """
        existing = (
            self.session.query(BlindedAnnotationRecord)
            .filter(
                BlindedAnnotationRecord.candidate_finding_id == candidate_finding_id,
                BlindedAnnotationRecord.annotator_id == annotator_id,
                BlindedAnnotationRecord.stage == stage,
                BlindedAnnotationRecord.version == version
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Duplicate active submission: An annotation for candidate {candidate_finding_id}, "
                f"stage {stage}, version {version} by annotator {annotator_id} already exists."
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        record = BlindedAnnotationRecord(
            id=str(uuid.uuid4()),
            candidate_finding_id=candidate_finding_id,
            contract_id=contract_id,
            clause_id=clause_id,
            annotator_id=annotator_id,
            stage=stage,
            version=version,
            is_locked=False,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            reference_action=reference_action,
            is_synthetic_fixture=is_synthetic_fixture,
            submitted_at=now,
            created_at=now,
            updated_at=now
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_blinded_annotation_by_id(self, annotation_id: str) -> Optional[BlindedAnnotationRecord]:
        """Retrieves a blinded annotation by its unique ID."""
        return self.session.query(BlindedAnnotationRecord).filter(BlindedAnnotationRecord.id == annotation_id).first()

    def get_active_blinded_annotation(
        self,
        candidate_finding_id: str,
        annotator_id: str,
        stage: str = AnnotationStage.FULL_RECORD.value
    ) -> Optional[BlindedAnnotationRecord]:
        """
        Retrieves the latest active (non-superseded) annotation for a candidate, annotator, and stage.
        """
        return (
            self.session.query(BlindedAnnotationRecord)
            .filter(
                BlindedAnnotationRecord.candidate_finding_id == candidate_finding_id,
                BlindedAnnotationRecord.annotator_id == annotator_id,
                BlindedAnnotationRecord.stage == stage,
                BlindedAnnotationRecord.superseded_by_id.is_(None)
            )
            .order_by(BlindedAnnotationRecord.version.desc())
            .first()
        )

    def get_blinded_annotations_for_candidate(
        self,
        candidate_finding_id: str,
        stage: str = AnnotationStage.FULL_RECORD.value,
        only_active: bool = True
    ) -> List[BlindedAnnotationRecord]:
        """
        Returns all blinded annotations for a candidate finding at a given stage.
        """
        query = self.session.query(BlindedAnnotationRecord).filter(
            BlindedAnnotationRecord.candidate_finding_id == candidate_finding_id,
            BlindedAnnotationRecord.stage == stage
        )
        if only_active:
            query = query.filter(BlindedAnnotationRecord.superseded_by_id.is_(None))
        return query.order_by(BlindedAnnotationRecord.submitted_at.asc()).all()

    def lock_blinded_annotation(
        self,
        annotation_id: str,
        locking_annotator_id: str
    ) -> BlindedAnnotationRecord:
        """
        Transitions an annotation to LOCKED state.
        Once locked, the submission cannot be edited or deleted through ordinary operations.
        """
        record = self.get_blinded_annotation_by_id(annotation_id)
        if not record:
            raise ValueError(f"Annotation record {annotation_id} not found.")

        if record.annotator_id != locking_annotator_id:
            raise PermissionError("Forbidden: cannot lock an annotation authored by another user.")

        if record.is_locked:
            raise ValueError("Annotation is already locked.")

        now = datetime.datetime.now(datetime.timezone.utc)
        record.is_locked = True
        record.locked_at = now
        record.updated_at = now
        self.session.flush()
        return record

    def update_unlocked_annotation_payload(
        self,
        annotation_id: str,
        annotator_id: str,
        new_payload_json: str,
        new_payload_sha256: str,
        reference_action: Optional[str] = None
    ) -> BlindedAnnotationRecord:
        """
        Updates the draft payload of an UNLOCKED annotation.
        Throws error if record is already locked.
        """
        record = self.get_blinded_annotation_by_id(annotation_id)
        if not record:
            raise ValueError(f"Annotation record {annotation_id} not found.")

        if record.annotator_id != annotator_id:
            raise PermissionError("Forbidden: cannot modify an annotation authored by another user.")

        if record.is_locked:
            raise ValueError("Forbidden: Locked submissions cannot be edited. A versioned amendment is required.")

        now = datetime.datetime.now(datetime.timezone.utc)
        record.payload_json = new_payload_json
        record.payload_sha256 = new_payload_sha256
        if reference_action:
            record.reference_action = reference_action
        record.updated_at = now
        self.session.flush()
        return record

    def supersede_blinded_annotation(
        self,
        original_annotation_id: str,
        new_payload_json: str,
        new_payload_sha256: str,
        annotator_id: str,
        reason: str,
        reference_action: Optional[str] = None
    ) -> BlindedAnnotationRecord:
        """
        Creates an explicit versioned correction (v+1) for a locked annotation,
        preserving the immutable original and marking superseded_by_id.
        """
        original = self.get_blinded_annotation_by_id(original_annotation_id)
        if not original:
            raise ValueError(f"Original annotation {original_annotation_id} not found.")

        if original.annotator_id != annotator_id:
            raise PermissionError("Forbidden: cannot supersede an annotation authored by another user.")

        now = datetime.datetime.now(datetime.timezone.utc)
        new_version = original.version + 1
        new_record = BlindedAnnotationRecord(
            id=str(uuid.uuid4()),
            candidate_finding_id=original.candidate_finding_id,
            contract_id=original.contract_id,
            clause_id=original.clause_id,
            annotator_id=annotator_id,
            stage=original.stage,
            version=new_version,
            is_locked=False,
            payload_json=new_payload_json,
            payload_sha256=new_payload_sha256,
            reference_action=reference_action or original.reference_action,
            is_synthetic_fixture=original.is_synthetic_fixture,
            submitted_at=now,
            created_at=now,
            updated_at=now
        )
        self.session.add(new_record)
        self.session.flush()

        original.superseded_by_id = new_record.id
        original.supersession_reason = reason
        original.updated_at = now
        self.session.flush()
        return new_record

    def get_or_create_adjudication(
        self,
        candidate_finding_id: str,
        contract_id: str,
        clause_id: str
    ) -> BlindedAdjudicationRecord:
        """
        Retrieves or creates an adjudication tracking record for a candidate finding.
        """
        adj = (
            self.session.query(BlindedAdjudicationRecord)
            .filter(BlindedAdjudicationRecord.candidate_finding_id == candidate_finding_id)
            .first()
        )
        if not adj:
            now = datetime.datetime.now(datetime.timezone.utc)
            adj = BlindedAdjudicationRecord(
                id=str(uuid.uuid4()),
                candidate_finding_id=candidate_finding_id,
                contract_id=contract_id,
                clause_id=clause_id,
                status=AdjudicationStatus.PENDING_SUBMISSIONS.value,
                created_at=now,
                updated_at=now
            )
            self.session.add(adj)
            self.session.flush()
        return adj

    def record_adjudication(
        self,
        candidate_finding_id: str,
        adjudicator_id: str,
        final_disposition: str,
        adjudicator_rationale: str,
        adjudication_payload_json: str,
        payload_sha256: str
    ) -> BlindedAdjudicationRecord:
        """
        Records and locks a final adjudication determination by Senior Counsel.
        """
        adj = (
            self.session.query(BlindedAdjudicationRecord)
            .filter(BlindedAdjudicationRecord.candidate_finding_id == candidate_finding_id)
            .first()
        )
        if not adj:
            raise ValueError(f"No adjudication record found for candidate {candidate_finding_id}.")

        if adj.is_locked:
            raise ValueError("Adjudication is already locked.")

        now = datetime.datetime.now(datetime.timezone.utc)
        adj.adjudicator_id = adjudicator_id
        adj.final_disposition = final_disposition
        adj.adjudicator_rationale = adjudicator_rationale
        adj.adjudication_payload_json = adjudication_payload_json
        adj.payload_sha256 = payload_sha256
        adj.status = AdjudicationStatus.ADJUDICATED.value
        adj.is_locked = True
        adj.adjudicated_at = now
        adj.updated_at = now
        self.session.flush()
        return adj


ReviewRepository = DocumentRepository
