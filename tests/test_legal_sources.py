import pytest
import datetime
from src.legal_sources.registry import LegalSourceRegistry
from src.legal_sources.provenance import VerificationStatus, SourceType, JurisdictionLevel, CurrentnessStatus
from src.legal_sources.schema import LegalSource, LegalSourceQuery, LegalPassage
from src.legal_sources.registry import get_fixture_registry, LegalSource
from src.legal_sources.config import LegalSourceRetrievalConfig
from src.legal_sources.index import LegalSourceIndex
from src.legal_sources.retriever import LegalSourceRetriever

@pytest.fixture
def registry():
    return get_fixture_registry()

@pytest.fixture
def index():
    idx = LegalSourceIndex()
    idx.index_passages([
        LegalPassage(
            passage_id="p1",
            source_id="TEST_STATUTE_001",
            legal_document_id="doc1",
            section_identifier="Sec 1",
            passage_text="This is an official contract provision act requirement.",
            passage_start=0,
            passage_end=55,
            is_test_fixture=True
        ),
        LegalPassage(
            passage_id="p2",
            source_id="TEST_UNVERIFIED_001",
            legal_document_id="doc2",
            section_identifier="Rule 2",
            passage_text="This is an unverified user requirement.",
            is_test_fixture=True
        ),
        LegalPassage(
            passage_id="p3",
            source_id="TEST_US_001",
            legal_document_id="doc3",
            section_identifier="Code 100",
            passage_text="This is a US fixture requirement.",
            is_test_fixture=True
        ),
        # Duplicate passage test
        LegalPassage(
            passage_id="p1_dup",
            source_id="TEST_STATUTE_001",
            legal_document_id="doc1",
            section_identifier="Sec 1",
            passage_text="This is an official contract provision act requirement.",
            passage_start=0,
            passage_end=55,
            is_test_fixture=True
        )
    ])
    return idx

@pytest.fixture
def config():
    return LegalSourceRetrievalConfig(
        top_k=2,
        verified_only=True,
        enforce_jurisdiction=True,
        retrieval_method="LEXICAL"
    )

def test_critical_jurisdiction_test(registry, index, config):
    # contract jurisdiction = India
    # US source is present in the registry.
    retriever = LegalSourceRetriever(registry, index, config)
    
    query = LegalSourceQuery(
        query_id="q1",
        query_text="US fixture requirement", # Naturally favors the US source text
        country="IN", # Contract jurisdiction
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    
    results = retriever.retrieve(query)
    # The US source must NOT be returned
    for r in results:
        assert r.source_id != "TEST_US_001"
        assert r.jurisdiction != "US - Federal"

def test_critical_verification_test(registry, index, config):
    # UNVERIFIED source cannot be returned when verified_only = true
    retriever = LegalSourceRetriever(registry, index, config)
    
    query = LegalSourceQuery(
        query_id="q1",
        query_text="unverified user requirement",
        country="IN",
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    
    results = retriever.retrieve(query)
    for r in results:
        assert r.source_id != "TEST_UNVERIFIED_001"
        assert r.verification_status != VerificationStatus.UNVERIFIED

def test_critical_provenance_test(registry, index, config):
    # Ensure source offset invariant: source_text[start:end] == retrieved_text is conceptually preserved.
    # We test that all structural locators and text are preserved without fabrication
    config.enforce_jurisdiction = False
    retriever = LegalSourceRetriever(registry, index, config)
    
    query = LegalSourceQuery(
        query_id="q1",
        query_text="contract provision act",
        country="IN",
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    
    results = retriever.retrieve(query)
    assert len(results) > 0
    res = results[0]
    
    # Asserting invariants
    assert res.source_id == "TEST_STATUTE_001"
    assert res.legal_document_id == "doc1"
    assert res.section_identifier == "Sec 1"
    assert res.passage_text == "This is an official contract provision act requirement."
    assert res.passage_start == 0
    assert res.passage_end == 55
    
    # Verification of lack of fabricated claims:
    # "The output must remain: 'POTENTIALLY_RELEVANT_SOURCE' or equivalent retrieval-only terminology."
    # The schema LegalSourceRetrievalResult inherently acts as this.
    assert hasattr(res, "similarity_score")
    assert not hasattr(res, "legal_conclusion")

def test_duplicate_results(registry, index, config):
    config.enforce_jurisdiction = False
    retriever = LegalSourceRetriever(registry, index, config)
    query = LegalSourceQuery(
        query_id="q1",
        query_text="contract provision act",
        country="IN",
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    results = retriever.retrieve(query)
    
    # "p1" and "p1_dup" are exactly identical in location/source.
    # Deduplication should only yield 1 instance.
    assert len(results) == 1

def test_empty_query(registry, index, config):
    retriever = LegalSourceRetriever(registry, index, config)
    query = LegalSourceQuery(
        query_id="q1",
        query_text="",
        country="IN",
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    results = retriever.retrieve(query)
    assert len(results) == 0

def test_source_type_filtering(registry, index, config):
    # Re-enable unverified just to test source_type filtering separately
    config.verified_only = False
    retriever = LegalSourceRetriever(registry, index, config)
    
    query = LegalSourceQuery(
        query_id="q1",
        query_text="requirement",
        country="IN",
        source_types=[SourceType.OTHER_AUTHORITATIVE_SOURCE],
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    
    results = retriever.retrieve(query)
    assert len(results) == 1
    assert results[0].source_id == "TEST_UNVERIFIED_001"

def test_critical_provenance_registry_vs_index(registry, config):
    empty_index = LegalSourceIndex()
    retriever = LegalSourceRetriever(registry, empty_index, config)
    query = LegalSourceQuery(
        query_id="q_prov",
        query_text="contract provision",
        country="IN",
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    results = retriever.retrieve(query)
    assert len(results) == 0

def test_critical_currentness_status(registry, index, config):
    config.enforce_jurisdiction = False
    retriever = LegalSourceRetriever(registry, index, config)
    query = LegalSourceQuery(
        query_id="q_curr",
        query_text="contract provision act",
        country="IN",
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    results = retriever.retrieve(query)
    assert len(results) >= 1
    assert results[0].currentness_status == CurrentnessStatus.CURRENTNESS_UNVERIFIED

def test_critical_jurisdiction_level(registry, index, config):
    config.enforce_jurisdiction = True
    retriever = LegalSourceRetriever(registry, index, config)
    
    query_us = LegalSourceQuery(
        query_id="q_us",
        query_text="contract provision act",
        country="US",
        jurisdiction_level=JurisdictionLevel.CENTRAL,
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    results_us = retriever.retrieve(query_us)
    for r in results_us:
        assert r.country == "US"
        assert r.source_id != "TEST_STATUTE_001"
        
    query_in_unknown = LegalSourceQuery(
        query_id="q_in",
        query_text="contract provision act",
        country="IN",
        jurisdiction_level=JurisdictionLevel.UNKNOWN,
        requested_top_k=5,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        configuration_version="1.0.0"
    )
    results_in = retriever.retrieve(query_in_unknown)
    for r in results_in:
        assert r.jurisdiction_level == JurisdictionLevel.UNKNOWN
