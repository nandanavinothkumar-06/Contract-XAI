from pydantic import BaseModel
import os

class RetrievalConfig(BaseModel):
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_revision: str = "main"
    batch_size: int = 32
    top_k: int = 5
    exclude_query: bool = True
    same_document_only: bool = False
    min_similarity: float = None
    force_mock: bool = False
