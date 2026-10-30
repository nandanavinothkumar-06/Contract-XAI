import uuid
import datetime
import re
from typing import List, Dict, Optional, Tuple
from src.legal_sources.schema import LegalSourceRetrievalResult, LegalSourceQuery, LegalPassage
from src.legal_sources.config import LegalSourceRetrievalConfig
from src.legal_sources.registry import LegalSourceRegistry
from src.legal_sources.index import LegalSourceIndex
from src.legal_sources.provenance import (
    VerificationStatus,
    RetrievalMethod,
    CurrentnessStatus,
    is_retrieval_eligible,
)
from src.legal_sources.citation import construct_statutory_citation

class LegalSourceRetriever:
    def __init__(
        self,
        registry: LegalSourceRegistry,
        index: LegalSourceIndex,
        config: LegalSourceRetrievalConfig
    ):
        self.registry = registry
        self.index = index
        self.config = config

    def _is_source_eligible(self, source_id: str, query: LegalSourceQuery) -> bool:
        source = self.registry.get_source(source_id)
        if not source:
            return False
            
        if self.config.enabled_only and not source.enabled:
            return False
            
        if self.config.verified_only:
            if not is_retrieval_eligible(source.verification_status):
                return False

        if self.config.enforce_currentness:
            if source.currentness_status in [
                CurrentnessStatus.HISTORICAL,
                CurrentnessStatus.REPEALED_SUPERSEDED
            ]:
                return False
                
        if self.config.enforce_jurisdiction and query.country:
            # Simple country-level check for this module
            if source.country != query.country:
                return False
            if query.jurisdiction_level and source.jurisdiction_level != query.jurisdiction_level:
                return False
                
        if query.source_types and source.source_type not in query.source_types:
            return False
            
        return True

    def retrieve(self, query: LegalSourceQuery) -> List[LegalSourceRetrievalResult]:
        if not query.query_text.strip() and not query.exact_section_filter:
            return []
            
        results = []
        seen_passages = set()
        
        # We fetch extra candidates in case they get filtered out
        fetch_k = min(query.requested_top_k + 20, len(self.index.passages))
        
        candidates: List[Tuple[float, LegalPassage]] = []
        method_str = (self.config.retrieval_method or "LEXICAL").upper()

        # 1. Exact section filter priority if specified
        if query.exact_section_filter:
            exact_matches = self.index.lookup_exact_section(query.exact_section_filter)
            for em in exact_matches:
                candidates.append((10.0, em))

        # 2. Method-specific candidate retrieval
        if method_str == RetrievalMethod.LEXICAL.value:
            lex_cands = self.index.search_lexical(query.query_text, fetch_k)
            candidates.extend(lex_cands)
        elif method_str == RetrievalMethod.BM25.value:
            bm25_cands = self.index.search_bm25(query.query_text, fetch_k)
            candidates.extend(bm25_cands)
        elif method_str == RetrievalMethod.EXACT_IDENTIFIER.value:
            # Detect section reference in query_text if not explicitly in exact_section_filter
            m = re.search(r"(?:section|sec\.?)\s*([0-9]+[A-Za-z]?)", query.query_text, re.IGNORECASE)
            sec_target = query.exact_section_filter or (m.group(1) if m else None)
            if sec_target:
                # Disambiguation: check if query context indicates a specific statute
                target_source_id = query.source_document_id
                q_lower = query.query_text.lower()
                if not target_source_id:
                    if "specific relief" in q_lower or "sra" in q_lower:
                        target_source_id = "IN_ACT_1963_47"
                    elif "contract act" in q_lower or "indian contract" in q_lower:
                        target_source_id = "IN_ACT_1872_09"
                    elif "arbitration" in q_lower:
                        target_source_id = "IN_ACT_1996_26"
                    elif "information technology" in q_lower or "it act" in q_lower:
                        target_source_id = "IN_ACT_2000_21"
                    elif "data protection" in q_lower or "dpdp" in q_lower:
                        target_source_id = "IN_ACT_2023_22"
                    elif "sakshya" in q_lower or "bsa" in q_lower:
                        target_source_id = "IN_ACT_2023_47"

                exact_matches = self.index.lookup_exact_section(sec_target, source_id=target_source_id)
                for em in exact_matches:
                    candidates.append((10.0, em))
            else:
                # Fallback to lexical
                candidates.extend(self.index.search_lexical(query.query_text, fetch_k))
        elif method_str == RetrievalMethod.HYBRID.value:
            bm25_cands = dict(self.index.search_bm25(query.query_text, fetch_k))
            lex_cands = dict(self.index.search_lexical(query.query_text, fetch_k))
            all_pids = set(bm25_cands.keys()).union(set(lex_cands.keys()))
            for pid in all_pids:
                passage = self.index.passages.get(pid)
                if not passage:
                    continue
                bm25_s = bm25_cands.get(pid, 0.0)
                lex_s = lex_cands.get(pid, 0.0)
                # Normalization and combination
                comb_score = bm25_s + (lex_s * 2.0)
                candidates.append((comb_score, passage))
        else:
            candidates.extend(self.index.search_lexical(query.query_text, fetch_k))
        
        # Deduplication and filtering
        for score, passage in candidates:
            if self.config.minimum_score is not None and score < self.config.minimum_score:
                continue
                
            if not self._is_source_eligible(passage.source_id, query):
                continue
                
            source = self.registry.get_source(passage.source_id)
            if not source:
                continue
            
            # Deduplicate by section/offsets
            dedup_key = (
                passage.source_id,
                passage.legal_document_id,
                passage.section_identifier,
                passage.passage_start,
                passage.passage_end
            )
            if dedup_key in seen_passages:
                continue
            seen_passages.add(dedup_key)

            citation = passage.citation_string or construct_statutory_citation(source, passage)
            
            explanation = f"Score: {score:.4f} via {method_str}"
            if method_str == RetrievalMethod.EXACT_IDENTIFIER.value:
                explanation = "Exact section identifier match"
            
            curr_status = passage.currentness_status
            if not curr_status or curr_status == CurrentnessStatus.UNKNOWN:
                curr_status = source.currentness_status

            result = LegalSourceRetrievalResult(
                result_id=str(uuid.uuid4()),
                query_id=query.query_id,
                source_id=source.source_id,
                source_title=source.title,
                source_type=source.source_type,
                jurisdiction=source.jurisdiction,
                jurisdiction_level=source.jurisdiction_level,
                verification_status=source.verification_status,
                currentness_status=curr_status,
                legal_document_id=passage.legal_document_id,
                section_identifier=passage.section_identifier,
                section_number=passage.section_number,
                subsection_identifier=passage.subsection_identifier,
                heading=passage.heading,
                passage_text=passage.passage_text,
                passage_start=passage.passage_start,
                passage_end=passage.passage_end,
                similarity_score=score,
                rank=0, # Assigned below
                retrieval_method=RetrievalMethod(self.config.retrieval_method if self.config.retrieval_method in RetrievalMethod.__members__ else "LEXICAL"),
                official_url=source.official_url,
                effective_date=source.effective_date,
                version_identifier=source.version_identifier,
                retrieved_at=source.retrieved_at or datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                citation_string=citation,
                commencement_status=passage.commencement_status,
                score_explanation=explanation,
                contract_source_document_id=query.source_document_id,
                contract_clause_id=query.clause_id,
                reviewed_by_human=source.reviewed_by_human,
                is_test_fixture=passage.is_test_fixture or source.is_test_fixture
            )
            results.append(result)
            
        # Re-sort and slice to top_k
        results.sort(key=lambda x: (-x.similarity_score, x.source_id, x.legal_document_id, x.section_identifier or ""))
        results = results[:query.requested_top_k]
        
        for i, res in enumerate(results):
            res.rank = i + 1
            
        return results

