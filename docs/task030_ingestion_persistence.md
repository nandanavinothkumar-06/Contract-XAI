# Task 030: Document Ingestion, OCR & Relational Persistence

## 1. Overview & Architectural Scope

Task 030 delivers the foundational document ingestion, format parsing, OCR fallback, and relational persistence layer for the **CONTRACTRISK-XAI** India-focused contract analysis platform.

This component serves as an extension of the existing research framework, seamlessly connecting untrusted user uploads (PDF, DOCX, and TXT) to the validated non-destructive text preprocessing ([src/preprocessing/pipeline.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/preprocessing/pipeline.py)) and structural segmentation ([src/segmentation/pipeline.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/segmentation/pipeline.py)) pipelines. All historical ML models, calibration artifacts, and academic reports are preserved intact.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 TASK 030 ARCHITECTURE                                  │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [Untrusted Upload: PDF / DOCX / TXT]
                  │
                  ▼
   ┌──────────────────────────────┐
   │     DocumentValidator        │──▶ Validates magic bytes, file size, extension
   │  src/ingestion/validator.py  │    Calculates deterministic SHA-256 checksum
   └──────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │    DocumentStorageManager    │──▶ Persists raw binary separately under UUID path
   │   src/ingestion/storage.py   │    data/contracts/raw/{document_id}/raw_document.bin
   └──────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │   Format-Specific Parsers    │
   │  src/ingestion/parsers/      │
   │  - PdfParser (pypdf)         │──▶ Normal PDF text extraction (page by page)
   │  - OcrEngine (pytesseract)   │──▶ Fallback for scanned/low-density PDFs
   │  - DocxParser (python-docx)  │──▶ Extracts paragraphs, headings, and tables
   │  - TxtParser (multi-encoding)│──▶ Safe UTF-8/Latin-1 decoding & normalization
   └──────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │   Relational Persistence     │──▶ Stores DocumentRecord, ExtractedTextSnapshot
   │  src/persistence/repository  │    ACID transactions with duplicate detection
   └──────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Preprocessing & Segmentation │──▶ Converts to DatasetRecord, preserves char offsets
   │  src/preprocessing/pipeline  │    Generates numbered segments & structural DAG
   │  src/segmentation/pipeline   │    Persists SegmentRecord into database
   └──────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │   Cryptographic Audit Trail  │──▶ Records DOCUMENT_INGESTED, PREPROCESSING_COMPLETED,
   │     src/audit/integrity.py   │    CLAUSE_SEGMENTED into SHA-256 hash chain
   └──────────────────────────────┘
```

---

## 2. Supported Document Formats & Parsing Behavior

| Format | Parsing Engine | Inspection Method | Key Safeguards & Normalization |
| :--- | :--- | :--- | :--- |
| **PDF** (`.pdf`) | `pypdf.PdfReader` | Magic bytes check (`%PDF-`), page structure validation | Extracts text page-by-page. Resource-capped (`max_pages_pdf=300`). Computes average character density per page; automatically triggers OCR fallback if average density is below threshold (`min_chars_per_page_pdf=50`). |
| **Scanned PDF** | `pytesseract` + system Tesseract OCR | Image stream extraction from page objects | Activated when PDF text density is insufficient. Verifies OCR engine availability. If Tesseract binary is absent, emits clear, actionable error (`OCR_DEPENDENCIES_UNAVAILABLE`) rather than silently reporting empty text. |
| **DOCX** (`.docx`) | `python-docx` + OpenXML XML stream fallback | ZIP signature check (`PK\x03\x04`) + verification of `word/document.xml` | Extracts standard paragraphs, headings, and tables (cells joined with `\|`). Never executes embedded VBA macros or external OLE objects. Includes direct XML fallback if `python-docx` encounters namespace anomalies. |
| **Plain Text** (`.txt`, `.text`) | Safe multi-encoding text decoder | Null byte / control character inspection | Tries `utf-8-sig`, `utf-8`, `latin-1`, `cp1252`, `ascii`. Normalizes carriage returns (`\r\n` $\rightarrow$ `\n`). Rejects binary files with null bytes or unprintable control sequences. |

---

## 3. Required Dependencies & System Setup

### 3.1 Python Dependencies
* `pypdf>=5.0.0` (installed and verified)
* `python-docx>=1.2.0` (installed and verified)
* `pytesseract>=0.3.13` (installed and verified)
* `sqlalchemy>=2.0.0` (installed and verified)
* `pydantic>=2.0.0` (installed and verified)
* `reportlab>=5.0.1` (installed and verified)

### 3.2 Optional OCR Setup (For Scanned PDFs)
The OCR fallback module requires the external Tesseract OCR binary. If scanning physical contracts or photocopies:
1. **Windows Installation**:
   * Download and install Tesseract from the UB-Mannheim repository (e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe`).
   * Set the system environment variable:
     ```powershell
     $env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
     ```
