"""
Statutory Evidence Retrieval and Formatting Interface for Lawyer Review Workbench.

Connects clause segmentation with Task 032's Authoritative Indian Legal Sources.
Ensures that:
1. Exact statutory text is preserved alongside source metadata.
2. Retrieval scores are explicitly presented as heuristic ranking metrics, not probabilities.
3. Currentness, commencement status, and source checksums are surfaced for independent lawyer verification.
4. Unverified or abstained provisions are never displayed as verified law.
5. Evidence quality states (TRACEABLE, PARTIAL, INSUFFICIENT, SOURCE_UNVERIFIED, STALE_EVIDENCE, NO_MATCHING_EVIDENCE)
   are explicitly evaluated and returned.
6. Curated extract limitations and non-exhaustive Indian law disclosures are clearly stated.
"""

from typing import Dict, Any, List, Optional
from src.legal_sources.routes import get_corpus_services
from src.legal_sources.provenance import (
    CommencementStatus,
    CurrentnessStatus,
    VerificationStatus,
    LegalSourceErrorStatus,
    is_retrieval_eligible,
    is_authoritatively_verified,
)
from src.persistence.models import EvidenceQualityStatus

SCORE_SEMANTICS_DISCLAIMER = (
    "Retrieval scores reflect heuristic lexical/BM25 relevance ranking metrics within the authoritative "
    "Indian statutory corpus. They do NOT represent probabilities that a legal provision applies or "
    "that a contract is legally compliant."
)

STATUTORY_EXTRACT_DISCLOSURE = (
    "This platform searches curated extracts of commercial provisions from six key central statutes: "
    "The Indian Contract Act 1872, Information Technology Act 2000, Digital Personal Data Protection Act 2023, "
    "Specific Relief Act 1963, Arbitration and Conciliation Act 1996, and Bharatiya Sakshya Adhiniyam 2023. "
    "It does NOT represent an exhaustive search of all Indian central, state, sector-specific laws, or judicial precedents."
)

