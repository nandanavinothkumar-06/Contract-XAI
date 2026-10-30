"""Baseline features for traditional ML models."""
from sklearn.feature_extraction.text import TfidfVectorizer

def get_tfidf_vectorizer(config: dict = None) -> TfidfVectorizer:
    config = config or {}
    return TfidfVectorizer(
        ngram_range=config.get('ngram_range', (1, 2)),
        sublinear_tf=config.get('sublinear_tf', True),
        min_df=config.get('min_df', 1),
        max_df=config.get('max_df', 1.0),
        stop_words=config.get('stop_words', None)
    )
