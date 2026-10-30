import os
import json
import hashlib
import pytest
from src.adapters.registry import registry
from src.adapters.schema import TaskType

def test_manifest_existence_and_schema():
    manifest_path = "data/dataset_manifest.json"
    assert os.path.exists(manifest_path), "dataset_manifest.json must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert "datasets" in manifest
    names = {d["dataset_name"] for d in manifest["datasets"]}
    assert {"ContractNLI", "CUAD", "LEDGAR"}.issubset(names)

    for d in manifest["datasets"]:
        if d["acquisition_status"] == "ACQUIRED_AND_VALIDATED":
            assert d["is_test_fixture"] is False
            assert d["validation_status"] == "VALID"
            assert len(d["files"]) > 0
            for f in d["files"]:
                assert os.path.exists(f["path"]), f"File must exist: {f['path']}"
                assert os.path.getsize(f["path"]) == f["size_bytes"]
                # Verify SHA256 matches manifest
                h = hashlib.sha256()
                with open(f["path"], "rb") as fp:
                    while chunk := fp.read(1024 * 1024):
                        h.update(chunk)
                assert h.hexdigest() == f["sha256"], f"SHA256 mismatch for {f['path']}"

def test_contractnli_adapter_real_sample():
    path = "data/raw/contractnli/extracted/contract-nli/dev.json"
    if not os.path.exists(path):
        pytest.skip("ContractNLI real file not present")
    adapter = registry.get("ContractNLI")(dataset_path=path)
    count = 0
    for rec in adapter.load():
        assert adapter.validate_source(rec) is True
        canonical = adapter.convert_record(rec)
        assert canonical.task == TaskType.DOCUMENT_NLI
        assert canonical.source_dataset == "ContractNLI"
        assert canonical.metadata["is_test_fixture"] is False
        count += 1
        if count >= 100:
            break
    assert count == 100

def test_cuad_adapter_real_sample():
    path = "data/raw/cuad/extracted/CUAD_v1/CUAD_v1.json"
    if not os.path.exists(path):
        pytest.skip("CUAD real file not present")
    adapter = registry.get("CUAD")(dataset_path=path)
    count = 0
    for rec in adapter.load():
        assert adapter.validate_source(rec) is True
        canonical = adapter.convert_record(rec)
        assert canonical.task == TaskType.QA_SPAN_EXTRACTION
        assert canonical.source_dataset == "CUAD"
        assert canonical.metadata["is_test_fixture"] is False
        count += 1
        if count >= 100:
            break
    assert count == 100

def test_ledgar_adapter_real_sample():
    path = "data/raw/ledgar/extracted/LEDGAR_2016-2019_clean.jsonl"
    if not os.path.exists(path):
        pytest.skip("LEDGAR real file not present")
    adapter = registry.get("LEDGAR")(dataset_path=path)
    count = 0
    for rec in adapter.load():
        assert adapter.validate_source(rec) is True
        canonical = adapter.convert_record(rec)
        assert canonical.task == TaskType.MULTI_LABEL_PROVISION_CLASSIFICATION
        assert canonical.source_dataset == "LEDGAR"
        assert canonical.metadata["is_test_fixture"] is False
        count += 1
        if count >= 100:
            break
    assert count == 100

def test_synthetic_fixture_remains_marked():
    raw_fixture = {
        "document_id": "synth_doc_1",
        "context": "Synthetic clause context for unit testing.",
        "qas_id": "synth_q1",
        "question": "Is this synthetic?",
        "answers": [{"text": "Synthetic clause", "answer_start": 0}],
        "is_test_fixture": True
    }
    adapter = registry.get("CUAD")()
    assert adapter.validate_source(raw_fixture) is True
    canonical = adapter.convert_record(raw_fixture)
    assert canonical.metadata["is_test_fixture"] is True
