import json
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DomainAssignment(str, Enum):
    COMMERCIAL = "Commercial contracts"
    EMPLOYMENT = "Employment contracts"
    CONSTRUCTION = "Construction contracts"
    CONSUMER = "Consumer Terms of Service"
    DOMAIN_UNRESOLVED = "DOMAIN_UNRESOLVED"
    NDA = "Non-Disclosure Agreements"
    SEC_PROVISIONS = "SEC contractual provisions"

class CrossDomainStatus(str, Enum):
    VALID = "VALID"
    NO_GENUINE_CROSS_DOMAIN_EXPERIMENT_COULD_BE_RUN = "NO_GENUINE_CROSS_DOMAIN_EXPERIMENT_COULD_BE_RUN"
    TASK_INCOMPATIBLE_FOR_CROSS_DOMAIN_COMPARISON = "TASK_INCOMPATIBLE_FOR_CROSS_DOMAIN_COMPARISON"

class DomainMetadata(BaseModel):
    dataset_name: str
    task_definition: str
    domain: DomainAssignment
    domain_evidence: str
    access_status: str
    license_status: str
    num_instances: int
    num_source_documents: int
    label_schema: List[str]
    is_test_fixture: bool = False

class CrossDomainValidator:
    def __init__(self):
        self.datasets: List[DomainMetadata] = []
        
    def add_dataset(self, metadata: DomainMetadata) -> None:
        # 13. Synthetic fixture rejection for experiments
        if metadata.is_test_fixture:
            raise ValueError("Synthetic fixtures must NEVER be used as cross-domain experimental data.")
            
        # 3. Unresolved domain rejection/marking
        if metadata.domain == DomainAssignment.DOMAIN_UNRESOLVED:
            # We don't raise error, but we do not use it for genuine multi-domain checks below
            pass
            
        self.datasets.append(metadata)
        
    def check_task_compatibility(self, dataset1: DomainMetadata, dataset2: DomainMetadata) -> bool:
        """
        Check if two datasets can be compared or trained together safely.
        """
        # 5. Cross-domain task compatibility
        if dataset1.task_definition != dataset2.task_definition:
            return False
            
        # Label schemas must match for classification comparison
        if set(dataset1.label_schema) != set(dataset2.label_schema):
            return False
            
        return True

    def validate_experiment_eligibility(self) -> CrossDomainStatus:
        """
        Evaluates whether we have at least 2 distinct, resolved, compatible domains to run an experiment.
        """
        # Filter for resolved domains
        resolved_datasets = [d for d in self.datasets if d.domain != DomainAssignment.DOMAIN_UNRESOLVED]
        
        # 17. Fewer-than-two-domains handling
        distinct_domains = {d.domain for d in resolved_datasets}
        if len(distinct_domains) < 2:
            return CrossDomainStatus.NO_GENUINE_CROSS_DOMAIN_EXPERIMENT_COULD_BE_RUN
            
        # 6. Incompatible task rejection
        # If any two datasets have incompatible tasks, we cannot run a unified multi-domain model natively
        for i in range(len(resolved_datasets)):
            for j in range(i + 1, len(resolved_datasets)):
                if not self.check_task_compatibility(resolved_datasets[i], resolved_datasets[j]):
                    return CrossDomainStatus.TASK_INCOMPATIBLE_FOR_CROSS_DOMAIN_COMPARISON
                    
        return CrossDomainStatus.VALID

class ExperimentCoordinator:
    def check_leakage(
        self, 
        group_list1: List[str], 
        group_list2: List[str], 
        hash_list1: List[str], 
        hash_list2: List[str],
        text_list1: List[str],
        text_list2: List[str]
    ) -> bool:
        """
        Returns True if leakage is found, False otherwise.
        """
        # 7. Group leakage detection
        if set(group_list1).intersection(set(group_list2)):
            return True
            
        # 8. Exact-text leakage detection
        if set(text_list1).intersection(set(text_list2)):
            return True
            
        # 9. Hash leakage detection
        if set(hash_list1).intersection(set(hash_list2)):
            return True
            
        return False
        
    def serialize_metrics(self, metrics: Dict[str, Any]) -> str:
        # 14. Serialization/deserialization & 20. Deterministic configuration behavior
        return json.dumps(metrics, sort_keys=True, separators=(',', ':'))
