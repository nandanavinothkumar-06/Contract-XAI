import re
from typing import List, Tuple

def split_into_blocks(text: str) -> List[Tuple[str, int, int]]:
    blocks = []
    # Identify non-whitespace blocks
    for match in re.finditer(r'(?s)(\S.*?)(?:\n[ \t]*\n|$)', text):
        block_text = match.group(1).rstrip()
        if block_text:
            start = match.start(1)
            end = start + len(block_text)
            blocks.append((text[start:end], start, end))
    return blocks
