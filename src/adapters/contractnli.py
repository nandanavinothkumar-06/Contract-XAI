from typing import Dict, Any, Iterator
import uuid
from .base import BaseDatasetAdapter
from .schema import DatasetRecord, TaskType, EvidenceSpan
from .registry import registry

class ContractNLIAdapter(BaseDatasetAdapter):
    source_dataset = "ContractNLI"
    license_status = "Dataset: CC BY 4.0 (Baseline Implementation: Apache 2.0)"
    access_status = "Open download"

    def load(self) -> Iterator[Dict[str, Any]]:
        import json, os
        if self.dataset_path is None or not os.path.exists(self.dataset_path):
            return iter([])

        files_to_load = []
        if os.path.isdir(self.dataset_path):
            for split in ["train.json", "dev.json", "test.json"]:
                p = os.path.join(self.dataset_path, split)
                if os.path.exists(p):
                    files_to_load.append(p)
        else:
            files_to_load.append(self.dataset_path)

        for filepath in files_to_load:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            labels_dict = data.get("labels", {})
            for doc in data.get("documents", []):
                doc_id = str(doc.get("id"))
                text = doc.get("text", "")
                spans = doc.get("spans", [])
                for ann_set in doc.get("annotation_sets", []):
                    for hyp_id, ann in ann_set.get("annotations", {}).items():
                        hyp_meta = labels_dict.get(hyp_id, {})
                        hypothesis = hyp_meta.get("hypothesis", hyp_id)
                        choice = ann.get("choice", "")
                        evidence_spans = []
                        for span_idx in ann.get("spans", []):
                            if isinstance(span_idx, int) and 0 <= span_idx < len(spans):
                                s_start, s_end = spans[span_idx]
                                evidence_spans.append({
                                    "start": s_start,
                                    "end": s_end,
                                    "text": text[s_start:s_end]
                                })
                        yield {
                            "document_id": doc_id,
                            "text": text,
                            "hypothesis": hypothesis,
                            "label": choice,
                            "evidence_spans": evidence_spans,
                            "is_test_fixture": False
                        }

    def validate_source(self, record: Dict[str, Any]) -> bool:
        required = {"document_id", "text", "hypothesis", "label", "evidence_spans"}
        return required.issubset(record.keys())

    def convert_record(self, record: Dict[str, Any]) -> DatasetRecord:
        # evidence_spans in source is expected to be a list of dicts: {"start": x, "end": y, "text": "..."}
        evidence = []
        for span in record.get("evidence_spans", []):
            start = span.get("start", -1)
            end = span.get("end", -1)
            text = span.get("text", "")
            if start >= 0 and end >= start:
                evidence.append(
                    EvidenceSpan(
                        start=start,
                        end=end,
                        text=text,
                        source_field="text"
                    )
                )

        return DatasetRecord(
            record_id=str(uuid.uuid4()),
            source_dataset=self.source_dataset,
            source_document_id=record["document_id"],
            contract_id=record["document_id"],
            text=record["text"],
            task=TaskType.DOCUMENT_NLI,
            original_label=record["label"],
            evidence=evidence,
            domain="Commercial (NDA)",
            language="English",
            annotation_source="Expert/Annotator",
            license_status=self.license_status,
            access_status=self.access_status,
            metadata={
                "hypothesis": record["hypothesis"],
                "is_test_fixture": record.get("is_test_fixture", False)
            }
        )

registry.register(ContractNLIAdapter)
