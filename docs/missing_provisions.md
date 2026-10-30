# Missing-Provision Detection

## 1. Purpose
The Missing-Provision Detection module analyzes input contract texts to determine the presence or potential absence of legally relevant clauses, driven strictly by deterministic, verifiable configurations defined in a reference taxonomy. 

**Disclaimer**: Potentially missing provision according to the selected reference taxonomy. This is an informational document analysis artifact. It does NOT assert that the contract is legally incomplete, violates the law, or must be amended. Requires human/legal review. 

## 2. Scope
Operates strictly downstream from TASK 006 (Segmentation) and TASK 012 (Semantic Retrieval). Fuses lexical string patterns, semantic vector distances, and configuration topologies (negation bounds) to produce hybrid evidence confidence blocks.

## 3. Provision Taxonomy
Evaluations parse against `ReferenceProvisionTaxonomy` schema bounds. Every element specifies:
- `domain`: commercial, employment, etc.
- `detection_terms`: lexical patterns mapping local string matches
- `semantic_description`: base string mapped vectorially via `sentence-transformers`.
- `required_status`: REQUIRED_BY_REFERENCE, OPTIONAL_REFERENCE_ITEM, etc.

## 4. Provenance
Legal requirement statuses originate exclusively from `TaxonomyProvenance` specifying textual reference origins (e.g., standard boilerplate references). No model weights arbitrarily dictate a mandatory legal requirement globally absent explicit reference loading. 

## 5. Detection Architecture
Segments funnel symmetrically into dual execution layers:
1. `ProvisionMatcher` scanning for lexical `detection_terms`.
2. `SemanticRetriever` querying FAISS dense vector spaces mapped over identical segment coordinates. 
Results aggregate sequentially mapping identical IDs into single confidence arrays. 

## 6. Lexical Matching
Exact-string evaluations parsing lowercased textual segment chunks against taxonomy criteria. Evaluates localized windows (e.g. ±50 characters) evaluating auxiliary boundaries natively.

## 7. Semantic Matching
Retrieves TASK 012 indices utilizing query strings derived from taxonomy `semantic_description`. Maps returned distance measurements identically. 

## 8. Hybrid Matching
Detection bounds dynamically shift natively if identical ID blocks report both semantic density collisions and precise textual phrase mapping. Output tags structurally record `HYBRID`. 

## 9. Negation
Scans trailing/leading term neighborhoods mapping exclusionary vocabularies (e.g. "not", "without", "prohibited"). When triggered beneath a `CONSERVATIVE` configuration bounding rule, explicit matches degrade their assertion cleanly to `UNCERTAIN` rather than false-positive satisfaction (`FOUND`). 

## 10. Conditional Language
Operates identically parsing contingent conditionals (e.g. "if applicable", "subject to"). Shifts final boolean confidence into `UNCERTAIN` preventing unconditional acceptance of contingent obligations natively.

## 11. Cross-Clause Evidence
Target requirements commonly distribute dynamically across separated segment boundaries. Evidence pipelines aggregate arrays of `ProvisionEvidence`, each matching individual segment geometries comprehensively. 

## 12. Cross-Reference Handling
Supported deterministically if upstream taxonomy mappings dictate explicitly. 

## 13. Partition Isolation
Evaluations structurally preserve TASK 012 `partition` parameters dynamically guaranteeing validation/test vectors are cleanly prohibited from utilizing training extraction arrays as candidate evidence baselines. 

## 14. Same-Document Requirement
Candidates natively bounding positive mappings must originate from identical `source_document_id`s relative to the extraction query dynamically. Global cross-document arrays provide structural referential similarity matrices but NOT deterministic local proof of inclusion. 

## 15. Status Definitions
- `FOUND`: Sufficient deterministic matching logic triggered.
- `POTENTIALLY_MISSING`: No sufficiently strong matching evidence was found under the selected taxonomy/configuration. 
- `UNCERTAIN`: Conflicting/contingent vocabulary bounded matches cleanly prompting review.
- `NOT_ASSESSED`: Configuration bounds blocked execution dynamically. 

## 16. Threshold Configuration
Values for `lexical_threshold` or `semantic_threshold` act explicitly as internal programmatic engineering defaults natively. They have not been empirically validated as legal decision thresholds universally. 

## 17. Limitations
- Absence of a match is not proof of legal absence.
- Taxonomy completeness is not guaranteed.
- Semantic embeddings may miss domain-specific terminology natively.
- Lexical matching may produce false positives.
- Conditional and negated language can be difficult.
- Legal obligations depend on jurisdiction, contract type, facts, and applicable law natively. 
- Reference taxonomy quality directly affects detection quality.
- No legal conclusion is produced dynamically.

## 18. Dataset Status
- **LEDGAR**: NOT_RUN_DATA_UNAVAILABLE
- **ContractNLI**: NOT_RUN_DATA_UNAVAILABLE
- **CUAD**: NOT_APPLICABLE 
- **CLAUDETTE**: NOT_RUN_LICENSE_UNRESOLVED
- **Construction Data**: NOT_RUN_DATA_UNAVAILABLE

## 19. Project Experimental-Result Status
**PROJECT EXPERIMENTAL RESULTS: NONE**
Execution explicitly mapped isolated synthetically generated test fixture configurations natively verifying module architectures independently without legitimate legal baselines structurally.
