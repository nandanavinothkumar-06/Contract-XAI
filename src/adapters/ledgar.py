from typing import Dict, Any, Iterator
import uuid
from .base import BaseDatasetAdapter
from .schema import DatasetRecord, TaskType
from .registry import registry

class LEDGARAdapter(BaseDatasetAdapter):
    source_dataset = "LEDGAR"
    license_status = "MIT (via LexGLUE)"
    access_status = "Open download"

    def load(self) -> Iterator[Dict[str, Any]]:
        import json, os
        if self.dataset_path is None or not os.path.exists(self.dataset_path):
            return iter([])

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if "provision_id" in record and "text" in record and "labels" in record:
                    yield {
                        "provision_id": record["provision_id"],
                        "text": record["text"],
                        "labels": record["labels"] if isinstance(record["labels"], list) else [record["labels"]],
                        "contract_id": record.get("contract_id"),
                        "is_test_fixture": False
                    }
                else:
                    # Raw Tuggener LEDGAR format: 'provision', 'label', 'source'
                    text = record.get("provision", "")
                    labels = record.get("label", [])
                    if not isinstance(labels, list):
                        labels = [labels] if labels else []
                    source = record.get("source", "")
                    prov_id = f"{source}#{idx}" if source else str(idx)
                    yield {
                        "provision_id": prov_id,
                        "text": text,
                        "labels": labels,
                        "contract_id": source,
                        "is_test_fixture": False
                    }

    def validate_source(self, record: Dict[str, Any]) -> bool:
        required = {"provision_id", "text", "labels"}
        if not required.issubset(record.keys()):
            return False
        if not isinstance(record["labels"], list):
            return False
        return True

    def convert_record(self, record: Dict[str, Any]) -> DatasetRecord:
        return DatasetRecord(
            record_id=str(uuid.uuid4()),
            source_dataset=self.source_dataset,
            source_document_id=record["provision_id"],
            clause_id=record["provision_id"],
            contract_id=record.get("contract_id"),
            text=record["text"],
            task=TaskType.MULTI_LABEL_PROVISION_CLASSIFICATION,
            original_label=record["labels"],
            domain="Commercial/Financial",
            language="English",
            annotation_source="Automatic extraction",
            license_status=self.license_status,
            access_status=self.access_status,
            metadata={"is_test_fixture": record.get("is_test_fixture", False)}
        )

registry.register(LEDGARAdapter)
