"""
Authoritative Statutory Comparison Engine.

Executes section-by-section comparison between curated local snapshots and extracted Gazette text:
1. Performs byte-level identity comparisons when files are expected to be identical.
2. Extracts and indexes structural sections from both snapshot and reference text.
3. Categorizes comparisons into:
   - EXACT_TEXT_MATCH (verbatim equivalence)
   - NORMALIZED_TEXT_MATCH (matches after documented typography/whitespace normalization)
   - TEXT_DIFFERENCE (textual drift with unified diffs)
   - SECTION_MISSING_IN_REFERENCE (provision in extract not found in gazette)
   - SECTIONS_ABSENT_FROM_SNAPSHOT (provisions in gazette omitted from extract)
4. Enforces strict verification transition invariants:
   - Partial section matches do NOT verify the entire Act.
   - Textual equivalence to an original enactment does NOT certify currentness if subsequent amendments occurred.
   - Exact text match does NOT imply legal applicability.
5. Produces machine-readable JSON and human-readable Markdown diff reports.
"""

import os
import re
import json
import difflib
import hashlib
import datetime
from typing import Dict, Any, List, Optional, Tuple, Set

from src.legal_sources.provenance import (
    VerificationStatus,
    SourceCompletenessStatus,
    CurrentnessStatus,
    CommencementStatus,
)
from src.legal_sources.ingestion import SECTION_PATTERN
from src.legal_sources.acquisition import safe_join_path, sanitize_identifier