class ClauseEvidenceRetriever:
    """
    Retrieves and structures Indian statutory evidence for review workbench clauses.
    """
    def __init__(self):
        self._registry, self._index, self._retriever, self._matcher = get_corpus_services()

    def retrieve_evidence_for_clause(
        self,
        clause_text: str,
        clause_id: Optional[str] = None,
        source_document_id: Optional[str] = None,
        top_k: int = 3,
        document_version_mismatch: bool = False
    ) -> Dict[str, Any]:
        """
        Executes bounded statutory matching and returns formatted evidence panel data.
        Evaluates evidence quality states and attaches cryptographic source checksums.
        """
        if document_version_mismatch:
            return {
                "evidence_id": f"stale-{clause_id or 'unknown'}",
                "clause_id": clause_id,
                "status": "ABSTAIN",
                "abstention_reason": "DOCUMENT_VERSION_STALE",
                "evidence_quality_status": EvidenceQualityStatus.STALE_EVIDENCE.value,
                "passages": [],
                "corpus_disclosure": STATUTORY_EXTRACT_DISCLOSURE,
                "score_disclaimer": SCORE_SEMANTICS_DISCLAIMER,
                "requires_lawyer_review": True,
                "is_curated_extract": True
            }

        if not clause_text or not clause_text.strip():
            return {
                "clause_id": clause_id,
                "status": "ABSTAIN",
                "abstention_reason": "EMPTY_CLAUSE_TEXT",
                "evidence_quality_status": EvidenceQualityStatus.INSUFFICIENT.value,
                "passages": [],
                "corpus_disclosure": STATUTORY_EXTRACT_DISCLOSURE,
                "score_disclaimer": SCORE_SEMANTICS_DISCLAIMER,
                "requires_lawyer_review": True,
                "is_curated_extract": True
            }

        evidence = self._matcher.match_clause(
            clause_text=clause_text,
            clause_id=clause_id,
            source_document_id=source_document_id,
            requested_top_k=top_k
        )

        formatted_passages = []
        for passage in evidence.passages:
            comm_val = (
                passage.commencement_status.value
                if passage.commencement_status and hasattr(passage.commencement_status, "value")
                else str(passage.commencement_status or "UNKNOWN")
            )
            curr_val = (
                passage.currentness_status.value
                if hasattr(passage.currentness_status, "value")
                else str(passage.currentness_status)
            )
            is_verified = is_retrieval_eligible(passage.verification_status)
            is_auth_verified = is_authoritatively_verified(passage.verification_status)
            ver_status_str = (
                passage.verification_status.value
                if hasattr(passage.verification_status, "value")
                else str(passage.verification_status or "UNVERIFIED")
            )

            # Retrieve checksum from registry or index
            source_rec = self._registry.get_source(passage.source_id) if self._registry else None
            passage_rec = self._index.passages.get(passage.result_id) if (self._index and hasattr(self._index, "passages")) else None
            source_checksum = (
                (passage_rec.passage_checksum_sha256 if passage_rec and hasattr(passage_rec, "passage_checksum_sha256") else None)
                or (source_rec.content_checksum_sha256 if source_rec and hasattr(source_rec, "content_checksum_sha256") else None)
                or ""
            )

            warnings = list(source_rec.extraction_warnings) if source_rec and hasattr(source_rec, "extraction_warnings") else []

            formatted_passages.append({
                "passage_id": passage.result_id,
                "statute_id": passage.source_id,
                "statute_title": passage.source_title,
                "section_number": passage.section_number or passage.section_identifier or "N/A",
                "section_title": passage.heading or "",
                "passage_text": passage.passage_text,
                "official_source_url": passage.official_url or (source_rec.official_url if source_rec else ""),
                "source_version": passage.version_identifier or (source_rec.version_identifier if source_rec else "1.0"),
                "source_checksum": source_checksum,
                "checksum_type": "LOCAL_SHA256",
                "checksum_meaning": "Local SHA-256 digest for snapshot file integrity; does not certify official gazette equivalence.",
                "legal_status": comm_val,
                "currentness_status": curr_val,
                "verification_status": ver_status_str,
                "is_verified_law": is_verified,
                "is_authoritatively_verified": is_auth_verified,
                "is_curated_extract": True,
                "legal_applicability_determined": False,
                "applicability_disclaimer": "Statutory match does not establish legal applicability to this contract. Independent advocate evaluation required.",
                "retrieval_method": str(passage.retrieval_method.value if hasattr(passage.retrieval_method, "value") else passage.retrieval_method),
                "ranking_score": round(passage.similarity_score, 4),
                "ranking_score_meaning": "BM25 heuristic ranking score (NOT a probability)",
                "warnings": warnings
            })

        abstention_code = None
        if evidence.abstention_reason:
            abstention_code = (
                evidence.abstention_reason.value
                if hasattr(evidence.abstention_reason, "value")
                else str(evidence.abstention_reason)
            )

        # Evaluate EvidenceQualityStatus
        if not formatted_passages:
            if abstention_code in ("HISTORICAL_ONLY_VERSION", "UNKNOWN_COMMENCEMENT", "UNVERIFIED_SOURCE"):
                quality = EvidenceQualityStatus.SOURCE_UNVERIFIED.value
            elif abstention_code in ("NO_MATCHING_PASSAGES", "ZERO_LEXICAL_MATCH"):
                quality = EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value
            else:
                quality = EvidenceQualityStatus.INSUFFICIENT.value
        else:
            top_p = formatted_passages[0]
            if not top_p.get("is_verified_law") or top_p.get("legal_status") in ("NOT_COMMENCED", "REPEALED", "STRUCK_DOWN", "UNKNOWN"):
                quality = EvidenceQualityStatus.SOURCE_UNVERIFIED.value
            elif not top_p.get("statute_title") or not top_p.get("passage_text") or top_p.get("section_number") in ("N/A", "", None):
                quality = EvidenceQualityStatus.PARTIAL.value
            elif top_p.get("ranking_score", 0.0) < 0.05:
                quality = EvidenceQualityStatus.INSUFFICIENT.value
            else:
                quality = EvidenceQualityStatus.TRACEABLE.value

        return {
            "evidence_id": evidence.evidence_id,
            "clause_id": clause_id,
            "status": evidence.status,
            "abstention_reason": abstention_code,
            "evidence_quality_status": quality,
            "passages": formatted_passages,
            "corpus_disclosure": STATUTORY_EXTRACT_DISCLOSURE,
            "score_disclaimer": SCORE_SEMANTICS_DISCLAIMER,
            "requires_lawyer_review": True,
            "is_curated_extract": True,
            "evaluated_at": evidence.evaluated_at
        }
