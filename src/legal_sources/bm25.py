"""
Pure-Python Okapi BM25 Implementation for Statutory Passage Retrieval.

Implements the standard Okapi BM25 ranking function without external C-extensions or
unreliable native dependencies, providing deterministic scoring and transparent evaluation.
"""

import math
import re
import string
from typing import List, Dict, Tuple, Optional, Set

# Standard legal English stopwords that add no discriminative value
LEGAL_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves"
}

def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """
    Deterministic tokenizer stripping punctuation and case-folding.
    """
    if not text:
        return []
    # Replace non-alphanumeric with spaces, preserving digits (e.g. section numbers '10A')
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = clean.split()
    if remove_stopwords:
        tokens = [t for t in tokens if t not in LEGAL_STOPWORDS and len(t) > 1]
    return tokens


class BM25Okapi:
    """
    Okapi BM25 index over a collection of documents/passages.
    Parameters:
      k1: Tuning parameter for term frequency saturation (default 1.5)
      b: Tuning parameter for document length normalization (default 0.75)
    """
    def __init__(self, corpus: List[str], doc_ids: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids = doc_ids
        self.corpus_size = len(corpus)
        self.doc_len: List[int] = []
        self.doc_freqs: List[Dict[str, int]] = []
        self.nd: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}

        total_length = 0
        for doc in corpus:
            tokens = tokenize(doc)
            self.doc_len.append(len(tokens))
            total_length += len(tokens)
            
            freqs: Dict[str, int] = {}
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)

            for token in freqs:
                self.nd[token] = self.nd.get(token, 0) + 1

        self.avgdl = (total_length / self.corpus_size) if self.corpus_size > 0 else 0.0

        # Precompute IDF for all terms in vocabulary
        for word, freq in self.nd.items():
            # Standard Lucene/BM25 formula with smoothing (+1 inside logarithm)
            idf_val = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[word] = max(idf_val, 0.0)

    def get_scores(self, query: str) -> List[float]:
        """
        Calculates BM25 scores for all documents in the corpus for the given query.
        """
        query_tokens = tokenize(query)
        scores = [0.0] * self.corpus_size
        if not query_tokens or self.corpus_size == 0:
            return scores

        for token in query_tokens:
            if token not in self.idf:
                continue
            idf = self.idf[token]
            for doc_idx, freqs in enumerate(self.doc_freqs):
                if token not in freqs:
                    continue
                tf = freqs[token]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_len[doc_idx] / self.avgdl))
                scores[doc_idx] += idf * (numerator / denominator)

        return scores

    def search(self, query: str, top_k: int = 5) -> List[Tuple[float, str]]:
        """
        Returns top-k ranked documents as (score, doc_id) pairs sorted descending.
        """
        scores = self.get_scores(query)
        ranked = []
        for idx, score in enumerate(scores):
            if score > 0.0:
                ranked.append((score, self.doc_ids[idx]))

        ranked.sort(key=lambda x: (-x[0], x[1]))
        return ranked[:top_k]
