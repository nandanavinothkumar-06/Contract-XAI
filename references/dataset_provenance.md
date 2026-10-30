# Dataset Provenance for ContractRisk-XAI

## Why Provenance Matters
In legal AI, datasets must be fully traceable to ensure that models do not hallucinate legal authority and that intellectual property rights are respected. A unified dataset taxonomy that conflates disparate definitions of "risk" or obscures the original annotation source corrupts the scientific integrity of the system. We preserve the original task and label semantics of every dataset. Model-derived "risk-priority" scores are explicitly tracked separately from ground-truth labels.

## Dataset Classification

### A. PRIMARY EXPERIMENT DATASETS
These datasets have verified open access and permissive commercial licensing for the datasets themselves, making them foundational for ContractRisk-XAI.
- **CUAD**: Foundational for commercial clause extraction. (Dataset released under CC BY 4.0; underlying contract rights remain subject to the source/disclaimer conditions.)
- **LEDGAR**: Foundational for large-scale multi-label classification. (MIT via LexGLUE).
- **ContractNLI**: Foundational for evidence-grounded reasoning. (Dataset: CC BY 4.0; Baseline Implementation: Apache 2.0).

### B. SECONDARY / BENCHMARK DATASETS
These datasets are highly valuable for specific evaluations but carry restrictions.
- **CLAUDETTE**: License status is "Not explicitly verified from authoritative source." Commercial-use permission remains unverified. It provides crucial rationale data but requires unresolved licensing checks before commercial integration.

### C. RESTRICTED / PAPER-DESCRIBED DATASETS
These datasets are described in academic papers but lack an independently verified official public dataset download/repository.
- **Moon et al. (2022) Construction Specs**
- **Shuai (2023) Construction Risk**
- **Zhou dataset (2023 online / 2025 issue) Missing Clauses**
Their access status is "Unresolved / not independently verified." We will NOT fabricate synthetic substitutes for these datasets or speculate regarding the reasons for their unavailability.

### D. NOT APPROVED
Any dataset lacking an authoritative verification trail. None are currently listed.
