from typing import Dict, Any, List, Optional
from src.models.config import LegalBertConfig
from src.models.tokenizer import LegalBertTokenizerWrapper
import logging

class LegalBertWrapper:
    def __init__(self, config: LegalBertConfig):
        self.config = config
        self.tokenizer_wrapper = LegalBertTokenizerWrapper(
            config.tokenizer_name, 
            config.max_sequence_length
        )
        self.model = None
        
        if self.tokenizer_wrapper.is_available():
            try:
                import transformers
                import torch
                
                # Check for multiclass vs multilabel setup if needed for specific loss logic
                problem_type = "multi_label_classification" if config.classification_mode == "multilabel" else "single_label_classification"
                
                self.model = transformers.AutoModelForSequenceClassification.from_pretrained(
                    config.model_checkpoint,
                    num_labels=config.num_labels,
                    problem_type=problem_type
                )
            except Exception as e:
                logging.error(f"Failed to load model checkpoint: {e}")
                self.model = None
                
    def is_available(self) -> bool:
        return self.model is not None and self.tokenizer_wrapper.is_available()
