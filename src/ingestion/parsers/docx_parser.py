"""
Secure DOCX parser extracting paragraphs, headings, and table cells without macro execution.
"""

import io
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Optional
from src.ingestion.parsers.base import BaseParser
from src.ingestion.schema import ExtractionResult, ExtractionMethod

class DocxParser(BaseParser):
    def parse(self, file_bytes: bytes, document_id: str) -> ExtractionResult:
        warnings = []
        errors = []
        paragraphs_extracted = []
        table_rows_extracted = 0

        if not file_bytes:
            return ExtractionResult(
                document_id=document_id,
                extraction_method=ExtractionMethod.DOCX_PARSER,
                raw_text="",
                page_count=0,
                char_count=0,
                errors=["Document is empty"]
            )

        # Primary extraction using python-docx
        parsed_via_docx = False
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            
            # 1. Paragraphs (including headings)
            for p in doc.paragraphs:
                p_text = p.text.strip()
                if p_text:
                    paragraphs_extracted.append(p.text)
                    
            # 2. Tables (contracts frequently place parties, schedules, or payment terms in tables)
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        # De-duplicate adjacent identical cells (common in merged DOCX cells)
                        unique_cells = []
                        for c in row_cells:
                            if not unique_cells or c != unique_cells[-1]:
                                unique_cells.append(c)
                        paragraphs_extracted.append(" | ".join(unique_cells))
                        table_rows_extracted += 1
                        
            parsed_via_docx = True
        except Exception as e:
            warnings.append(f"python-docx parsing encountered issue: {str(e)}; falling back to XML extraction.")

        # Fallback: XML stream extraction via zipfile
        if not parsed_via_docx or not paragraphs_extracted:
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                    if "word/document.xml" in z.namelist():
                        xml_content = z.read("word/document.xml")
                        tree = ET.fromstring(xml_content)
                        # OpenXML namespace for text elements is w:t
                        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                        
                        xml_paragraphs = []
                        for p_elem in tree.findall(".//w:p", ns):
                            texts = [t_elem.text for t_elem in p_elem.findall(".//w:t", ns) if t_elem.text]
                            p_str = "".join(texts).strip()
                            if p_str:
                                xml_paragraphs.append(p_str)
                                
                        if xml_paragraphs:
                            paragraphs_extracted = xml_paragraphs
                            warnings.append("Extracted text using direct OpenXML parsing fallback.")
            except Exception as xml_err:
                errors.append(f"Failed to extract text from DOCX archive: {str(xml_err)}")

        full_text = "\n\n".join(paragraphs_extracted)
        if not full_text.strip():
            errors.append("DOCX document contains no extractable paragraphs or text content")

        return ExtractionResult(
            document_id=document_id,
            extraction_method=ExtractionMethod.DOCX_PARSER,
            raw_text=full_text,
            page_count=max(1, len(paragraphs_extracted) // 25),  # Heuristic estimation (~25 paras per page)
            char_count=len(full_text),
            warnings=warnings,
            errors=errors,
            ocr_applied=False,
            metadata={
                "paragraph_count": len(paragraphs_extracted),
                "table_rows_extracted": table_rows_extracted
            }
        )
