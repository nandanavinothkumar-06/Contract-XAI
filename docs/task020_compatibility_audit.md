# Task 020 Compatibility Audit

## 1. Task 020 Objective
Investigate whether the project's NLP framework can support legitimate cross-domain evaluation using the existing acquired datasets.

## 2. Available Datasets
The project currently has genuinely acquired and validated the following:
- **ContractNLI**
- **LEDGAR**
- **CUAD**

Construction datasets and CLAUDETTE have not been acquired due to strict rules surrounding unresolved license statuses and lack of verified data sources.

## 3. Native Task Matrix

| Dataset | Native Task | Input | Output | Labels | Domain |
|---------|-------------|-------|--------|--------|--------|
| **ContractNLI** | Document-level NLI | Hypothesis + Contract Text | Classification Label | 3 (Contradiction, Entailment, NotMentioned) | NDAs |
| **LEDGAR** | Multi-label provision classification | Provision text | List of provision topics | 12,608 provision classes | SEC contractual provisions |
| **CUAD** | Extractive QA / Span extraction | Question + Contract text | Answer spans | 41 Categories | Commercial contracts |

## 4. Domain Metadata Matrix
- **ContractNLI**: NDAs
- **LEDGAR**: SEC contractual provisions
- **CUAD**: Commercial contracts
- **Construction**: NOT_ACQUIRED
- **CLAUDETTE**: NOT_ACQUIRED

## 5. Pairwise Compatibility Matrix
- **ContractNLI ↔ LEDGAR**: `INVALID`
  - *Reason*: Fundamentally different supervised task and label semantics. ContractNLI is a 3-class NLI entailment task over full documents. LEDGAR is a 12,608-class multi-label classification task over individual provisions. There is no common label space or target overlap.
- **ContractNLI ↔ CUAD**: `NOT_APPLICABLE`
  - *Reason*: Task mismatch. CUAD requires a span-extraction/extractive-QA pipeline which is unsupported by the current sequence classification models implemented in `src/models`.
- **LEDGAR ↔ CUAD**: `NOT_APPLICABLE`
  - *Reason*: Same as above; CUAD's task formulation requires Extractive QA, rendering it strictly incompatible with multi-label sequence classification architectures.

## 6. Invalid Experiment Combinations
- ContractNLI → LEDGAR
- LEDGAR → ContractNLI

## 7. Potentially Valid Experiments
None. No two datasets within the current repository share a compatible input structure, task objective, and label space.

## 8. Construction-Domain Availability
**CONSTRUCTION_CROSS_DOMAIN**: `NOT_RUN_DATA_UNAVAILABLE`
- *Reason*: Construction-domain cross-domain evaluation cannot be performed because no verified construction dataset is currently acquired within the project.

## 9. CLAUDETTE Availability
**CLAUDETTE**: `NOT_RUN_ACCESS_UNRESOLVED`
- *Reason*: Access and license status remain unresolved.

## 10. CUAD Compatibility
**CUAD**: `NOT_APPLICABLE_TASK_MISMATCH`
- *Reason*: Task mismatch (Extractive QA vs Classification).

## 11. Resource Constraints
- **ContractNLI / LEDGAR**: Full baseline Legal-BERT training runs have already proven to be `NOT_RUN_RESOURCE_LIMITATION` on the current CPU hardware, independent of cross-domain design validity.

## 12. Leakage Considerations
- If an experiment were valid, strict enforcement via `document_id` and `contract_id` string matching across all splits would be required. However, because no experiment is valid, no empirical leakage occurred.

## 13. Recommended Valid Experiment Matrix
- **None.**

## 14. Explicit Experiments That Must NOT Be Run
- Any mapping forcing ContractNLI's 3 NLI labels onto LEDGAR's 12,608 provision categories.
- Forcing CUAD into an artificial text-classification benchmark.

## 15. Final Recommendation
**NO_VALID_CROSS_DOMAIN_EXPERIMENT_AVAILABLE_WITH_CURRENT_DATA**
There is no unified "legal" abstraction across the acquired corpus. Each dataset encodes disjoint semantics and varying NLP paradigms. Manufacturing artificial cross-dataset alignments would fundamentally violate scientific integrity.
