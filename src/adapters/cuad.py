from typing import Dict, Any, Iterator
import uuid
from .base import BaseDatasetAdapter
from .schema import DatasetRecord, TaskType, EvidenceSpan
from .registry import registry

class CUADAdapter(BaseDatasetAdapter):
    source_dataset = "CUAD"
    license_status = "Dataset released under CC BY 4.0; underlying contract rights remain subject to the source/disclaimer conditions."
    access_status = "Open download"
    
    def load(self) -> Iterator[Dict[str, Any]]:
        import json, os
        if self.dataset_path is None or not os.path.exists(self.dataset_path):
            return iter([])
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for article in data.get("data", []):
            doc_id = article.get("title", "")
            for paragraph in article.get("paragraphs", []):
                context = paragraph.get("context", "")
                for qa in paragraph.get("qas", []):
                    yield {
                        "document_id": doc_id,
                        "context": context,
                        "qas_id": qa.get("id", ""),
                        "question": qa.get("question", ""),
                        "answers": qa.get("answers", []),
                        "is_test_fixture": False
                    }

    def validate_source(self, record: Dict[str, Any]) -> bool:
        required = {"document_id", "context", "qas_id", "question", "answers"}
        return required.issubset(record.keys())

    def convert_record(self, record: Dict[str, Any]) -> DatasetRecord:
        evidence_spans = []
        for ans in record.get("answers", []):
            start = ans.get("answer_start", -1)
            text = ans.get("text", "")
            if start >= 0 and text:
                evidence_spans.append(
                    EvidenceSpan(
                        start=start,
                        end=start + len(text),
                        text=text,
                        source_field="context"
                    )
                )

        return DatasetRecord(
            record_id=str(uuid.uuid4()),
            source_dataset=self.source_dataset,
            source_document_id=record["document_id"],
            contract_id=record["document_id"],
            clause_id=record["qas_id"],
            text=record["context"],
            task=TaskType.QA_SPAN_EXTRACTION,
            original_label=record["question"],
            evidence=evidence_spans,
            domain="Commercial",
            language="English",
            annotation_source="Legal experts (The Atticus Project)",
            license_status=self.license_status,
            access_status=self.access_status,
            metadata={"is_test_fixture": record.get("is_test_fixture", False)}
        )

registry.register(CUADAdapter)
