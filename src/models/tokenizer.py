from typing import List, Dict, Any, Tuple
import logging

class LegalBertTokenizerWrapper:
    def __init__(self, checkpoint: str, max_length: int = 512):
        self.checkpoint = checkpoint
        self.max_length = max_length
        self.tokenizer = None
        try:
            import transformers
            self.tokenizer = transformers.AutoTokenizer.from_pretrained(checkpoint)
        except ImportError:
            logging.error("transformers library is missing")
        except Exception as e:
            logging.error(f"Failed to load tokenizer: {e}")
            
    def is_available(self) -> bool:
        return self.tokenizer is not None
        
    def encode(self, texts: List[str]) -> Tuple[Dict[str, Any], List[bool]]:
        """Encodes texts and returns tokenized output + truncation flags."""
        if not self.is_available():
            raise RuntimeError("MODEL_UNAVAILABLE")
            
        encodings = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt"
        )
        
        # Determine explicit truncation manually
        truncation_flags = []
        import transformers
        old_level = transformers.logging.get_verbosity()
        transformers.logging.set_verbosity_error()
        try:
            for text in texts:
                tokens = self.tokenizer.tokenize(text)
                num_special_tokens = self.tokenizer.num_special_tokens_to_add()
                truncation_flags.append(len(tokens) + num_special_tokens > self.max_length)
        finally:
            transformers.logging.set_verbosity(old_level)
            
        return encodings, truncation_flags
