"""
Secure document storage manager for isolated binary file persistence and safe temporary file lifecycle.
"""

import os
import uuid
import shutil
import tempfile
from typing import Optional
from src.ingestion.config import IngestionConfig

class DocumentStorageManager:
    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or IngestionConfig()
        self.storage_root = os.path.abspath(self.config.storage_root)
        os.makedirs(self.storage_root, exist_ok=True)

    def generate_document_id(self) -> str:
        """Generates cryptographically random UUID v4 string for document identity."""
        return str(uuid.uuid4())

    def store_document(self, document_id: str, file_bytes: bytes, original_filename: str) -> str:
        """
        Stores the raw binary file under an isolated directory keyed by document_id.
        Preserves original file separately from extracted text snapshots.
        Returns the relative/sanitized storage path.
        """
        doc_dir = os.path.join(self.storage_root, document_id)
        os.makedirs(doc_dir, exist_ok=True)
        
        # Save raw binary with fixed standard name to prevent any directory traversal
        target_path = os.path.join(doc_dir, "raw_document.bin")
        with open(target_path, "wb") as f:
            f.write(file_bytes)
            
        return target_path

    def retrieve_document_bytes(self, document_id: str) -> Optional[bytes]:
        """Retrieves raw binary bytes for a given document_id."""
        target_path = os.path.join(self.storage_root, document_id, "raw_document.bin")
        if not os.path.exists(target_path):
            return None
        with open(target_path, "rb") as f:
            return f.read()

    def create_temp_file(self, suffix: str = ".tmp") -> str:
        """Creates a temporary file for safe parsing with automatic path confinement."""
        if self.config.temp_dir:
            os.makedirs(self.config.temp_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=self.config.temp_dir)
        os.close(fd)
        return temp_path

    def cleanup_path(self, path: Optional[str]):
        """Safely removes temporary file or directory without throwing errors."""
        if not path:
            return
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
