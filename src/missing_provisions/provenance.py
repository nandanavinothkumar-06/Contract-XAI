from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class RequiredStatus(str, Enum):
    REQUIRED_BY_REFERENCE = "REQUIRED_BY_REFERENCE"
    RECOMMENDED_BY_REFERENCE = "RECOMMENDED_BY_REFERENCE"
    OPTIONAL_REFERENCE_ITEM = "OPTIONAL_REFERENCE_ITEM"
    UNKNOWN = "UNKNOWN"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    USER_SUPPLIED = "USER_SUPPLIED"
    NOT_VERIFIED = "NOT_VERIFIED"

class TaxonomyProvenance(BaseModel):
    source_reference: str
    source_reference_type: str
    source_title: Optional[str] = None
    source_location: Optional[str] = None
    verification_status: VerificationStatus
