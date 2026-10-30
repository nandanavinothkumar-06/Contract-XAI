from pydantic import BaseModel

class AbstentionConfig(BaseModel):
    policy_version: str = "1.0.0"
    
    # ENGINEERING DEFAULT - NOT EMPIRICALLY CALIBRATED
    confidence_accept_threshold: float = 0.85 
    
    # ENGINEERING DEFAULT - NOT EMPIRICALLY CALIBRATED
    confidence_review_threshold: float = 0.50
    
    # ENGINEERING DEFAULT - NOT EMPIRICALLY CALIBRATED
    margin_threshold: float = 0.10
    
    # ENGINEERING DEFAULT - NOT EMPIRICALLY CALIBRATED
    entropy_threshold: float = 0.80
    
    # ENGINEERING DEFAULT - NOT EMPIRICALLY CALIBRATED
    near_threshold_window: float = 0.05
    
    require_evidence: bool = False
    
    # Truncation policy options: "ABSTAIN", "REVIEW_REQUIRED", "IGNORE"
    truncation_policy: str = "REVIEW_REQUIRED"
    
    # Retrieval policy options: "REQUIRE_RETRIEVAL", "OPTIONAL"
    retrieval_policy: str = "OPTIONAL"
    
    # Calibration requirement: "REQUIRE_CALIBRATION", "OPTIONAL"
    calibration_requirement: str = "OPTIONAL"
