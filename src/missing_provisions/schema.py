from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from src.missing_provisions.provenance import TaxonomyProvenance, RequiredStatus

class ProvisionStatus(str, Enum):
    FOUND = "FOUND"
    POTENTIALLY_MISSING = "POTENTIALLY_MISSING"
    UNCERTAIN = "UNCERTAIN"
    NOT_ASSESSED = "NOT_ASSESSED"

class DetectionMethod(str, Enum):
    LEXICAL = "LEXICAL"
    SEMANTIC = "SEMANTIC"
    HYBRID = "HYBRID"
    STRUCTURAL = "STRUCTURAL"
    HYBRID_STRUCTURAL = "HYBRID_STRUCTURAL"
    NOT_ASSESSED = "NOT_ASSESSED"

class ProvisionDefinition(BaseModel):
    provision_id: str
    name: str
    description: str
    domain: str
    provenance: TaxonomyProvenance
    detection_terms: List[str]
    semantic_description: str
    required_status: RequiredStatus
    enabled: bool = True

class ReferenceProvisionTaxonomy(BaseModel):
    taxonomy_id: str
    domain: str
    provisions: List[ProvisionDefinition]
    is_test_fixture: bool = False

class LexicalMatchInfo(BaseModel):
    matched_term: str
    source_start: int
    source_end: int
    has_negation: bool = False
    has_conditional: bool = False

class ProvisionEvidence(BaseModel):
    clause_id: str
    source_document_id: str
    text: str
    source_start: int
    source_end: int
    similarity_score: Optional[float] = None
    lexical_matches: List[LexicalMatchInfo] = []
    evidence_status: str = "AVAILABLE"

class ProvisionReference(BaseModel):
    provision_id: str
    name: str
    provenance: TaxonomyProvenance

class DetectionMetadata(BaseModel):
    detection_method: DetectionMethod
    configuration_version: str
    is_test_fixture: bool = False
    domain: str

class MissingProvisionAssessment(BaseModel):
    assessment_id: str
    source_document_id: str
    provision_id: str
    provision_name: str
    domain: str
    status: ProvisionStatus
    reason: str
    matching_clause_ids: List[str]
    evidence: List[ProvisionEvidence]
    reference_provenance: ProvisionReference
    metadata: DetectionMetadata
    partition: str
