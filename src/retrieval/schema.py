from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class RetrievalQuery(BaseModel):
    query_clause_id: str
    query_source_document_id: str
    query_text: str
    partition: str
    is_contextualized: bool = False
    target_clause_id: Optional[str] = None

class RetrievalResult(BaseModel):
    query_clause_id: str
    query_source_document_id: str
    result_clause_id: str
    source_document_id: str
    result_text: str
    similarity_score: float
    rank: int
    embedding_model: str
    index_id: str
    source_start: int
    source_end: int
    partition: str

class RetrievalMetadata(BaseModel):
    embedding_model: str
    embedding_model_revision: Optional[str] = None
    embedding_dimension: int
    normalization: str
    similarity_metric: str
    max_sequence_length: Optional[int] = None
    random_seed: Optional[int] = None
    is_test_fixture: bool = False

class IndexMetadata(BaseModel):
    index_id: str
    index_version: str
    embedding_model: str
    embedding_dimension: int
    metric: str
    normalization: str
    partition: str
    source_dataset: str
    number_of_documents: int
    number_of_clauses: int
    creation_metadata: Dict[str, Any]
    mapping: Dict[int, str] # FAISS int ID -> clause_id
