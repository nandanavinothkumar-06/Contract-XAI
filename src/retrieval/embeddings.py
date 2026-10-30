import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from src.retrieval.config import RetrievalConfig
from src.retrieval.schema import RetrievalMetadata

class EmbeddingsModule:
    def __init__(self, config: RetrievalConfig):
        self.config = config
        self.model = None
        self.dimension = None
        self.max_seq_length = None
        
        if self.config.force_mock:
            self._init_mock()
        else:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(
                    self.config.embedding_model_name, 
                    revision=self.config.embedding_model_revision
                )
                self.dimension = self.model.get_sentence_embedding_dimension()
                self.max_seq_length = self.model.max_seq_length
            except Exception as e:
                print(f"Warning: SentenceTransformer failed to load: {e}")
                self._init_mock()

    def _init_mock(self):
        self.model = None
        self.dimension = 384 # default for all-MiniLM
        self.max_seq_length = 256
        
    def is_available(self) -> bool:
        return self.model is not None
        
    def get_metadata(self) -> RetrievalMetadata:
        return RetrievalMetadata(
            embedding_model=self.config.embedding_model_name,
            embedding_model_revision=self.config.embedding_model_revision,
            embedding_dimension=self.dimension,
            normalization="L2",
            similarity_metric="Inner Product (Cosine Similarity)",
            max_sequence_length=self.max_seq_length,
            is_test_fixture=self.config.force_mock or not self.is_available()
        )

    def encode(self, texts: List[str]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Returns L2-normalized embeddings and truncation metadata.
        """
        truncation_metadata = {"truncated": False}
        
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32), truncation_metadata
            
        if self.model:
            embeddings = self.model.encode(
                texts,
                batch_size=self.config.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True # Crucial for L2 norm
            )
            # The model internally might truncate based on max_seq_length
            # We record that truncation might have occurred
            truncation_metadata["truncated"] = True # We assume it might have happened silently by ST
        else:
            # Mock behavior
            embeddings = np.random.randn(len(texts), self.dimension).astype(np.float32)
            # Normalize mock embeddings
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1
            embeddings = embeddings / norms
            
        return embeddings, truncation_metadata
