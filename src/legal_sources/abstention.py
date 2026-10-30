"""
Confidence Gates and Structured Abstention Policy for Statutory Retrieval.

Enforces deterministic rules preventing unverified, weak, conflicting, or uncommenced
statutory evidence from being presented as authoritative law.
"""

from typing import List, Optional, Tuple, Dict, Any
from src.legal_sources.schema import LegalSourceRetrievalResult
from src.legal_sources.provenance import (
    LegalSourceErrorStatus,
    VerificationStatus,
    CurrentnessStatus,
    CommencementStatus,
    RetrievalMethod,
    is_retrieval_eligible,
)

DEFAULT_MINIMUM_RETRIEVAL_SCORE = 0.05
DEFAULT_MINIMUM_BM25_SCORE = 3.0

FOREIGN_JURISDICTION_INDICATORS = [
    "delaware", "new york", "california", "england and wales", "english law", "singapore", "difc", "hong kong"
]

class LegalAbstentionPolicy:
    """
    Evaluates retrieval results against strict legal confidence gates.
    """
    def __init__(
        self,
        min_lexical_score: float = DEFAULT_MINIMUM_RETRIEVAL_SCORE,
        min_bm25_score: float = DEFAULT_MINIMUM_BM25_SCORE,
        require_verified: bool = True,
        require_commenced: bool = True,
        disallow_historical: bool = True,
        require_human_reviewed: bool = False,
    ):
        self.min_lexical_score = min_lexical_score
        self.min_bm25_score = min_bm25_score
        self.require_verified = require_verified
        self.require_commenced = require_commenced
        self.disallow_historical = disallow_historical
        self.require_human_reviewed = require_human_reviewed

    def evaluate(
        self,
        query_text: str,
        results: List[LegalSourceRetrievalResult]
    ) -> Tuple[bool, Optional[LegalSourceErrorStatus], str]:
        """
        Determines whether the system must ABSTAIN from returning statutory evidence.
        Returns: (should_abstain, reason_code, message)
        """
        # 0. Check foreign jurisdiction keywords
        if any(fj in query_text.lower() for fj in FOREIGN_JURISDICTION_INDICATORS):
            return True, LegalSourceErrorStatus.UNSUPPORTED_LEGAL_QUESTION, "Clause references foreign governing law or jurisdiction outside Indian statutory scope."

        # 1. Empty query or no results
        if not results:
            return True, LegalSourceErrorStatus.NO_MATCH, "No relevant statutory passages retrieved for the given query."

        # Check for ambiguous exact section lookup across multiple statutes
        exact_results = [
            r for r in results 
            if getattr(r, "retrieval_method", None) == RetrievalMethod.EXACT_IDENTIFIER
            or getattr(r, "score_explanation", "") == "Exact section identifier match"
        ]
        if exact_results:
            statutes_matched = {r.source_id for r in exact_results}
            if len(statutes_matched) > 1:
                return True, LegalSourceErrorStatus.AMBIGUOUS_SECTION_REFERENCE, (
                    f"Ambiguous exact section reference matches multiple statutes ({statutes_matched}) "
                    "without sufficient context or filter to disambiguate."
                )

        top_result = results[0]

        # Check human review gate
        if self.require_human_reviewed and not getattr(top_result, "reviewed_by_human", True):
            return True, LegalSourceErrorStatus.SOURCE_UNVERIFIED, f"Source '{top_result.source_id}' has not been reviewed by a human legal reviewer."

        # 2. Weak retrieval evidence
        score = top_result.similarity_score
        method = top_result.retrieval_method.value if hasattr(top_result.retrieval_method, "value") else str(top_result.retrieval_method)
        
        if score < 10.0:  # Not an exact section match
            if method == "BM25" and score < self.min_bm25_score:
                return True, LegalSourceErrorStatus.WEAK_RETRIEVAL_EVIDENCE, f"Top BM25 retrieval score ({score:.4f}) is below confidence threshold ({self.min_bm25_score})."
            elif method == "LEXICAL" and score < self.min_lexical_score:
                return True, LegalSourceErrorStatus.WEAK_RETRIEVAL_EVIDENCE, f"Top lexical similarity score ({score:.4f}) is below confidence threshold ({self.min_lexical_score})."

        # 3. Unverified source
        if self.require_verified and not is_retrieval_eligible(top_result.verification_status):
            return True, LegalSourceErrorStatus.SOURCE_UNVERIFIED, f"Source '{top_result.source_id}' verification status is {top_result.verification_status.value}."

        # 4. Currentness unverified
        if top_result.currentness_status in [
            CurrentnessStatus.CURRENTNESS_UNVERIFIED,
            CurrentnessStatus.UNKNOWN,
        ]:
            return True, LegalSourceErrorStatus.CURRENTNESS_UNVERIFIED, f"Currentness status of '{top_result.source_id}' is unverified."

        # 5. Historical or repealed statute
        if self.disallow_historical and top_result.currentness_status in [
            CurrentnessStatus.HISTORICAL,
            CurrentnessStatus.REPEALED_SUPERSEDED,
        ]:
            return True, LegalSourceErrorStatus.HISTORICAL_ONLY_VERSION, f"Retrieved source is historical or superseded ({top_result.currentness_status.value})."

        # 6. Commencement status gate
        if self.require_commenced and top_result.commencement_status in [
            CommencementStatus.NOT_COMMENCED,
            CommencementStatus.UNKNOWN,
            CommencementStatus.REPEALED,
        ]:
            return True, LegalSourceErrorStatus.UNKNOWN_COMMENCEMENT, (
                f"Statutory provision ({top_result.section_identifier}) commencement status is "
                f"{top_result.commencement_status.value if top_result.commencement_status else 'UNKNOWN'}. "
                "Substantive rules or official notification have not been verified in force."
            )

        # 7. Conflicting versions check
        # If multiple top passages from the same statute present conflicting version identifiers
        versions = {r.version_identifier for r in results if r.source_id == top_result.source_id and r.version_identifier}
        if len(versions) > 1:
            return True, LegalSourceErrorStatus.CONFLICTING_VERSIONS, f"Conflicting versions detected across retrieved passages: {versions}."

        return False, None, "Valid authoritative evidence retrieved."
