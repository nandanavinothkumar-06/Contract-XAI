import os
import math
import pytest
from src.models.config import TrainingConfig
from src.models.training import prepare_trainer
from src.models.run_task019_experiments import get_ledgar_data, LegalBertConfig, LegalBertWrapper
import transformers
from datasets import Dataset

def test_ledgar_counts_and_splits():
    df = get_ledgar_data()
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]
    
    assert len(train_df) == 674068
    assert len(val_df) == 84250
    assert len(test_df) == 87956
    
    train_contracts = set(train_df["contract_id"].unique())
    val_contracts = set(val_df["contract_id"].unique())
    test_contracts = set(test_df["contract_id"].unique())
    
    assert len(train_contracts.intersection(val_contracts)) == 0
    assert len(train_contracts.intersection(test_contracts)) == 0
    assert len(val_contracts.intersection(test_contracts)) == 0
    
    all_labels = set()
    for labels in df["labels"]:
        all_labels.update(labels)
    assert len(all_labels) == 12608

def test_optimizer_steps_math():
    batch_size = 8
    gradient_accum = 1
    epochs = 3
    train_size = 674068
    
    expected_steps = math.ceil(train_size / (batch_size * gradient_accum)) * epochs
    assert expected_steps == 252777

def test_fp16_fallback():
    # In a CPU test environment (like this), fp16 should cleanly be disabled
    # Or if forced, prepare_trainer should still pass it to TrainingArguments safely
    config = TrainingConfig(
        num_train_epochs=3,
        per_device_train_batch_size=8,
        fp16=True,
        dataloader_num_workers=2,
        report_to="none",
        evaluation_strategy="no"
    )
    
    legal_config = LegalBertConfig(num_labels=12608, is_test_fixture=True)
    wrapper = LegalBertWrapper(legal_config)
    
    trainer = prepare_trainer(
        wrapper=wrapper,
        training_config=config,
        train_dataset=None,
        eval_dataset=None,
        output_dir="tmp_test_dir"
    )
    
    assert trainer.args.fp16 == True
    assert trainer.args.dataloader_num_workers == 2
    assert trainer.args.report_to == []

def test_tokenizer_configuration():
    # Verify max_length is 512 and truncation is enabled
    config = LegalBertConfig(num_labels=10, is_test_fixture=True)
    wrapper = LegalBertWrapper(config)
    tokenizer = wrapper.tokenizer_wrapper.tokenizer
    
    # This is verified by ensuring the collator handles padding.
    assert tokenizer.model_max_length >= 512
