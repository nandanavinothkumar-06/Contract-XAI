from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any
from .schema import DatasetRecord

class BaseDatasetAdapter(ABC):
    source_dataset: str = "BASE"
    license_status: str = "Not verified"
    access_status: str = "Not verified"
    
    def __init__(self, dataset_path: str = None):
        self.dataset_path = dataset_path

    @abstractmethod
    def load(self) -> Iterator[Dict[str, Any]]:
        """Loads records from the dataset source."""
        pass
        
    @abstractmethod
    def validate_source(self, record: Dict[str, Any]) -> bool:
        """Validates that a raw source record contains required fields."""
        pass
        
    @abstractmethod
    def convert_record(self, record: Dict[str, Any]) -> DatasetRecord:
        """Converts a valid raw record into the canonical DatasetRecord schema."""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Returns metadata about the adapter."""
        return {
            "source_dataset": self.source_dataset,
            "license_status": self.license_status,
            "access_status": self.access_status
        }

    def process_all(self) -> Iterator[DatasetRecord]:
        """Processes all records and yields canonical DatasetRecords."""
        for raw_record in self.load():
            if self.validate_source(raw_record):
                canonical = self.convert_record(raw_record)
                yield canonical
            else:
                raise ValueError(f"Record failed source validation: {raw_record}")
