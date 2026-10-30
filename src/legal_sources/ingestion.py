"""
Statutory Corpus Ingestion and Structural Legal Parser.

Ingests verified Indian legislative source snapshots, validates SHA-256 checksums,
parses official section boundaries without inventing text, and generates traceable
LegalPassage records with exact character offsets.
"""

import os
import re
import json
import hashlib
from typing import List, Dict, Tuple, Optional
from src.legal_sources.schema import LegalSource, LegalPassage
from src.legal_sources.provenance import (
    VerificationStatus,
    SourceCompletenessStatus,
    AmendmentCoverageStatus,
    VerificationMethod,
    SourceType,
    JurisdictionLevel,
    CurrentnessStatus,
    CommencementStatus,
)
from src.legal_sources.citation import construct_statutory_citation

# Matches patterns such as:
# Section 10. What agreements are contracts.—All agreements are contracts...
# Section 10A. Validity of contracts formed through electronic means.—Where in a contract...
# Section 27. Agreement in restraint of trade, void.—Every agreement...
SECTION_PATTERN = re.compile(
    r"(?m)^Section\s+([0-9]+[A-Za-z]?)\.\s*([^—\n]+?)(?:—|--|-|\.\s*—|\.)\s*(.*?)(?=(?:^Section\s+[0-9]+[A-Za-z]?\.|\Z))",
    re.DOTALL
)

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def normalize_text_for_search(text: str) -> str:
    """
    Separate normalized search representation; never alters the immutable passage_text.
    """
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(clean.split())


