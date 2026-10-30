"""
Evaluation Harness for Evidence-Aware Abstention in CONTRACTRISK-XAI.

Implements prespecified, mathematically defensible evaluation metrics for comparing
confidence-only and evidence-aware contract analysis policies.

Adheres strictly to:
1. Primary UFR definition: WITHHOLD fraction among evaluable retained candidates.
2. Safety Discrepancy reporting: HUMAN_REVIEW_REQUIRED reference candidates retained by policy are tracked separately.
3. Empty denominator handling: UFR is UNDEFINED (None) when retained denominator is zero; never 0.0%.
4. Useful-Finding Coverage (UFC): Candidates sent to human review do NOT count as automatically retained.
5. Deterministic tie-breaking: SortKey = (-confidence, candidate_finding_id) without outcome leakage.
6. Coverage matching: Matched comparison strictly requires |UFC_A - UFC_B| <= 0.02; otherwise returns MATCHED_COVERAGE_UNACHIEVED.
7. Contract-level clustering: Requires contract_id on all candidates for future clustered inferential testing.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field, ConfigDict

from src.candidates.schema import (
    CandidateFindingRecord,
    VersionConsistencyStatus,
)
from src.evaluation.partition_validator import (
    PartitionIsolationValidator,
    PartitionValidationResult,
)


class ReferenceDecision(str, Enum):
    """Ground-truth human legal reference decision."""
    RETAIN = "RETAIN"
    WITHHOLD = "WITHHOLD"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class PolicyAction(str, Enum):
    """Automated operational action taken by a decision policy."""
    ACCEPT = "ACCEPT"
    RETAIN = "RETAIN" # Alias for ACCEPT
    WITHHOLD = "WITHHOLD"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ReferenceAnnotationRecord(BaseModel):
    """Reference ground truth record for a single candidate finding."""
    model_config = ConfigDict(extra="forbid")

    candidate_finding_id: str
    decision: ReferenceDecision
    rationale: Optional[str] = None
    is_synthetic_fixture: bool = False


class PolicyDecisionRecord(BaseModel):
    """Operational policy action record for a single candidate finding."""
    model_config = ConfigDict(extra="forbid")

    candidate_finding_id: str
    policy_id: str
    action: PolicyAction
    threshold_applied: Optional[float] = None
    decision_metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluationSummary(BaseModel):
    """Comprehensive metric summary for a single policy evaluated on a candidate pool."""
    policy_id: str
    total_candidates: int
    evaluable_candidates: int
    unassessable_candidates: int

    # Retention Rate
    retained_count: int
    retention_rate: float

    # Unsupported Finding Rate (UFR) & Counts
    evaluable_retained_count: int
    unsupported_finding_count: int # y_ref == WITHHOLD
    ufr: Optional[float] # None if evaluable_retained_count == 0
    
    # Safety Discrepancies (y_ref == HUMAN_REVIEW_REQUIRED retained automatically)
    human_review_discrepancy_count: int
    human_review_discrepancy_rate: Optional[float]

    # Useful Finding Coverage (UFC)
    total_reference_retainable: int
    retained_useful_count: int # y_ref == RETAIN retained automatically
    ufc: Optional[float] # None if total_reference_retainable == 0

    # Unnecessary Abstention Rate (UAR)
    uar_total_rate: Optional[float]
    uar_withheld_count: int
    uar_withheld_rate: Optional[float]
    uar_human_review_count: int
    uar_human_review_rate: Optional[float]

    # Stale-Evidence Acceptance Rate (SEAR)
    sear_stale_count: int
    sear_stale_rate: Optional[float]
    sear_unknown_count: int
    sear_unknown_rate: Optional[float]

    # Human Review Workload (HRW)
    routed_to_review_count: int
    hrw_rate: float

    # Unassessable Rate (UR)
    unassessable_rate: float


class CoverageMatchingResult(BaseModel):
    """Result of comparing two policies at matched coverage."""
    status: str # "MATCHED_COVERAGE_ACHIEVED" or "MATCHED_COVERAGE_UNACHIEVED"
    tolerance: float = 0.02
    policy_a_id: str
    policy_b_id: str
    policy_a_ufc: Optional[float]
    policy_b_ufc: Optional[float]
    coverage_difference: Optional[float]
    policy_a_ufr: Optional[float]
    policy_b_ufr: Optional[float]
    delta_ufr: Optional[float] # UFR(A) - UFR(B)
    notes: str


def sort_candidates_by_confidence(
    candidates: List[CandidateFindingRecord]
) -> List[CandidateFindingRecord]:
    """
    Sorts candidate findings deterministically by numerical confidence score descending.
    Ties in confidence score are broken strictly using the non-outcome key:
    SortKey(F) = (-confidence_value, candidate_finding_id).
    
    Strictly forbids inspecting ground-truth reference labels or policy outcomes.
    """
    return sorted(candidates, key=lambda c: (-c.confidence_value, c.candidate_finding_id))


def validate_evaluation_inputs(
    candidates: List[CandidateFindingRecord],
    reference_annotations: Dict[str, ReferenceDecision],
    policy_decisions: Dict[str, PolicyAction],
) -> None:
    """
    Validates experimental integrity of candidates, references, and policy decisions.
    Raises ValueError on duplicate IDs, missing references, or metadata mismatch.
    """
    if not candidates:
        raise ValueError("Candidate finding list cannot be empty.")

    candidate_ids: Set[str] = set()
    for c in candidates:
        if c.candidate_finding_id in candidate_ids:
            raise ValueError(f"Duplicate candidate_finding_id detected in candidate set: {c.candidate_finding_id}")
        candidate_ids.add(c.candidate_finding_id)

    missing_refs = candidate_ids - set(reference_annotations.keys())
    if missing_refs:
        raise ValueError(f"Missing reference annotations for {len(missing_refs)} candidates. Example ID: {next(iter(missing_refs))}")

    missing_policy = candidate_ids - set(policy_decisions.keys())
    if missing_policy:
        raise ValueError(f"Missing policy decisions for {len(missing_policy)} candidates. Example ID: {next(iter(missing_policy))}")


def preflight_partition_check(
    validation_items: Optional[List[Any]] = None,
    test_items: Optional[List[Any]] = None,
    partition_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[PartitionValidationResult]:
    """
    Executes a pre-flight partition isolation check before threshold evaluation.
    
    Adheres strictly to Strategy A (RDR-002):
    1. Zero cross-partition template family leakage: Families(Validation) ∩ Families(Test) == ∅.
    2. MACRO-FAM-DOE-PPD locking: allocated exclusively to Validation/Development; prohibited from Test.
    3. Fails closed on detected leakage by raising ValueError.
    
    LIMITATION NOTE:
    When validation/test partition metadata is absent (None or empty), partition isolation
    cannot be verified prior to evaluation. In this case, existing evaluation behavior
    is preserved, but callers are alerted that cross-partition template family leakage
    checks were unperformed due to absent partition metadata.
    """
    val_items = list(validation_items) if validation_items is not None else []
    tst_items = list(test_items) if test_items is not None else []

    if partition_metadata:
        if not val_items:
            val_items = partition_metadata.get("validation_items") or partition_metadata.get("validation") or []
        if not tst_items:
            tst_items = partition_metadata.get("test_items") or partition_metadata.get("test") or []

    if not val_items and not tst_items:
        # Partition metadata is absent - preserve existing behavior
        return None

    validator = PartitionIsolationValidator()
    result = validator.validate_partition_splits(val_items, tst_items)

    # Check sibling alternatives co-location if alternative metadata is present
    has_alts = any(
        (isinstance(it, dict) and it.get("alternative_group_id")) or hasattr(it, "alternative_group_id")
        for it in (val_items + tst_items)
    )
    if has_alts:
        alt_valid, alt_errors = validator.validate_sibling_alternative_partitions(val_items, tst_items)
        if not alt_valid:
            result.is_valid = False
            result.errors.extend(alt_errors)

    if not result.is_valid:
        # FAIL CLOSED on detected leakage
        raise ValueError(
            f"Pre-flight partition isolation check failed closed due to detected leakage: "
            f"{'; '.join(result.errors)}"
        )

    return result


def evaluate_policy(
    policy_id: str,
    candidates: List[CandidateFindingRecord],
    reference_annotations: Dict[str, ReferenceDecision],
    policy_decisions: Dict[str, PolicyAction],
    validation_items: Optional[List[Any]] = None,
    test_items: Optional[List[Any]] = None,
    partition_metadata: Optional[Dict[str, Any]] = None,
) -> PolicyEvaluationSummary:
    """
    Evaluates an operational policy against ground-truth reference decisions for a candidate pool.

    Pre-flight Partition Isolation:
    When validation/test partition metadata is supplied (via validation_items/test_items or
    partition_metadata), executes PartitionIsolationValidator and fails closed on detected leakage.
    
    LIMITATION NOTE:
    When partition metadata is absent, partition isolation cannot be verified before threshold
    evaluation. Existing evaluation behavior is preserved.
    """
    # 0. Pre-flight partition check before threshold evaluation
    preflight_partition_check(
        validation_items=validation_items,
        test_items=test_items,
        partition_metadata=partition_metadata,
    )

    validate_evaluation_inputs(candidates, reference_annotations, policy_decisions)

    total_candidates = len(candidates)
    
    # 1. Unassessable identification
    unassessable_ids = {
        c.candidate_finding_id for c in candidates
        if reference_annotations[c.candidate_finding_id] == ReferenceDecision.NOT_ASSESSABLE
    }
    unassessable_count = len(unassessable_ids)
    evaluable_candidates = total_candidates - unassessable_count
    ur_rate = unassessable_count / total_candidates if total_candidates > 0 else 0.0

    # 2. Policy actions classification
    retained_candidates: List[CandidateFindingRecord] = []
    review_candidates: List[CandidateFindingRecord] = []
    withheld_candidates: List[CandidateFindingRecord] = []

    for c in candidates:
        cid = c.candidate_finding_id
        action = policy_decisions[cid]
        if action in (PolicyAction.ACCEPT, PolicyAction.RETAIN):
            retained_candidates.append(c)
        elif action == PolicyAction.REVIEW_REQUIRED:
            review_candidates.append(c)
        elif action == PolicyAction.WITHHOLD:
            withheld_candidates.append(c)

    retained_count = len(retained_candidates)
    retention_rate = retained_count / total_candidates if total_candidates > 0 else 0.0

    hrw_count = len(review_candidates)
    hrw_rate = hrw_count / total_candidates if total_candidates > 0 else 0.0

    # 3. Evaluable retained subset (excludes NOT_ASSESSABLE)
    evaluable_retained = [c for c in retained_candidates if c.candidate_finding_id not in unassessable_ids]
    evaluable_retained_count = len(evaluable_retained)

    # 4. Unsupported Finding Rate (UFR) & Safety Discrepancies
    unsupported_count = 0
    discrepancy_count = 0

    for c in evaluable_retained:
        ref_dec = reference_annotations[c.candidate_finding_id]
        if ref_dec == ReferenceDecision.WITHHOLD:
            unsupported_count += 1
        elif ref_dec == ReferenceDecision.HUMAN_REVIEW_REQUIRED:
            discrepancy_count += 1

    # STRICT INVARIANT: If evaluable_retained_count == 0, UFR is None (UNDEFINED), NEVER 0.0
    ufr = (unsupported_count / evaluable_retained_count) if evaluable_retained_count > 0 else None
    discrepancy_rate = (discrepancy_count / evaluable_retained_count) if evaluable_retained_count > 0 else None

    # 5. Useful Finding Coverage (UFC)
    # Denominator: Total reference RETAIN in evaluable corpus
    evaluable_retain_target = [
        c for c in candidates
        if c.candidate_finding_id not in unassessable_ids
        and reference_annotations[c.candidate_finding_id] == ReferenceDecision.RETAIN
    ]
    total_reference_retainable = len(evaluable_retain_target)

    # Numerator: Genuinely retainable candidates automatically retained
    retained_useful_count = sum(
        1 for c in evaluable_retained
        if reference_annotations[c.candidate_finding_id] == ReferenceDecision.RETAIN
    )

    ufc = (retained_useful_count / total_reference_retainable) if total_reference_retainable > 0 else None

    # 6. Unnecessary Abstention Rate (UAR)
    # Reference RETAIN candidates NOT automatically retained
    uar_withheld_count = sum(
        1 for c in withheld_candidates
        if c.candidate_finding_id not in unassessable_ids
        and reference_annotations[c.candidate_finding_id] == ReferenceDecision.RETAIN
    )
    uar_review_count = sum(
        1 for c in review_candidates
        if c.candidate_finding_id not in unassessable_ids
        and reference_annotations[c.candidate_finding_id] == ReferenceDecision.RETAIN
    )
    uar_total_count = uar_withheld_count + uar_review_count

    uar_total_rate = (uar_total_count / evaluable_candidates) if evaluable_candidates > 0 else None
    uar_withheld_rate = (uar_withheld_count / evaluable_candidates) if evaluable_candidates > 0 else None
    uar_review_rate = (uar_review_count / evaluable_candidates) if evaluable_candidates > 0 else None

    # 7. Stale-Evidence Acceptance Rate (SEAR)
    sear_stale_count = 0
    sear_unknown_count = 0

    for c in retained_candidates:
        if c.version_consistency_status == VersionConsistencyStatus.STALE:
            sear_stale_count += 1
        elif c.version_consistency_status == VersionConsistencyStatus.UNKNOWN:
            sear_unknown_count += 1

    sear_stale_rate = (sear_stale_count / retained_count) if retained_count > 0 else None
    sear_unknown_rate = (sear_unknown_count / retained_count) if retained_count > 0 else None

    return PolicyEvaluationSummary(
        policy_id=policy_id,
        total_candidates=total_candidates,
        evaluable_candidates=evaluable_candidates,
        unassessable_candidates=unassessable_count,
        retained_count=retained_count,
        retention_rate=retention_rate,
        evaluable_retained_count=evaluable_retained_count,
        unsupported_finding_count=unsupported_count,
        ufr=ufr,
        human_review_discrepancy_count=discrepancy_count,
        human_review_discrepancy_rate=discrepancy_rate,
        total_reference_retainable=total_reference_retainable,
        retained_useful_count=retained_useful_count,
        ufc=ufc,
        uar_total_rate=uar_total_rate,
        uar_withheld_count=uar_withheld_count,
        uar_withheld_rate=uar_withheld_rate,
        uar_human_review_count=uar_review_count,
        uar_human_review_rate=uar_review_rate,
        sear_stale_count=sear_stale_count,
        sear_stale_rate=sear_stale_rate,
        sear_unknown_count=sear_unknown_count,
        sear_unknown_rate=sear_unknown_rate,
        routed_to_review_count=hrw_count,
        hrw_rate=hrw_rate,
        unassessable_rate=ur_rate,
    )


def compare_policies_at_matched_coverage(
    eval_a: PolicyEvaluationSummary,
    eval_b: PolicyEvaluationSummary,
    tolerance: float = 0.02,
    validation_items: Optional[List[Any]] = None,
    test_items: Optional[List[Any]] = None,
    partition_metadata: Optional[Dict[str, Any]] = None,
) -> CoverageMatchingResult:
    """
    Compares two evaluated policies under the prespecified matched-coverage tolerance protocol.
    
    Pre-flight Partition Isolation:
    When validation/test partition metadata is supplied, verifies partition isolation before
    matched-coverage evaluation and fails closed on leakage.
    
    LIMITATION NOTE:
    When partition metadata is absent, partition isolation cannot be verified before
    matched-coverage comparison. Existing evaluation behavior is preserved.

    Rules:
    1. If |UFC_A - UFC_B| <= tolerance, matched coverage is achieved.
       Delta-UFR is computed as UFR(A) - UFR(B).
    2. If |UFC_A - UFC_B| > tolerance, returns MATCHED_COVERAGE_UNACHIEVED.
       Prohibits forced interpolation or claiming superiority without matched coverage.
    """
    # Pre-flight check before matched-coverage evaluation
    preflight_partition_check(
        validation_items=validation_items,
        test_items=test_items,
        partition_metadata=partition_metadata,
    )

    ufc_a = eval_a.ufc
    ufc_b = eval_b.ufc

    if ufc_a is None or ufc_b is None:
        return CoverageMatchingResult(
            status="MATCHED_COVERAGE_UNACHIEVED",
            tolerance=tolerance,
            policy_a_id=eval_a.policy_id,
            policy_b_id=eval_b.policy_id,
            policy_a_ufc=ufc_a,
            policy_b_ufc=ufc_b,
            coverage_difference=None,
            policy_a_ufr=eval_a.ufr,
            policy_b_ufr=eval_b.ufr,
            delta_ufr=None,
            notes="Cannot evaluate matched coverage: One or both policies have undefined UFC."
        )

    cov_diff = abs(ufc_a - ufc_b)

    if cov_diff <= tolerance:
        delta_ufr = None
        if eval_a.ufr is not None and eval_b.ufr is not None:
            delta_ufr = eval_a.ufr - eval_b.ufr

        return CoverageMatchingResult(
            status="MATCHED_COVERAGE_ACHIEVED",
            tolerance=tolerance,
            policy_a_id=eval_a.policy_id,
            policy_b_id=eval_b.policy_id,
            policy_a_ufc=ufc_a,
            policy_b_ufc=ufc_b,
            coverage_difference=round(cov_diff, 4),
            policy_a_ufr=eval_a.ufr,
            policy_b_ufr=eval_b.ufr,
            delta_ufr=round(delta_ufr, 4) if delta_ufr is not None else None,
            notes=f"Coverage matched within prespecified tolerance of {tolerance:.2f}."
        )
    else:
        return CoverageMatchingResult(
            status="MATCHED_COVERAGE_UNACHIEVED",
            tolerance=tolerance,
            policy_a_id=eval_a.policy_id,
            policy_b_id=eval_b.policy_id,
            policy_a_ufc=ufc_a,
            policy_b_ufc=ufc_b,
            coverage_difference=round(cov_diff, 4),
            policy_a_ufr=eval_a.ufr,
            policy_b_ufr=eval_b.ufr,
            delta_ufr=None,
            notes=f"Coverage difference ({cov_diff:.4f}) exceeds prespecified tolerance of {tolerance:.2f}. Single-point comparison unachieved."
        )
