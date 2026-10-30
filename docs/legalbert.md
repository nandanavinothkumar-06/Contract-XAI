# Legal-BERT Model Layer

## 1. What Legal-BERT is
Legal-BERT is a domain-adapted transformer model pre-trained exclusively on legal text, including legislation, court cases, and contracts. It provides stronger contextual representations for legal domain tasks than standard generic BERT models.

**Citation:**
> Chalkidis et al., 2020, "LEGAL-BERT: The Muppets straight out of Law School", Findings of EMNLP 2020.  
> Authoritative source: https://aclanthology.org/2020.findings-emnlp.261/  
> DOI: 10.18653/v1/2020.findings-emnlp.261

## 2. Checkpoint Identity
The standard configured checkpoint is `nlpaueb/legal-bert-base-uncased`.

## 3. Why Legal-BERT is Appropriate
Standard models (e.g., BERT-base) struggle with legal terminology, complex phrasing, and highly structured contractual syntax. Legal-BERT's vocabulary and pre-trained weights were derived directly from a vast corpora of legal documents, making its self-attention mechanism natively adapted to legal discourse.

## 4. What this Task Implements
TASK 008 introduces the sequence-classification wrapper for Legal-BERT. It provides a standardized integration interface allowing the ContractRisk-XAI framework to pass segmented clauses into the transformer and evaluate predictions against verified test datasets.

## 5. Dataset/Task Mappings
- **LEDGAR**: Multilabel legal-provision classification.
- **ContractNLI**: Multiclass NLI.
- **CUAD**: `NOT_APPLICABLE` (span-extraction is fundamentally inappropriate for sequence classification without heavy reconfiguration not meant for this baseline).
- **CLAUDETTE / Construction Datasets**: Remain tied to unresolved license or unavailable dataset statuses.

## 6. Tokenization
Tokenization relies exclusively on the checkpoint-native `AutoTokenizer`. Max length is strictly configurable (default `512`). 

## 7. Training Configuration
The Hugging Face Trainer receives explicitly separated dataset partitions. Leakage prevention is enforced by the pre-training three-way split and explicit group/text-hash leakage checks, not by Trainer itself. Configurations (e.g., `learning_rate`, `num_train_epochs`, `per_device_train_batch_size`) are exposed via `TrainingConfig`. These defaults are sensible starting parameters, not empirically validated optimal values.

## 8. Split Strategy
Splitting retains the `group_aware_split` methodology (or official dataset splits if available). The split isolates partitions as follows:
- **TRAIN**: Used for model fitting.
- **VALIDATION**: Used for model selection/configuration where applicable.
- **TEST**: Held out for final evaluation. (No test-set tuning allowed).

## 9. Leakage Prevention
Integrated directly with the leakage tracking from TASK 007 (`check_leakage`). Both group IDs (`source_document_id`) and exact text overlaps are verified across all three splits before training proceeds.

## 10. Multiclass vs Multilabel Handling
Configured via `classification_mode`:
- **Multiclass**: Applies softmax and uses `argmax` for inference.
- **Multilabel**: Applies sigmoid and thresholding (configurable `multilabel_threshold`, default `0.5`). 

## 11. Truncation Handling
Truncation flags are generated explicitly during tokenization. If a clause exceeds `max_sequence_length` (e.g. 512), `was_truncated = True` is logged in the prediction output to ensure no information loss goes unrecorded.

## 12. Reproducibility
Python, NumPy, PyTorch, and Transformers seeds are pinned deterministically prior to instantiation using `configure_deterministic_training`. 

## 13. Artifact Handling
Models and run metadata are safely stored in dedicated directories (e.g., `artifacts/models/legalbert`). Large neural weights are generated locally and not committed to source tracking.

## 14. Current Execution Status
The current codebase safely traps unavailable models (`MODEL_UNAVAILABLE`). If the checkpoint cannot be accessed or loaded, the software wrapper will gracefully fail without silently substituting generic models.

## 15. Known Limitations
Because the actual canonical legal datasets (e.g., LEDGAR, ContractNLI) were not officially acquired in TASK 003, no real benchmark training or fine-tuning was executed. 

## 16. Difference Between Literature Results and Project Results
To maintain absolute scientific clarity, baseline numbers are strictly categorized into one of three domains:
- **Project Experimental Results**: Actual experiments run on legitimate verified datasets within the project repository using the `LegalBertWrapper`. Currently: NONE.
- **Test Fixture Results**: Small deterministic synthetic tests used only to test the implementation architecture itself.
- **Published Literature Results**: Results reported by original authors in published papers (e.g., Chalkidis et al., 2020). These baseline benchmarks remain strictly within the references subsystem and are never falsely re-cast as experimental outputs of the ContractRisk-XAI system. Our project did not generate benchmark results for TASK 008.
