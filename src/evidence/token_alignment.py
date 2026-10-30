from typing import List, Tuple, Dict, Any
import logging

class TokenAligner:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        
    def align_tokens_to_source(self, source_text: str, max_length: int = 512) -> Tuple[str, List[Tuple[int, int]], bool]:
        """
        Tokenizes text and returns token-to-character offset mappings.
        Uses transformers fast tokenizer's `return_offsets_mapping`.
        Returns:
            status: "SUCCESS" or "FAILED"
            offsets: List of (start_char, end_char) for each token.
            truncated: boolean
        """
        if not self.tokenizer.is_fast:
            logging.warning("Tokenizer is not fast, offsets_mapping might fail.")
            return "FAILED", [], False
            
        try:
            encoding = self.tokenizer(
                source_text,
                max_length=max_length,
                truncation=True,
                return_offsets_mapping=True,
                add_special_tokens=True,
                return_tensors="pt"
            )
            
            offsets = encoding['offset_mapping'][0].tolist()
            
            num_special_tokens = self.tokenizer.num_special_tokens_to_add()
            raw_tokens = self.tokenizer.tokenize(source_text)
            truncated = (len(raw_tokens) + num_special_tokens) > max_length
            
            return "SUCCESS", offsets, truncated
        except Exception as e:
            logging.error(f"Failed to align tokens: {e}")
            return "FAILED", [], False
            
    def get_special_token_mask(self, source_text: str, max_length: int = 512) -> List[int]:
        encoding = self.tokenizer(
            source_text,
            max_length=max_length,
            truncation=True,
            return_special_tokens_mask=True,
            add_special_tokens=True,
            return_tensors="pt"
        )
        return encoding['special_tokens_mask'][0].tolist()
