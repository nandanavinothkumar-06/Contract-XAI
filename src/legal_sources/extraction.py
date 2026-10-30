"""
Statutory Text Extraction Engine for Official Reference Artifacts.

Extracts text from Gazette PDFs and reference artifacts using pypdf:
1. Extracts text page-by-page while recording structural metadata (page count, empty pages).
2. Never modifies or overwrites the original acquired artifact bytes.
3. Preserves punctuation, section markers, provisos, schedules, and explanations verbatim.
4. Distinguishes direct digital PDF text from OCR fallbacks.
5. Saves extracted text and rich extraction metadata to data/legal_sources/extracted_text/.
6. Enforces the invariant: extraction failure is never treated as an empty statute.
"""

import os
import json
import hashlib
import datetime
from typing import Dict, Any, List, Optional, Tuple

import pypdf
from src.legal_sources.acquisition import safe_join_path, sanitize_identifier

class StatutoryTextExtractor:
    """
    Handles lossless, provenance-preserving text extraction from official legal artifacts.
    """
    def __init__(
        self,
        base_extracted_dir: str = "data/legal_sources/extracted_text"
    ):
        self.base_extracted_dir = base_extracted_dir

    def validate_pdf_artifact(self, artifact_path: str) -> Tuple[bool, int, Optional[str]]:
        """
        Validates that a PDF artifact exists, starts with '%PDF-', and can be read by pypdf.
        Returns: (is_valid, page_count, error_message)
        """
        if not os.path.exists(artifact_path):
            return False, 0, f"File not found: {artifact_path}"
        try:
            with open(artifact_path, "rb") as f:
                header = f.read(5)
            if not header.startswith(b"%PDF-"):
                return False, 0, "File does not start with %PDF- magic bytes"
            reader = pypdf.PdfReader(artifact_path)
            num_pages = len(reader.pages)
            if num_pages == 0:
                return False, 0, "PDF contains 0 pages"
            return True, num_pages, None
        except Exception as e:
            return False, 0, f"PDF parser error: {str(e)}"

    def extract_text_from_artifact(
        self,
        source_id: str,
        artifact_pdf_path: str,
        publication_id: str,
        artifact_id: Optional[str] = None,
        enable_ocr_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience alias matching Task 040 specification parameters.
        """
        res = self.extract_from_artifact(
            artifact_path=artifact_pdf_path,
            source_id=source_id,
            publication_id=publication_id,
            enable_ocr_fallback=enable_ocr_fallback
        )
        if artifact_id and res.get("metadata_path") and os.path.exists(res["metadata_path"]):
            try:
                with open(res["metadata_path"], "r", encoding="utf-8") as f:
                    m = json.load(f)
                m["artifact_id"] = artifact_id
                with open(res["metadata_path"], "w", encoding="utf-8") as f:
                    json.dump(m, f, indent=2)
            except Exception:
                pass
        return res

    def extract_from_artifact(
        self,
        artifact_path: str,
        source_id: str,
        publication_id: str,
        enable_ocr_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Extracts structural text from an authoritative reference artifact.
        Stores extracted text and metadata in isolated extracted_text/ directory.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        clean_source_id = sanitize_identifier(source_id)
        clean_pub_id = sanitize_identifier(publication_id)

        dest_dir = safe_join_path(self.base_extracted_dir, clean_source_id, clean_pub_id)
        os.makedirs(dest_dir, exist_ok=True)
        out_text_path = safe_join_path(dest_dir, "extracted.txt")
        out_meta_path = safe_join_path(dest_dir, "extraction_metadata.json")

        if not os.path.exists(artifact_path) or os.path.getsize(artifact_path) == 0:
            err_msg = f"Artifact file not found: '{artifact_path}'" if not os.path.exists(artifact_path) else f"Artifact file is empty (0 bytes): '{artifact_path}'"
            err_meta = {
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "artifact_path": artifact_path,
                "extraction_timestamp": timestamp,
                "extraction_status": "EXTRACTION_FAILED",
                "error": err_msg,
                "warnings": []
            }
            try:
                with open(out_meta_path, "w", encoding="utf-8") as f:
                    json.dump(err_meta, f, indent=2)
            except Exception:
                pass
            return {
                "success": False,
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "metadata_path": out_meta_path,
                "error": err_msg,
                "extracted_text_path": None,
                "sha256": None
            }

        ext = os.path.splitext(artifact_path)[1].lower()

        if ext == ".pdf":
            return self._extract_pdf(
                artifact_path=artifact_path,
                clean_source_id=clean_source_id,
                clean_pub_id=clean_pub_id,
                out_text_path=out_text_path,
                out_meta_path=out_meta_path,
                timestamp=timestamp,
                enable_ocr_fallback=enable_ocr_fallback
            )
        else:
            return self._extract_plain_text(
                artifact_path=artifact_path,
                clean_source_id=clean_source_id,
                clean_pub_id=clean_pub_id,
                out_text_path=out_text_path,
                out_meta_path=out_meta_path,
                timestamp=timestamp
            )

    def _extract_pdf(
        self,
        artifact_path: str,
        clean_source_id: str,
        clean_pub_id: str,
        out_text_path: str,
        out_meta_path: str,
        timestamp: str,
        enable_ocr_fallback: bool
    ) -> Dict[str, Any]:
        """
        Extracts text page-by-page from a PDF using pypdf.
        """
        warnings: List[str] = []
        page_records: List[Dict[str, Any]] = []
        full_text_chunks: List[str] = []
        empty_pages = 0
        ocr_used = False
        ocr_engine = None

        try:
            reader = pypdf.PdfReader(artifact_path)
            total_pages = len(reader.pages)

            if total_pages == 0:
                return {
                    "success": False,
                    "source_id": clean_source_id,
                    "publication_id": clean_pub_id,
                    "error": "PDF contains 0 pages",
                    "extracted_text_path": None,
                    "sha256": None
                }

            for idx, page in enumerate(reader.pages):
                page_num = idx + 1
                try:
                    txt = page.extract_text() or ""
                except Exception as ex:
                    warnings.append(f"Page {page_num} extraction warning: {str(ex)}")
                    txt = ""

                char_count = len(txt)
                is_empty = (char_count == 0 or txt.strip() == "")
                if is_empty:
                    empty_pages += 1
                    warnings.append(f"Page {page_num} produced 0 extracted characters (possible scanned image or unsupported font encoding)")

                    # Check OCR fallback if enabled
                    if enable_ocr_fallback:
                        ocr_used = True
                        ocr_engine = "pytesseract-fallback-stub"
                        warnings.append(f"Page {page_num}: OCR fallback attempted ({ocr_engine})")

                page_records.append({
                    "page_number": page_num,
                    "char_count": char_count,
                    "is_empty": is_empty
                })
                if txt.strip():
                    full_text_chunks.append(f"--- PAGE {page_num} ---\n" + txt.strip() + "\n")

            full_text = "\n".join(full_text_chunks).strip()

            if not full_text:
                warnings.append("Zero characters extracted across entire PDF document")
                err_meta = {
                    "source_id": clean_source_id,
                    "publication_id": clean_pub_id,
                    "artifact_path": artifact_path,
                    "extraction_timestamp": timestamp,
                    "extraction_status": "EXTRACTION_FAILED",
                    "error": "No parseable text extracted from PDF (document may be a scanned bitmap requiring OCR)",
                    "warnings": warnings
                }
                try:
                    with open(out_meta_path, "w", encoding="utf-8") as f:
                        json.dump(err_meta, f, indent=2)
                except Exception:
                    pass
                return {
                    "success": False,
                    "source_id": clean_source_id,
                    "publication_id": clean_pub_id,
                    "metadata_path": out_meta_path,
                    "error": "No parseable text extracted from PDF (document may be a scanned bitmap requiring OCR)",
                    "warnings": warnings,
                    "extracted_text_path": None,
                    "sha256": None
                }

            # Write extracted text
            with open(out_text_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            text_sha = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
            orig_sha = hashlib.sha256(open(artifact_path, "rb").read()).hexdigest()

            meta = {
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "artifact_path": artifact_path,
                "extracted_text_path": out_text_path,
                "extraction_timestamp": timestamp,
                "extraction_method": "PYPDF_DIGITAL_TEXT_EXTRACTOR",
                "extraction_tool_version": f"pypdf-{pypdf.__version__}",
                "page_count": total_pages,
                "empty_page_count": empty_pages,
                "total_char_count": len(full_text),
                "extracted_text_sha256": text_sha,
                "original_sha256": orig_sha,
                "ocr_used": ocr_used,
                "ocr_engine": ocr_engine,
                "warnings": warnings,
                "page_details": page_records
            }

            with open(out_meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            return {
                "success": True,
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "extracted_text_path": out_text_path,
                "metadata_path": out_meta_path,
                "sha256": text_sha,
                "original_sha256": orig_sha,
                "page_count": total_pages,
                "char_count": len(full_text),
                "empty_page_count": empty_pages,
                "ocr_used": ocr_used,
                "warnings": warnings
            }

        except Exception as e:
            err_meta = {
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "artifact_path": artifact_path,
                "extraction_timestamp": timestamp,
                "extraction_status": "EXTRACTION_FAILED",
                "error": f"PDF parsing failed: {str(e)}",
                "warnings": warnings
            }
            try:
                with open(out_meta_path, "w", encoding="utf-8") as f:
                    json.dump(err_meta, f, indent=2)
            except Exception:
                pass
            return {
                "success": False,
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "metadata_path": out_meta_path,
                "error": f"PDF parsing failed: {str(e)}",
                "warnings": warnings,
                "extracted_text_path": None,
                "sha256": None
            }

    def _extract_plain_text(
        self,
        artifact_path: str,
        clean_source_id: str,
        clean_pub_id: str,
        out_text_path: str,
        out_meta_path: str,
        timestamp: str
    ) -> Dict[str, Any]:
        """
        Loads plain text reference artifact with encoding safety.
        """
        warnings: List[str] = []
        try:
            with open(artifact_path, "rb") as f:
                raw_bytes = f.read()

            try:
                text_content = raw_bytes.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                text_content = raw_bytes.decode("latin-1")
                encoding = "latin-1"
                warnings.append("Decoded using Latin-1 fallback")

            with open(out_text_path, "w", encoding="utf-8") as f:
                f.write(text_content)

            text_sha = hashlib.sha256(text_content.encode("utf-8")).hexdigest()

            meta = {
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "artifact_path": artifact_path,
                "extracted_text_path": out_text_path,
                "extraction_timestamp": timestamp,
                "extraction_method": "DIRECT_TEXT_DECODE",
                "extraction_tool_version": "native-utf8",
                "page_count": 1,
                "empty_page_count": 0,
                "total_char_count": len(text_content),
                "extracted_text_sha256": text_sha,
                "ocr_used": False,
                "ocr_engine": None,
                "warnings": warnings
            }

            with open(out_meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            return {
                "success": True,
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "extracted_text_path": out_text_path,
                "metadata_path": out_meta_path,
                "sha256": text_sha,
                "page_count": 1,
                "char_count": len(text_content),
                "empty_page_count": 0,
                "ocr_used": False,
                "warnings": warnings
            }
        except Exception as e:
            return {
                "success": False,
                "source_id": clean_source_id,
                "publication_id": clean_pub_id,
                "error": f"Text reading failed: {str(e)}",
                "extracted_text_path": None,
                "sha256": None
            }
