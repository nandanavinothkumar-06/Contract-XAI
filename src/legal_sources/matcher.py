"""
Contract-to-Statute Evidence Matching Interface.

Provides a strictly bounded evidence-retrieval interface that connects contractual clauses
to verified statutory provisions. Never generates automated legal opinions or validity claims.
"""

import uuid
import datetime
from typing import Optional, List
from src.legal_sources.schema import LegalSourceQuery, LegalSourceRetrievalResult, RetrievedLegalEvidence
from src.legal_sources.retriever import LegalSourceRetriever
from src.legal_sources.abstention import LegalAbstentionPolicy
from src.legal_sources.provenance import LegalSourceErrorStatus, JurisdictionLevel, SourceType

class ContractStatuteMatcher:
    """
    Binds contract clauses to authoritative Indian statutory evidence.
    Enforces abstention gates and mandates human legal review.
    """
    def __init__(
        self,
        retriever: LegalSourceRetriever,
        abstention_policy: Optional[LegalAbstentionPolicy] = None
    ):
        self.retriever = retriever
        self.abstention_policy = abstention_policy or LegalAbstentionPolicy()

    def match_clause(
        self,
        clause_text: str,
        clause_id: Optional[str] = None,
        source_document_id: Optional[str] = None,
        country: Optional[str] = "IN",
        jurisdiction: Optional[str] = None,
        jurisdiction_level: Optional[JurisdictionLevel] = None,
        source_types: Optional[List[SourceType]] = None,
        exact_section_filter: Optional[str] = None,
        requested_top_k: int = 3
    ) -> RetrievedLegalEvidence:
        """
        Executes bounded statutory matching against authoritative Indian legislation.
        """
        evidence_id = str(uuid.uuid4())
        evaluated_at = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"

        if not clause_text or not clause_text.strip():
            return RetrievedLegalEvidence(
                evidence_id=evidence_id,
                clause_id=clause_id,
                clause_text=clause_text or "",
                status="ABSTAIN",
                passages=[],
                abstention_reason=LegalSourceErrorStatus.NO_MATCH,
                requires_lawyer_review=True,
                evaluated_at=evaluated_at
            )

        query = LegalSourceQuery(
            query_id=str(uuid.uuid4()),
            query_text=clause_text,
            clause_id=clause_id,
            source_document_id=source_document_id,
            country=country,
            jurisdiction=jurisdiction,
            jurisdiction_level=jurisdiction_level,
            source_types=source_types,
            requested_top_k=requested_top_k,
            exact_section_filter=exact_section_filter,
            created_at=evaluated_at,
            configuration_version="1.0.0"
        )

        results = self.retriever.retrieve(query)

        # Apply confidence gates
        should_abstain, reason_code, message = self.abstention_policy.evaluate(clause_text, results)

        if should_abstain:
            return RetrievedLegalEvidence(
                evidence_id=evidence_id,
                clause_id=clause_id,
                clause_text=clause_text,
                status="ABSTAIN",
                passages=[],
                abstention_reason=reason_code,
                requires_lawyer_review=True,
                evaluated_at=evaluated_at
            )

        return RetrievedLegalEvidence(
            evidence_id=evidence_id,
            clause_id=clause_id,
            clause_text=clause_text,
            status="EVIDENCE_FOUND",
            passages=results,
            abstention_reason=None,
            requires_lawyer_review=True,
            evaluated_at=evaluated_at
        )
