from typing import List, Dict, Iterator
from src.adapters.schema import DatasetRecord
from .config import PreprocessingConfig
from .schema import PreprocessedRecord, TransformationLog
from .normalization import normalize_unicode, normalize_whitespace, remove_accidental_artifacts
from .quality import generate_quality_flags
from .fingerprints import generate_fingerprint
from .offsets import process_evidence_spans

class PreprocessingPipeline:
    def __init__(self, config: PreprocessingConfig = None):
        self.config = config or PreprocessingConfig()
        self.version = "1.0.0"

    def preprocess_record(self, record: DatasetRecord) -> PreprocessedRecord:
        current_text = record.text
        operations = []
        offsets_preserved = True
        
        # Quality flags
        flags = generate_quality_flags(record)
        
        # Unicode Normalization
        if self.config.unicode_normalization:
            current_text, applied, op_preserved = normalize_unicode(current_text, self.config.unicode_normalization)
            offsets_preserved = offsets_preserved and op_preserved
            operations.append(TransformationLog(
                operation="unicode_normalization",
                applied=applied,
                description=f"Applied {self.config.unicode_normalization}",
                reversible=False
            ))
            
        # Whitespace Normalization
        if self.config.normalize_whitespace:
            current_text, applied, op_preserved = normalize_whitespace(current_text)
            offsets_preserved = offsets_preserved and op_preserved
            operations.append(TransformationLog(
                operation="whitespace_normalization",
                applied=applied,
                description="Collapsed multiple spaces and newlines",
                reversible=False
            ))
            
        # Artifact Removal
        if self.config.remove_accidental_artifacts:
            current_text, applied, op_preserved = remove_accidental_artifacts(current_text)
            offsets_preserved = offsets_preserved and op_preserved
            operations.append(TransformationLog(
                operation="remove_accidental_artifacts",
                applied=applied,
                description="Removed NULL bytes and basic artifacts",
                reversible=False
            ))
            
        # Log preserves
        if self.config.preserve_punctuation:
            operations.append(TransformationLog(
                operation="preserve_punctuation", applied=True, description="Punctuation preserved", reversible=True
            ))
        if self.config.preserve_numbers:
            operations.append(TransformationLog(
                operation="preserve_numbers", applied=True, description="Numbers/dates preserved", reversible=True
            ))
        if self.config.preserve_section_numbers:
            operations.append(TransformationLog(
                operation="preserve_section_numbers", applied=True, description="Section numbers preserved", reversible=True
            ))
        if self.config.preserve_defined_terms:
            operations.append(TransformationLog(
                operation="preserve_defined_terms", applied=True, description="Defined terms preserved", reversible=True
            ))

        # Fingerprint
        text_hash = generate_fingerprint(current_text)
        
        # Evidence Mapping
        processed_evidence = process_evidence_spans(record.evidence, offsets_preserved)
        
        return PreprocessedRecord(
            original_record=record,
            processed_text=current_text,
            evidence=processed_evidence,
            preprocessing_operations=operations,
            quality_flags=flags,
            text_hash=text_hash,
            preprocessing_version=self.version,
            config_hash=self.config.config_hash()
        )

    def preprocess_dataset(self, records: Iterator[DatasetRecord]) -> Iterator[PreprocessedRecord]:
        seen_hashes = set()
        for record in records:
            processed = self.preprocess_record(record)
            
            if self.config.deduplicate:
                if processed.text_hash in seen_hashes:
                    processed.quality_flags.append("DUPLICATE_TEXT")
                    if self.config.drop_duplicates:
                        operations = list(processed.preprocessing_operations)
                        operations.append(TransformationLog(
                            operation="drop_duplicates", applied=True, description="Record dropped due to duplicate text", reversible=False
                        ))
                        processed.preprocessing_operations = operations
                        continue # Skip yielding
                seen_hashes.add(processed.text_hash)
                
            yield processed
