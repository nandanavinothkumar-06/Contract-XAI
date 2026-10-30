import pytest
from src.models.config import LegalBertConfig, TrainingConfig
from src.models.legalbert import LegalBertWrapper
from src.models.tokenizer import LegalBertTokenizerWrapper
from src.models.model_metadata import save_model_metadata
from src.models.prediction import predict
from src.models.training import configure_deterministic_training
import os
import json

def test_legalbert_config_defaults():
    config = LegalBertConfig()
    assert config.model_checkpoint == "nlpaueb/legal-bert-base-uncased"
    assert config.max_sequence_length == 512
    assert config.task_type == "CLASSIFICATION"
    
def test_tokenizer_unavailable_handling():
    # Provide a clearly invalid checkpoint
    wrapper = LegalBertTokenizerWrapper(checkpoint="invalid/nonexistent-model")
    assert not wrapper.is_available()
    
    with pytest.raises(RuntimeError, match="MODEL_UNAVAILABLE"):
        wrapper.encode(["Test text"])
        
def test_model_unavailable_handling():
    config = LegalBertConfig(model_checkpoint="invalid/nonexistent-model", tokenizer_name="invalid/nonexistent-model")
    wrapper = LegalBertWrapper(config)
    assert not wrapper.is_available()
    
    with pytest.raises(RuntimeError, match="MODEL_UNAVAILABLE"):
        predict(wrapper, ["Test text"])
        
def test_metadata_serialization(tmp_path):
    config = LegalBertConfig(is_test_fixture=True, classification_mode="multilabel")
    tconfig = TrainingConfig()
    
    save_model_metadata(
        output_dir=str(tmp_path),
        model_config=config,
        dataset_name="TEST",
        split_strategy="group_aware",
        status="MODEL_UNAVAILABLE",
        run_id="test_run_123",
        label_to_id={"A": 0, "B": 1},
        training_config=tconfig,
        metrics={"macro_f1": 0.85}
    )
    
    filepath = os.path.join(tmp_path, "metadata.json")
    assert os.path.exists(filepath)
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["model_checkpoint"] == "nlpaueb/legal-bert-base-uncased"
    assert data["is_test_fixture"] is True
    assert data["status"] == "MODEL_UNAVAILABLE"
    assert data["metrics"]["macro_f1"] == 0.85
    assert "training_config" in data
    
def test_deterministic_training_does_not_crash():
    configure_deterministic_training(42)
    
def test_trainer_partition_isolation():
    from src.models.training import prepare_trainer
    config = LegalBertConfig(is_test_fixture=True)
    tconfig = TrainingConfig()
    wrapper = LegalBertWrapper(config)
    
    # Mocking unavailable to avoid downloading weights
    wrapper.model = "mock_model"
    wrapper.tokenizer_wrapper.tokenizer = "mock_tokenizer"
    
    train_dataset = ["train_item"]
    eval_dataset = ["val_item"]
    
    # Mock transformers module
    import sys
    from unittest.mock import MagicMock
    mock_transformers = MagicMock()
    mock_transformers.TrainingArguments = MagicMock()
    
    class MockTrainer:
        def __init__(self, model, args, train_dataset, eval_dataset, **kwargs):
            self.model = model
            self.args = args
            self.train_dataset = train_dataset
            self.eval_dataset = eval_dataset
            self.tokenizer = kwargs.get('processing_class', kwargs.get('tokenizer'))
            
    mock_transformers.Trainer = MockTrainer
    sys.modules['transformers'] = mock_transformers
    
    try:
        from src.models.training import prepare_trainer
        trainer = prepare_trainer(
            wrapper,
            tconfig,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            output_dir="tmp_test_dir"
        )
        
        assert trainer.train_dataset == train_dataset
        assert trainer.eval_dataset == eval_dataset
        assert "train_item" in trainer.train_dataset
        assert "val_item" not in trainer.train_dataset
        assert "val_item" in trainer.eval_dataset
        assert "train_item" not in trainer.eval_dataset
        assert "test_item" not in trainer.train_dataset
        assert "test_item" not in trainer.eval_dataset
    finally:
        del sys.modules['transformers']
    

