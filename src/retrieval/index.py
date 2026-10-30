import json
import os
import hashlib
import numpy as np
from typing import List, Dict, Tuple, Any
from src.retrieval.schema import IndexMetadata
from src.retrieval.embeddings import EmbeddingsModule
from src.segmentation.schema import Segment

class VectorIndex:
    def __init__(self, index_id: str, partition: str, embeddings_module: EmbeddingsModule):
        self.index_id = index_id
        self.partition = partition
        self.embeddings_module = embeddings_module
        self.index = None
        self.mapping: Dict[int, str] = {} # faiss_id -> clause_id
        self.clause_data: Dict[str, Segment] = {} # clause_id -> Segment
        self.text_hashes = set()
        
        if not self.embeddings_module.config.force_mock:
            try:
                import faiss
                # We use IndexFlatIP because embeddings are L2 normalized, so IP == Cosine
                self.index = faiss.IndexFlatIP(self.embeddings_module.dimension)
            except Exception:
                self.index = None # Mock
        
    def _hash_text(self, text: str) -> str:
        # Simple exact text hash for leakage prevention
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def build(self, segments: List[Segment]):
        if not segments:
            raise ValueError("Empty corpus")
            
        # 1. Deterministic sorting
        # Sort by source_document_id, then sequence
        sorted_segments = sorted(segments, key=lambda x: (x.source_document_id, x.sequence))
        
        # 2. Partition & Leakage check
        texts = []
        for s in sorted_segments:
            seg_partition = s.metadata.get("partition", "UNKNOWN")
            if seg_partition != self.partition:
                raise ValueError(f"FAILED_LEAKAGE_CHECK: Segment partition {seg_partition} does not match index partition {self.partition}")
            
            txt_hash = self._hash_text(s.text)
            self.text_hashes.add(txt_hash)
            texts.append(s.text)
            
        # 3. Embed
        embeddings, _ = self.embeddings_module.encode(texts)
        
        # 4. Add to Index and record mapping
        # FAISS integer ID is just the row index in the added matrix
        current_id_offset = len(self.mapping)
        
        if self.index is not None:
            self.index.add(embeddings)
            
        for i, s in enumerate(sorted_segments):
            faiss_id = current_id_offset + i
            self.mapping[faiss_id] = s.segment_id
            self.clause_data[s.segment_id] = s

    def check_exact_leakage(self, other_index: 'VectorIndex'):
        overlap = self.text_hashes.intersection(other_index.text_hashes)
        if overlap:
            raise ValueError(f"FAILED_LEAKAGE_CHECK: Exact text overlap between partitions {self.partition} and {other_index.partition}")

    def get_metadata(self) -> IndexMetadata:
        doc_ids = set(s.source_document_id for s in self.clause_data.values())
        return IndexMetadata(
            index_id=self.index_id,
            index_version="1.0",
            embedding_model=self.embeddings_module.config.embedding_model_name,
            embedding_dimension=self.embeddings_module.dimension,
            metric="InnerProduct",
            normalization="L2",
            partition=self.partition,
            source_dataset="Mixed",
            number_of_documents=len(doc_ids),
            number_of_clauses=len(self.clause_data),
            creation_metadata={},
            mapping=self.mapping
        )

    def search(self, query_embeddings: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        # Returns distances, indices
        if self.index is not None:
            return self.index.search(query_embeddings, top_k)
        else:
            # Mock search: return random matches
            num_queries = query_embeddings.shape[0]
            num_candidates = len(self.mapping)
            if num_candidates == 0:
                return np.empty((num_queries, 0)), np.empty((num_queries, 0), dtype=int)
            
            k = min(top_k, num_candidates)
            indices = np.zeros((num_queries, k), dtype=int)
            distances = np.zeros((num_queries, k), dtype=np.float32)
            for i in range(num_queries):
                indices[i] = np.random.choice(list(self.mapping.keys()), k, replace=False)
                distances[i] = np.sort(np.random.rand(k))[::-1] # sorted descending
            return distances, indices

    def save(self, path: str):
        os.makedirs(path, exist_ok=True)
        if self.index is not None:
            import faiss
            faiss.write_index(self.index, os.path.join(path, "faiss.index"))
            
        with open(os.path.join(path, "metadata.json"), "w") as f:
            f.write(self.get_metadata().model_dump_json())
            
        # Since clause_data is not in metadata schema, save it too
        clause_dump = {k: v.model_dump() for k, v in self.clause_data.items()}
        with open(os.path.join(path, "clause_data.json"), "w") as f:
            json.dump(clause_dump, f)

    def load(self, path: str):
        if not self.embeddings_module.config.force_mock:
            try:
                import faiss
                self.index = faiss.read_index(os.path.join(path, "faiss.index"))
            except Exception:
                pass
                
        with open(os.path.join(path, "metadata.json"), "r") as f:
            meta = IndexMetadata.model_validate_json(f.read())
            self.mapping = {int(k): v for k, v in meta.mapping.items()}
            self.partition = meta.partition
            
        with open(os.path.join(path, "clause_data.json"), "r") as f:
            clause_dump = json.load(f)
            self.clause_data = {k: Segment.model_validate(v) for k, v in clause_dump.items()}
            
        for s in self.clause_data.values():
            self.text_hashes.add(self._hash_text(s.text))
