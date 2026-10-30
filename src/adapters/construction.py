from typing import Dict, Any, Iterator
import uuid
from .base import BaseDatasetAdapter
from .schema import DatasetRecord, TaskType
from .registry import registry

class ConstructionAdapter(BaseDatasetAdapter):
    """
    Abstracts over Moon 2022, Shuai 2023, and Zhou 2023_2025 construction datasets.
    These datasets are RESTRICTED / Unresolved access, so this adapter serves primarily
    for schema documentation and structural validation when authorized data is available.
    """
    source_dataset = "CONSTRUCTION_BASE"
    license_status = "Not verified"
    access_status = "Unresolved / not independently verified"

    def __init__(self, dataset_path: str = None, specific_source: str = "Moon2022"):
        super().__init__(dataset_path)
        self.specific_source = specific_source
        self.source_dataset = specific_source

    def load(self) -> Iterator[Dict[str, Any]]:
        if self.dataset_path is None:
            return iter([])
        raise NotImplementedError("Actual file loading is deferred and requires authorized data access.")

    def validate_source(self, record: Dict[str, Any]) -> bool:
        required = {"document_id", "text", "label", "task_type"}
        return required.issubset(record.keys())

    def convert_record(self, record: Dict[str, Any]) -> DatasetRecord:
        task_str = record.get("task_type", "")
        task_map = {
            "CLAUSE_RISK_CLASSIFICATION": TaskType.CLAUSE_RISK_CLASSIFICATION,
            "UNILATERAL_CHANGE_RISK_DETECTION": TaskType.UNILATERAL_CHANGE_RISK_DETECTION,
            "MISSING_CLAUSE_DETECTION": TaskType.MISSING_CLAUSE_DETECTION
        }
        task = task_map.get(task_str, TaskType.OTHER)

        return DatasetRecord(
            record_id=str(uuid.uuid4()),
            source_dataset=self.source_dataset,
            source_document_id=record["document_id"],
            clause_id=record.get("clause_id"),
            contract_id=record.get("contract_id"),
            text=record["text"],
            task=task,
            original_label=record["label"],
            rationale=record.get("rationale"),
            domain="Construction",
            language="English",
            annotation_source="Researchers",
            license_status=self.license_status,
            access_status=self.access_status,
            metadata={"is_test_fixture": record.get("is_test_fixture", False)}
        )

registry.register(ConstructionAdapter)
