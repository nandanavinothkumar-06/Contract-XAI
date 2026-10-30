from typing import Dict, Type
from .base import BaseDatasetAdapter

class DatasetAdapterRegistry:
    def __init__(self):
        self._adapters: Dict[str, Type[BaseDatasetAdapter]] = {}

    def register(self, adapter_cls: Type[BaseDatasetAdapter]):
        self._adapters[adapter_cls.source_dataset] = adapter_cls
    
    def get(self, source_dataset: str) -> Type[BaseDatasetAdapter]:
        if source_dataset not in self._adapters:
            raise KeyError(f"Adapter for {source_dataset} not found in registry.")
        return self._adapters[source_dataset]

registry = DatasetAdapterRegistry()
