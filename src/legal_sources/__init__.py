"""
Authoritative Indian Statutory Corpus & Verified Legal Retrieval Module.
"""

from src.legal_sources.provenance import (
    VerificationStatus,
    SourceType,
    RetrievalMethod,
    JurisdictionLevel,
    CurrentnessStatus,
    CommencementStatus,
    LegalSourceErrorStatus,
)
from src.legal_sources.schema import (
    LegalSource,
    LegalPassage,
    LegalSourceQuery,
    LegalSourceRetrievalResult,
    RetrievedLegalEvidence,
)
from src.legal_sources.config import LegalSourceRetrievalConfig
from src.legal_sources.index import LegalSourceIndex
from src.legal_sources.registry import LegalSourceRegistry, get_fixture_registry, get_authoritative_indian_corpus
from src.legal_sources.retriever import LegalSourceRetriever
from src.legal_sources.ingestion import StatutoryIngestionEngine
from src.legal_sources.citation import construct_statutory_citation, format_citation_with_heading
from src.legal_sources.abstention import LegalAbstentionPolicy
from src.legal_sources.matcher import ContractStatuteMatcher
from src.legal_sources.bm25 import BM25Okapi

__all__ = [
    "VerificationStatus",
    "SourceType",
    "RetrievalMethod",
    "JurisdictionLevel",
    "CurrentnessStatus",
    "CommencementStatus",
    "LegalSourceErrorStatus",
    "LegalSource",
    "LegalPassage",
    "LegalSourceQuery",
    "LegalSourceRetrievalResult",
    "RetrievedLegalEvidence",
    "LegalSourceRetrievalConfig",
    "LegalSourceIndex",
    "LegalSourceRegistry",
    "LegalSourceRetriever",
    "StatutoryIngestionEngine",
    "construct_statutory_citation",
    "format_citation_with_heading",
    "LegalAbstentionPolicy",
    "ContractStatuteMatcher",
    "BM25Okapi",
    "get_fixture_registry",
    "get_authoritative_indian_corpus",
]
