# Task 019 Correction Log

## Date & Time
**Timestamp:** 2026-09-14T14:15:00Z

## Discovered Error
1. **Label Misconfiguration Risk (`IndexError: Target 3 is out of bounds`)**: The previous unvalidated implementation posed a risk where labels mapping to indices $\ge 3$ or resulting in `NaN` could crash the trainer and violate the fixed label output cardinality required for ContractNLI.
2. **Tokenizer Truncation Warning**: `sequence length 1763 > 512` warning exposed that manual truncation counting tokenized the full text without limits, spamming execution logs and suggesting inputs were overreaching the model's absolute maximum position embeddings.

## Root Cause
- The explicit validation of `EXPECTED_LABELS` and output shapes was absent before handing data to the Hugging Face `Trainer`.
- The manual truncation tracker `self.tokenizer.tokenize(text)` ignored `truncation=True` during tracking, artificially parsing thousands of tokens and raising warnings, despite the formal data loaders enforcing strict bounds.

## Correction
1. **Tokenizer Truncation Check**: Updated `src/models/tokenizer.py` to suppress standard token limit warnings strictly during manual counting by wrapping the logic in an internal logger override, ensuring actual pipeline extraction still formally applies `truncation=True` under the 512-token limit.
2. **Hard Validations**: Inserted strict dataset assertions in `src/models/run_task019_experiments.py` checking that every processed label explicitly matches `{"Contradiction", "Entailment", "NotMentioned"}` with integer IDs `[0, 1, 2]`. 
3. **Leakage Validations**: Added set intersection assertions to strictly enforce empty overlap across Train, Validation, and Test document IDs.
4. **Sanity Check Routine**: Injected a 2-batch single forward-and-backward propagation explicitly checking that output `logits.shape == (2, 3)` and no indexing exceptions happen.

## Sanity-Check Result
- **TASK019_CONTRACTNLI_SANITY_CHECK:** PASS 
*(No IndexErrors, Shape matches 3 logits, Gradient successfully propagates)*

## Corrected Feasibility Pilot
- **Metric:** 5 training steps completed successfully without bounds issues.
- **Average Step Time:** 17.78 seconds.
- **ContractNLI Projected Time:** ~13.32 hours for full training.

## Final Feasibility Decision
- **ContractNLI:** NOT_RUN_RESOURCE_LIMITATION
- **LEDGAR:** NOT_RUN_RESOURCE_LIMITATION 
- **CUAD:** NOT_APPLICABLE_TASK_MISMATCH

## Affected Previous Artifacts
Any unvalidated numbers or assertions from past tasks prior to this log are officially **INVALIDATED_CONFIGURATION**. The pipeline generated in this session completely supersedes all prior Task 019 states.

## Validation Performed
The internal test `tests/test_baselines_experiments.py` verified architecture constraints.
The corrected pilot correctly handled label sets, sequence embeddings, and serialized exact metrics.