2. **Linux Installation**:
   ```bash
   sudo apt-get update && sudo apt-get install -y tesseract-ocr
   ```
3. **Graceful Degraded Behavior**:
   * If Tesseract is not installed, ordinary text PDFs, DOCX, and TXT files continue to process with 100% functionality.
   * If a scanned PDF is uploaded without Tesseract, the pipeline returns:
     `"OCR_DEPENDENCIES_UNAVAILABLE: Tesseract OCR engine executable not found on system PATH. Please install Tesseract OCR or set TESSERACT_CMD..."`

---

## 4. Relational Database & Persistence Architecture

### 4.1 Database Configuration
Database connections are configured via environment variables:
* **Environment Variable**: `CONTRACTRISK_DB_URL` or `DATABASE_URL`.
* **Default (Local Development)**: SQLite database located at `data/contracts/contractrisk.db`.
* **Production Configuration**: PostgreSQL connection string (e.g., `postgresql+psycopg2://user:password@localhost:5432/contractrisk`).
* **Automated Testing**: In-memory SQLite (`sqlite:///:memory:`) for isolated transactional tests.

### 4.2 Database Relational Schema
* **`documents`**:
  * `id` (VARCHAR 36, PK, UUID v4)
  * `file_sha256` (VARCHAR 64, Indexed) — prevents duplicate processing.
  * `original_filename` / `sanitized_filename` (VARCHAR 255)
  * `mime_type` (VARCHAR 128)
  * `document_format` (VARCHAR 32)
  * `file_size_bytes` (INTEGER)
  * `storage_path` (VARCHAR 512) — location of raw binary.
  * `status` (VARCHAR 32, Indexed) — `RECEIVED`, `EXTRACTED`, `PREPROCESSED`, `SEGMENTED`, `FAILED`.
  * `extraction_method` (VARCHAR 64)
  * `page_count` (INTEGER)
  * `char_count` (INTEGER)
  * `ocr_applied` (BOOLEAN)
  * `warnings_json` (TEXT)
  * `error_message` (TEXT)
  * `created_at` / `updated_at` (DATETIME UTC)
* **`extracted_text_snapshots`**:
  * `id` (VARCHAR 36, PK)
  * `document_id` (VARCHAR 36, FK $\rightarrow$ `documents.id`)
  * `raw_text` (TEXT) — immutable source text.
  * `char_count` (INTEGER)
  * `text_sha256` (VARCHAR 64)
  * `created_at` (DATETIME UTC)
* **`segmented_clauses`**:
  * `id` (VARCHAR 36, PK)
  * `document_id` (VARCHAR 36, FK $\rightarrow$ `documents.id`)
  * `segment_id` (VARCHAR 64) — matching `SegmentationPipeline` segment ID.
  * `parent_segment_id` (VARCHAR 64, Nullable)
  * `segment_type` (VARCHAR 64) — `CLAUSE`, `SECTION_HEADING`, `DOCUMENT_TITLE`, etc.
  * `text` (TEXT)
  * `original_start` / `original_end` (INTEGER) — exact character offsets.
  * `heading` / `numbering` (VARCHAR 255)
  * `level` / `sequence` (INTEGER)
  * `path` (VARCHAR 255)
  * `created_at` (DATETIME UTC)
