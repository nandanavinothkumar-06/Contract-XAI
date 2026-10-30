from typing import List, Optional
from src.segmentation.schema import Segment
from src.context.schema import ContextualizedInput, ContextComponent, ContextMetadata
from src.context.strategies import get_strategy_none, get_strategy_previous_next, get_strategy_window, get_strategy_parent_child
from src.context.budget import ContextBudgeter
from src.models.tokenizer import LegalBertTokenizerWrapper

class ContextBuilder:
    def __init__(self, tokenizer_wrapper: LegalBertTokenizerWrapper, max_sequence_length: int = 512):
        self.budgeter = ContextBudgeter(tokenizer_wrapper, max_sequence_length)
        
    def _determine_role(self, target: Segment, comp: Segment) -> str:
        if target.segment_id == comp.segment_id:
            return "TARGET"
        if target.parent_segment_id == comp.segment_id:
            return "PARENT"
        if comp.parent_segment_id == target.segment_id:
            return "CHILD"
        if comp.sequence == target.sequence - 1:
            return "PREVIOUS"
        if comp.sequence == target.sequence + 1:
            return "NEXT"
        return "WINDOW"
        
    def build(
        self, 
        target: Segment, 
        all_segments: List[Segment], 
        strategy: str = "NONE",
        window_size: int = 2
    ) -> ContextualizedInput:
        
        # 1. Leakage Protection Check
        # Context MUST remain inside the same source document AND same partition
        target_partition = target.metadata.get("partition", "UNKNOWN")
        for s in all_segments:
            if s.source_document_id != target.source_document_id:
                raise ValueError("Cross-document context leakage detected.")
            if s.metadata.get("partition", "UNKNOWN") != target_partition:
                raise ValueError(f"Cross-partition context leakage detected. Target: {target_partition}, Context: {s.metadata.get('partition', 'UNKNOWN')}")
            
        # 2. Select strategy
        if strategy == "NONE":
            selected_segments = get_strategy_none(target, all_segments)
        elif strategy == "PREVIOUS_NEXT":
            selected_segments = get_strategy_previous_next(target, all_segments)
        elif strategy == "WINDOW":
            selected_segments = get_strategy_window(target, all_segments, window_size)
        elif strategy == "PARENT_CHILD":
            selected_segments = get_strategy_parent_child(target, all_segments)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
            
        # 3. Create components
        target_component = None
        context_components = []
        
        # Sort them by their original sequence to ensure deterministic order
        selected_segments.sort(key=lambda x: x.sequence)
        
        for s in selected_segments:
            role = self._determine_role(target, s)
            comp = ContextComponent(
                clause_id=s.segment_id,
                source_document_id=s.source_document_id,
                role=role,
                order=s.sequence,
                source_start=s.original_start,
                source_end=s.original_end,
                model_input_start=-1, # Will be set during assembly
                model_input_end=-1,
                text=s.text
            )
            if role == "TARGET":
                target_component = comp
            else:
                context_components.append(comp)
                
        # We need an explicit priority if we must truncate context.
        # Priority: TARGET > PARENT > PREVIOUS > NEXT > CHILD > WINDOW
        def priority(c: ContextComponent) -> int:
            priorities = {"TARGET": 0, "PARENT": 1, "PREVIOUS": 2, "NEXT": 3, "CHILD": 4, "WINDOW": 5}
            return priorities.get(c.role, 10)
            
        context_components.sort(key=priority)
        
        # 4. Budgeting
        included_context, excluded_context, context_truncated, target_truncated = self.budgeter.budget_components(
            target_component, 
            context_components
        )
        
        # 5. Assembly and Offset Tracking
        final_components = [target_component] + included_context
        final_components.sort(key=lambda x: x.order)
        
        final_text_parts = []
        current_offset = 0
        
        for comp in final_components:
            if comp.role == "TARGET":
                prefix = "[TARGET]\n"
                suffix = "\n[/TARGET]"
            else:
                prefix = "[CONTEXT]\n"
                suffix = "\n[/CONTEXT]"
                
            # The component text starts after the prefix
            comp.model_input_start = current_offset + len(prefix)
            comp.model_input_end = comp.model_input_start + len(comp.text)
            
            part_str = f"{prefix}{comp.text}{suffix}"
            final_text_parts.append(part_str)
            
            # +2 for the "\n\n" separator joining components, except the last one
            current_offset += len(part_str) + 2
                
        final_text = "\n\n".join(final_text_parts)
        
        metadata = ContextMetadata(
            target_clause_id=target_component.clause_id,
            source_document_id=target_component.source_document_id,
            context_strategy=strategy,
            context_clause_ids=[c.clause_id for c in context_components],
            included_context_clause_ids=[c.clause_id for c in included_context],
            excluded_context_clause_ids=[c.clause_id for c in excluded_context],
            target_position=target_component.order,
            context_truncated=context_truncated,
            target_truncated=target_truncated,
            target_model_input_start=target_component.model_input_start,
            target_model_input_end=target_component.model_input_end,
            target_source_start=target_component.source_start,
            target_source_end=target_component.source_end
        )
        
        return ContextualizedInput(
            target_clause_id=target_component.clause_id,
            components=final_components,
            text=final_text,
            metadata=metadata
        )
