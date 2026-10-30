from pydantic import BaseModel

class PreprocessingConfig(BaseModel):
    unicode_normalization: str = "NFC"
    normalize_whitespace: bool = True
    preserve_punctuation: bool = True
    preserve_numbers: bool = True
    preserve_section_numbers: bool = True
    preserve_defined_terms: bool = True
    deduplicate: bool = False
    drop_duplicates: bool = False
    strict_offsets: bool = True
    remove_accidental_artifacts: bool = True
    
    def config_hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()
