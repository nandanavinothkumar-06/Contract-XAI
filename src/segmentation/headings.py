import re

def is_likely_heading(text: str, has_numbering: bool) -> bool:
    text = text.strip()
    if not text:
        return False
        
    if len(text) < 100 and text.isupper():
        return True
        
    if len(text) < 150 and has_numbering:
        if not re.search(r'[a-z]{2,}[\.\?\!]$', text):
            return True

    return False