def normalize_comparison_text(text: str) -> str:
    """
    Documented text normalization for comparison:
    - Strips PDF page separator markers (e.g., '--- PAGE 1 ---').
    - Normalizes unicode curly quotes to straight quotes.
    - Normalizes em-dashes and en-dashes to standard hyphens.
    - Normalizes spacing around statutory dash separators.
    - Collapses multiple whitespace characters to single space.
    - Strips leading and trailing whitespace.
    """
    clean = re.sub(r"---\s*PAGE\s+\d+\s*---", "", text)
    clean = clean.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    clean = clean.replace("—", "-").replace("–", "-")
    clean = re.sub(r"\s*-\s*", " - ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

def extract_sections_from_raw_text(text: str) -> Dict[str, Dict[str, str]]:
    """
    Extracts section numbers and section texts from raw statutory text.
    Returns: { '10': { 'heading': '...', 'passage_text': '...' }, ... }
    """
    sections: Dict[str, Dict[str, str]] = {}
    matches = list(SECTION_PATTERN.finditer(text))
    for m in matches:
        sec_num = m.group(1).strip()
        heading = m.group(2).strip()
        body = m.group(3).strip()
        raw_passage = text[m.start():m.end()].strip()
        sections[sec_num] = {
            "section_number": sec_num,
            "heading": heading,
            "body": body,
            "passage_text": raw_passage
        }
    return sections


class StatutoryComparisonEngine:
    """
    Aligns curated local statutory snapshots with authoritative reference artifacts.
    """
    def __init__(
        self,
        base_comparisons_dir: str = "data/legal_sources/comparisons"
    ):
        self.base_comparisons_dir = base_comparisons_dir

    def compare_snapshot_with_reference(
        self,
        source_id: str,
        snapshot_file_path: str,
        reference_text_path: str,
        reference_metadata: Optional[Dict[str, Any]] = None,
        comparison_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes granular section-by-section comparison between local snapshot and reference text.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        clean_source_id = sanitize_identifier(source_id)
        cid = sanitize_identifier(comparison_id or f"comp_{clean_source_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}")

        dest_dir = safe_join_path(self.base_comparisons_dir, clean_source_id, cid)
        os.makedirs(dest_dir, exist_ok=True)
        json_report_path = safe_join_path(dest_dir, "comparison_report.json")
        md_report_path = safe_join_path(dest_dir, "comparison_report.md")

        if not os.path.exists(snapshot_file_path):
            return {
                "success": False,
                "error": f"Snapshot file not found: '{snapshot_file_path}'"
            }
        if not os.path.exists(reference_text_path):
            return {
                "success": False,
                "error": f"Reference extracted text file not found: '{reference_text_path}'"
            }

        with open(snapshot_file_path, "r", encoding="utf-8") as f:
            snapshot_raw = f.read()
        with open(reference_text_path, "r", encoding="utf-8") as f:
            reference_raw = f.read()

        snapshot_sha = hashlib.sha256(snapshot_raw.encode("utf-8")).hexdigest()
        reference_sha = hashlib.sha256(reference_raw.encode("utf-8")).hexdigest()

        # 1. Byte-level exact comparison
        is_byte_for_byte_identical = (snapshot_raw.strip() == reference_raw.strip())

        # 2. Extract sections from both texts
        snap_sections = extract_sections_from_raw_text(snapshot_raw)
        ref_sections = extract_sections_from_raw_text(reference_raw)

        section_comparisons: List[Dict[str, Any]] = []
        exact_matches = 0
        normalized_matches = 0
        differing_sections = 0
        missing_in_ref = 0

        for sec_num, snap_data in snap_sections.items():
            snap_text = snap_data["passage_text"]
            if sec_num in ref_sections:
                ref_text = ref_sections[sec_num]["passage_text"]

                # A. Verbatim exact match
                if snap_text.strip() == ref_text.strip():
                    exact_matches += 1
                    section_comparisons.append({
                        "section_number": sec_num,
                        "heading": snap_data["heading"],
                        "match_type": "EXACT_TEXT_MATCH",
                        "diff": [],
                        "char_count_snapshot": len(snap_text),
                        "char_count_reference": len(ref_text),
                        "notes": "Verbatim text equivalence verified"
                    })
                else:
                    # B. Check normalized match
                    norm_snap = normalize_comparison_text(snap_text)
                    norm_ref = normalize_comparison_text(ref_text)
                    if norm_snap == norm_ref:
                        normalized_matches += 1
                        section_comparisons.append({
                            "section_number": sec_num,
                            "heading": snap_data["heading"],
                            "match_type": "NORMALIZED_TEXT_MATCH",
                            "diff": [],
                            "char_count_snapshot": len(snap_text),
                            "char_count_reference": len(ref_text),
                            "notes": "Text matches after normalizing typography and whitespace"
                        })
                    else:
                        differing_sections += 1
                        # Generate unified diff
                        diff_lines = list(difflib.unified_diff(
                            snap_text.splitlines(keepends=True),
                            ref_text.splitlines(keepends=True),
                            fromfile=f"snapshot_Section_{sec_num}",
                            tofile=f"reference_Section_{sec_num}"
                        ))
                        section_comparisons.append({
                            "section_number": sec_num,
                            "heading": snap_data["heading"],
                            "match_type": "TEXT_DIFFERENCE",
                            "diff": diff_lines[:30],  # bounded diff summary
                            "char_count_snapshot": len(snap_text),
                            "char_count_reference": len(ref_text),
                            "notes": "Textual divergence detected between snapshot and official reference"
                        })
            else:
                missing_in_ref += 1
                section_comparisons.append({
                    "section_number": sec_num,
                    "heading": snap_data["heading"],
                    "match_type": "SECTION_MISSING_IN_REFERENCE",
                    "diff": [],
                    "char_count_snapshot": len(snap_text),
                    "char_count_reference": 0,
                    "notes": "Section present in snapshot extract could not be located in reference text"
                })

        # Identify sections present in Gazette but omitted from snapshot
        snap_sec_keys = set(snap_sections.keys())
        ref_sec_keys = set(ref_sections.keys())
        omitted_from_snapshot = sorted(list(ref_sec_keys - snap_sec_keys), key=lambda x: (int(re.sub(r'\D', '', x) or 0), x))

        total_compared = len(snap_sections)
        concordant_count = exact_matches + normalized_matches
        concordance_ratio = (concordant_count / max(total_compared, 1))

        # 3. Determine defensible verification status
        if total_compared == 0:
            defensible_status = VerificationStatus.VERIFICATION_FAILED.value
            ver_notes = "Zero sections detected in snapshot text."
        elif concordant_count == total_compared:
            # All extract sections match official gazette publication
            defensible_status = VerificationStatus.CONTENT_MATCH_VERIFIED.value
            ver_notes = (
                f"Content match verified for all {total_compared} curated extract sections "
                f"({exact_matches} exact, {normalized_matches} normalized). "
                f"Omitted central sections ({len(omitted_from_snapshot)}) remain unrepresented."
            )
        elif concordant_count > 0:
            defensible_status = VerificationStatus.PARTIALLY_VERIFIED.value
            ver_notes = (
                f"Partial verification: {concordant_count} of {total_compared} sections matched. "
                f"{differing_sections} differing, {missing_in_ref} missing in reference."
            )
        else:
            defensible_status = VerificationStatus.VERIFICATION_FAILED.value
            ver_notes = "Zero sections matched between snapshot extract and reference artifact."

        report = {
            "comparison_id": cid,
            "source_id": clean_source_id,
            "timestamp": timestamp,
            "snapshot": {
                "file_path": snapshot_file_path,
                "sha256": snapshot_sha,
                "total_sections_count": total_compared,
                "section_numbers": sorted(list(snap_sec_keys))
            },
            "reference": {
                "file_path": reference_text_path,
                "sha256": reference_sha,
                "total_sections_found": len(ref_sections),
                "metadata": reference_metadata or {}
            },
            "byte_level_match": is_byte_for_byte_identical,
            "summary": {
                "sections_in_snapshot": total_compared,
                "exact_text_matches": exact_matches,
                "normalized_matches": normalized_matches,
                "textual_differences": differing_sections,
                "missing_in_reference": missing_in_ref,
                "concordance_percentage": round(concordance_ratio * 100, 2),
                "sections_in_reference_omitted_from_snapshot_count": len(omitted_from_snapshot),
                "sections_in_reference_omitted_from_snapshot": omitted_from_snapshot[:50]
            },
            "verification_outcome": {
                "defensible_status": defensible_status,
                "verified_scope": [s["section_number"] for s in section_comparisons if s["match_type"] in ("EXACT_TEXT_MATCH", "NORMALIZED_TEXT_MATCH")],
                "unverified_scope": [s["section_number"] for s in section_comparisons if s["match_type"] not in ("EXACT_TEXT_MATCH", "NORMALIZED_TEXT_MATCH")],
                "currentness_status": "CURRENTNESS_UNVERIFIED_PENDING_AMENDMENT_AUDIT",
                "applicability_status": "REQUIRES_ADVOCATE_DETERMINATION",
                "notes": ver_notes
            },
            "epistemic_disclosures": {
                "scope_limitation": (
                    "Content verification applies ONLY to the specific sections successfully matched. "
                    "It does not verify the entire Act or omitted sections."
                ),
                "currentness_boundary": (
                    "Matching an official enactment publication verifies textual authenticity as enacted. "
                    "It does not establish that subsequent amending Acts have been checked or that uncommenced "
                    "rules have been notified."
                ),
                "applicability_boundary": (
                    "Textual equivalence does not establish legal applicability to any specific contract clause, "
                    "dispute, or jurisdiction. Independent advocate evaluation is required."
                )
            },
            "sections": section_comparisons
        }

        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        self._render_markdown_report(report, md_report_path)

        return {
            "success": True,
            "comparison_id": cid,
            "source_id": clean_source_id,
            "defensible_status": defensible_status,
            "concordance_percentage": report["summary"]["concordance_percentage"],
            "json_report_path": json_report_path,
            "markdown_report_path": md_report_path,
            "report": report
        }

    def _render_markdown_report(self, report: Dict[str, Any], output_path: str):
        """
        Renders a detailed human-readable comparison report with diffs.
        """
        summ = report["summary"]
        out = report["verification_outcome"]
        lines = [
            f"# Statutory Comparison Report: `{report['source_id']}`",
            f"**Comparison ID:** `{report['comparison_id']}`  ",
            f"**Audit Timestamp:** `{report['timestamp']}`  ",
            f"**Defensible Status:** `{out['defensible_status']}`  ",
            f"**Concordance Rate:** **{summ['concordance_percentage']}%**  ",
            "",
            "## 1. Executive Comparison Metrics",
            "",
            "| Metric | Count | Defensible Meaning |",
            "|---|---|---|",
            f"| Snapshot Sections Compared | {summ['sections_in_snapshot']} | Sections present in local curated extract |",
            f"| Exact Verbatim Matches | {summ['exact_text_matches']} | Exact character-for-character equivalence |",
            f"| Normalized Matches | {summ['normalized_matches']} | Equivalent after typography & whitespace normalization |",
            f"| Textual Differences | {summ['textual_differences']} | Textual divergences identified with diffs |",
            f"| Missing in Reference | {summ['missing_in_reference']} | Sections in extract not found in gazette artifact |",
            f"| Reference Sections Omitted from Extract | {summ['sections_in_reference_omitted_from_snapshot_count']} | Gazette sections omitted from curated snapshot |",
            "",
            "## 2. Verification Status & Scope Invariants",
            f"- **Verified Scope:** `{', '.join(out['verified_scope']) if out['verified_scope'] else 'NONE'}`",
            f"- **Unverified Scope:** `{', '.join(out['unverified_scope']) if out['unverified_scope'] else 'NONE'}`",
            f"- **Currentness:** `{out['currentness_status']}`",
            f"- **Legal Applicability:** `{out['applicability_status']}`",
            f"- **Audit Notes:** {out['notes']}",
            "",
            "## 3. Epistemic Disclosures",
            f"1. **Scope Boundary:** {report['epistemic_disclosures']['scope_limitation']}",
            f"2. **Currentness Invariant:** {report['epistemic_disclosures']['currentness_boundary']}",
            f"3. **Applicability Invariant:** {report['epistemic_disclosures']['applicability_boundary']}",
            "",
            "## 4. Section-by-Section Alignment Results",
            "",
            "| Section | Heading | Match Type | Snapshot Len | Reference Len | Notes |",
            "|---|---|---|---|---|---|"
        ]

        for s in report["sections"]:
            match_icon = "✅" if s["match_type"] in ("EXACT_TEXT_MATCH", "NORMALIZED_TEXT_MATCH") else "⚠️"
            lines.append(
                f"| `{s['section_number']}` | {s['heading']} | "
                f"{match_icon} `{s['match_type']}` | "
                f"{s['char_count_snapshot']} | {s['char_count_reference']} | "
                f"{s['notes']} |"
            )

        # Append unified diffs for differing sections
        diff_sections = [s for s in report["sections"] if s["match_type"] == "TEXT_DIFFERENCE"]
        if diff_sections:
            lines.extend([
                "",
                "## 5. Textual Divergence Details (Unified Diffs)",
                ""
            ])
            for ds in diff_sections:
                lines.extend([
                    f"### Section {ds['section_number']}: {ds['heading']}",
                    "```diff"
                ])
                lines.extend([d.rstrip() for d in ds["diff"]])
                lines.extend(["```", ""])

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
