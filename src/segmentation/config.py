from pydantic import BaseModel

class SegmentationConfig(BaseModel):
    detect_numbering: bool = True
    detect_headings: bool = True
    detect_definitions: bool = True
    detect_schedules: bool = True
    detect_exhibits: bool = True
    preserve_source_boundaries: bool = True
    strict_offsets: bool = True
    
    def config_hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()
