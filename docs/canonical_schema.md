# Canonical Schema

The `DatasetRecord` Pydantic model is the universal representation for all dataset inputs within ContractRisk-XAI. It ensures that critical semantic and provenance data is carried alongside the raw text.

## Fields
- **record_id** (`str`): Unique UUID for the parsed instance.
- **source_dataset** (`str`): Identifier of the original dataset (e.g. "CUAD", "LEDGAR").
- **source_version** (`Optional[str]`): Version of the dataset, if applicable.
- **source_document_id** (`str`): The primary document identifier from the source.
- **contract_id** (`Optional[str]`): The broader contract identifier, if the text is a localized clause.
- **clause_id** (`Optional[str]`): A specific clause identifier.
- **text** (`str`): The raw, unmodified text content.
- **task** (`TaskType`): An enumeration of the NLP task (e.g., `DOCUMENT_NLI`, `MULTI_LABEL_PROVISION_CLASSIFICATION`).
- **original_label** (`Any`): The exact, unmodified label from the source dataset.
- **normalized_label** (`Optional[Any]`): Populated only in later tasks if a safe, scientifically rigorous mapping is performed. Defaults to None.
- **evidence** (`List[EvidenceSpan]`): A list of exact textual evidence offsets supporting the label.
- **rationale** (`Optional[str]`): Human-annotated textual rationale.
- **domain** (`Optional[str]`): The domain of the document (e.g., "Commercial", "Consumer").
- **language** (`Optional[str]`): Language of the document.
- **annotation_source** (`Optional[str]`): Information on who provided the labels (e.g., "Legal experts", "Automatic").
- **source_reference** (`Optional[str]`): Link or reference to the source.
- **license_status** (`Optional[str]`): The explicitly verified dataset license.
- **access_status** (`Optional[str]`): The explicitly verified access availability.
- **metadata** (`Dict[str, Any]`): Arbitrary dataset-specific attributes (e.g. hypotheses).

## EvidenceSpan
- **start** (`int`): Starting character offset (0-indexed).
- **end** (`int`): Ending character offset.
- **text** (`str`): The exact string located at the specified offset.
- **source_field** (`str`): The field containing the evidence (e.g. "text", "context").
