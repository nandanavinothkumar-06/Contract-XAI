import math
from typing import List, Dict, Tuple
from src.abstention.schema import UncertaintySignals
from src.abstention.provenance import PredictionType, CalibrationStatus

def calculate_multiclass_signals(probabilities: List[float]) -> dict:
    if not probabilities:
        raise ValueError("Probabilities list cannot be empty.")
        
    if not all(math.isfinite(p) for p in probabilities):
        raise ValueError("Probabilities must be finite numbers.")
        
    if any(p < 0 or p > 1 for p in probabilities):
        raise ValueError("Probabilities must be within [0, 1].")
        
    total_prob = sum(probabilities)
    if not math.isclose(total_prob, 1.0, rel_tol=1e-5, abs_tol=1e-5):
        raise ValueError(f"Probabilities must sum to 1. Got {total_prob}")
        
    sorted_probs = sorted(probabilities, reverse=True)
    top_p = sorted_probs[0]
    second_p = sorted_probs[1] if len(sorted_probs) > 1 else 0.0
    
    margin = top_p - second_p
    
    # Shannon Entropy H(p) = -Σ p_i log(p_i)
    entropy = 0.0
    for p in probabilities:
        if p > 0:
            entropy -= p * math.log(p)
            
    return {
        "top_probability": top_p,
        "second_probability": second_p,
        "margin": margin,
        "entropy": entropy
    }

def calculate_multilabel_signals(probabilities: Dict[str, float], threshold: float, near_threshold_window: float = 0.05) -> dict:
    if not probabilities:
        raise ValueError("Probabilities dictionary cannot be empty.")
        
    near_threshold_labels = []
    
    for label, p in probabilities.items():
        if not math.isfinite(p):
            raise ValueError(f"Probability for {label} is not finite.")
        if p < 0 or p > 1:
            raise ValueError(f"Probability for {label} must be within [0, 1]. Got {p}")
            
        if abs(p - threshold) <= near_threshold_window:
            near_threshold_labels.append(label)
            
    return {
        "per_label_probabilities": probabilities,
        "near_threshold_labels": near_threshold_labels
    }
