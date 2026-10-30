"""
Central Ingestion Pipeline: orchestrates validation, binary storage, format-specific extraction
(PDF, DOCX, TXT with OCR fallback), integration with PreprocessingPipeline and SegmentationPipeline,
cryptographic audit logging, and relational persistence.
"""

import os
import json
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session

from src.ingestion.config import IngestionConfig
from src.ingestion.schema import (
    DocumentFormat, ExtractionMethod, IngestionStatus,
    ValidationResult, ExtractionResult, IngestionResult,
    ModelAgreementProvenanceRecord,
)
from src.ingestion.validator import DocumentValidator
from src.ingestion.storage import DocumentStorageManager
from src.ingestion.parsers.txt_parser import TxtParser
from src.ingestion.parsers.docx_parser import DocxParser
from src.ingestion.parsers.pdf_parser import PdfParser
from src.ingestion.parsers.ocr_engine import OcrEngine

from src.adapters.schema import DatasetRecord, TaskType
from src.preprocessing.pipeline import PreprocessingPipeline
from src.segmentation.pipeline import SegmentationPipeline

from src.audit.logger import AuditLogger
from src.audit.store import AuditStore
from src.audit.schema import AuditEvent
from src.audit.provenance import EventType, ActorType
from src.audit.integrity import AuditVerifier

from src.persistence.database import get_db_session, get_engine
from src.persistence.repository import DocumentRepository
from src.persistence.models import AuditEventRecord

