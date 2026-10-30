from typing import Dict, Any, Iterator
import uuid
from .base import BaseDatasetAdapter
from .schema import DatasetRecord, TaskType
from .registry import registry

class ClaudetteAdapter(BaseDatasetAdapter):
    source_dataset = "CLAUDETTE"
    license_status = "Not explicitly verified from authoritative source"
    access_status = "Open download"

    def load(self) -> Iterator[Dict[str, Any]]:
        if self.dataset_path is None:
            return iter([])
        raise NotImplementedError("Actual file loading is deferred.")

    def validate_source(self, record: Dict[str, Any]) -> bool:
        required = {"sentence_id", "text", "label"}
        return required.issubset(record.keys())

    def convert_record(self, record: Dict[str, Any]) -> DatasetRecord:
        return DatasetRecord(
            record_id=str(uuid.uuid4()),
            source_dataset=self.source_dataset,
            source_document_id=record["sentence_id"],
            clause_id=record["sentence_id"],
            contract_id=record.get("document_id"),
            text=record["text"],
            task=TaskType.UNFAIR_CLAUSE_DETECTION,
            original_label=record["label"],
            rationale=record.get("rationale"),
            domain="Consumer (ToS)",
            language="English",
            annotation_source="Legal experts",
            license_status=self.license_status,
            access_status=self.access_status,
            metadata={"is_test_fixture": record.get("is_test_fixture", False)}
        )

registry.register(ClaudetteAdapter)
