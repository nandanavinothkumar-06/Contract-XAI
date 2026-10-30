import uuid
from typing import List, Dict, Optional
from src.missing_provisions.schema import (
    MissingProvisionAssessment, ProvisionDefinition, ProvisionStatus,
    ProvisionEvidence, ProvisionReference, DetectionMetadata, DetectionMethod
)
from src.missing_provisions.config import MissingProvisionConfig
from src.missing_provisions.matching import ProvisionMatcher
from src.segmentation.schema import Segment
from src.retrieval.retriever import SemanticRetriever
from src.retrieval.schema import RetrievalQuery

class MissingProvisionDetector:
    def __init__(self, config: MissingProvisionConfig, retriever: Optional[SemanticRetriever] = None):
        self.config = config
        self.retriever = retriever
        self.matcher = ProvisionMatcher()

    def assess_provision(
        self, 
        document_segments: List[Segment], 
        provision: ProvisionDefinition,
        partition: str,
        source_document_id: str,
        is_test_fixture: bool = False
    ) -> MissingProvisionAssessment:
        
        # 1. Lexical Matching
        lexical_evidence_map: Dict[str, ProvisionEvidence] = {}
        for seg in document_segments:
            lexical_matches = self.matcher.find_lexical_matches(seg, provision)
            if lexical_matches:
                lexical_evidence_map[seg.segment_id] = ProvisionEvidence(
                    clause_id=seg.segment_id,
                    source_document_id=seg.source_document_id,
                    text=seg.text,
                    source_start=seg.original_start,
                    source_end=seg.original_end,
                    lexical_matches=lexical_matches
                )
                
        # 2. Semantic Matching
        semantic_evidence_map: Dict[str, ProvisionEvidence] = {}
        if self.retriever:
            is_avail = self.retriever.index.is_available() if hasattr(self.retriever.index, 'is_available') else True
            if is_avail:
                # Create a synthetic query representing the provision
                try:
                    query = RetrievalQuery(
                        query_clause_id=f"query_{provision.provision_id}",
                        query_source_document_id=source_document_id, # Ensure same-doc logic is followed if enabled
                        query_text=provision.semantic_description,
                        partition=partition
                    )
                    
                    # Temporarily override retriever same_document config to match detector's requirement
                    orig_same_doc = self.retriever.config.same_document_only
                    self.retriever.config.same_document_only = self.config.same_document_only
                    
                    retrieval_results = self.retriever.retrieve(query)
                    
                    # Restore
                    self.retriever.config.same_document_only = orig_same_doc
                    
                    for res in retrieval_results:
                        if res.similarity_score >= self.config.semantic_threshold:
                            if res.result_clause_id not in semantic_evidence_map:
                                semantic_evidence_map[res.result_clause_id] = ProvisionEvidence(
                                    clause_id=res.result_clause_id,
                                    source_document_id=res.source_document_id,
                                    text=res.result_text,
                                    source_start=res.source_start,
                                    source_end=res.source_end,
                                    similarity_score=res.similarity_score
                                )
                except Exception as e:
                    pass # If retrieval fails (e.g. index empty or blocked partition), we continue with lexical

        # 3. Evidence Fusion
        final_evidence_map: Dict[str, ProvisionEvidence] = {}
        for cid, ev in lexical_evidence_map.items():
            final_evidence_map[cid] = ev
            if cid in semantic_evidence_map:
                final_evidence_map[cid].similarity_score = semantic_evidence_map[cid].similarity_score
                
        for cid, ev in semantic_evidence_map.items():
            if cid not in final_evidence_map:
                final_evidence_map[cid] = ev

        evidence_list = list(final_evidence_map.values())
        
        # 4. Status Determination
        status = ProvisionStatus.POTENTIALLY_MISSING
        reason = "No sufficiently matching provision was identified under the selected reference taxonomy and detection configuration."
        method = DetectionMethod.NOT_ASSESSED
        
        has_lexical = len(lexical_evidence_map) > 0
        has_semantic = len(semantic_evidence_map) > 0
        
        if has_lexical and has_semantic:
            method = DetectionMethod.HYBRID
        elif has_lexical:
            method = DetectionMethod.LEXICAL
        elif has_semantic:
            method = DetectionMethod.SEMANTIC
            
        uncertain = False
        
        if evidence_list:
            # Check negation and conditions
            for ev in evidence_list:
                for match in ev.lexical_matches:
                    if match.has_negation and self.config.negation_policy == "CONSERVATIVE":
                        uncertain = True
                    if match.has_conditional and self.config.conditional_policy == "CONSERVATIVE":
                        uncertain = True
            
            if uncertain:
                status = ProvisionStatus.UNCERTAIN
                reason = "Matching evidence found but contained negation or conditional language requiring human review."
            else:
                status = ProvisionStatus.FOUND
                reason = "Sufficient evidence found."
        
        return MissingProvisionAssessment(
            assessment_id=str(uuid.uuid4()),
            source_document_id=source_document_id,
            provision_id=provision.provision_id,
            provision_name=provision.name,
            domain=self.config.domain,
            status=status,
            reason=reason,
            matching_clause_ids=list(final_evidence_map.keys()),
            evidence=evidence_list,
            reference_provenance=ProvisionReference(
                provision_id=provision.provision_id,
                name=provision.name,
                provenance=provision.provenance
            ),
            metadata=DetectionMetadata(
                detection_method=method,
                configuration_version=self.config.configuration_version,
                is_test_fixture=is_test_fixture,
                domain=self.config.domain
            ),
            partition=partition
        )
