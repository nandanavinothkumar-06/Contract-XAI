from typing import Dict, Any, Optional
import logging
from src.models.legalbert import LegalBertWrapper
from src.models.config import TrainingConfig
from src.baselines.leakage import check_leakage
from src.baselines.splitting import group_aware_split
import pandas as pd

def configure_deterministic_training(seed: int):
    try:
        import torch
        import numpy as np
        import random
        import transformers
        
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        transformers.set_seed(seed)
    except ImportError:
        logging.warning("torch or transformers not found. Cannot set deterministic seed.")

def prepare_trainer(
    wrapper: LegalBertWrapper, 
    training_config: TrainingConfig, 
    train_dataset, 
    eval_dataset,
    output_dir: str
):
    if not wrapper.is_available():
        raise RuntimeError("MODEL_UNAVAILABLE")
        
    import transformers
    
    args = transformers.TrainingArguments(
        output_dir=output_dir,
        learning_rate=training_config.learning_rate,
        num_train_epochs=training_config.num_train_epochs,
        per_device_train_batch_size=training_config.per_device_train_batch_size,
        per_device_eval_batch_size=training_config.per_device_eval_batch_size,
        weight_decay=training_config.weight_decay,
        gradient_accumulation_steps=training_config.gradient_accumulation_steps,
        eval_strategy=training_config.evaluation_strategy,
        save_strategy=training_config.save_strategy,
        save_steps=training_config.save_steps,
        save_total_limit=training_config.save_total_limit,
        seed=wrapper.config.random_seed,
        fp16=training_config.fp16,
        dataloader_num_workers=training_config.dataloader_num_workers,
        dataloader_pin_memory=training_config.fp16, # pin memory when CUDA is used
        report_to=training_config.report_to,
        remove_unused_columns=training_config.remove_unused_columns
    )
    
    trainer = transformers.Trainer(
        model=wrapper.model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=wrapper.tokenizer_wrapper.tokenizer
    )
    
    return trainer

def check_legalbert_leakage(df: pd.DataFrame, text_col: str, label_col: str, group_col: str, seed: int):
    """Integrates with TASK 007 leakage checking."""
    train, val, test = group_aware_split(df, group_col, random_state=seed)
    has_leakage, leak_details = check_leakage(train, val, test, group_col, text_col)
    
    if has_leakage:
        raise ValueError(f"FAILED_LEAKAGE_CHECK: {leak_details}")
        
    return train, val, test
