import re
from typing import List
from .schema import Segment

def build_hierarchy(segments: List[Segment]) -> List[Segment]:
    stack = []
    
    def get_level(seg: Segment) -> int:
        if seg.segment_type.value == "DOCUMENT_TITLE": return 0
        num = seg.numbering
        if num:
            if "Article" in num or "Section" in num: return 1
            if re.match(r'^\d+[\.\:]?$', num.strip()): 
                return 2
            if re.match(r'^\d+(\.\d+)+[\.\:]?$', num.strip()):
                parts = [p for p in num.replace(':', '.').split('.') if p]
                return 1 + len(parts) 
            if re.match(r'^\([a-z]\)$', num.strip()) and not re.match(r'^\([ivxlcdm]+\)$', num.strip()):
                return 5
            if re.match(r'^\([ivxlcdm]+\)$', num.strip()):
                return 6
            if re.match(r'^\([A-Z]\)$', num.strip()):
                return 7
        if seg.segment_type.value == "SECTION_HEADING": return 1
        return 99

    for i, seg in enumerate(segments):
        level = get_level(seg)
        if level == 99 and stack:
            level = stack[-1][0] + 1
            
        while stack and stack[-1][0] >= level:
            stack.pop()
            
        if stack:
            parent_level, parent_seg = stack[-1]
            seg.parent_segment_id = parent_seg.segment_id
            seg.path = f"{parent_seg.path}/{i}"
            seg.level = level
        else:
            seg.parent_segment_id = None
            seg.path = str(i)
            seg.level = level
            
        stack.append((level, seg))
        
    return segments
