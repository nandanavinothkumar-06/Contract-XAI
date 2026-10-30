from typing import List, Tuple
from src.models.legalbert import LegalBertWrapper

def predict(wrapper: LegalBertWrapper, texts: List[str]):
    if not wrapper.is_available():
        raise RuntimeError("MODEL_UNAVAILABLE")
        
    import torch
        
    encodings, truncations = wrapper.tokenizer_wrapper.encode(texts)
    
    wrapper.model.eval()
    with torch.no_grad():
        outputs = wrapper.model(**encodings)
        logits = outputs.logits
        
    if wrapper.config.classification_mode == "multilabel":
        probs = torch.sigmoid(logits)
        preds = (probs > wrapper.config.multilabel_threshold).int()
    else:
        probs = torch.softmax(logits, dim=-1)
        preds = torch.argmax(logits, dim=-1)
        
    return preds.cpu().numpy(), probs.cpu().numpy(), truncations
