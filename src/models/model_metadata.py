import json
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from src.models.config import LegalBertConfig, TrainingConfig

def save_model_metadata(
    output_dir: str,
    model_config: LegalBertConfig,
    dataset_name: str,
    split_strategy: str,
    status: str,
    run_id: str,
    label_to_id: Dict[str, int],
    training_config: Optional[TrainingConfig] = None,
    metrics: Optional[Dict[str, float]] = None
):
    os.makedirs(output_dir, exist_ok=True)
    
    id_to_label = {str(v): k for k, v in label_to_id.items()}
    
    metadata = {
        "model_family": model_config.model_family,
        "model_checkpoint": model_config.model_checkpoint,
        "task_type": model_config.task_type,
        "dataset": dataset_name,
        "split_strategy": split_strategy,
        "max_sequence_length": model_config.max_sequence_length,
        "random_seed": model_config.random_seed,
        "status": status,
        "is_test_fixture": model_config.is_test_fixture,
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "label_mapping": {
            "label_to_id": label_to_id,
            "id_to_label": id_to_label
        },
        "classification_mode": model_config.classification_mode,
        "multilabel_threshold": model_config.multilabel_threshold,
    }
    
    if training_config:
        metadata["training_config"] = training_config.model_dump()
        
    if metrics:
        metadata["metrics"] = metrics
        
    filepath = os.path.join(output_dir, "metadata.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