class StatutoryIngestionEngine:
    """
    Handles loading, integrity verification, structural parsing, and passage generation
    for authoritative Indian statutes.
    """
    def __init__(self, snapshots_dir: str = "data/legal_sources/snapshots"):
        self.snapshots_dir = snapshots_dir

    def verify_snapshot_integrity(self, snapshot_path: str, expected_sha256: Optional[str] = None) -> Tuple[bool, str, int]:
        """
        Verifies file existence and SHA-256 checksum.
        Returns: (is_valid, computed_hash, file_size)
        """
        if not os.path.exists(snapshot_path):
            return False, "", 0
        with open(snapshot_path, "rb") as f:
            data = f.read()
        computed = compute_sha256(data)
        if expected_sha256 and computed.lower() != expected_sha256.lower():
            return False, computed, len(data)
        return True, computed, len(data)

    def parse_statute_text(
        self,
        source: LegalSource,
        raw_text: str
    ) -> Tuple[List[LegalPassage], List[str]]:
        """
        Extracts structural sections from official statutory text.
        Preserves exact text and character offsets.
        """
        passages: List[LegalPassage] = []
        warnings: List[str] = []

        matches = list(SECTION_PATTERN.finditer(raw_text))
        if not matches:
            warnings.append(f"No sections detected using standard pattern for {source.source_id}")
            return passages, warnings

        for match in matches:
            sec_num = match.group(1).strip()
            heading = match.group(2).strip()
            body = match.group(3).strip()

            # The exact passage includes heading and body as printed in the official text
            start_offset = match.start()
            end_offset = match.end()
            exact_text = raw_text[start_offset:end_offset].strip()

            # Verify character offset invariant
            assert raw_text[start_offset:start_offset + len(exact_text)] == exact_text, (
                f"Offset invariant violation for Section {sec_num} of {source.source_id}"
            )

            passage_id = f"{source.source_id}_SEC_{sec_num.upper()}"
            sec_identifier = f"Section {sec_num}"

            # Inherit commencement and currentness from source unless provision-specific
            comm_status = source.commencement_status
            curr_status = source.currentness_status

            # Handle specific known exceptions (e.g. DPDP uncommenced substantive provisions)
            if source.source_id == "IN_ACT_2023_22":
                if sec_num == "1":
                    comm_status = CommencementStatus.IN_FORCE
                else:
                    comm_status = CommencementStatus.NOT_COMMENCED

            # IT Act 66A struck down
            if source.source_id == "IN_ACT_2000_21" and sec_num == "66A":
                comm_status = CommencementStatus.REPEALED
                curr_status = CurrentnessStatus.REPEALED_SUPERSEDED

            passage_checksum = compute_sha256(exact_text.encode("utf-8"))

            passage = LegalPassage(
                passage_id=passage_id,
                source_id=source.source_id,
                legal_document_id=source.source_id,
                statute_title=source.title,
                section_identifier=sec_identifier,
                section_number=sec_num,
                heading=heading,
                passage_text=exact_text,
                normalized_text=normalize_text_for_search(exact_text),
                passage_start=start_offset,
                passage_end=start_offset + len(exact_text),
                passage_checksum_sha256=passage_checksum,
                currentness_status=curr_status,
                verification_status=source.verification_status,
                commencement_status=comm_status,
                extraction_warnings=[],
                is_test_fixture=source.is_test_fixture
            )

            # Generate canonical citation
            passage.citation_string = construct_statutory_citation(source, passage)
            passages.append(passage)

        return passages, warnings

    def ingest_source_file(
        self,
        source_meta: Dict,
        file_path: Optional[str] = None
    ) -> Tuple[LegalSource, List[LegalPassage]]:
        """
        Ingests a single statutory source from metadata and snapshot file.
        """
        snapshot_file = file_path or os.path.join(self.snapshots_dir, source_meta.get("snapshot_file", ""))
        expected_sha = source_meta.get("content_checksum_sha256")

        is_valid, computed_sha, file_size = self.verify_snapshot_integrity(snapshot_file, expected_sha)
        warnings: List[str] = list(source_meta.get("extraction_warnings", []))

        if not is_valid and expected_sha:
            warnings.append(f"Checksum mismatch: expected {expected_sha}, got {computed_sha}")

        if not os.path.exists(snapshot_file):
            raise FileNotFoundError(f"Statutory snapshot file not found: {snapshot_file}")

        with open(snapshot_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Parse completeness and amendment status with safe defaults
        completeness_raw = source_meta.get("source_completeness_status", "CURATED_EXTRACT")
        try:
            completeness_enum = SourceCompletenessStatus(completeness_raw)
        except Exception:
            completeness_enum = SourceCompletenessStatus.CURATED_EXTRACT

        amendment_raw = source_meta.get("amendment_coverage_status", "UNKNOWN")
        try:
            amendment_enum = AmendmentCoverageStatus(amendment_raw)
        except Exception:
            amendment_enum = AmendmentCoverageStatus.UNKNOWN

        method_raw = source_meta.get("verification_method")
        try:
            method_enum = VerificationMethod(method_raw) if method_raw else VerificationMethod.LOCAL_HASH_AND_METADATA_VALIDATED
        except Exception:
            method_enum = VerificationMethod.LOCAL_HASH_AND_METADATA_VALIDATED

        source = LegalSource(
            source_id=source_meta["source_id"],
            canonical_title=source_meta.get("canonical_title", source_meta.get("title")),
            title=source_meta["title"],
            short_title=source_meta.get("short_title"),
            act_number=source_meta.get("act_number"),
            jurisdiction=source_meta.get("jurisdiction", "India - Central"),
            jurisdiction_level=JurisdictionLevel(source_meta.get("jurisdiction_level", "CENTRAL")),
            country=source_meta.get("country", "IN"),
            instrument_type=source_meta.get("instrument_type", "CENTRAL_ACT"),
            source_type=SourceType(source_meta.get("source_type", "STATUTE")),
            issuing_authority=source_meta.get("issuing_authority", source_meta.get("publisher", "Government of India")),
            publisher=source_meta.get("publisher", "Government of India"),
            authoritative_source_url=source_meta.get("authoritative_source_url", source_meta.get("official_url")),
            official_url=source_meta.get("official_url"),
            source_file=source_meta.get("source_file", source_meta.get("snapshot_file", os.path.basename(snapshot_file))),
            source_snapshot_path=snapshot_file,
            source_format=source_meta.get("source_format", "txt"),
            source_language=source_meta.get("source_language", source_meta.get("language", "en")),
            language=source_meta.get("language", "en"),
            source_scope=source_meta.get("source_scope", "Curated commercial contract provisions (extract)"),
            covered_sections_or_provisions=source_meta.get("covered_sections_or_provisions", []),
            publication_or_version_date=source_meta.get("publication_or_version_date", source_meta.get("enactment_date")),
            effective_from=source_meta.get("effective_from", source_meta.get("commencement_date")),
            effective_until=source_meta.get("effective_until"),
            last_checked_at=source_meta.get("last_checked_at", source_meta.get("retrieved_at", "2026-10-17T12:00:00Z")),
            last_verified_at=source_meta.get("last_verified_at", source_meta.get("review_timestamp")),
            verification_status=VerificationStatus(source_meta.get("verification_status", "PARTIALLY_VERIFIED")),
            verification_method=method_enum,
            verification_notes=source_meta.get("verification_notes", source_meta.get("notes")),
            source_sha256=computed_sha,
            content_checksum_sha256=computed_sha,
            authoritative_reference_sha256=source_meta.get("authoritative_reference_sha256"),
            source_completeness_status=completeness_enum,
            amendment_coverage_status=amendment_enum,
            commencement_status=CommencementStatus(source_meta.get("commencement_status", "IN_FORCE")),
            currentness_status=CurrentnessStatus(source_meta.get("currentness_status", "COMMENCED_FULL")),
            applicability_limitations=source_meta.get("applicability_limitations"),
            reviewer_status=source_meta.get("reviewer_status", "ADVOCATE_REVIEWED" if source_meta.get("reviewed_by_human") else "PENDING_REVIEW"),
            reviewer_notes=source_meta.get("reviewer_notes"),
            effective_date=source_meta.get("commencement_date"),
            enactment_date=source_meta.get("enactment_date"),
            commencement_date=source_meta.get("commencement_date"),
            retrieved_at=source_meta.get("retrieved_at", "2026-10-15T00:00:00Z"),
            version_identifier=source_meta.get("version_identifier"),
            reviewed_by_human=source_meta.get("reviewed_by_human", False),
            reviewer_id=source_meta.get("reviewer_id"),
            review_timestamp=source_meta.get("review_timestamp"),
            extraction_method="STRUCTURED_LEGAL_PARSER",
            extraction_warnings=warnings,
            notes=source_meta.get("notes"),
            enabled=True,
            is_test_fixture=source_meta.get("is_test_fixture", False)
        )

        passages, parse_warnings = self.parse_statute_text(source, raw_text)
        source.extraction_warnings.extend(parse_warnings)

        # If covered sections were not in metadata, populate from parsed passages
        if not source.covered_sections_or_provisions and passages:
            source.covered_sections_or_provisions = [p.section_number for p in passages if p.section_number]

        return source, passages

    def ingest_corpus_from_manifest(
        self,
        manifest_path: str = "data/legal_sources/corpus_manifest.json"
    ) -> Tuple[List[LegalSource], List[LegalPassage]]:
        """
        Loads and parses all authoritative statutory sources listed in the manifest.
        """
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        sources: List[LegalSource] = []
        all_passages: List[LegalPassage] = []

        for src_meta in manifest.get("official_sources", []):
            snapshot_path = os.path.join(self.snapshots_dir, src_meta.get("snapshot_file", ""))
            source, passages = self.ingest_source_file(src_meta, snapshot_path)
            sources.append(source)
            all_passages.extend(passages)

        return sources, all_passages
