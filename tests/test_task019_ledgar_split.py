import os
import pytest
from src.models.run_task019_experiments import get_ledgar_data, get_project_root

@pytest.fixture(scope="module")
def ledgar_df():
    # Only run if LEDGAR is present
    root = get_project_root()
    path = root / "data" / "raw" / "ledgar" / "extracted" / "LEDGAR_2016-2019_clean.jsonl"
    if not path.exists():
        pytest.skip("LEDGAR dataset not available for test.")
    
    df = get_ledgar_data()
    if df.empty:
        pytest.skip("LEDGAR returned empty.")
    return df

def test_ledgar_partition_counts(ledgar_df):
    train_df = ledgar_df[ledgar_df["split"] == "train"]
    val_df = ledgar_df[ledgar_df["split"] == "val"]
    test_df = ledgar_df[ledgar_df["split"] == "test"]
    
    assert len(train_df) == 674068, f"Expected 674068 train, got {len(train_df)}"
    assert len(val_df) == 84250, f"Expected 84250 val, got {len(val_df)}"
    assert len(test_df) == 87956, f"Expected 87956 test, got {len(test_df)}"
    assert len(ledgar_df) == 846274, "Expected total 846274 provisions"

def test_ledgar_contract_counts(ledgar_df):
    train_df = ledgar_df[ledgar_df["split"] == "train"]
    val_df = ledgar_df[ledgar_df["split"] == "val"]
    test_df = ledgar_df[ledgar_df["split"] == "test"]
    
    train_contracts = set(train_df["contract_id"].unique())
    val_contracts = set(val_df["contract_id"].unique())
    test_contracts = set(test_df["contract_id"].unique())
    
    assert len(train_contracts) == 48432, f"Expected 48432 train contracts, got {len(train_contracts)}"
    assert len(val_contracts) == 6054, f"Expected 6054 val contracts, got {len(val_contracts)}"
    assert len(test_contracts) == 6054, f"Expected 6054 test contracts, got {len(test_contracts)}"
    assert len(train_contracts | val_contracts | test_contracts) == 60540, "Expected 60540 total contracts"

def test_ledgar_zero_contract_overlap(ledgar_df):
    train_df = ledgar_df[ledgar_df["split"] == "train"]
    val_df = ledgar_df[ledgar_df["split"] == "val"]
    test_df = ledgar_df[ledgar_df["split"] == "test"]
    
    train_contracts = set(train_df["contract_id"])
    val_contracts = set(val_df["contract_id"])
    test_contracts = set(test_df["contract_id"])
    
    assert len(train_contracts.intersection(val_contracts)) == 0, "Overlap between train and val contracts"
    assert len(train_contracts.intersection(test_contracts)) == 0, "Overlap between train and test contracts"
    assert len(val_contracts.intersection(test_contracts)) == 0, "Overlap between val and test contracts"

def test_ledgar_label_count(ledgar_df):
    all_labels = set()
    for labels in ledgar_df["labels"]:
        all_labels.update(labels)
    assert len(all_labels) == 12608, f"Expected 12608 unique labels, got {len(all_labels)}"
