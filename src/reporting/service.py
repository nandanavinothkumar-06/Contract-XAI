"""
Core Report Service for Task 034: Final Lawyer-Reviewed Reports and Client Feedback.

Enforces:
1. Strict Report Eligibility checks (document version match, REVIEW_COMPLETED status,
   all findings with recorded decisions and rationales, no unresolved clarifications,
   assigned lawyer / supervisor authorization).
2. Distinction between draft previews and immutable final reports.
3. Segregation of AI observations, lawyer decisions, corrections, and authored findings.
4. Clear marking of rejected AI observations so they are never presented as accepted conclusions.
5. Strict exclusion of internal lawyer notes and confidential comments from client reports.
6. Report versioning and superseding without destructive overwriting.
7. Publication-quality PDF generation with cryptographic SHA-256 integrity digests.
8. Structured client feedback collection and advocate response lifecycle.
9. Hash-chained audit logging for all reporting and feedback events.
"""

import os
import io
import uuid
import json
import hashlib
import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from src.persistence.models import (
    UserRecord, DocumentRecord, ReviewRecord, ReviewCommentRecord,
    ClauseFindingRecord, FinalReportRecord, ClientFeedbackRecord, FeedbackResponseRecord,
    UserRole, AccountStatus, AdvocateStatus,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility,
    ReportStatus, FeedbackStatus, AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.reporting.schema import (
    MANDATORY_LEGAL_DISCLAIMER, STATUTORY_CORPUS_NOTICE, SCORE_RETRIEVAL_DISCLAIMER,
    FeedbackSubmitRequest, FeedbackResponseRequest
)
from src.reporting.client_pdf import ClientPDFReportBuilder
from src.audit.provenance import EventType, ActorType
from src.audit.schema import AuditEvent
from src.audit.events import calculate_event_hash

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "reports"))


