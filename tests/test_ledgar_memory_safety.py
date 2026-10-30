import pytest
import torch
import numpy as np
from datasets import Dataset
from src.models.run_task019_experiments import MemorySafeLedgarCollator
from src.models.config import LegalBertConfig
from src.models.legalbert import LegalBertWrapper

def test_collator_memory_safety_and_forward():
    # Prove that the collator works on raw text and dynamically produces 
    # padded input_ids, attention_mask, and dense float label vectors
    
    # 1. Setup mock wrapper
    config = LegalBertConfig(classification_mode="multilabel", num_labels=10, is_test_fixture=True)
    wrapper = LegalBertWrapper(config)
    tokenizer = wrapper.tokenizer_wrapper.tokenizer
    model = wrapper.model
    
    # 2. Setup mock data (8 rows)
    texts = [
        "This is a short provision.",
        "This is a slightly longer provision to test dynamic padding.",
        "Another provision.",
        "Short.",
        "A"*100, # medium string
        "B"*1000, # long string, will be truncated to max_length=512
        "C",
        "D"
    ]
    labels = [
        ["labelA"],
        ["labelB", "labelC"],
        [],
        ["labelA", "labelD"],
        ["labelC"],
        ["labelD"],
        ["labelA"],
        ["labelA", "labelB", "labelC", "labelD"]
    ]
    
    label2id = {"labelA": 0, "labelB": 1, "labelC": 2, "labelD": 3}
    num_labels = 10
    
    # 3. Create raw dataset 
    # Crucially, it does NOT contain input_ids or attention_mask
    raw_ds = Dataset.from_dict({"text": texts, "labels": labels})
    assert "input_ids" not in raw_ds.column_names
    
    # 4. Initialize collator
    collator = MemorySafeLedgarCollator(tokenizer, label2id, num_labels)
    
    # 5. Extract batch features exactly as Trainer would
    features = [raw_ds[i] for i in range(len(raw_ds))]
    
    # 6. Collate (this is the core memory safety mechanism being tested)
    batch = collator(features)
    
    # 7. Assertions
    assert "input_ids" in batch
    assert "attention_mask" in batch
    assert "labels" in batch
    
    # Check dynamic padding (longest string is "B"*1000 which is 512 tokens max)
    # The actual padding length depends on the max length of the batch, capped at 512
    seq_len = batch["input_ids"].shape[1]
    assert seq_len <= 512
    assert batch["input_ids"].shape[0] == 8 # batch size
    
    # Check dense label vectors
    assert batch["labels"].shape == (8, 10)
    assert batch["labels"].dtype == torch.float32
    
    # Specific label checks
    # Row 0: ["labelA"] -> index 0 = 1.0
    assert batch["labels"][0, 0].item() == 1.0
    assert batch["labels"][0, 1].item() == 0.0
    
    # Row 1: ["labelB", "labelC"] -> index 1 = 1.0, index 2 = 1.0
    assert batch["labels"][1, 1].item() == 1.0
    assert batch["labels"][1, 2].item() == 1.0
    assert batch["labels"][1, 0].item() == 0.0
    
    # 8. Structural Smoke Test: Forward pass
    # Proves the collated dictionary is perfectly compatible with the model
    with torch.no_grad():
        outputs = model(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            labels=batch["labels"]
        )
        
    assert outputs.loss is not None
    assert outputs.logits.shape == (8, 10)
    print("Memory-safe collation and structural forward pass verified.")

def test_trainer_remove_unused_columns_is_false():
    # Prove that the LEDGAR Trainer configuration correctly explicitly disables 
    # remove_unused_columns, which prevents KeyError: 'text' during collation.
    
    import ast
    with open("src/models/run_task019_experiments.py", "r") as f:
        tree = ast.parse(f.read())
        
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "TrainingConfig":
                for kw in node.keywords:
                    if kw.arg == "remove_unused_columns":
                        if getattr(kw.value, "value", getattr(kw.value, "id", None)) == False:
                            found = True
                            
    assert found, "TrainingConfig must be instantiated with remove_unused_columns=False to prevent KeyError: 'text'"
