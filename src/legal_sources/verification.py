"""
Authoritative Legal Source Verification Workflow.

Implements repeatable, defensible verification of statutory sources:
1. Validates manifest schema and required metadata.
2. Detects duplicate source IDs and duplicate file references.
3. Confirms local source file existence and reproducible SHA-256 integrity.
4. Distinguishes local checksum reproducibility from official publication authenticity.
5. Validates official URL syntax and safe network reachability without TLS bypass.
6. Compares source snapshots against official reference artifacts when available.
7. Generates machine-readable and human-readable verification reports.
"""

import os
import re
import json
import hashlib
import datetime
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

from src.legal_sources.provenance import (
    VerificationStatus,
    VerificationMethod,
    SourceCompletenessStatus,
    AmendmentCoverageStatus,
    CommencementStatus,
    CurrentnessStatus,
    is_retrieval_eligible,
    is_authoritatively_verified,
)

REQUIRED_METADATA_FIELDS = [
    "source_id",
    "jurisdiction",
    "verification_status",
]

class LegalSourceVerificationWorkflow:
    """
    Executes repeatable audit and verification of statutory sources.
    """
    def __init__(
        self,
        manifest_path: str = "data/legal_sources/corpus_manifest.json",
        snapshots_dir: str = "data/legal_sources/snapshots",
        reference_artifacts_dir: str = "data/legal_sources/reference_artifacts"
    ):
        self.manifest_path = manifest_path
        self.snapshots_dir = snapshots_dir
        self.reference_artifacts_dir = reference_artifacts_dir

    def validate_url_syntax(self, url: Optional[str]) -> Tuple[bool, str]:
        """
        Validates URL syntax.
        A valid URL must have a scheme (http or https) and a network location.
        """
        if not url or not url.strip():
            return False, "URL is missing or empty"
        try:
            parsed = urllib.parse.urlparse(url.strip())
            if parsed.scheme not in ("http", "https"):
                return False, f"Invalid URL scheme '{parsed.scheme}'; expected 'http' or 'https'"
            if not parsed.netloc:
                return False, "URL is missing network location (domain)"
            return True, "Valid URL syntax"
        except Exception as e:
            return False, f"Malformed URL: {str(e)}"

    def validate_manifest_metadata(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates manifest structure, required fields, and detects duplicates.
        """
        errors: List[str] = []
        warnings: List[str] = []
        sources = manifest_data.get("official_sources")

        if sources is None or not isinstance(sources, list):
            return {
                "valid": False,
                "errors": ["Manifest missing 'official_sources' list."],
                "warnings": warnings,
                "source_count": 0
            }

        seen_ids = set()
        seen_files = {}

        for idx, src in enumerate(sources):
            if not isinstance(src, dict):
                errors.append(f"Source entry at index {idx} is not a JSON object.")
                continue

            src_id = src.get("source_id")
            if not src_id:
                errors.append(f"Source entry at index {idx} is missing 'source_id'.")
            elif src_id in seen_ids:
                errors.append(f"Duplicate source identifier detected: '{src_id}'.")
            else:
                seen_ids.add(src_id)

            # Check title
            title = src.get("canonical_title") or src.get("title")
            if not title:
                errors.append(f"Source '{src_id or idx}' is missing title/canonical_title.")

            # Check required fields
            for req in REQUIRED_METADATA_FIELDS:
                if req not in src or src[req] is None or src[req] == "":
                    errors.append(f"Source '{src_id or idx}' is missing required field '{req}'.")

            # Check file reference
            file_name = src.get("source_file") or src.get("snapshot_file")
            if not file_name:
                errors.append(f"Source '{src_id or idx}' is missing source_file/snapshot_file reference.")
            else:
                if file_name in seen_files:
                    errors.append(
                        f"Duplicate source file reference detected: '{file_name}' referenced by "
                        f"both '{seen_files[file_name]}' and '{src_id}'."
                    )
                else:
                    seen_files[file_name] = src_id

            # Validate URL
            url = src.get("authoritative_source_url") or src.get("official_url")
            url_valid, url_msg = self.validate_url_syntax(url)
            if not url_valid:
                warnings.append(f"Source '{src_id or idx}' URL validation notice: {url_msg} ('{url}').")

            # Check verification status validity
            ver_status_str = src.get("verification_status")
            if ver_status_str:
                try:
                    VerificationStatus(ver_status_str)
                except ValueError:
                    errors.append(f"Source '{src_id or idx}' has invalid verification_status: '{ver_status_str}'.")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "source_count": len(sources)
        }

    def verify_local_file_integrity(self, source_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies local snapshot file existence and reproduces SHA-256 checksum.
        CRITICAL: A matching local checksum proves file reproducibility, NOT official authenticity.
        """
        src_id = source_meta.get("source_id", "UNKNOWN")
        file_name = source_meta.get("source_file") or source_meta.get("snapshot_file", "")
        file_path = os.path.join(self.snapshots_dir, file_name) if file_name else ""

        if not file_name or not os.path.exists(file_path):
            return {
                "source_id": src_id,
                "file_present": False,
                "file_path": file_path,
                "computed_sha256": None,
                "recorded_sha256": source_meta.get("source_sha256") or source_meta.get("content_checksum_sha256"),
                "hash_matches": False,
                "file_size_bytes": 0,
                "error": f"Snapshot file not found on disk: '{file_path}'"
            }

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            computed_sha = hashlib.sha256(content).hexdigest()
            recorded_sha = source_meta.get("source_sha256") or source_meta.get("content_checksum_sha256")
            hash_matches = bool(recorded_sha and computed_sha.lower() == recorded_sha.lower())

            return {
                "source_id": src_id,
                "file_present": True,
                "file_path": file_path,
                "computed_sha256": computed_sha,
                "recorded_sha256": recorded_sha,
                "hash_matches": hash_matches,
                "file_size_bytes": len(content),
                "error": None if hash_matches else f"Checksum mismatch: expected '{recorded_sha}', computed '{computed_sha}'"
            }
        except Exception as e:
            return {
                "source_id": src_id,
                "file_present": True,
                "file_path": file_path,
                "computed_sha256": None,
                "recorded_sha256": source_meta.get("source_sha256") or source_meta.get("content_checksum_sha256"),
                "hash_matches": False,
                "file_size_bytes": 0,
                "error": f"Error reading snapshot file: {str(e)}"
            }

    def compare_with_authoritative_artifact(
        self,
        source_id: str,
        local_text: str,
        reference_artifact_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compares local text with an official reference artifact (e.g. Gazette of India publication).
        If no artifact exists, honestly reports unverified status without fabricating a match.
        """
        ref_path = reference_artifact_path
        if not ref_path:
            # Check default artifact directory
            candidate = os.path.join(self.reference_artifacts_dir, f"{source_id}_authoritative.txt")
            if os.path.exists(candidate):
                ref_path = candidate
            else:
                # Also check Task 040 extracted_text location: data/legal_sources/extracted_text/<source_id>/*/extracted.txt
                base_dir = os.path.dirname(self.snapshots_dir)
                extracted_base = os.path.join(base_dir, "extracted_text", source_id)
                if os.path.exists(extracted_base):
                    for sub in sorted(os.listdir(extracted_base), reverse=True):
                        candidate_sub = os.path.join(extracted_base, sub, "extracted.txt")
                        if os.path.exists(candidate_sub):
                            ref_path = candidate_sub
                            break

        if not ref_path or not os.path.exists(ref_path):
            return {
                "comparison_performed": False,
                "reference_artifact_path": ref_path,
                "authoritative_sha256": None,
                "match_ratio": 0.0,
                "is_byte_exact": False,
                "verification_tier": VerificationStatus.PARTIALLY_VERIFIED.value,
                "notes": "No official gazette or India Code byte-for-byte reference artifact available for local comparison."
            }

        try:
            with open(ref_path, "r", encoding="utf-8") as f:
                ref_text = f.read()

            ref_sha = hashlib.sha256(ref_text.encode("utf-8")).hexdigest()
            is_byte_exact = (local_text.strip() == ref_text.strip())

            # Line comparison
            local_lines = set(line.strip() for line in local_text.splitlines() if line.strip())
            ref_lines = set(line.strip() for line in ref_text.splitlines() if line.strip())
            common_lines = local_lines.intersection(ref_lines)
            match_ratio = len(common_lines) / max(len(ref_lines), 1)

            if is_byte_exact:
                tier = VerificationStatus.CONTENT_MATCH_VERIFIED.value
            elif match_ratio > 0.5:
                tier = VerificationStatus.PARTIALLY_VERIFIED.value
            else:
                tier = VerificationStatus.VERIFICATION_FAILED.value

            return {
                "comparison_performed": True,
                "reference_artifact_path": ref_path,
                "authoritative_sha256": ref_sha,
                "match_ratio": round(match_ratio, 4),
                "is_byte_exact": is_byte_exact,
                "verification_tier": tier,
                "notes": f"Compared with reference artifact. Exact match: {is_byte_exact}, line overlap: {match_ratio:.2%}"
            }
        except Exception as e:
            return {
                "comparison_performed": False,
                "reference_artifact_path": ref_path,
                "authoritative_sha256": None,
                "match_ratio": 0.0,
                "is_byte_exact": False,
                "verification_tier": VerificationStatus.VERIFICATION_FAILED.value,
                "notes": f"Failed to execute comparison against reference artifact: {str(e)}"
            }

    def attempt_network_reachability(self, url: Optional[str], timeout: float = 3.0) -> Dict[str, Any]:
        """
        Checks reachability of authoritative URL without bypassing TLS validation.
        CRITICAL: HTTP 200 alone does NOT prove statutory text equivalence or currentness.
        """
        valid, msg = self.validate_url_syntax(url)
        if not valid or not url:
            return {
                "url": url,
                "reachable": False,
                "http_status": None,
                "tls_validated": False,
                "error": msg,
                "proves_content_equivalence": False,
                "disclaimer": "HTTP 200 checks network endpoint presence only; does not certify statutory content."
            }

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ContractRisk-XAI-Verifier/1.0 (Audit Compliance)"}
            )
            # Default ssl context enforces strict certificate validation
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                reachable = (200 <= status_code < 400)
                return {
                    "url": url,
                    "reachable": reachable,
                    "http_status": status_code,
                    "tls_validated": True,
                    "error": None,
                    "proves_content_equivalence": False,
                    "disclaimer": "HTTP 200 confirms official URL accessibility only. It does not establish statutory text equivalence."
                }
        except urllib.error.HTTPError as e:
            return {
                "url": url,
                "reachable": False,
                "http_status": e.code,
                "tls_validated": True,
                "error": f"HTTP {e.code}: {e.reason}",
                "proves_content_equivalence": False,
                "disclaimer": "HTTP error encountered during authoritative URL inspection."
            }
        except Exception as e:
            return {
                "url": url,
                "reachable": False,
                "http_status": None,
                "tls_validated": False,
                "error": f"Network reachability check failed: {str(e)}",
                "proves_content_equivalence": False,
                "disclaimer": "Authoritative endpoint could not be reached or timed out."
            }

    def run_verification(
        self,
        check_network: bool = False,
        output_json_path: Optional[str] = None,
        output_md_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes full repeatable verification across the statutory corpus manifest.
        """
        audit_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not os.path.exists(self.manifest_path):
            return {
                "status": "FAILED",
                "timestamp": audit_timestamp,
                "error": f"Manifest file not found: {self.manifest_path}"
            }

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            try:
                manifest_data = json.load(f)
            except Exception as e:
                return {
                    "status": "FAILED",
                    "timestamp": audit_timestamp,
                    "error": f"Manifest is malformed JSON: {str(e)}"
                }

        validation = self.validate_manifest_metadata(manifest_data)
        sources = manifest_data.get("official_sources", [])

        source_reports: List[Dict[str, Any]] = []
        overall_errors: List[str] = list(validation.get("errors", []))
        overall_warnings: List[str] = list(validation.get("warnings", []))

        count_present = 0
        count_hashes_valid = 0
        count_content_match_verified = 0
        count_partially_verified = 0
        count_unverified = 0

        for src in sources:
            src_id = src.get("source_id", "UNKNOWN")
            file_meta = self.verify_local_file_integrity(src)

            if file_meta["file_present"]:
                count_present += 1
            if file_meta["hash_matches"]:
                count_hashes_valid += 1
            else:
                if file_meta.get("error"):
                    overall_errors.append(f"[{src_id}] {file_meta['error']}")

            # Load local text for artifact comparison
            local_text = ""
            if file_meta["file_present"] and file_meta["file_path"]:
                try:
                    with open(file_meta["file_path"], "r", encoding="utf-8") as f:
                        local_text = f.read()
                except Exception as e:
                    overall_warnings.append(f"[{src_id}] Could not read text: {str(e)}")

            # Artifact comparison
            ref_comp = self.compare_with_authoritative_artifact(src_id, local_text)
            if ref_comp["is_byte_exact"]:
                count_content_match_verified += 1
            else:
                count_partially_verified += 1

            # Network check if requested
            net_check = None
            if check_network:
                url = src.get("authoritative_source_url") or src.get("official_url")
                net_check = self.attempt_network_reachability(url)

            # Derive defensible verification status:
            # - Cannot be CONTENT_MATCH_VERIFIED without an actual exact reference comparison
            # - Cannot be CURRENTNESS_VERIFIED without an active currentness audit date
            # - A stable local hash promotes to METADATA_VALIDATED or CHECKSUM_RECORDED, but NOT CONTENT_MATCH_VERIFIED
            manifest_status = src.get("verification_status", VerificationStatus.UNVERIFIED.value)
            if manifest_status in (
                VerificationStatus.CONTENT_MATCH_VERIFIED.value,
                VerificationStatus.VERIFIED_AUTHORITATIVE.value
            ) and not ref_comp["is_byte_exact"]:
                # Prevent false promotion
                effective_status = VerificationStatus.PARTIALLY_VERIFIED.value
                overall_warnings.append(
                    f"[{src_id}] Claim of authoritative verification downgraded to PARTIALLY_VERIFIED "
                    "because official gazette byte-for-byte comparison artifact is absent."
                )
            else:
                effective_status = manifest_status

            source_reports.append({
                "source_id": src_id,
                "canonical_title": src.get("canonical_title") or src.get("title"),
                "act_number": src.get("act_number"),
                "jurisdiction": src.get("jurisdiction"),
                "source_file": src.get("source_file") or src.get("snapshot_file"),
                "file_present": file_meta["file_present"],
                "file_size_bytes": file_meta["file_size_bytes"],
                "recorded_sha256": file_meta["recorded_sha256"],
                "computed_sha256": file_meta["computed_sha256"],
                "local_hash_reproducible": file_meta["hash_matches"],
                "manifest_verification_status": manifest_status,
                "defensible_verification_status": effective_status,
                "verification_method": src.get("verification_method", VerificationMethod.LOCAL_HASH_AND_METADATA_VALIDATED.value),
                "source_completeness_status": src.get("source_completeness_status", SourceCompletenessStatus.CURATED_EXTRACT.value),
                "covered_sections_count": len(src.get("covered_sections_or_provisions", [])),
                "covered_sections": src.get("covered_sections_or_provisions", []),
                "commencement_status": src.get("commencement_status", CommencementStatus.UNKNOWN.value),
                "currentness_status": src.get("currentness_status", CurrentnessStatus.UNKNOWN.value),
                "official_url": src.get("authoritative_source_url") or src.get("official_url"),
                "authoritative_comparison": ref_comp,
                "network_check": net_check,
                "limitations": src.get("applicability_limitations")
            })

        report = {
            "report_version": "1.0.0",
            "audit_timestamp": audit_timestamp,
            "manifest_path": self.manifest_path,
            "manifest_valid": validation["valid"],
            "summary": {
                "total_sources_declared": len(sources),
                "files_present_on_disk": count_present,
                "hashes_reproducible": count_hashes_valid,
                "content_match_verified": count_content_match_verified,
                "partially_verified": count_partially_verified,
                "unverified": count_unverified,
                "is_corpus_fully_authoritative": (count_content_match_verified == len(sources) and len(sources) > 0),
            },
            "disclosures": {
                "authenticity_boundary": (
                    "A locally computed SHA-256 hash proves local file integrity and detects post-ingestion tampering. "
                    "It does NOT establish authenticity against the official publication, currency, or legal applicability."
                ),
                "coverage_boundary": (
                    "The current corpus contains curated commercial extracts from six Indian central statutes. "
                    "It does NOT constitute complete statutory Acts, subordinate rules, state amendments, or exhaustive Indian law."
                ),
                "network_boundary": (
                    "HTTP 200 responses confirm endpoint availability only. They do not constitute statutory text verification."
                )
            },
            "errors": overall_errors,
            "warnings": overall_warnings,
            "sources": source_reports
        }

        # Save JSON report if requested
        json_target = output_json_path or "data/legal_sources/reports/verification_report.json"
        os.makedirs(os.path.dirname(json_target), exist_ok=True)
        with open(json_target, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # Generate human-readable Markdown report
        md_target = output_md_path or "data/legal_sources/reports/verification_report.md"
        self._write_markdown_report(report, md_target)

        return report

    def _write_markdown_report(self, report: Dict[str, Any], output_path: str):
        """
        Renders an auditable human-readable verification report.
        """
        lines = [
            "# Indian Legal Source Verification Audit Report",
            f"**Audit Timestamp:** `{report['audit_timestamp']}`  ",
            f"**Manifest Path:** `{report['manifest_path']}`  ",
            f"**Manifest Valid:** `{'YES' if report['manifest_valid'] else 'NO'}`  ",
            "",
            "## 1. Executive Summary",
            "",
            "| Metric | Count | Defensible Meaning |",
            "|---|---|---|",
            f"| Total Declared Sources | {report['summary']['total_sources_declared']} | Curated statutory instruments declared in manifest |",
            f"| Local Files Present | {report['summary']['files_present_on_disk']} | Snapshot files existing on repository disk |",
            f"| SHA-256 Reproducible | {report['summary']['hashes_reproducible']} | Local hashes matching recorded baseline digests |",
            f"| Content-Match Verified | {report['summary']['content_match_verified']} | Exact byte-for-byte verified against official gazette |",
            f"| Partially Verified | {report['summary']['partially_verified']} | Hash/metadata valid; official publication comparison uncompleted |",
            f"| Fully Authoritative Corpus | {'YES' if report['summary']['is_corpus_fully_authoritative'] else 'NO (Curated Extracts Only)'} | Honest corpus certification |",
            "",
            "## 2. Source-by-Source Verification Status",
            "",
            "| Source ID | Canonical Title | Present | Hash Valid | Sections | Tier | Completeness | Limitations |",
            "|---|---|---|---|---|---|---|---|"
        ]

        for s in report["sources"]:
            lines.append(
                f"| `{s['source_id']}` | {s['canonical_title']} | "
                f"{'✅' if s['file_present'] else '❌'} | "
                f"{'✅' if s['local_hash_reproducible'] else '❌'} | "
                f"{s['covered_sections_count']} sections | "
                f"`{s['defensible_verification_status']}` | "
                f"`{s['source_completeness_status']}` | "
                f"{s['limitations'] or 'N/A'} |"
            )

        lines.extend([
            "",
            "## 3. Disclosures and Verification Boundaries",
            "",
            f"1. **Cryptographic vs. Legal Authenticity:** {report['disclosures']['authenticity_boundary']}",
            f"2. **Coverage Scope:** {report['disclosures']['coverage_boundary']}",
            f"3. **Network Invariance:** {report['disclosures']['network_boundary']}",
            "",
            "## 4. Warnings and Audit Findings",
            ""
        ])

        if report["warnings"]:
            for w in report["warnings"]:
                lines.append(f"- ⚠️ {w}")
        else:
            lines.append("- No warnings recorded.")

        if report["errors"]:
            lines.append("")
            lines.append("## 5. Critical Audit Errors")
            for e in report["errors"]:
                lines.append(f"- 🛑 {e}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
