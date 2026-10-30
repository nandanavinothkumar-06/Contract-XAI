from pydantic import BaseModel
from typing import Optional

class MissingProvisionConfig(BaseModel):
    domain: str = "general"
    taxonomy_id: str = "default_taxonomy"
    semantic_top_k: int = 5
    semantic_threshold: float = 0.75
    lexical_threshold: float = 1.0 # 1.0 means exact term match
    negation_policy: str = "CONSERVATIVE" # CONSERVATIVE -> mark UNCERTAIN if negated
    conditional_policy: str = "CONSERVATIVE" # CONSERVATIVE -> mark UNCERTAIN if conditional
    same_document_only: bool = True
    exclude_cross_partition: bool = True
    minimum_evidence: int = 1
    configuration_version: str = "1.0.0"
