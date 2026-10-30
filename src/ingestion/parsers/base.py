"""
Base abstract interface for document parsers.
"""

from abc import ABC, abstractmethod
from src.ingestion.schema import ExtractionResult

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes, document_id: str) -> ExtractionResult:
        """
        Parses raw document bytes and returns an ExtractionResult.
        Must not silently truncate content or execute macros.
        """
        pass
