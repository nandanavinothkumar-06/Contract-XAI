# Preprocessing Layer

## Philosophy & Legal-Text Preservation
In ContractRisk-XAI, legal text must not be "cleaned" destructively as in standard NLP pipelines. Operations like stop-word removal, stemming, lemmatization, and aggressive punctuation removal are strictly prohibited because they may materially alter legal meaning.
The core principle is **non-destructive transformation**:
- The `original_text` field in the `DatasetRecord` is never overwritten.
- A `processed_text` is created for normalized output.
- All transformations are recorded in the `preprocessing_operations` transformation log for auditability.

## Transformations
Supported transformations (configurable via `PreprocessingConfig`):
- **Unicode Normalization**: Default `NFC`.
- **Whitespace Normalization**: Safe collapsing of duplicated spaces and newlines.
- **Accidental Artifact Removal**: Safe removal of extraction anomalies like NULL bytes.

The pipeline explicitly logs the preservation of legal constructs:
- Legal punctuation
- Numbers and dates
- Section numbers
- Defined terms

## Configuration
The pipeline is managed by a `PreprocessingConfig` Pydantic model. 
```python
unicode_normalization: str = "NFC"
normalize_whitespace: bool = True
deduplicate: bool = False
drop_duplicates: bool = False
```

## Offset & Evidence Handling
Because evidence spans (e.g. from CUAD, ContractNLI) depend on exact character offsets in the original text, modifying the text length during preprocessing invalidates these offsets. 
If an operation preserves text length (e.g., standard Unicode normalization), the processed offset maps 1:1 (`offset_mapping_status = "AVAILABLE"`).
If an operation changes text length (e.g., whitespace collapsing), mapping becomes unreliable without a complex byte-mapper. To be safe, the pipeline marks `offset_mapping_status = "UNAVAILABLE"` and retains the original offsets. It does **not** guess offsets.

## Quality Flags
The pipeline identifies issues and adds tags to `quality_flags` instead of silently deleting records:
- `EMPTY_TEXT`, `VERY_SHORT_TEXT`
- `UNICODE_ANOMALY`
- `EXCESSIVE_WHITESPACE`
- `MISSING_SOURCE_ID`, `MISSING_LABEL`, `MISSING_EVIDENCE`
- `EVIDENCE_OUT_OF_BOUNDS`
- `DUPLICATE_TEXT`

## Duplicate Detection
If `config.deduplicate = True`, the pipeline computes a SHA-256 `text_hash`. Duplicates get the `DUPLICATE_TEXT` flag. Unless `drop_duplicates` is explicitly set to `True`, the pipeline will not delete them.

## Reproducibility
The output of the pipeline is entirely deterministic.
Every `PreprocessedRecord` tracks:
- `preprocessing_version`
- `config_hash`: A SHA-256 hash of the configuration JSON used to generate it.

## Limitations
- This layer performs string-level document normalization. It does **not** perform clause segmentation or NLP tokenization (e.g. WordPiece/SentencePiece).
- OCR correction is deferred, assuming text extraction has been previously completed.
