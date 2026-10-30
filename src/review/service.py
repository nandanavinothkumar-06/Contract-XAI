"""
Core Review Service and State Machine for Collaborative Lawyer Review Workbench.

Enforces:
1. Strict review lifecycle state transitions (rejecting invalid transitions).
2. Advocate verification gates on assignment (AdvocateStatus.VERIFIED).
3. Client tenant isolation and assigned lawyer boundaries.
4. Independent lawyer decisions (ACCEPT, CORRECT, REJECT, etc.) and authored findings.
5. Scoped comments and clarification requests (internal notes hidden from clients).
6. Document revisions and versioning (preserving immutable original contracts).
7. Review completion prerequisites and mandatory statutory disclaimers.
8. Continuous tamper-evident SHA-256 audit chaining.
"""

import uuid
import json
import difflib
import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from src.persistence.models import (
    UserRecord, DocumentRecord, ReviewRecord, ReviewStateTransitionRecord,
    ClauseFindingRecord, ReviewCommentRecord, DocumentRevisionRecord,
    UserRole, AccountStatus, AdvocateStatus,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility, RevisionStatus,
    EvidenceQualityStatus, AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.audit.provenance import EventType, ActorType
from src.audit.schema import AuditEvent
from src.audit.events import calculate_event_hash

VALID_REVIEW_TRANSITIONS: Dict[str, List[str]] = {
    ReviewStatus.DOCUMENT_SUBMITTED.value: [
        ReviewStatus.PROCESSING.value,
        ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value,
    ],
    ReviewStatus.PROCESSING.value: [
        ReviewStatus.PROCESSING_FAILED.value,
        ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value,
    ],
    ReviewStatus.PROCESSING_FAILED.value: [
        ReviewStatus.PROCESSING.value,
        ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value,
    ],
    ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value: [
        ReviewStatus.ASSIGNED.value,
    ],
    ReviewStatus.ASSIGNED.value: [
        ReviewStatus.IN_REVIEW.value,
        ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value,
    ],
    ReviewStatus.IN_REVIEW.value: [
        ReviewStatus.REVISION_REQUESTED.value,
        ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value,
        ReviewStatus.REVIEW_COMPLETED.value,
    ],
    ReviewStatus.REVISION_REQUESTED.value: [
        ReviewStatus.CLIENT_RESPONSE_RECEIVED.value,
        ReviewStatus.IN_REVIEW.value,
    ],
    ReviewStatus.CLIENT_RESPONSE_RECEIVED.value: [
        ReviewStatus.IN_REVIEW.value,
        ReviewStatus.REVISION_REQUESTED.value,
    ],
    ReviewStatus.REVIEW_COMPLETED.value: [
        ReviewStatus.REVIEW_REOPENED.value,
    ],
    ReviewStatus.REVIEW_REOPENED.value: [
        ReviewStatus.IN_REVIEW.value,
    ],
}

MANDATORY_REVIEW_DISCLAIMER = (
    "This review reflects the professional assessment of the assigned advocate based on the provided "
    "document version and available statutory extracts at the time of review. It does not constitute a "
    "guarantee of legal outcome or certified statutory compliance."
)

class ReviewService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = DocumentRepository(session)

    def _log_audit_event(
        self,
        event_type: EventType,
        actor_type: ActorType,
        source_document_id: Optional[str] = None,
        review_id: Optional[str] = None,
        clause_id: Optional[str] = None,
        actor_reference: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Creates and stores a cryptographically hash-chained audit record in the database.
        """
        last_db_event = (
            self.session.query(AuditEventRecord)
            .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc())
            .first()
        )
        previous_hash = last_db_event.event_hash if last_db_event else None

        evt = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            source_document_id=source_document_id,
            clause_id=clause_id,
            review_id=review_id,
            actor_type=actor_type,
            actor_reference=actor_reference,
            module_name="src.review.service",
            module_version="1.0.0",
            previous_event_hash=previous_hash,
            event_payload=payload or {}
        )
        evt.event_hash = calculate_event_hash(evt)
        self.repo.record_audit_event(evt)
        return evt

    def can_user_access_review(self, user: UserRecord, review: ReviewRecord, require_full_content: bool = True) -> bool:
        """
        Enforces tenant and role boundaries on a review record:
        - CLIENT: only reviews of documents owned by this client.
        - LAWYER: only reviews assigned to this lawyer (must be verified).
        - SUPERVISING_LAWYER: supervisory access to all reviews.
        - AUDITOR: access to metadata only.
        """
        if not user or not review:
            return False
        if user.account_status != AccountStatus.ACTIVE.value:
            return False

        doc = review.document or self.repo.get_document_by_id(review.document_id)
        if not doc:
            return False

        return self.repo.can_user_access_document(user, doc, require_full_content=require_full_content)

    def initiate_review(
        self,
        document_id: str,
        actor_user: UserRecord,
        initial_status: ReviewStatus = ReviewStatus.DOCUMENT_SUBMITTED
    ) -> ReviewRecord:
        """
        Initializes a review record for an ingested document.
        """
        doc = self.repo.get_document_by_id(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        # Permission check
        if actor_user.role == UserRole.CLIENT.value and doc.owner_id != actor_user.id:
            raise PermissionError("Client cannot initiate review on another user's document.")

        existing = self.repo.get_review_by_document_id(document_id)
        if existing:
            return existing

        review = self.repo.create_review(
            document_id=document_id,
            document_version=1,
            initial_status=initial_status
        )

        self.repo.record_review_transition(
            review_id=review.id,
            from_state="",
            to_state=review.status,
            actor_id=actor_user.id,
            reason="Review initiated"
        )

        self._log_audit_event(
            event_type=EventType.REVIEW_CREATED,
            actor_type=ActorType.USER,
            source_document_id=document_id,
            review_id=review.id,
            actor_reference=actor_user.id,
            payload={
                "document_id": document_id,
                "initial_status": review.status,
                "version": 1
            }
        )

        return review

    def transition_review_state(
        self,
        review_id: str,
        to_state: str,
        actor_user: UserRecord,
        reason: Optional[str] = None
    ) -> ReviewRecord:
        """
        Executes a validated state transition in the persistent review lifecycle.
        Rejects invalid transitions server-side with ValueError.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        current_state = review.status
        allowed_targets = VALID_REVIEW_TRANSITIONS.get(current_state, [])

        if to_state not in allowed_targets:
            raise ValueError(
                f"Invalid state transition: Cannot transition review from '{current_state}' to '{to_state}'. "
                f"Allowed transitions from '{current_state}': {allowed_targets}"
            )

        # Enforce role-based state transition authorization
        role = actor_user.role
        if to_state == ReviewStatus.ASSIGNED.value:
            if role != UserRole.SUPERVISING_LAWYER.value:
                raise PermissionError("Only Supervising Lawyers can assign or transition to ASSIGNED.")
        elif to_state in (ReviewStatus.IN_REVIEW.value, ReviewStatus.REVISION_REQUESTED.value):
            if role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
                raise PermissionError(f"Role '{role}' cannot transition review to '{to_state}'.")
            if role == UserRole.LAWYER.value and review.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Only the assigned lawyer can transition this review.")
        elif to_state == ReviewStatus.CLIENT_RESPONSE_RECEIVED.value:
            doc = review.document or self.repo.get_document_by_id(review.document_id)
            if role == UserRole.CLIENT.value and doc.owner_id != actor_user.id:
                raise PermissionError("Client cannot transition another user's review.")

        from_state = review.status
        review.status = to_state
        review.updated_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.flush()

        self.repo.record_review_transition(
            review_id=review.id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_user.id,
            reason=reason
        )

        # Map to specific audit event if applicable
        event_type = EventType.REVIEW_OPENED if to_state == ReviewStatus.IN_REVIEW.value else EventType.REVIEW_CREATED
        self._log_audit_event(
            event_type=event_type,
            actor_type=ActorType.USER,
            source_document_id=review.document_id,
            review_id=review.id,
            actor_reference=actor_user.id,
            payload={
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason
            }
        )

        return review

    def assign_review(
        self,
        review_id: str,
        lawyer_id: str,
        assigning_user: UserRecord,
        rationale: Optional[str] = None
    ) -> ReviewRecord:
        """
        Assigns or reassigns a review to a verified advocate.
        Requires SUPERVISING_LAWYER.
        Enforces AdvocateStatus.VERIFIED on candidate lawyer.
        Prevents client self-assignment.
        """
        if assigning_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Only Supervising Lawyers are authorized to assign or reassign reviews.")

        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        doc = review.document or self.repo.get_document_by_id(review.document_id)
        if not doc:
            raise ValueError(f"Document associated with review {review_id} not found.")

        # Prevent client from assigning themselves as reviewing lawyer
        if doc.owner_id == lawyer_id:
            raise ValueError("Document owner cannot be assigned as the reviewing advocate for their own contract.")

        # Validate candidate lawyer
        lawyer = self.repo.get_user_by_id(lawyer_id)
        if not lawyer:
            raise ValueError(f"Lawyer user {lawyer_id} not found.")

        if lawyer.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            raise ValueError(f"User {lawyer.email} does not possess an advocate role (role={lawyer.role}).")

        if lawyer.advocate_status != AdvocateStatus.VERIFIED.value:
            raise ValueError(
                f"Advocate {lawyer.email} cannot be assigned: Verification status is "
                f"'{lawyer.advocate_status}', but '{AdvocateStatus.VERIFIED.value}' is required."
            )

        if lawyer.account_status != AccountStatus.ACTIVE.value:
            raise ValueError(f"Advocate {lawyer.email} account is not active (status={lawyer.account_status}).")

        is_reassignment = bool(review.assigned_lawyer_id and review.assigned_lawyer_id != lawyer_id)
        prev_lawyer_id = review.assigned_lawyer_id
        from_state = review.status

        # Perform assignment in repo
        self.repo.assign_review(
            review_id=review_id,
            lawyer_id=lawyer_id,
            assigned_by_id=assigning_user.id
        )

        self.repo.record_review_transition(
            review_id=review.id,
            from_state=from_state,
            to_state=ReviewStatus.ASSIGNED.value,
            actor_id=assigning_user.id,
            reason=f"Assigned to {lawyer.full_name} ({lawyer.email}). Rationale: {rationale or 'N/A'}"
        )

        event_type = EventType.LAWYER_REASSIGNED if is_reassignment else EventType.LAWYER_ASSIGNED
        self._log_audit_event(
            event_type=event_type,
            actor_type=ActorType.USER,
            source_document_id=review.document_id,
            review_id=review.id,
            actor_reference=assigning_user.id,
            payload={
                "assigned_lawyer_id": lawyer_id,
                "assigned_lawyer_name": lawyer.full_name,
                "previous_lawyer_id": prev_lawyer_id,
                "assigned_by_id": assigning_user.id,
                "rationale": rationale,
                "advocate_verification_status": lawyer.advocate_status
            }
        )

        return review

    def record_clause_decision(
        self,
        review_id: str,
        segment_id: str,
        decision: str,
        lawyer_rationale: str,
        actor_user: UserRecord,
        lawyer_notes: Optional[str] = None,
        is_disclosed_to_client: bool = False,
        statutory_evidence_json: Optional[str] = None,
        ai_metadata_json: Optional[str] = None,
        model_attribution_json: Optional[str] = None,
        evidence_quality_status: Optional[str] = None
    ) -> ClauseFindingRecord:
        """
        Records a lawyer's evaluation decision on an AI observation or clause finding.
        Requires assigned lawyer or supervising lawyer with verified status.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        # Access check
        if actor_user.role == UserRole.LAWYER.value:
            if review.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Forbidden: You are not assigned to review this contract.")
            if actor_user.advocate_status != AdvocateStatus.VERIFIED.value:
                raise PermissionError("Forbidden: Verified advocate credentials required.")
        elif actor_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: Only lawyers can record review decisions.")

        # Ensure review is in reviewable state
        if review.status not in (ReviewStatus.IN_REVIEW.value, ReviewStatus.ASSIGNED.value):
            raise ValueError(f"Cannot record decision: Review is in status '{review.status}', must be IN_REVIEW.")

        # Auto-transition to IN_REVIEW if currently ASSIGNED
        if review.status == ReviewStatus.ASSIGNED.value:
            self.transition_review_state(review_id, ReviewStatus.IN_REVIEW.value, actor_user, reason="Lawyer commenced review")

        # Validate decision type
        valid_decisions = [d.value for d in LawyerDecisionType]
        if decision not in valid_decisions:
            raise ValueError(f"Invalid decision '{decision}'. Valid options: {valid_decisions}")

        if not lawyer_rationale or not lawyer_rationale.strip():
            raise ValueError("A clear lawyer rationale is required for all review decisions.")

        finding = self.repo.create_or_update_clause_finding(
            review_id=review_id,
            document_id=review.document_id,
            segment_id=segment_id,
            decision=decision,
            lawyer_rationale=lawyer_rationale.strip(),
            lawyer_notes=lawyer_notes.strip() if lawyer_notes else None,
            statutory_evidence_json=statutory_evidence_json,
            ai_metadata_json=ai_metadata_json,
            model_attribution_json=model_attribution_json,
            evidence_quality_status=evidence_quality_status,
            is_disclosed_to_client=is_disclosed_to_client,
            author_id=actor_user.id,
            document_version=review.document_version
        )

        self._log_audit_event(
            event_type=EventType.LAWYER_DECISION_RECORDED,
            actor_type=ActorType.REVIEWER,
            source_document_id=review.document_id,
            review_id=review.id,
            clause_id=segment_id,
            actor_reference=actor_user.id,
            payload={
                "segment_id": segment_id,
                "decision": decision,
                "rationale_preview": lawyer_rationale[:100] if lawyer_rationale else "",
                "is_disclosed": is_disclosed_to_client,
                "has_notes": bool(lawyer_notes)
            }
        )

        return finding

    def create_lawyer_authored_finding(
        self,
        review_id: str,
        segment_id: str,
        risk_label: str,
        lawyer_observation: str,
        decision: str,
        lawyer_rationale: str,
        actor_user: UserRecord,
        lawyer_notes: Optional[str] = None,
        is_disclosed_to_client: bool = False,
        statutory_evidence_json: Optional[str] = None,
        evidence_quality_status: Optional[str] = None
    ) -> ClauseFindingRecord:
        """
        Creates an independent lawyer-authored finding not generated by AI.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        if actor_user.role == UserRole.LAWYER.value and review.assigned_lawyer_id != actor_user.id:
            raise PermissionError("Forbidden: You are not assigned to review this contract.")
        if actor_user.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            raise PermissionError("Forbidden: Only authorized advocates can author findings.")

        if not lawyer_observation or not lawyer_observation.strip():
            raise ValueError("Lawyer observation text is required.")
        if not lawyer_rationale or not lawyer_rationale.strip():
            raise ValueError("Lawyer rationale is required.")

        finding = self.repo.create_or_update_clause_finding(
            review_id=review_id,
            document_id=review.document_id,
            segment_id=segment_id,
            finding_origin=FindingOrigin.LAWYER_AUTHORED.value,
            risk_label=risk_label.strip(),
            ai_observation=lawyer_observation.strip(),
            decision=decision,
            lawyer_rationale=lawyer_rationale.strip(),
            lawyer_notes=lawyer_notes.strip() if lawyer_notes else None,
            statutory_evidence_json=statutory_evidence_json,
            evidence_quality_status=evidence_quality_status or EvidenceQualityStatus.TRACEABLE.value,
            is_disclosed_to_client=is_disclosed_to_client,
            author_id=actor_user.id,
            document_version=review.document_version
        )

        self._log_audit_event(
            event_type=EventType.FINDING_CREATED,
            actor_type=ActorType.REVIEWER,
            source_document_id=review.document_id,
            review_id=review.id,
            clause_id=segment_id,
            actor_reference=actor_user.id,
            payload={
                "segment_id": segment_id,
                "origin": FindingOrigin.LAWYER_AUTHORED.value,
                "risk_label": risk_label,
                "decision": decision
            }
        )

        return finding

    def create_or_update_ai_finding(
        self,
        review_id: str,
        segment_id: str,
        risk_label: str,
        ai_observation: str,
        ai_confidence_score: Optional[str] = None,
        ai_metadata_json: Optional[str] = None,
        model_attribution_json: Optional[str] = None,
        statutory_evidence_json: Optional[str] = None,
        evidence_quality_status: Optional[str] = None,
        is_disclosed_to_client: bool = False
    ) -> ClauseFindingRecord:
        """
        Creates or updates a preliminary AI finding grounded in model inference and statutory retrieval.
        Explicitly marks origin as AI_GENERATED and attaches model metadata and disclaimer.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        finding = self.repo.create_or_update_clause_finding(
            review_id=review_id,
            document_id=review.document_id,
            segment_id=segment_id,
            finding_origin=FindingOrigin.AI_GENERATED.value,
            risk_label=risk_label,
            ai_observation=ai_observation,
            ai_confidence_score=ai_confidence_score,
            statutory_evidence_json=statutory_evidence_json,
            ai_metadata_json=ai_metadata_json,
            model_attribution_json=model_attribution_json,
            evidence_quality_status=evidence_quality_status or EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value,
            is_disclosed_to_client=is_disclosed_to_client,
            document_version=review.document_version
        )
        return finding

    def add_comment(
        self,
        review_id: str,
        actor_user: UserRecord,
        comment_text: str,
        visibility: str = CommentVisibility.INTERNAL_LAWYER_ONLY.value,
        segment_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        parent_comment_id: Optional[str] = None
    ) -> ReviewCommentRecord:
        """
        Adds a scoped comment or clarification request.
        Strictly enforces that CLIENT users cannot post INTERNAL_LAWYER_ONLY comments.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        if not self.can_user_access_review(actor_user, review, require_full_content=True):
            raise PermissionError("Access forbidden to this review.")

        if not comment_text or not comment_text.strip():
            raise ValueError("Comment text cannot be empty.")

        # Client cannot create internal lawyer notes
        if actor_user.role == UserRole.CLIENT.value:
            if visibility == CommentVisibility.INTERNAL_LAWYER_ONLY.value:
                raise PermissionError("Clients are strictly prohibited from creating internal lawyer notes.")
            if visibility not in (CommentVisibility.CLIENT_VISIBLE.value, CommentVisibility.CLIENT_RESPONSE.value):
                visibility = CommentVisibility.CLIENT_RESPONSE.value

        comment = self.repo.create_comment(
            review_id=review_id,
            document_id=review.document_id,
            author_id=actor_user.id,
            author_role=actor_user.role,
            author_name=actor_user.full_name,
            comment_text=comment_text.strip(),
            visibility=visibility,
            segment_id=segment_id,
            finding_id=finding_id,
            parent_comment_id=parent_comment_id
        )

        evt_type = (
            EventType.CLIENT_CLARIFICATION_SUBMITTED
            if visibility == CommentVisibility.CLIENT_RESPONSE.value
            else EventType.COMMENT_ADDED
        )

        self._log_audit_event(
            event_type=evt_type,
            actor_type=ActorType.USER if actor_user.role == UserRole.CLIENT.value else ActorType.REVIEWER,
            source_document_id=review.document_id,
            review_id=review.id,
            clause_id=segment_id,
            actor_reference=actor_user.id,
            payload={
                "comment_id": comment.id,
                "visibility": visibility,
                "author_role": actor_user.role,
                "has_parent": bool(parent_comment_id)
            }
        )

        return comment

    def resolve_comment(self, comment_id: str, actor_user: UserRecord) -> ReviewCommentRecord:
        """
        Resolves a comment thread or clarification request.
        Only lawyers and supervising lawyers can mark comments resolved.
        """
        if actor_user.role not in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            raise PermissionError("Only reviewing advocates can resolve clarification threads.")

        comment = self.repo.resolve_comment(comment_id, resolved_by_id=actor_user.id)
        if not comment:
            raise ValueError(f"Comment {comment_id} not found.")

        self._log_audit_event(
            event_type=EventType.COMMENT_RESOLVED,
            actor_type=ActorType.REVIEWER,
            source_document_id=comment.document_id,
            review_id=comment.review_id,
            clause_id=comment.segment_id,
            actor_reference=actor_user.id,
            payload={
                "comment_id": comment_id,
                "resolved_by": actor_user.id
            }
        )

        return comment

    def propose_document_revision(
        self,
        document_id: str,
        review_id: str,
        actor_user: UserRecord,
        revised_text: str,
        change_reason: Optional[str] = None
    ) -> DocumentRevisionRecord:
        """
        Creates a versioned revision of the contract text.
        Preserves original document completely intact and immutable.
        """
        doc = self.repo.get_document_by_id(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        if not self.can_user_access_review(actor_user, review, require_full_content=True):
            raise PermissionError("Access forbidden to this review.")

        if not revised_text or not revised_text.strip():
            raise ValueError("Revised text cannot be empty.")

        # Fetch original text snapshot for diff generation
        snapshot = doc.text_snapshots[0] if doc.text_snapshots else None
        orig_text = snapshot.raw_text if snapshot else ""

        # Compute unified diff
        diff_lines = list(difflib.unified_diff(
            orig_text.splitlines(keepends=True),
            revised_text.splitlines(keepends=True),
            fromfile=f"original_v1_{doc.sanitized_filename}",
            tofile=f"proposed_rev_{doc.sanitized_filename}"
        ))
        diff_summary = "".join(diff_lines[:50])

        existing_revs = self.repo.get_revisions_for_document(document_id)
        next_version = len(existing_revs) + 2

        rev = self.repo.create_document_revision(
            document_id=document_id,
            review_id=review_id,
            version_number=next_version,
            original_file_sha256=doc.file_sha256,
            revised_text=revised_text,
            author_id=actor_user.id,
            change_reason=change_reason,
            diff_summary=diff_summary
        )

        # Transition review if applicable
        if actor_user.role == UserRole.CLIENT.value:
            if review.status == ReviewStatus.REVISION_REQUESTED.value:
                self.transition_review_state(review_id, ReviewStatus.CLIENT_RESPONSE_RECEIVED.value, actor_user, reason="Client submitted revision proposal")
        elif actor_user.role in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value):
            if review.status == ReviewStatus.IN_REVIEW.value:
                self.transition_review_state(review_id, ReviewStatus.REVISION_REQUESTED.value, actor_user, reason="Lawyer proposed contract revisions")

        self._log_audit_event(
            event_type=EventType.REVISION_PROPOSED,
            actor_type=ActorType.USER if actor_user.role == UserRole.CLIENT.value else ActorType.REVIEWER,
            source_document_id=document_id,
            review_id=review_id,
            actor_reference=actor_user.id,
            payload={
                "revision_id": rev.id,
                "version_number": next_version,
                "revised_text_sha256": rev.revised_text_sha256,
                "change_reason": change_reason
            }
        )

        return rev

    def decide_document_revision(
        self,
        revision_id: str,
        decision: str,
        actor_user: UserRecord,
        rationale: Optional[str] = None
    ) -> DocumentRevisionRecord:
        """
        Accepts or rejects a proposed document revision.
        Original uploaded document remains immutable.
        """
        rev = self.session.query(DocumentRevisionRecord).filter(DocumentRevisionRecord.id == revision_id).first()
        if not rev:
            raise ValueError(f"Revision {revision_id} not found.")

        if decision not in (RevisionStatus.ACCEPTED.value, RevisionStatus.REJECTED.value):
            raise ValueError(f"Invalid decision '{decision}'. Must be ACCEPTED or REJECTED.")

        updated = self.repo.decide_document_revision(
            revision_id=revision_id,
            decision=decision,
            decided_by_id=actor_user.id
        )

        event_type = EventType.REVISION_ACCEPTED if decision == RevisionStatus.ACCEPTED.value else EventType.COMMENT_RESOLVED
        self._log_audit_event(
            event_type=event_type,
            actor_type=ActorType.REVIEWER,
            source_document_id=rev.document_id,
            review_id=rev.review_id,
            actor_reference=actor_user.id,
            payload={
                "revision_id": revision_id,
                "decision": decision,
                "rationale": rationale
            }
        )

        return updated

    def complete_review(
        self,
        review_id: str,
        actor_user: UserRecord,
        completion_summary: str,
        outstanding_limitations: Optional[str] = None,
        unresolved_questions: Optional[str] = None,
        further_client_action_required: bool = False
    ) -> ReviewRecord:
        """
        Completes a review after validating all completion workflow prerequisites.
        Requires assigned lawyer or supervising lawyer.
        Attaches statutory disclaimer.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        if actor_user.role == UserRole.LAWYER.value:
            if review.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Forbidden: You are not the assigned reviewing lawyer.")
            if actor_user.advocate_status != AdvocateStatus.VERIFIED.value:
                raise PermissionError("Forbidden: Verified advocate credentials required.")
        elif actor_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: Only authorized advocates can mark a review complete.")

        if review.status != ReviewStatus.IN_REVIEW.value:
            raise ValueError(f"Cannot complete review: Current status is '{review.status}', must be IN_REVIEW.")

        if not completion_summary or not completion_summary.strip():
            raise ValueError("A comprehensive completion summary is mandatory to complete a review.")

        # Prerequisites: Check for unresolved client clarifications
        unresolved_clarifications = (
            self.session.query(ReviewCommentRecord)
            .filter(
                ReviewCommentRecord.review_id == review_id,
                ReviewCommentRecord.visibility == CommentVisibility.CLARIFICATION_REQUEST.value,
                ReviewCommentRecord.is_resolved == False
            )
            .count()
        )
        if unresolved_clarifications > 0:
            raise ValueError(
                f"Cannot complete review: There are {unresolved_clarifications} unresolved client clarification requests. "
                "All clarification requests must be resolved or formally documented before completion."
            )

        from_state = review.status
        completed = self.repo.complete_review(
            review_id=review_id,
            completed_by_id=actor_user.id,
            completion_summary=completion_summary.strip(),
            outstanding_limitations=outstanding_limitations.strip() if outstanding_limitations else None,
            unresolved_questions=unresolved_questions.strip() if unresolved_questions else None,
            further_client_action_required=further_client_action_required,
            disclaimer_text=MANDATORY_REVIEW_DISCLAIMER
        )

        self.repo.record_review_transition(
            review_id=review_id,
            from_state=from_state,
            to_state=ReviewStatus.REVIEW_COMPLETED.value,
            actor_id=actor_user.id,
            reason=f"Review completed by {actor_user.full_name}. Summary: {completion_summary[:80]}"
        )

        self._log_audit_event(
            event_type=EventType.REVIEW_COMPLETED,
            actor_type=ActorType.REVIEWER,
            source_document_id=review.document_id,
            review_id=review.id,
            actor_reference=actor_user.id,
            payload={
                "completed_by_id": actor_user.id,
                "completed_by_name": actor_user.full_name,
                "further_client_action_required": further_client_action_required,
                "disclaimer_attached": True
            }
        )

        return completed

    def reopen_review(
        self,
        review_id: str,
        actor_user: UserRecord,
        reason: str
    ) -> ReviewRecord:
        """
        Reopens a completed review with mandatory justification.
        Requires assigned lawyer or supervising lawyer.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found.")

        if actor_user.role == UserRole.LAWYER.value:
            if review.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Forbidden: You are not the assigned reviewing lawyer.")
        elif actor_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: Only reviewing advocates or supervisors can reopen a review.")

        if review.status != ReviewStatus.REVIEW_COMPLETED.value:
            raise ValueError(f"Cannot reopen review: Status is '{review.status}', must be REVIEW_COMPLETED.")

        if not reason or not reason.strip():
            raise ValueError("A clear, substantive reason is required to reopen a completed review.")

        # Explicit transition from REVIEW_COMPLETED -> REVIEW_REOPENED -> IN_REVIEW
        self.repo.record_review_transition(
            review_id=review_id,
            from_state=ReviewStatus.REVIEW_COMPLETED.value,
            to_state=ReviewStatus.REVIEW_REOPENED.value,
            actor_id=actor_user.id,
            reason=reason.strip()
        )

        self.repo.record_review_transition(
            review_id=review_id,
            from_state=ReviewStatus.REVIEW_REOPENED.value,
            to_state=ReviewStatus.IN_REVIEW.value,
            actor_id=actor_user.id,
            reason="Resumed review operations following reopening"
        )

        reopened = self.repo.reopen_review(review_id, actor_id=actor_user.id, reason=reason)

        self._log_audit_event(
            event_type=EventType.REVIEW_REOPENED,
            actor_type=ActorType.REVIEWER,
            source_document_id=review.document_id,
            review_id=review.id,
            actor_reference=actor_user.id,
            payload={
                "reopened_by_id": actor_user.id,
                "reason": reason.strip()
            }
        )

        return reopened
