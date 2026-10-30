import re
from typing import List, Optional
from src.missing_provisions.schema import LexicalMatchInfo, ProvisionDefinition
from src.segmentation.schema import Segment

class ProvisionMatcher:
    def __init__(self):
        # Basic negation cues
        self.negation_pattern = re.compile(r'\b(not|no|neither|nor|without|never|prohibited)\b', re.IGNORECASE)
        # Basic conditional cues
        self.conditional_pattern = re.compile(r'\b(if applicable|where required|subject to|unless|provided that|except)\b', re.IGNORECASE)

    def find_lexical_matches(self, segment: Segment, provision: ProvisionDefinition) -> List[LexicalMatchInfo]:
        matches = []
        text_lower = segment.text.lower()
        
        for term in provision.detection_terms:
            term_lower = term.lower()
            start_idx = 0
            
            while True:
                idx = text_lower.find(term_lower, start_idx)
                if idx == -1:
                    break
                
                # Check for negation in a window before/after the match
                window_start = max(0, idx - 50)
                window_end = min(len(text_lower), idx + len(term_lower) + 50)
                window_text = text_lower[window_start:window_end]
                
                has_negation = bool(self.negation_pattern.search(window_text))
                has_conditional = bool(self.conditional_pattern.search(window_text))
                
                matches.append(LexicalMatchInfo(
                    matched_term=term,
                    source_start=segment.original_start + idx,
                    source_end=segment.original_start + idx + len(term),
                    has_negation=has_negation,
                    has_conditional=has_conditional
                ))
                
                start_idx = idx + len(term_lower)
                
        return matches