class IngestionPipeline:
    def __init__(
        self,
        config: Optional[IngestionConfig] = None,
        db_engine = None,
        audit_store: Optional[AuditStore] = None
    ):
        self.config = config or IngestionConfig()
        self.db_engine = db_engine or get_engine()
        self.validator = DocumentValidator(self.config)
        self.storage = DocumentStorageManager(self.config)
        
        self.ocr_engine = OcrEngine(self.config)
        self.txt_parser = TxtParser()
        self.docx_parser = DocxParser()
        self.pdf_parser = PdfParser(self.config, self.ocr_engine)
        
        self.preprocessing_pipeline = PreprocessingPipeline()
        self.segmentation_pipeline = SegmentationPipeline()
        
        self.audit_store = audit_store or AuditStore()
        self.audit_logger = AuditLogger(self.audit_store)
        self.audit_verifier = AuditVerifier()

    def _route_parser(self, doc_format: DocumentFormat, file_bytes: bytes, document_id: str) -> ExtractionResult:
        if doc_format == DocumentFormat.PDF:
            return self.pdf_parser.parse(file_bytes, document_id)
        elif doc_format == DocumentFormat.DOCX:
            return self.docx_parser.parse(file_bytes, document_id)
        elif doc_format == DocumentFormat.TXT:
            return self.txt_parser.parse(file_bytes, document_id)
        else:
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.UNKNOWN,
                raw_text="",
                page_count=0,
                char_count=0,
                errors=[f"Unsupported document format: {doc_format}"]
            )

    def ingest_document(
        self,
        file_bytes: bytes,
        original_filename: str,
        document_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        assigned_lawyer_id: Optional[str] = None,
        session: Optional[Session] = None,
        model_agreement_provenance: Optional[Union[Dict[str, Any], ModelAgreementProvenanceRecord]] = None,
    ) -> IngestionResult:
        """
        Executes end-to-end ingestion:
        1. Validate untrusted file input.
        2. Validate optional model_agreement_provenance if supplied.
        3. Prevent duplicate processing if identical file exists.
        4. Store binary file securely.
        5. Extract text via appropriate parser (PDF, DOCX, TXT, OCR fallback).
        6. Persist immutable text snapshot.
        7. Feed into PreprocessingPipeline and SegmentationPipeline.
        8. Persist segmented clauses and audit events in a transactional unit of work.
        """
        doc_id = document_id or self.storage.generate_document_id()
        
        # 1. File Validation
        validation = self.validator.validate(file_bytes, original_filename)
        if not validation.is_valid:
            return IngestionResult(
                document_id=doc_id,
                status=IngestionStatus.FAILED,
                validation=validation,
                errors=validation.errors,
                warnings=validation.warnings
            )

        # 1b. Model Agreement Provenance Validation (Strategy A Hook)
        prov_record: Optional[ModelAgreementProvenanceRecord] = None
        if model_agreement_provenance is not None:
            prov_record, prov_errors = self.validator.validate_model_agreement_provenance(model_agreement_provenance)
            if prov_errors or prov_record is None:
                return IngestionResult(
                    document_id=doc_id,
                    status=IngestionStatus.FAILED,
                    validation=validation,
                    errors=[f"Invalid model_agreement_provenance: {'; '.join(prov_errors)}"],
                    warnings=validation.warnings
                )

        # Helper to execute within provided session or managed session
        def _execute_ingestion(sess: Session) -> IngestionResult:
            repo = DocumentRepository(sess)

            # 2. Duplicate Detection / Retry check
            existing = repo.find_duplicate_by_sha256(validation.file_sha256)
            if existing:
                # If identical document already completed segmentation, return idempotent result
                if existing.status == IngestionStatus.SEGMENTED.value:
                    existing_segs = existing.segments
                    return IngestionResult(
                        document_id=existing.id,
                        status=IngestionStatus.SEGMENTED,
                        validation=validation,
                        dataset_record_id=f"REC_{existing.id[:8]}",
                        segment_count=len(existing_segs),
                        storage_path=existing.storage_path,
                        warnings=["Duplicate document detected by SHA-256; returned existing processed record."],
                        model_agreement_provenance=prov_record,
                    )

            # 3. Secure Binary Storage
            storage_path = self.storage.store_document(doc_id, file_bytes, validation.sanitized_filename)

            # 4. Create Document Record
            doc_record = repo.create_document(
                document_id=doc_id,
                validation=validation,
                storage_path=storage_path,
                initial_status=IngestionStatus.RECEIVED,
                owner_id=owner_id,
                assigned_lawyer_id=assigned_lawyer_id
            )

            # Ensure continuity with tamper-evident audit hash chain if store was not pre-populated
            if self.audit_store.get_last_event() is None:
                last_rec = (
                    sess.query(AuditEventRecord)
                    .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc())
                    .first()
                )
                if last_rec:
                    ae = AuditEvent(
                        event_id=last_rec.event_id,
                        event_type=EventType(last_rec.event_type),
                        timestamp=last_rec.timestamp,
                        source_document_id=last_rec.document_id,
                        actor_type=ActorType(last_rec.actor_type),
                        event_payload=json.loads(last_rec.payload_json) if last_rec.payload_json else {},
                        previous_event_hash=last_rec.previous_event_hash
                    )
                    ae.event_hash = last_rec.event_hash
                    self.audit_store.append(ae)

            # Audit: Document Ingested
            ingest_payload = {
                "file_sha256": validation.file_sha256,
                "mime_type": validation.mime_type,
                "file_size_bytes": validation.file_size_bytes,
                "original_filename": validation.sanitized_filename
            }
            if prov_record is not None:
                ingest_payload["model_agreement_provenance"] = prov_record.model_dump()

            evt_ingest = self.audit_logger.log_event(
                event_type=EventType.DOCUMENT_INGESTED,
                actor_type=ActorType.SYSTEM,
                source_document_id=doc_id,
                module_name="src.ingestion.pipeline",
                module_version="1.0.0",
                event_payload=ingest_payload
            )
            repo.record_audit_event(evt_ingest)

            # 5. Extraction
            extraction = self._route_parser(validation.format, file_bytes, doc_id)
            if extraction.errors or not extraction.raw_text.strip():
                err_msg = "; ".join(extraction.errors) if extraction.errors else "No extractable text found in document"
                repo.update_document_status(
                    document_id=doc_id,
                    status=IngestionStatus.FAILED,
                    extraction_result=extraction,
                    error_message=err_msg
                )
                return IngestionResult(
                    document_id=doc_id,
                    status=IngestionStatus.FAILED,
                    validation=validation,
                    extraction=extraction,
                    storage_path=storage_path,
                    errors=[err_msg],
                    warnings=validation.warnings + extraction.warnings,
                    model_agreement_provenance=prov_record,
                )

            # 6. Save Extracted Text Snapshot
            repo.save_extracted_snapshot(doc_id, extraction.raw_text)
            repo.update_document_status(
                document_id=doc_id,
                status=IngestionStatus.EXTRACTED,
                extraction_result=extraction
            )

            # 7. Preprocessing Integration
            record_id = f"REC_{doc_id[:8]}"
            record_meta = {
                "file_sha256": validation.file_sha256,
                "extraction_method": extraction.extraction_method.value,
                "ocr_applied": extraction.ocr_applied
            }
            if prov_record is not None:
                record_meta["model_agreement_provenance"] = prov_record.model_dump()

            dataset_rec = DatasetRecord.model_construct(
                record_id=record_id,
                source_dataset="USER_UPLOAD",
                source_document_id=doc_id,
                contract_id=doc_id,
                clause_id=None,
                text=extraction.raw_text,
                task=TaskType.CLAUSE_RISK_CLASSIFICATION,
                original_label="Unreviewed",
                normalized_label=None,
                evidence=[],
                rationale=None,
                domain="Commercial Contract",
                language="en",
                annotation_source="ingestion_pipeline",
                source_reference=validation.sanitized_filename,
                license_status="proprietary",
                access_status="client_confidential",
                metadata=record_meta
            )

            preprocessed = self.preprocessing_pipeline.preprocess_record(dataset_rec)
            repo.update_document_status(document_id=doc_id, status=IngestionStatus.PREPROCESSED)

            evt_prep = self.audit_logger.log_event(
                event_type=EventType.PREPROCESSING_COMPLETED,
                actor_type=ActorType.SYSTEM,
                source_document_id=doc_id,
                module_name="src.preprocessing.pipeline",
                module_version=self.preprocessing_pipeline.version,
                event_payload={
                    "record_id": record_id,
                    "processed_char_count": len(preprocessed.processed_text),
                    "quality_flags": preprocessed.quality_flags
                }
            )
            repo.record_audit_event(evt_prep)

            # 8. Segmentation Integration
            segmented_doc = self.segmentation_pipeline.segment_record(preprocessed)
            repo.save_segments(doc_id, segmented_doc.segments)
            repo.update_document_status(document_id=doc_id, status=IngestionStatus.SEGMENTED)

            evt_seg = self.audit_logger.log_event(
                event_type=EventType.CLAUSE_SEGMENTED,
                actor_type=ActorType.SYSTEM,
                source_document_id=doc_id,
                module_name="src.segmentation.pipeline",
                module_version=self.segmentation_pipeline.version,
                event_payload={
                    "segment_count": len(segmented_doc.segments),
                    "quality_flags": segmented_doc.quality_flags
                }
            )
            repo.record_audit_event(evt_seg)

            return IngestionResult(
                document_id=doc_id,
                status=IngestionStatus.SEGMENTED,
                validation=validation,
                extraction=extraction,
                dataset_record_id=record_id,
                preprocessed_status="SUCCESS",
                segment_count=len(segmented_doc.segments),
                storage_path=storage_path,
                errors=[],
                warnings=validation.warnings + extraction.warnings,
                model_agreement_provenance=prov_record,
            )

        if session is not None:
            return _execute_ingestion(session)
        else:
            with get_db_session(self.db_engine) as managed_session:
                return _execute_ingestion(managed_session)
