from typing import Dict, Any, Optional
from pydantic import BaseModel

class LegalBertConfig(BaseModel):
    model_name: str = "legal-bert"
    model_family: str = "Legal-BERT"
    model_checkpoint: str = "nlpaueb/legal-bert-base-uncased"
    tokenizer_name: str = "nlpaueb/legal-bert-base-uncased"
    max_sequence_length: int = 512
    task_type: str = "CLASSIFICATION"
    classification_mode: str = "multiclass" # 'multiclass' or 'multilabel'
    multilabel_threshold: float = 0.5
    num_labels: int = 2
    random_seed: int = 42
    class_weight_strategy: str = "none" # 'none' or 'balanced'
    is_test_fixture: bool = False
    
class TrainingConfig(BaseModel):
    learning_rate: float = 2e-5
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 8
    per_device_eval_batch_size: int = 8
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    gradient_accumulation_steps: int = 1
    evaluation_strategy: str = "epoch"
    save_strategy: str = "steps"
    save_steps: int = 500
    save_total_limit: int = 2
    fp16: bool = False
    dataloader_num_workers: int = 0
    report_to: str = "none"
    remove_unused_columns: bool = True
