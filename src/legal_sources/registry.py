import os
from typing import Dict, List, Optional, Tuple
from src.legal_sources.schema import LegalSource, LegalPassage
from src.legal_sources.provenance import VerificationStatus, JurisdictionLevel, CurrentnessStatus, SourceType
from src.legal_sources.index import LegalSourceIndex

class LegalSourceRegistry:
    def __init__(self):
        self.sources: Dict[str, LegalSource] = {}

    def register_source(self, source: LegalSource):
        self.sources[source.source_id] = source

    def get_source(self, source_id: str) -> Optional[LegalSource]:
        return self.sources.get(source_id)
        
    def get_all_sources(self) -> List[LegalSource]:
        return list(self.sources.values())

    def update_verification_status(
        self,
        source_id: str,
        new_status: VerificationStatus,
        reviewer_id: Optional[str] = None
    ) -> bool:
        source = self.get_source(source_id)
        if not source:
            return False
        source.verification_status = new_status
        if reviewer_id:
            source.reviewer_id = reviewer_id
            source.reviewed_by_human = True
        return True

def get_fixture_registry() -> LegalSourceRegistry:
    registry = LegalSourceRegistry()
    registry.register_source(LegalSource(
        source_id="TEST_STATUTE_001",
        title="Fixture Contract Provision Act",
        jurisdiction="India - Central",
        jurisdiction_level=JurisdictionLevel.CENTRAL,
        country="IN",
        source_type=SourceType.STATUTE,
        publisher="Fixture Publisher",
        language="en",
        verification_status=VerificationStatus.VERIFIED_OFFICIAL,
        currentness_status=CurrentnessStatus.CURRENTNESS_UNVERIFIED,
        is_test_fixture=True
    ))
    registry.register_source(LegalSource(
        source_id="TEST_UNVERIFIED_001",
        title="Unverified User Guidelines",
        jurisdiction="India - State",
        jurisdiction_level=JurisdictionLevel.STATE,
        country="IN",
        source_type=SourceType.OTHER_AUTHORITATIVE_SOURCE,
        publisher="User",
        language="en",
        verification_status=VerificationStatus.UNVERIFIED,
        currentness_status=CurrentnessStatus.UNKNOWN,
        is_test_fixture=True
    ))
    registry.register_source(LegalSource(
        source_id="TEST_US_001",
        title="US Fixture Law",
        jurisdiction="US - Federal",
        jurisdiction_level=JurisdictionLevel.UNKNOWN,
        country="US",
        source_type=SourceType.STATUTE,
        publisher="US Fixture",
        language="en",
        verification_status=VerificationStatus.VERIFIED_OFFICIAL,
        currentness_status=CurrentnessStatus.CURRENTNESS_UNVERIFIED,
        is_test_fixture=True
    ))
    return registry

def get_authoritative_indian_corpus(
    manifest_path: str = "data/legal_sources/corpus_manifest.json",
    snapshots_dir: str = "data/legal_sources/snapshots"
) -> Tuple[LegalSourceRegistry, LegalSourceIndex]:
    """
    Ingests and indexes the verified Indian statutory corpus into registry and index.
    """
    from src.legal_sources.ingestion import StatutoryIngestionEngine
    engine = StatutoryIngestionEngine(snapshots_dir=snapshots_dir)
    sources, passages = engine.ingest_corpus_from_manifest(manifest_path=manifest_path)

    registry = LegalSourceRegistry()
    for s in sources:
        registry.register_source(s)

    index = LegalSourceIndex()
    index.index_passages(passages)

    return registry, index

