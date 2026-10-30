import unicodedata
import re
from typing import Tuple

def normalize_unicode(text: str, form: str = "NFC") -> Tuple[str, bool, bool]:
    """Returns (processed_text, was_applied, offsets_preserved)"""
    processed = unicodedata.normalize(form, text)
    applied = processed != text
    offsets_preserved = len(processed) == len(text)
    return processed, applied, offsets_preserved

def normalize_whitespace(text: str) -> Tuple[str, bool, bool]:
    # Replace \r\n with \n
    processed = text.replace('\r\n', '\n')
    # Collapse multiple spaces (but not newlines)
    processed = re.sub(r'[ \t]+', ' ', processed)
    # Collapse >2 newlines into 2 newlines
    processed = re.sub(r'\n{3,}', '\n\n', processed)
    
    applied = processed != text
    offsets_preserved = len(processed) == len(text)
    return processed, applied, offsets_preserved

def remove_accidental_artifacts(text: str) -> Tuple[str, bool, bool]:
    processed = text.replace('\x00', '')
    applied = processed != text
    offsets_preserved = len(processed) == len(text)
    return processed, applied, offsets_preserved
