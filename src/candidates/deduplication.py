"""
Deterministic Deduplication Protocol for Candidate Findings in CONTRACTRISK-XAI.

Implements the prespecified deduplication key and audit logging protocol.
Preserves distinct multi-label risk categories on the same clause segment
while collapsing exact duplicate inferences into an immutable audit log.
"""

import json
import re
from typing import List, Tuple, Dict, Any, Optional
from src.candidates.schema import CandidateFindingRecord, DuplicateFindingEntry


def normalize_finding_text(text: Optional[str]) -> Optional[str]:
    """
    Normalizes candidate finding text for deduplication:
    - If text is None, returns None to explicitly preserve the absence of finding text.
    - If text is a string, trims leading/trailing whitespace, collapses internal whitespace,
      converts to lowercase, and strips standardized non-alphanumeric punctuation.
    """
    if text is None:
        return None
    # Strip leading/trailing and collapse internal whitespace
    norm = " ".join(text.strip().split()).lower()
    # Remove standard punctuation that does not alter substantive legal meaning
    norm = re.sub(r"[^\w\s]", "", norm)
    return norm


def compute_deduplication_key(candidate: CandidateFindingRecord) -> str:
    """
    Computes an unambiguous, canonical JSON-serialized deduplication key:
    Canonical key payload = [
        contract_id,
        contract_version,
        clause_id,
        prediction_category,
        raw_model_label,
        origin,
        normalize(candidate_finding_text)
    ]

    Serialized with ensure_ascii=True and separators=(',', ':') to guarantee:
    1. Strict field boundary protection against delimiter injection (colons, commas, quotes).
    2. Distinct field tuples never serialize to the same key (injective mapping).
    3. Deterministic output across repeated invocations.
    4. Explicit differentiation between None (null) and empty string ("").
    5. Preservation of multi-label distinctions, distinct raw labels, and origins.
    """
    norm_text = normalize_finding_text(candidate.candidate_finding_text)
    origin_str = candidate.origin.value if hasattr(candidate.origin, "value") else str(candidate.origin or "")
    raw_label = str(candidate.raw_model_label) if candidate.raw_model_label is not None else ""
    key_payload = [
        candidate.contract_id,
        candidate.contract_version,
        candidate.clause_id,
        candidate.prediction_category,
        raw_label,
        origin_str,
        norm_text,
    ]
    return json.dumps(key_payload, ensure_ascii=True, separators=(",", ":"))


def deduplicate_candidates(
    candidates: List[CandidateFindingRecord]
) -> Tuple[List[CandidateFindingRecord], List[DuplicateFindingEntry]]:
    """
    Deduplicates a candidate finding collection deterministically.
    
    Rules:
    1. Preserves distinct risk categories on the same clause (e.g. INDEMNIFICATION vs LIMITATION_OF_LIABILITY).
    2. Exact duplicate inferences sharing the deduplication key are collapsed.
    3. The first encountered candidate is retained as the canonical finding.
    4. Removed duplicates are logged as DuplicateFindingEntry records for auditability.
    5. Order of canonical findings is preserved.
    """
    seen_keys: Dict[str, str] = {} # key -> canonical_finding_id
    canonical_candidates: List[CandidateFindingRecord] = []
    duplicate_log: List[DuplicateFindingEntry] = []

    for candidate in candidates:
        key = compute_deduplication_key(candidate)
        if key in seen_keys:
            canonical_id = seen_keys[key]
            entry = DuplicateFindingEntry(
                canonical_finding_id=canonical_id,
                duplicate_finding_id=candidate.candidate_finding_id,
                deduplication_key=key,
                contract_id=candidate.contract_id,
                clause_id=candidate.clause_id,
                prediction_category=candidate.prediction_category
            )
            duplicate_log.append(entry)
        else:
            seen_keys[key] = candidate.candidate_finding_id
            canonical_candidates.append(candidate)

    return canonical_candidates, duplicate_log
