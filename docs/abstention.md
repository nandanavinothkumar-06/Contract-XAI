# Abstention and Uncertainty Handling

## 1. Purpose
The Abstention and Uncertainty Handling module implements an explicit uncertainty layer for ContractRisk-XAI. Its purpose is to evaluate raw model outputs (logits, probabilities, similarities) and decide whether the system has sufficient configured evidence and confidence to make a substantive prediction.

## 2. Why Abstention is Needed
Models inevitably encounter ambiguous clauses, unseen variations, or inputs outside their training distribution. Rather than forcing a prediction that may be unreliable, the system must recognize when to abstain. This ensures that uncertain cases are explicitly flagged for human review.

## 3. Confidence vs Uncertainty
> [!IMPORTANT]
> The term **CONFIDENCE** in this module refers strictly to **MODEL-DERIVED CONFIDENCE**, not "legal confidence" or "guaranteed correctness". Similarly, **UNCERTAINTY** means **MODEL-DERIVED UNCERTAINTY**, not "legal uncertainty".

Model probability is a derived score, not an absolute guarantee. A probability of 0.9999 does not mean "99.99% probability the legal decision is correct." It is merely a statistical signal.

## 4. Multiclass Signals
For multiclass models, the following signals are extracted from the normalized probability distribution:
- **Top Probability**: The highest probability score among all classes.
- **Second Probability**: The second-highest probability score.
- **Margin**: The difference between the top probability and the second probability.
- **Entropy**: The Shannon entropy of the distribution, $H(p) = -\sum p_i \log(p_i)$.

## 5. Multilabel Signals
For multilabel models, each label's probability is evaluated independently against a configurable decision threshold. 
- **Per-Label Probabilities**: Maintained explicitly for each possible label.
- **Near-Threshold Labels**: Labels whose probability falls within a defined `near_threshold_window` distance from the decision threshold, indicating ambiguity.

## 6. Entropy
Entropy measures the overall dispersion of probabilities. High entropy suggests the model is highly uncertain and distributing its confidence across multiple outcomes. 

## 7. Margin
Margin measures the "separation" of the model's top choice from its second choice. A low margin indicates prediction ambiguity (competing predictions), while a high margin suggests clear separation. **High margin does NOT equal legally correct.**

## 8. Thresholds
All abstention thresholds are configurable via `AbstentionConfig`. Examples include `confidence_accept_threshold`, `margin_threshold`, and `entropy_threshold`.

> [!WARNING]
> By default, these thresholds are **ENGINEERING DEFAULTS** and are **NOT EMPIRICALLY CALIBRATED**. They are provided for software validation, not optimized for real legal precision.

## 9. Calibration
The module explicitly tracks `calibration_status` (e.g., `NOT_CALIBRATED`, `CALIBRATED`). The system does not silently perform calibration and defaults to `NOT_CALIBRATED`.

## 10. Evidence
The abstention layer integrates evidence availability. If a policy requires evidence (`require_evidence = True`) and none is provided, the policy abstains. No evidence quality scores are fabricated.

## 11. Truncation
If `input_truncated` or `context_incomplete` is True, the system may `ABSTAIN` or flag as `REVIEW_REQUIRED` according to the `truncation_policy`. It does not automatically label the underlying clause as risky due to truncation.

## 12. Retrieval
Semantic and legal-source retrieval signals are tracked (`retrieval_available`, `retrieval_top_score`). High similarity does not equate to high legal confidence. 

## 13. Abstention States
- **ACCEPT**: The configured policy permits the system's prediction to proceed.
- **REVIEW_REQUIRED**: The model produced a substantive output, but uncertainty/evidence conditions require human review. (e.g. "HUMAN REVIEW REQUIRED")
- **ABSTAIN**: The system intentionally withholds a substantive prediction ("ABSTAINED FROM PREDICTION").
- **NOT_ASSESSED**: Required model/input/configuration information was unavailable or invalid.

## 14. Reason Codes
Decision outcomes are paired with explicit reason codes, such as `HIGH_UNCERTAINTY`, `LOW_MARGIN`, `HIGH_ENTROPY`, `TRUNCATED_INPUT`, `INVALID_INPUT`, and `CALIBRATION_UNAVAILABLE`.

## 15. Provenance
Every `AbstentionDecision` explicitly identifies `prediction_id`, `model_id`, `model_version`, and `policy_version`. 

## 16. Engineering Defaults
Configurable defaults are provided purely as **ENGINEERING DEFAULTS** for testing purposes. They are not empirically validated, optimal, scientifically established, or legally meaningful.

## 17. Limitations
The abstention policy relies purely on statistical thresholds and metadata flags. It has no understanding of actual legal nuance or semantic correctness.

## 18. Legal-Safety Boundaries
> [!CAUTION]
> The abstention layer evaluates **software safety conditions**. It must never generate conclusions such as "illegal", "invalid", "unenforceable", "non-compliant", "legally safe", or "violates statute". 
It only determines `ACCEPT`, `REVIEW_REQUIRED`, `ABSTAIN`, or `NOT_ASSESSED` relative to the configured evidence policy.

## 19. Dataset Status
- LEDGAR: NOT_RUN_DATA_UNAVAILABLE
- ContractNLI: NOT_RUN_DATA_UNAVAILABLE
- CUAD: NOT_APPLICABLE
- CLAUDETTE: NOT_RUN_LICENSE_UNRESOLVED
- Construction: NOT_RUN_DATA_UNAVAILABLE

## 20. Experimental-Result Status
**PROJECT EXPERIMENTAL RESULTS: NONE**
Synthetic tests are for **SOFTWARE VALIDATION**, not **MODEL PERFORMANCE**. No real legal benchmark results have been produced.
