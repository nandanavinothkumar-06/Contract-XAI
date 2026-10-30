from typing import List, Optional
from src.segmentation.schema import Segment

def get_strategy_none(target: Segment, all_segments: List[Segment]) -> List[Segment]:
    return [target]

def get_strategy_previous_next(target: Segment, all_segments: List[Segment]) -> List[Segment]:
    idx = all_segments.index(target)
    components = []
    if idx > 0:
        components.append(all_segments[idx - 1])
    components.append(target)
    if idx < len(all_segments) - 1:
        components.append(all_segments[idx + 1])
    return components

def get_strategy_window(target: Segment, all_segments: List[Segment], window_size: int = 2) -> List[Segment]:
    idx = all_segments.index(target)
    start_idx = max(0, idx - window_size)
    end_idx = min(len(all_segments), idx + window_size + 1)
    return all_segments[start_idx:end_idx]

def get_strategy_parent_child(target: Segment, all_segments: List[Segment]) -> List[Segment]:
    components = []
    # Find parent
    if target.parent_segment_id:
        parent = next((s for s in all_segments if s.segment_id == target.parent_segment_id), None)
        if parent:
            components.append(parent)
            
    # Add target
    components.append(target)
    
    # Find children
    children = [s for s in all_segments if s.parent_segment_id == target.segment_id]
    components.extend(children)
    
    # Sort them by their original sequence to ensure deterministic order
    components.sort(key=lambda x: x.sequence)
    return components
