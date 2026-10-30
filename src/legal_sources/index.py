import re
import string
from typing import List, Dict, Tuple, Optional
from src.legal_sources.schema import LegalPassage
from src.legal_sources.bm25 import BM25Okapi

class LegalSourceIndex:
    def __init__(self):
        self.passages: Dict[str, LegalPassage] = {}
        self.section_map: Dict[Tuple[str, str], LegalPassage] = {}  # (source_id, normalized_sec) -> passage
        self.bm25: Optional[BM25Okapi] = None
        
    def index_passages(self, passages: List[LegalPassage]):
        for p in passages:
            self.passages[p.passage_id] = p
            
            # Map exact section
            sec_num = p.section_number or ""
            if not sec_num and p.section_identifier:
                # Extract number if available
                m = re.search(r"[0-9]+[A-Za-z]?", p.section_identifier)
                if m:
                    sec_num = m.group(0)
            if sec_num:
                self.section_map[(p.source_id, sec_num.upper())] = p
                # Also store under section identifier format
                self.section_map[(p.source_id, f"SECTION_{sec_num.upper()}")] = p
                self.section_map[(p.source_id, f"SEC_{sec_num.upper()}")] = p

        # Re-build BM25 index over all indexed passages
        corpus = [p.normalized_text or p.passage_text for p in self.passages.values()]
        doc_ids = list(self.passages.keys())
        self.bm25 = BM25Okapi(corpus=corpus, doc_ids=doc_ids)

    def lookup_exact_section(
        self,
        section_number_or_id: str,
        source_id: Optional[str] = None
    ) -> List[LegalPassage]:
        """
        Retrieves passages matching an exact section identifier or section number.
        """
        clean_sec = section_number_or_id.strip().upper()
        # Strip prefixes like "SECTION " or "SEC "
        m = re.search(r"([0-9]+[A-Z]?)", clean_sec)
        sec_num = m.group(1) if m else clean_sec

        matches = []
        if source_id:
            for key_variant in [sec_num, f"SECTION_{sec_num}", f"SEC_{sec_num}"]:
                p = self.section_map.get((source_id, key_variant))
                if p and p not in matches:
                    matches.append(p)
        else:
            for (s_id, s_num), p in self.section_map.items():
                if s_num == sec_num and p not in matches:
                    matches.append(p)

        return matches

    def search_bm25(self, query_text: str, top_k: int) -> List[Tuple[float, LegalPassage]]:
        """
        Ranks passages using the Okapi BM25 algorithm.
        """
        if not self.bm25 or not query_text.strip():
            return []

        ranked_results = self.bm25.search(query_text, top_k=top_k)
        results = []
        for score, pid in ranked_results:
            passage = self.passages.get(pid)
            if passage:
                results.append((score, passage))
        return results

    def search_lexical(self, query_text: str, top_k: int) -> List[Tuple[float, LegalPassage]]:
        """
        Deterministic lexical baseline search.
        Ranks by word overlap for simplicity.
        """
        query_words = set(re.sub(r"[^\w\s]", " ", query_text.lower()).split())
        if not query_words:
            return []
            
        results = []
        for pid, passage in self.passages.items():
            passage_words = set(re.sub(r"[^\w\s]", " ", passage.passage_text.lower()).split())
            overlap = len(query_words.intersection(passage_words))
            if overlap == 0:
                continue
            # simple Jaccard-ish similarity
            score = float(overlap) / (len(query_words) + len(passage_words) - overlap + 1e-9)
            results.append((score, passage))
            
        # Sort descending
        results.sort(key=lambda x: (-x[0], x[1].passage_id))
        return results[:top_k]

