"""
Configuration parameters for document ingestion, resource limits, and OCR fallback.
"""

import os
from dataclasses import dataclass, field
from typing import Set, Optional

@dataclass
class IngestionConfig:
    # Supported file extensions
    allowed_extensions: Set[str] = field(default_factory=lambda: {".pdf", ".docx", ".txt"})
    
    # Resource limits (prevent resource exhaustion from untrusted inputs)
    max_file_size_bytes: int = 25 * 1024 * 1024  # 25 MB default limit
    max_pages_pdf: int = 300                      # 300 pages default limit
    min_chars_per_page_pdf: int = 50             # Threshold below which PDF page is flagged as scanned/empty
    extraction_timeout_seconds: int = 120        # 2 minutes timeout for extraction
    
    # Storage settings
    storage_root: str = field(default_factory=lambda: os.getenv("CONTRACTRISK_STORAGE_ROOT", "data/contracts/raw"))
    temp_dir: Optional[str] = None
    
    # OCR settings
    ocr_enabled: bool = field(default_factory=lambda: os.getenv("CONTRACTRISK_OCR_ENABLED", "true").lower() in ("1", "true", "yes"))
    ocr_engine_path: Optional[str] = field(default_factory=lambda: os.getenv("TESSERACT_CMD", None))
    ocr_language: str = "eng"
    ocr_min_confidence: float = 60.0
    
    # Preprocessing & segmentation integration
    auto_preprocess: bool = True
    auto_segment: bool = True
