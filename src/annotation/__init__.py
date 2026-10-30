"""
Blinded Legal Annotation Package for Strategy A Evaluation.
"""

from src.annotation.firewall import PresentationFirewall, BlindingViolationError, AnnotationStage
from src.annotation.service import (
    BlindedAnnotationService, get_annotation_schema, canonical_json_dumps, compute_payload_sha256
)
from src.annotation.candidate_registry import CandidateRegistry
from src.annotation.routes import annotation_bp

__all__ = [
    "PresentationFirewall",
    "BlindingViolationError",
    "AnnotationStage",
    "BlindedAnnotationService",
    "CandidateRegistry",
    "get_annotation_schema",
    "canonical_json_dumps",
    "compute_payload_sha256",
    "annotation_bp"
]