class ReportService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = DocumentRepository(session)
        os.makedirs(REPORTS_DIR, exist_ok=True)

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
            module_name="src.reporting.service",
            module_version="1.0.0",
            previous_event_hash=previous_hash,
            event_payload=payload or {}
        )
        evt.event_hash = calculate_event_hash(evt)

        db_event = AuditEventRecord(
            id=str(uuid.uuid4()),
            document_id=source_document_id,
            event_id=evt.event_id,
            event_type=evt.event_type.value if hasattr(evt.event_type, "value") else str(evt.event_type),
            timestamp=evt.timestamp,
            actor_type=evt.actor_type.value if hasattr(evt.actor_type, "value") else str(evt.actor_type),
            previous_event_hash=evt.previous_event_hash,
            event_hash=evt.event_hash,
            payload_json=json.dumps(evt.event_payload),
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.session.add(db_event)
        self.session.flush()
        return evt

    # =========================================================================
    # 1. REPORT ELIGIBILITY VERIFICATION
    # =========================================================================

    def check_report_eligibility(
        self,
        review_id: str,
        actor_user: UserRecord
    ) -> Tuple[bool, Optional[str], Optional[ReviewRecord]]:
        """
        Server-side validation of all prerequisites for final report generation.
        Returns: (is_eligible, failure_reason, review_record)
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            return False, f"Review '{review_id}' does not exist.", None

        doc = review.document
        if not doc:
            return False, f"Associated document for review '{review_id}' was not found.", review

        # Version consistency check
        if review.document_version != getattr(doc, "current_version", 1):
            # Check if document has revisions
            revisions = self.repo.get_revisions_for_document(doc.id)
            latest_version = max([r.version_number for r in revisions], default=1) if revisions else 1
            if review.document_version < latest_version:
                return False, f"Review is for document version {review.document_version}, but latest document version is {latest_version}.", review

        # Role and permissions check
        if actor_user.role == UserRole.LAWYER.value:
            if review.assigned_lawyer_id != actor_user.id:
                return False, "Unauthorized: You are not the assigned reviewing lawyer for this document.", review
            if actor_user.advocate_status != AdvocateStatus.VERIFIED.value:
                return False, "Unauthorized: Verified advocate status is required to issue final reports.", review
        elif actor_user.role != UserRole.SUPERVISING_LAWYER.value:
            return False, "Unauthorized: Only assigned verified lawyers or supervising lawyers can generate final reports.", review

        # Review lifecycle state: Must be REVIEW_COMPLETED
        if review.status == ReviewStatus.REVIEW_REOPENED.value:
            return False, "Cannot generate final report: The review has been reopened and requires re-evaluation.", review
        if review.status != ReviewStatus.REVIEW_COMPLETED.value:
            return False, f"Cannot generate final report: Review status is '{review.status}'. It must reach REVIEW_COMPLETED first.", review

        # Completion summary required
        if not review.completion_summary or not review.completion_summary.strip():
            return False, "Cannot generate final report: Missing mandatory completion summary in the review record.", review

        # Unresolved client clarifications check
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
            return False, f"Cannot generate final report: {unresolved_clarifications} unresolved client clarification request(s) block completion.", review

        # Findings decision and rationale verification
        findings = review.findings
        for finding in findings:
            if not finding.decision:
                return False, f"Finding '{finding.id}' for segment '{finding.segment_id}' has no recorded lawyer decision.", review
            if not finding.lawyer_rationale or not finding.lawyer_rationale.strip():
                return False, f"Finding '{finding.id}' has no recorded lawyer rationale.", review
            if finding.decision == LawyerDecisionType.REQUIRES_CLIENT_CLARIFICATION.value:
                return False, f"Finding '{finding.id}' still has unresolved client clarification requirement.", review

        return True, None, review

    # =========================================================================
    # 2. REPORT COMPILATION & JSON PAYLOAD CONSTRUCTION
    # =========================================================================

    def compile_report_payload(
        self,
        review_id: str,
        is_final: bool = True
    ) -> Dict[str, Any]:
        """
        Compiles the immutable structured data payload for the report.
        Excludes confidential internal notes and comments.
        Segregates AI observations from human lawyer conclusions.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review '{review_id}' not found.")

        doc = review.document
        lawyer = review.assigned_lawyer

        # Process findings
        findings_list = []
        accepted_ai_cnt = 0
        corrected_cnt = 0
        rejected_ai_cnt = 0
        lawyer_authored_cnt = 0

        for f in review.findings:
            origin = f.finding_origin or FindingOrigin.AI_GENERATED.value
            decision = f.decision or "UNREVIEWED"
            is_rejected = (decision == LawyerDecisionType.REJECT_AI_OBSERVATION.value)

            if origin == FindingOrigin.LAWYER_AUTHORED.value:
                lawyer_authored_cnt += 1
            elif is_rejected:
                rejected_ai_cnt += 1
            elif decision in (LawyerDecisionType.ACCEPT_AI_OBSERVATION.value, "ACCEPT", "ACCEPTED"):
                accepted_ai_cnt += 1
            elif decision in (LawyerDecisionType.CORRECT_AI_OBSERVATION.value, "CORRECT", "CORRECTED", "MODIFY"):
                corrected_cnt += 1

            # Parse statutory references if available
            stat_refs = []
            if f.statutory_evidence_json:
                try:
                    evidence_data = json.loads(f.statutory_evidence_json)
                    if isinstance(evidence_data, dict) and "passages" in evidence_data:
                        for p in evidence_data["passages"]:
                            stat_refs.append({
                                "act_name": p.get("statute_title") or p.get("act_name", "Indian Commercial Corpus"),
                                "section": str(p.get("section_number") or p.get("section", "Provision")),
                                "title": p.get("section_title") or p.get("title", ""),
                                "excerpt": p.get("passage_text") or p.get("text") or p.get("excerpt", ""),
                                "source_id": p.get("statute_id") or p.get("source_id", "CURATED_EXTRACT"),
                                "snapshot_version": p.get("source_version") or p.get("snapshot_version", "1.0"),
                                "commencement_date": p.get("legal_status"),
                                "source_checksum": p.get("source_checksum", ""),
                                "score_semantics_disclaimer": SCORE_RETRIEVAL_DISCLAIMER,
                                "retrieval_caveat": p.get("ranking_score_meaning")
                            })
                    elif isinstance(evidence_data, list):
                        for item in evidence_data:
                            stat_refs.append({
                                "act_name": item.get("act_name") or item.get("statute_title", "Indian Legal Corpus"),
                                "section": str(item.get("section") or item.get("section_number", "Provision")),
                                "title": item.get("title") or item.get("section_title"),
                                "excerpt": item.get("text") or item.get("excerpt") or item.get("passage_text", ""),
                                "source_id": item.get("source_id", "CURATED_EXTRACT"),
                                "snapshot_version": item.get("snapshot_version", "1.0"),
                                "commencement_date": item.get("commencement_date"),
                                "source_checksum": item.get("source_checksum", ""),
                                "score_semantics_disclaimer": SCORE_RETRIEVAL_DISCLAIMER,
                                "retrieval_caveat": item.get("retrieval_caveat")
                            })
                    elif isinstance(evidence_data, dict):
                        stat_refs.append({
                            "act_name": evidence_data.get("act_name") or evidence_data.get("statute_title", "Indian Legal Corpus"),
                            "section": str(evidence_data.get("section") or evidence_data.get("section_number", "Provision")),
                            "title": evidence_data.get("title") or evidence_data.get("section_title"),
                            "excerpt": evidence_data.get("text") or evidence_data.get("excerpt") or evidence_data.get("passage_text", ""),
                            "source_id": evidence_data.get("source_id", "CURATED_EXTRACT"),
                            "snapshot_version": evidence_data.get("snapshot_version", "1.0"),
                            "commencement_date": evidence_data.get("commencement_date"),
                            "source_checksum": evidence_data.get("source_checksum", ""),
                            "score_semantics_disclaimer": SCORE_RETRIEVAL_DISCLAIMER,
                            "retrieval_caveat": evidence_data.get("retrieval_caveat")
                        })
                except Exception:
                    pass

            # Resolve segment text
            segment_record = (
                self.session.query(DocumentRecord)
                .join(DocumentRecord.segments)
                .filter(DocumentRecord.id == doc.id)
                .first()
            )
            clause_heading = None
            clause_numbering = None
            clause_text_excerpt = ""

            for s in (doc.segments if doc else []):
                if s.segment_id == f.segment_id:
                    clause_heading = s.heading
                    clause_numbering = s.numbering
                    clause_text_excerpt = s.text[:300] if s.text else ""
                    break

            if not clause_text_excerpt and f.ai_observation:
                clause_text_excerpt = f.ai_observation[:200]

            ai_meta = None
            if f.ai_metadata_json:
                try:
                    ai_meta = json.loads(f.ai_metadata_json)
                except Exception:
                    ai_meta = None

            model_attrib = None
            if f.model_attribution_json:
                try:
                    model_attrib = json.loads(f.model_attribution_json)
                except Exception:
                    model_attrib = None

            # NOTE: internal lawyer notes are NEVER included!
            finding_item = {
                "finding_id": f.id,
                "segment_id": f.segment_id,
                "document_version": f.document_version,
                "evidence_quality_status": f.evidence_quality_status or "NO_MATCHING_EVIDENCE",
                "clause_heading": clause_heading,
                "clause_numbering": clause_numbering,
                "clause_text_excerpt": clause_text_excerpt,
                "finding_origin": origin,
                "risk_label": f.risk_label,
                "ai_confidence_score": f.ai_confidence_score,
                "ai_observation": f.ai_observation,
                "ai_metadata": ai_meta,
                "model_attribution": model_attrib,
                "lawyer_decision": decision,
                "lawyer_decision_label": decision.replace("_", " "),
                "lawyer_rationale": f.lawyer_rationale or "",
                "statutory_references": stat_refs,
                "is_clarification_flagged": (decision == LawyerDecisionType.REQUIRES_CLIENT_CLARIFICATION.value),
                "is_ai_observation_rejected": is_rejected
            }
            findings_list.append(finding_item)

        total_findings = len(findings_list)
        summary_text = review.completion_summary or "Contract legal assessment completed under advocate supervision."

        payload = {
            "metadata": {
                "report_id": str(uuid.uuid4()),
                "report_number": "",  # Populated during generation
                "report_version": 1,
                "status": ReportStatus.FINAL.value if is_final else ReportStatus.DRAFT.value,
                "is_final": is_final,
                "document_id": doc.id if doc else "",
                "document_version": review.document_version,
                "original_filename": doc.original_filename if doc else "contract",
                "file_sha256": doc.file_sha256 if doc else "",
                "review_id": review.id,
                "review_completed_at": review.completed_at.isoformat() if review.completed_at else None,
                "assigned_lawyer_id": lawyer.id if lawyer else None,
                "assigned_lawyer_name": lawyer.full_name if lawyer else "Assigned Advocate",
                "assigned_lawyer_email": lawyer.email if lawyer else "",
                "bar_enrolment_id": lawyer.bar_enrolment_id if lawyer else None,
                "state_bar_council": lawyer.state_bar_council if lawyer else None,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                "content_sha256": "",
                "pdf_storage_path": None,
                "pdf_sha256": None,
                "superseded_at": None,
                "superseded_by_id": None,
                "supersession_reason": None
            },
            "executive_summary": {
                "contract_description": f"Contract document: {doc.original_filename if doc else 'Unnamed'}",
                "scope_of_review": "AI-assisted contractual risk and Indian statutory grounding review under verified advocate supervision.",
                "key_findings_summary": summary_text,
                "total_findings_count": total_findings,
                "accepted_ai_findings_count": accepted_ai_cnt,
                "corrected_findings_count": corrected_cnt,
                "rejected_ai_findings_count": rejected_ai_cnt,
                "lawyer_authored_findings_count": lawyer_authored_cnt,
                "outstanding_limitations": review.outstanding_limitations,
                "unresolved_questions": review.unresolved_questions,
                "further_client_action_required": bool(review.further_client_action_required)
            },
            "findings": findings_list,
            "disclaimer_and_limitations": MANDATORY_LEGAL_DISCLAIMER,
            "statutory_corpus_notice": STATUTORY_CORPUS_NOTICE
        }

        # Deterministic SHA-256 computation of payload content
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        content_hash = hashlib.sha256(payload_bytes).hexdigest()
        payload["metadata"]["content_sha256"] = content_hash

        return payload

    # =========================================================================
    # 3. REPORT GENERATION & PDF EXPORT
    # =========================================================================

    def generate_final_report(
        self,
        review_id: str,
        actor_user: UserRecord,
        export_pdf: bool = True
    ) -> FinalReportRecord:
        """
        Validates prerequisites, compiles final report, supersedes older versions,
        generates PDF, stores artifact, and hash-chains audit events.
        """
        # Audit: Request initiated
        self._log_audit_event(
            event_type=EventType.REPORT_GENERATION_REQUESTED,
            actor_type=ActorType.REVIEWER,
            review_id=review_id,
            actor_reference=actor_user.id,
            payload={"review_id": review_id, "requested_by": actor_user.email}
        )

        is_eligible, failure_reason, review = self.check_report_eligibility(review_id, actor_user)
        if not is_eligible:
            self._log_audit_event(
                event_type=EventType.REPORT_GENERATION_FAILED,
                actor_type=ActorType.REVIEWER,
                review_id=review_id,
                actor_reference=actor_user.id,
                payload={"review_id": review_id, "failure_reason": failure_reason}
            )
            raise ValueError(f"Report Generation Rejected: {failure_reason}")

        # Check existing final reports for this review to manage versioning and superseding
        existing_reports = self.repo.get_reports_for_review(review_id)
        active_report = next((r for r in existing_reports if r.status == ReportStatus.FINAL.value), None)

        report_version = 1
        if active_report:
            report_version = active_report.report_version + 1

        report_id = str(uuid.uuid4())
        short_doc = review.document_id[:8].upper()
        short_id = uuid.uuid4().hex[:6].upper()
        report_number = f"REP-{short_doc}-V{report_version}-{short_id}"

        # Compile payload
        payload = self.compile_report_payload(review_id=review_id, is_final=True)
        payload["metadata"]["report_id"] = report_id
        payload["metadata"]["report_number"] = report_number
        payload["metadata"]["report_version"] = report_version
        
        # Recompute hash with exact metadata
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        content_hash = hashlib.sha256(payload_bytes).hexdigest()
        payload["metadata"]["content_sha256"] = content_hash

        # Supersede existing active report if present
        if active_report:
            self.repo.supersede_report(
                report_id=active_report.id,
                new_report_id=report_id,
                reason=f"Superseded by new Final Report version {report_version} ({report_number})"
            )
            self._log_audit_event(
                event_type=EventType.REPORT_SUPERSEDED,
                actor_type=ActorType.REVIEWER,
                source_document_id=review.document_id,
                review_id=review.id,
                actor_reference=actor_user.id,
                payload={
                    "old_report_id": active_report.id,
                    "old_report_number": active_report.report_number,
                    "new_report_id": report_id,
                    "new_report_number": report_number,
                    "reason": f"Superseded by version {report_version}"
                }
            )

        # Persist FinalReportRecord
        report = self.repo.create_report(
            report_id=report_id,
            report_number=report_number,
            document_id=review.document_id,
            review_id=review.id,
            document_version=review.document_version,
            report_version=report_version,
            title=f"Legal Review Assessment — {review.document.original_filename if review.document else 'Contract'}",
            disclaimer_text=MANDATORY_LEGAL_DISCLAIMER,
            report_payload_json=json.dumps(payload),
            content_sha256=content_hash,
            generated_by_id=actor_user.id,
            status=ReportStatus.FINAL.value,
            is_final=True,
            executive_summary=payload["executive_summary"]["key_findings_summary"],
            scope_of_review=payload["executive_summary"]["scope_of_review"],
            review_outcome_summary=review.completion_summary,
            outstanding_limitations=review.outstanding_limitations,
            statutory_corpus_version="1.0"
        )

        # Generate and store PDF if requested
        if export_pdf:
            try:
                pdf_filename = f"{report_number}.pdf"
                pdf_path = os.path.join(REPORTS_DIR, pdf_filename)
                builder = ClientPDFReportBuilder(payload, output_path=pdf_path)
                pdf_bytes = builder.build()

                pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
                file_size = len(pdf_bytes)

                self.repo.update_report_pdf_artifact(
                    report_id=report.id,
                    pdf_path=pdf_path,
                    pdf_sha256=pdf_hash,
                    file_size=file_size
                )
                payload["metadata"]["pdf_storage_path"] = pdf_path
                payload["metadata"]["pdf_sha256"] = pdf_hash
                report.report_payload_json = json.dumps(payload)
                self.session.flush()

            except Exception as e:
                # PDF generation failure must not mark success falsely
                self._log_audit_event(
                    event_type=EventType.REPORT_GENERATION_FAILED,
                    actor_type=ActorType.REVIEWER,
                    source_document_id=review.document_id,
                    review_id=review.id,
                    actor_reference=actor_user.id,
                    payload={"report_id": report_id, "pdf_error": str(e)}
                )
                raise RuntimeError(f"Report created but PDF generation failed: {str(e)}")

        # Audit: Report successfully generated
        self._log_audit_event(
            event_type=EventType.REPORT_GENERATED,
            actor_type=ActorType.REVIEWER,
            source_document_id=review.document_id,
            review_id=review.id,
            actor_reference=actor_user.id,
            payload={
                "report_id": report.id,
                "report_number": report.report_number,
                "report_version": report.report_version,
                "content_sha256": report.content_sha256,
                "pdf_sha256": report.pdf_sha256
            }
        )

        return report

    def generate_draft_preview(
        self,
        review_id: str,
        actor_user: UserRecord
    ) -> Dict[str, Any]:
        """
        Generates a non-final draft preview for review progress inspection.
        Clearly marked as DRAFT with is_final = False.
        """
        review = self.repo.get_review_by_id(review_id)
        if not review:
            raise ValueError(f"Review '{review_id}' not found.")

        # Permissions: Assigned lawyer, supervisor, or document owner
        if actor_user.role == UserRole.CLIENT.value:
            if review.document.owner_id != actor_user.id:
                raise PermissionError("Forbidden: You cannot preview reports for other clients' contracts.")
        elif actor_user.role == UserRole.LAWYER.value:
            if review.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Forbidden: You are not assigned to this review.")

        payload = self.compile_report_payload(review_id=review_id, is_final=False)
        payload["metadata"]["report_number"] = f"DRAFT-{review.document_id[:8].upper()}-V{review.document_version}"
        payload["metadata"]["status"] = ReportStatus.DRAFT.value

        self._log_audit_event(
            event_type=EventType.REPORT_PREVIEWED,
            actor_type=ActorType.REVIEWER if actor_user.role in (UserRole.LAWYER.value, UserRole.SUPERVISING_LAWYER.value) else ActorType.USER,
            source_document_id=review.document_id,
            review_id=review.id,
            actor_reference=actor_user.id,
            payload={"review_id": review_id, "is_final": False}
        )

        return payload

    def download_report_pdf(
        self,
        report_id: str,
        actor_user: UserRecord
    ) -> Tuple[bytes, str]:
        """
        Validates RBAC and returns PDF bytes and suggested filename.
        Enforces tenant isolation between clients.
        """
        report = self.repo.get_report_by_id(report_id)
        if not report:
            raise ValueError(f"Report '{report_id}' not found.")

        doc = report.document

        # Access Control
        if actor_user.role == UserRole.CLIENT.value:
            if doc and doc.owner_id != actor_user.id:
                self._log_audit_event(
                    event_type=EventType.AUTHORIZATION_FAILURE,
                    actor_type=ActorType.USER,
                    source_document_id=doc.id if doc else None,
                    review_id=report.review_id,
                    actor_reference=actor_user.id,
                    payload={"action": "download_pdf", "report_id": report_id, "reason": "Tenant isolation violation"}
                )
                raise PermissionError("Forbidden: You cannot access or download reports belonging to other clients.")
        elif actor_user.role == UserRole.LAWYER.value:
            if doc and doc.assigned_lawyer_id != actor_user.id and report.generated_by_id != actor_user.id:
                raise PermissionError("Forbidden: You are not assigned to this contract's review.")
        elif actor_user.role == UserRole.AUDITOR.value:
            # Auditors can inspect report metadata, not raw client PDF downloads unless permitted
            pass

        # Load PDF bytes
        pdf_bytes = None
        if report.pdf_storage_path and os.path.exists(report.pdf_storage_path):
            with open(report.pdf_storage_path, "rb") as f:
                pdf_bytes = f.read()
        else:
            # Recompile on demand if missing
            payload = json.loads(report.report_payload_json)
            builder = ClientPDFReportBuilder(payload)
            pdf_bytes = builder.build()

        self._log_audit_event(
            event_type=EventType.REPORT_DOWNLOADED,
            actor_type=ActorType.USER if actor_user.role == UserRole.CLIENT.value else ActorType.REVIEWER,
            source_document_id=doc.id if doc else None,
            review_id=report.review_id,
            actor_reference=actor_user.id,
            payload={
                "report_id": report_id,
                "report_number": report.report_number,
                "file_sha256": hashlib.sha256(pdf_bytes).hexdigest()
            }
        )

        filename = f"{report.report_number}.pdf"
        return pdf_bytes, filename

    # =========================================================================
    # 4. CLIENT FEEDBACK WORKFLOW
    # =========================================================================

    def submit_client_feedback(
        self,
        report_id: str,
        client_user: UserRecord,
        feedback_data: FeedbackSubmitRequest
    ) -> ClientFeedbackRecord:
        """
        Validates report, ensures client owns the document, validates ratings (1-5),
        and records structured client feedback.
        """
        report = self.repo.get_report_by_id(report_id)
        if not report:
            raise ValueError(f"Report '{report_id}' not found.")

        if not report.is_final:
            raise ValueError("Feedback cannot be submitted against draft previews. Only final reports accept feedback.")

        doc = report.document
        if client_user.role == UserRole.CLIENT.value:
            if doc and doc.owner_id != client_user.id:
                raise PermissionError("Forbidden: You cannot submit feedback for another client's report.")

        # Determine initial status
        initial_status = FeedbackStatus.SUBMITTED.value
        if feedback_data.needs_clarification or feedback_data.follow_up_requested:
            initial_status = FeedbackStatus.RESPONSE_REQUIRED.value

        feedback_id = str(uuid.uuid4())
        feedback = self.repo.create_client_feedback(
            feedback_id=feedback_id,
            report_id=report.id,
            document_id=report.document_id,
            review_id=report.review_id,
            client_id=client_user.id,
            overall_satisfaction=feedback_data.overall_satisfaction,
            clarity_rating=feedback_data.clarity_rating,
            usefulness_rating=feedback_data.usefulness_rating,
            needs_clarification=feedback_data.needs_clarification,
            follow_up_requested=feedback_data.follow_up_requested,
            client_comments=feedback_data.client_comments,
            status=initial_status
        )

        self._log_audit_event(
            event_type=EventType.FEEDBACK_SUBMITTED,
            actor_type=ActorType.USER,
            source_document_id=report.document_id,
            review_id=report.review_id,
            actor_reference=client_user.id,
            payload={
                "feedback_id": feedback.id,
                "report_id": report.id,
                "overall_satisfaction": feedback.overall_satisfaction,
                "needs_clarification": feedback.needs_clarification,
                "status": feedback.status
            }
        )

        return feedback

    def respond_to_feedback(
        self,
        feedback_id: str,
        actor_user: UserRecord,
        response_data: FeedbackResponseRequest
    ) -> FeedbackResponseRecord:
        """
        Records an advocate or supervising lawyer response to client feedback.
        Distinguishes client-visible responses from internal notes.
        """
        feedback = self.repo.get_feedback_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback '{feedback_id}' not found.")

        # Authorization: Assigned lawyer or supervising lawyer
        if actor_user.role == UserRole.LAWYER.value:
            doc = feedback.document
            if doc and doc.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Forbidden: You are not assigned to this client review.")
        elif actor_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: Only assigned advocates or supervising lawyers can respond to client feedback.")

        response_id = str(uuid.uuid4())
        resp = self.repo.add_feedback_response(
            response_id=response_id,
            feedback_id=feedback.id,
            responder_id=actor_user.id,
            responder_role=actor_user.role,
            response_text=response_data.response_text.strip(),
            is_client_visible=response_data.is_client_visible,
            internal_notes=response_data.internal_notes
        )

        # Update feedback status to RESPONDED if response is client-visible
        if response_data.is_client_visible and feedback.status in (FeedbackStatus.SUBMITTED.value, FeedbackStatus.RESPONSE_REQUIRED.value):
            self.repo.update_feedback_status(feedback.id, FeedbackStatus.RESPONDED.value)

        self._log_audit_event(
            event_type=EventType.FEEDBACK_RESPONSE_RECORDED,
            actor_type=ActorType.REVIEWER,
            source_document_id=feedback.document_id,
            review_id=feedback.review_id,
            actor_reference=actor_user.id,
            payload={
                "feedback_id": feedback.id,
                "response_id": response_id,
                "is_client_visible": response_data.is_client_visible,
                "responder": actor_user.email
            }
        )

        return resp

    def update_feedback_status(
        self,
        feedback_id: str,
        actor_user: UserRecord,
        new_status: str
    ) -> ClientFeedbackRecord:
        """
        Transitions feedback state: ACKNOWLEDGED, CLOSED, etc.
        """
        feedback = self.repo.get_feedback_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback '{feedback_id}' not found.")

        # Authorization: Assigned lawyer or supervising lawyer
        if actor_user.role == UserRole.LAWYER.value:
            doc = feedback.document
            if doc and doc.assigned_lawyer_id != actor_user.id:
                raise PermissionError("Forbidden: You are not assigned to this client review.")
        elif actor_user.role != UserRole.SUPERVISING_LAWYER.value:
            raise PermissionError("Forbidden: Only authorized advocates can update feedback status.")

        valid_statuses = [s.value for s in FeedbackStatus]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of: {valid_statuses}")

        updated = self.repo.update_feedback_status(feedback_id, new_status)

        # Audit event based on new status
        evt_type = EventType.FEEDBACK_ACKNOWLEDGED if new_status == FeedbackStatus.ACKNOWLEDGED.value else (
            EventType.FEEDBACK_CLOSED if new_status == FeedbackStatus.CLOSED.value else EventType.FEEDBACK_SUBMITTED
        )

        self._log_audit_event(
            event_type=evt_type,
            actor_type=ActorType.REVIEWER,
            source_document_id=feedback.document_id,
            review_id=feedback.review_id,
            actor_reference=actor_user.id,
            payload={
                "feedback_id": feedback_id,
                "new_status": new_status,
                "updated_by": actor_user.email
            }
        )

        return updated
