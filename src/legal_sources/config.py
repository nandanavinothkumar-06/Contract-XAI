from pydantic import BaseModel
from typing import Optional

class LegalSourceRetrievalConfig(BaseModel):
    top_k: int = 5
    minimum_score: Optional[float] = None
    verified_only: bool = True
    enforce_jurisdiction: bool = True
    enabled_only: bool = True
    enforce_currentness: bool = False
    configuration_version: str = "1.0.0"
    retrieval_method: str = "LEXICAL"
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

