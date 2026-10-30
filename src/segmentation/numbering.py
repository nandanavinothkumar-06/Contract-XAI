import re
from typing import Optional, Tuple

NUMBERING_PATTERNS = [
    r'^(Article\s+[IVX\d]+[\.\:]?)',
    r'^(Section\s+\d+(\.\d+)*[\.\:]?)',
    r'^(\d+(\.\d+)+[\.\:]?)', # 1.1 or 1.1.
    r'^(\d+[\.\:])',          # 1. or 1:
    r'^(\([a-z]\))',         # (a)
    r'^(\([A-Z]\))',         # (A)
    r'^(\([ivxlcdm]+\))',    # (i)
    r'^([A-Z]\.)',           # A.
    r'^([a-z]\.)'            # a.
]

def detect_numbering(text: str) -> Tuple[Optional[str], str]:
    text_stripped = text.strip()
    for pattern in NUMBERING_PATTERNS:
        match = re.search(pattern, text_stripped)
        if match:
            return match.group(1), text
    return None, text
