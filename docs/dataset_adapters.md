# Dataset Adapters

## Architecture
The dataset adapter layer acts as a provenance-preserving bridge between diverse, heterogeneous source datasets and the internal analytical components of ContractRisk-XAI. The architecture strictly enforces semantic preservation: adapters map raw files into the unified `DatasetRecord` schema without dropping annotations, synthesizing fake "risk" labels, or altering offsets.

## Canonical Schema
See `canonical_schema.md` for full field specifications.

## Adapter Responsibilities
Each adapter inherits from `BaseDatasetAdapter` and is responsible for:
- Implementing dataset-specific `load()`, `validate_source()`, and `convert_record()` methods.
- Documenting the dataset's licensing and access constraints as explicitly verified in TASK 003.
- Parsing original text, identifiers, labels, and evidence spans.

## Dataset-Specific Mappings
- **CUAD**: Maps QAs into `QA_SPAN_EXTRACTION` records, maintaining QA IDs as `clause_id`.
- **LEDGAR**: Maps provisions into `MULTI_LABEL_PROVISION_CLASSIFICATION` records.
- **ContractNLI**: Maps NLI hypotheses to `DOCUMENT_NLI` records, converting character-level evidence spans appropriately.
- **CLAUDETTE**: Maps sentences into `UNFAIR_CLAUSE_DETECTION` and preserves human-annotated rationales.
- **Construction Datasets**: Serves as a structural definition for restricted access papers.

## Label Preservation and Data Integrity
Original labels (`original_label`) are strictly retained. The system explicitly blocks the automated reduction of distinct legal tasks into a fabricated universal 'LOW/MEDIUM/HIGH' risk classification at the ingestion phase.

## Access/Licensing Safeguards
Adapters enforce awareness of license status directly in the schema objects. The registry's inclusion of an adapter does not imply data possession or redistribution rights. In particular, Construction datasets are marked "Unresolved / not independently verified" and CLAUDETTE is marked "Not explicitly verified."

## Limitations
- Datasets without open access cannot currently be executed in automated pipelines without offline authorization.
- Tokenization or NLP normalizations are strictly omitted at this stage; text is raw.
