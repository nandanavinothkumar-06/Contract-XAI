from src.missing_provisions.schema import ReferenceProvisionTaxonomy, ProvisionDefinition
from src.missing_provisions.provenance import TaxonomyProvenance, VerificationStatus, RequiredStatus

def get_fixture_taxonomy() -> ReferenceProvisionTaxonomy:
    prov1 = ProvisionDefinition(
        provision_id="PROV_CONFIDENTIALITY",
        name="Confidentiality",
        description="Requirement to keep information confidential.",
        domain="commercial",
        provenance=TaxonomyProvenance(
            source_reference="Fixture Legal Guide 2026",
            source_reference_type="FIXTURE",
            verification_status=VerificationStatus.NOT_VERIFIED
        ),
        detection_terms=["confidential", "non-disclosure", "shall not disclose"],
        semantic_description="The parties agree not to disclose confidential information to third parties.",
        required_status=RequiredStatus.RECOMMENDED_BY_REFERENCE
    )
    
    prov2 = ProvisionDefinition(
        provision_id="PROV_SEVERABILITY",
        name="Severability",
        description="If one part is invalid, the rest remains valid.",
        domain="commercial",
        provenance=TaxonomyProvenance(
            source_reference="Fixture Commercial Standard",
            source_reference_type="FIXTURE",
            verification_status=VerificationStatus.NOT_VERIFIED
        ),
        detection_terms=["severability", "severable", "invalid or unenforceable"],
        semantic_description="If any provision of this agreement is held to be invalid or unenforceable, the remaining provisions will continue in full force and effect.",
        required_status=RequiredStatus.OPTIONAL_REFERENCE_ITEM
    )

    return ReferenceProvisionTaxonomy(
        taxonomy_id="fixture_taxonomy_001",
        domain="commercial",
        provisions=[prov1, prov2],
        is_test_fixture=True
    )
