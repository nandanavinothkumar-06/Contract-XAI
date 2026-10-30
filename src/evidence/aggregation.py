from typing import List, Tuple
from src.evidence.schema import EvidenceSpan

def aggregate_and_rank_evidence(
    token_scores: List[float],
    offsets: List[Tuple[int, int]],
    special_tokens_mask: List[int],
    source_text: str,
    top_k: int = 3,
    evidence_id_prefix: str = "ev",
    document_id: str = None,
    clause_id: str = None,
    method: str = "InputXGradient",
    prediction_label: str = "UNKNOWN",
    prediction_score: float = 0.0
) -> List[EvidenceSpan]:
    """
    Aggregates adjacent/overlapping high-scoring tokens into contiguous spans.
    Tokens that are special tokens (mask=1) are ignored.
    """
    if len(token_scores) != len(offsets) or len(token_scores) != len(special_tokens_mask):
        raise ValueError("Mismatched token lengths.")
        
    # Calculate ranking score as absolute value of attribution
    # scored_tokens will hold: (i, start, end, raw_score, ranking_score)
    scored_tokens = []
    for i, (score, offset, is_special) in enumerate(zip(token_scores, offsets, special_tokens_mask)):
        if is_special:
            continue
        start, end = offset
        if start == end: # padding or empty
            continue
        scored_tokens.append((i, start, end, score, abs(score)))
        
    # Sort by ranking score descending
    scored_tokens.sort(key=lambda x: x[4], reverse=True)
    
    # We select roughly top_k tokens
    # Select tokens that have non-zero ranking score
    positive_tokens = [t for t in scored_tokens if t[4] > 0]
    
    if not positive_tokens:
        return []
        
    num_to_take = max(min(len(positive_tokens), top_k), 1)
    selected = positive_tokens[:num_to_take]
    
    # Sort selected tokens back by position for merging
    selected.sort(key=lambda x: x[1])
    
    merged_spans = []
    if not selected:
        return []
        
    current_span = [selected[0]]
    
    for i in range(1, len(selected)):
        prev_tok = current_span[-1]
        curr_tok = selected[i]
        
        # Merge if they are adjacent characters (or within 2 chars to handle spaces)
        if curr_tok[1] <= prev_tok[2] + 2:
            current_span.append(curr_tok)
        else:
            merged_spans.append(current_span)
            current_span = [curr_tok]
            
    if current_span:
        merged_spans.append(current_span)
        
    # Build EvidenceSpan objects
    results = []
    for i, span_group in enumerate(merged_spans):
        start_char = span_group[0][1]
        end_char = span_group[-1][2]
        
        start_tok = span_group[0][0]
        end_tok = span_group[-1][0]
        
        avg_raw_score = sum(t[3] for t in span_group) / len(span_group)
        avg_ranking_score = sum(t[4] for t in span_group) / len(span_group)
        extracted_text = source_text[start_char:end_char]
        
        results.append({
            "start": start_char,
            "end": end_char,
            "t_start": start_tok,
            "t_end": end_tok,
            "raw_score": avg_raw_score,
            "ranking_score": avg_ranking_score,
            "text": extracted_text
        })
        
    results.sort(key=lambda x: x["ranking_score"], reverse=True)
    results = results[:top_k]
    
    final_spans = []
    for i, res in enumerate(results):
        span = EvidenceSpan(
            evidence_id=f"{evidence_id_prefix}_{i}",
            document_id=document_id,
            clause_id=clause_id,
            source_start=res["start"],
            source_end=res["end"],
            text=res["text"],
            token_start=res["t_start"],
            token_end=res["t_end"],
            raw_score=float(res["raw_score"]),
            ranking_score=float(res["ranking_score"]),
            rank=i+1,
            method=method,
            prediction_label=prediction_label,
            prediction_score=prediction_score,
            evidence_type="MODEL_DERIVED_EVIDENCE",
            is_ground_truth=False,
            is_model_derived=True
        )
        final_spans.append(span)
        
    return final_spans
