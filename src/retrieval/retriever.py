from typing import List, Optional
from src.retrieval.config import RetrievalConfig
from src.retrieval.schema import RetrievalQuery, RetrievalResult
from src.retrieval.index import VectorIndex

class SemanticRetriever:
    def __init__(self, index: VectorIndex, config: RetrievalConfig):
        self.index = index
        self.config = config
        
    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        if not query.query_text:
            raise ValueError("Empty query")
            
        if query.partition != self.index.partition:
            raise ValueError(f"FAILED_LEAKAGE_CHECK: Query partition {query.partition} blocked from index {self.index.partition}")
            
        if not self.index.clause_data:
            raise ValueError("Empty corpus")
            
        # We fetch extra candidates in case we have to filter some out
        # (e.g. self-retrieval, same-document filters)
        fetch_k = min(self.config.top_k + 20, len(self.index.clause_data))
        
        query_emb, _ = self.index.embeddings_module.encode([query.query_text])
        distances, indices = self.index.search(query_emb, fetch_k)
        
        results = []
        
        for i in range(len(indices[0])):
            faiss_id = int(indices[0][i])
            similarity = float(distances[0][i])
            
            if faiss_id not in self.index.mapping:
                continue
                
            clause_id = self.index.mapping[faiss_id]
            segment = self.index.clause_data[clause_id]
            
            # Apply filters
            if self.config.min_similarity is not None and similarity < self.config.min_similarity:
                continue
                
            actual_query_clause_id = query.target_clause_id if query.is_contextualized else query.query_clause_id
                
            if self.config.exclude_query and clause_id == actual_query_clause_id:
                continue
                
            if self.config.same_document_only and segment.source_document_id != query.query_source_document_id:
                continue
                
            result = RetrievalResult(
                query_clause_id=actual_query_clause_id,
                query_source_document_id=query.query_source_document_id,
                result_clause_id=segment.segment_id,
                source_document_id=segment.source_document_id,
                result_text=segment.text,
                similarity_score=similarity,
                rank=0, # assigned after sorting
                embedding_model=self.index.embeddings_module.config.embedding_model_name,
                index_id=self.index.index_id,
                source_start=segment.original_start,
                source_end=segment.original_end,
                partition=self.index.partition
            )
            results.append(result)
            
        # Sort results: descending similarity, deterministic tie-breaking on result_clause_id
        results.sort(key=lambda x: (-x.similarity_score, x.result_clause_id))
        
        # Apply top_k
        results = results[:self.config.top_k]
        
        # Assign rank
        for i, r in enumerate(results):
            r.rank = i + 1
            
        return results