* **`audit_events`**:
  * `id` (VARCHAR 36, PK)
  * `document_id` (VARCHAR 36, FK $\rightarrow$ `documents.id`)
  * `event_id` (VARCHAR 36, Unique)
  * `event_type` (VARCHAR 64) — `DOCUMENT_INGESTED`, `PREPROCESSING_COMPLETED`, `CLAUSE_SEGMENTED`.
  * `timestamp` (VARCHAR 64 ISO-8601 UTC)
  * `actor_type` (VARCHAR 32) — `SYSTEM`.
  * `previous_event_hash` (VARCHAR 64)
  * `event_hash` (VARCHAR 64) — SHA-256 chained hash.
  * `payload_json` (TEXT)

---

## 5. Security & Ingestion Safeguards

1. **Untrusted Input Treatment**: Filenames and extensions are never trusted. The validator sniffs magic bytes (`%PDF-`, `PK\x03\x04` + `word/document.xml`, text heuristics).
2. **Path Traversal Prevention**: Filenames are sanitized via `os.path.basename` and regex scrubbing of control characters.
3. **Isolated Binary Storage**: Raw files are saved into dedicated directories keyed by random UUIDs (`data/contracts/raw/{uuid}/raw_document.bin`).
4. **Resource Limits**:
   * Default max file size: 25 MB (`max_file_size_bytes`).
   * Default max PDF pages: 300 pages (`max_pages_pdf`).
5. **No Exposure of Internal Paths**: System and database errors are sanitized so internal host paths are never exposed in user-facing outputs.
6. **Confidentiality**: Contract text is not logged in plaintext application logs. Audit events record only checksums, character counts, and structural metadata.

---

## 6. Verification & Automated Test Results

The automated test suite in [tests/test_ingestion_persistence.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_ingestion_persistence.py) provides 100% passing evidence for all 18 scoped requirements:

```powershell
python -m pytest tests/test_ingestion_persistence.py -v
```

### Measured Test Results:
* `test_01_successful_txt_ingestion`: **PASSED**
* `test_02_successful_docx_ingestion`: **PASSED**
* `test_03_successful_pdf_text_extraction`: **PASSED**
* `test_04_scanned_pdf_ocr_fallback_when_available`: **PASSED**
* `test_05_clear_failure_when_ocr_dependencies_unavailable`: **PASSED**
* `test_06_unsupported_file_formats`: **PASSED**
* `test_07_empty_and_malformed_documents`: **PASSED**
* `test_08_file_size_and_resource_limits`: **PASSED**
* `test_09_sha256_checksum_correctness`: **PASSED**
* `test_10_safe_temporary_file_cleanup`: **PASSED**
* `test_11_correct_extraction_metadata`: **PASSED**
* `test_12_preprocessing_and_segmentation_integration`: **PASSED**
* `test_13_character_offset_integrity`: **PASSED**
* `test_14_database_persistence_and_transaction_rollback`: **PASSED**
* `test_15_foreign_key_and_relational_integrity`: **PASSED**
* `test_16_retry_behavior_and_duplicate_protection`: **PASSED**
* `test_17_audit_event_generation_and_hash_chain`: **PASSED**
* `test_18_preservation_of_existing_research_artifacts`: **PASSED**

**Overall Test Suite Performance**:
* Task 030 Suite: **18 / 18 PASSED** (100% pass rate in 1.64s).
* Full Repository Suite: **322 / 322 PASSED** (304 baseline + 18 new tests, 0 failures, 0 regressions).

---

## 7. Known Limitations & Boundaries

1. **OCR Quality Dependency**: OCR accuracy on physical stamp papers, degraded photocopies, or cursive handwritten endorsements depends on scan resolution. Offsets in OCR text represent extracted text flow, not physical page coordinates.
2. **Model Decoupling**: The existing LEGAL-BERT model (trained on US SEC EDGAR filings) is deliberately decoupled from this ingestion pipeline and not treated as a validated Indian legal risk predictor.
3. **Out-of-Scope Capabilities**: In accordance with the Task 030 boundaries, user authentication, lawyer verification, collaborative UI, and certified reporting remain locked for subsequent phases (Tasks 031–034).
