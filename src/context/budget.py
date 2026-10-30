from typing import List, Dict, Any, Tuple
from src.segmentation.schema import Segment
from src.context.schema import ContextComponent
from src.models.tokenizer import LegalBertTokenizerWrapper

class ContextBudgeter:
    def __init__(self, tokenizer_wrapper: LegalBertTokenizerWrapper, max_sequence_length: int = 512):
        self.tokenizer = tokenizer_wrapper.tokenizer
        self.max_length = max_sequence_length
        if hasattr(self.tokenizer, "num_special_tokens_to_add"):
            self.special_tokens = self.tokenizer.num_special_tokens_to_add()
        else:
            self.special_tokens = 2 # [CLS] and [SEP]
            
    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.tokenize(text))
        
    def budget_components(
        self, 
        target_component: ContextComponent, 
        context_components: List[ContextComponent]
    ) -> Tuple[List[ContextComponent], List[ContextComponent], bool, bool]:
        """
        Prioritizes the target. Then greedily adds context components based on priority.
        Returns:
            included_context, excluded_context, context_truncated, target_truncated
        """
        # Format overhead:
        # [TARGET]\n{target}\n[/TARGET]\n
        # [CONTEXT]\n{context}\n[/CONTEXT]\n
        
        target_wrapper = f"[TARGET]\n{target_component.text}\n[/TARGET]"
        target_tokens = self.count_tokens(target_wrapper)
        
        included = []
        excluded = []
        context_truncated = False
        target_truncated = False
        
        current_budget = self.special_tokens + target_tokens
        
        if current_budget > self.max_length:
            # The target itself exceeds the budget!
            # We must truncate the target and exclude all context.
            target_truncated = True
            context_truncated = len(context_components) > 0
            excluded = context_components
            return included, excluded, context_truncated, target_truncated
            
        for comp in context_components:
            comp_wrapper = f"[CONTEXT]\n{comp.text}\n[/CONTEXT]"
            # +1 for a newline or space between components
            comp_tokens = self.count_tokens(comp_wrapper) + 1 
            
            if current_budget + comp_tokens <= self.max_length:
                included.append(comp)
                current_budget += comp_tokens
            else:
                excluded.append(comp)
                context_truncated = True
                
        return included, excluded, context_truncated, target_truncated
