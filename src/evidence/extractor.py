from typing import List, Dict, Any, Optional
import uuid
import logging
from src.evidence.schema import EvidenceResult, EvidenceSpan
from src.evidence.token_alignment import TokenAligner
from src.evidence.aggregation import aggregate_and_rank_evidence

class EvidenceExtractor:
    def __init__(self, legalbert_wrapper, method: str = "GradientXInput"):
        self.wrapper = legalbert_wrapper
        self.method = method
        self.aligner = None
        if self.wrapper and self.wrapper.is_available():
            self.aligner = TokenAligner(self.wrapper.tokenizer_wrapper.tokenizer)
            
    def is_available(self) -> bool:
        return self.wrapper is not None and self.wrapper.is_available() and self.aligner is not None

    def extract(
        self, 
        source_text: str, 
        target_label_id: int, 
        target_label_str: str,
        top_k: int = 3,
        document_id: Optional[str] = None,
        clause_id: Optional[str] = None,
        is_test_fixture: bool = False
    ) -> EvidenceResult:
        if not self.is_available():
            return EvidenceResult(
                evidence_spans=[],
                method=self.method,
                target_label=target_label_str,
                target_score=0.0,
                alignment_status="FAILED",
                is_test_fixture=is_test_fixture
            )
            
        import torch
        
        status, offsets, truncated = self.aligner.align_tokens_to_source(
            source_text, 
            max_length=self.wrapper.config.max_sequence_length
        )
        
        if status == "FAILED" or not offsets:
            return EvidenceResult(
                evidence_spans=[],
                method=self.method,
                target_label=target_label_str,
                target_score=0.0,
                alignment_status="FAILED",
                truncation_status=truncated,
                is_test_fixture=is_test_fixture
            )
            
        special_tokens_mask = self.aligner.get_special_token_mask(
            source_text, 
            max_length=self.wrapper.config.max_sequence_length
        )
        
        # Tokenize explicitly to compute gradients
        encodings = self.wrapper.tokenizer_wrapper.tokenizer(
            source_text,
            max_length=self.wrapper.config.max_sequence_length,
            truncation=True,
            padding=False,
            return_tensors="pt"
        )
        
        input_ids = encodings["input_ids"]
        attention_mask = encodings["attention_mask"]
        
        self.wrapper.model.eval()
        
        try:
            # We fetch embeddings directly
            embeddings = self.wrapper.model.get_input_embeddings()(input_ids)
            embeddings.retain_grad()
            
            outputs = self.wrapper.model(inputs_embeds=embeddings, attention_mask=attention_mask)
            logits = outputs.logits[0]
            
            if self.wrapper.config.classification_mode == "multilabel":
                probs = torch.sigmoid(logits)
                target_score = probs[target_label_id]
            else:
                probs = torch.softmax(logits, dim=-1)
                target_score = probs[target_label_id]
                
            # Compute gradient of target logit wrt embeddings
            target_logit = logits[target_label_id]
            
            self.wrapper.model.zero_grad()
            target_logit.backward()
            
            gradients = embeddings.grad[0] # (seq_len, hidden_size)
            input_embeds = embeddings[0] # (seq_len, hidden_size)
            
            # Gradient X Input attribution (dot product over hidden dim)
            attribution_scores = (gradients * input_embeds).sum(dim=-1).detach().cpu().numpy().tolist()
            
        except Exception as e:
            logging.error(f"Attribution failed: {e}")
            return EvidenceResult(
                evidence_spans=[],
                method=self.method,
                target_label=target_label_str,
                target_score=0.0,
                alignment_status="FAILED",
                truncation_status=truncated,
                is_test_fixture=is_test_fixture
            )
            
        spans = aggregate_and_rank_evidence(
            token_scores=attribution_scores,
            offsets=offsets,
            special_tokens_mask=special_tokens_mask,
            source_text=source_text,
            top_k=top_k,
            evidence_id_prefix=str(uuid.uuid4())[:8],
            document_id=document_id,
            clause_id=clause_id,
            method=self.method,
            prediction_label=target_label_str,
            prediction_score=target_score.item()
        )
        
        visible_end = offsets[-1][1] if offsets else -1
        
        return EvidenceResult(
            evidence_spans=spans,
            method=self.method,
            target_label=target_label_str,
            target_score=target_score.item(),
            truncation_status=truncated,
            alignment_status="SUCCESS",
            visible_source_start=0,
            visible_source_end=visible_end,
            is_test_fixture=is_test_fixture
        )
