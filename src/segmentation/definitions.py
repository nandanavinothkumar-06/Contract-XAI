import re

def is_definition(text: str) -> bool:
    patterns = [
        r'^\s*["“][^"”]+["”]\s+(means|shall mean|refers to)',
        r'^\s*([A-Z][a-z]+(\s+[A-Z][a-z]+)*)\s+(means|shall mean)'
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False
