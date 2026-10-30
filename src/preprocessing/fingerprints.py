import hashlib

def generate_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
