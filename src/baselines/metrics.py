from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, hamming_loss
from typing import Dict, Any
import numpy as np

def calculate_metrics(y_true, y_pred, is_multilabel: bool = False) -> Dict[str, float]:
    """Calculates task-appropriate metrics."""
    metrics = {}
    
    if is_multilabel:
        metrics['micro_f1'] = float(f1_score(y_true, y_pred, average='micro', zero_division=0))
        metrics['macro_f1'] = float(f1_score(y_true, y_pred, average='macro', zero_division=0))
        metrics['hamming_loss'] = float(hamming_loss(y_true, y_pred))
    else:
        metrics['accuracy'] = float(accuracy_score(y_true, y_pred))
        metrics['macro_f1'] = float(f1_score(y_true, y_pred, average='macro', zero_division=0))
        metrics['macro_precision'] = float(precision_score(y_true, y_pred, average='macro', zero_division=0))
        metrics['macro_recall'] = float(recall_score(y_true, y_pred, average='macro', zero_division=0))
        metrics['weighted_f1'] = float(f1_score(y_true, y_pred, average='weighted', zero_division=0))
        
    return metrics
