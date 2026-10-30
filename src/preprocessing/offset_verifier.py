"""
Extraction Offset and Literal-Placeholder Integrity Verifier for Strategy A (RDR-002, Step 3).

Enforces:
1. Python Unicode character index offset semantics:
   raw_text[char_start:char_end] == expected_extracted_text (NEVER UTF-8 byte offsets).
2. Robust Unicode boundary validation handling multi-byte characters (e.g. currency ₹, em-dashes —, Indic scripts).
3. Exact preservation of literal placeholders (names, dates, amounts, bracketed options, underlines, redaction tokens).
4. Balanced defect classification: missing terminal punctuation or external references are treated
   as WARNINGS; only genuine structural corruption (hyphenated word breaks, dangling operators, unclosed brackets)
   triggers ERRORS.
"""

import re
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional, Set
from pydantic import BaseModel, Field, ConfigDict


class OffsetVerificationStatus(str, Enum):
    """Status classification of character offset verification."""
    VERIFIED_EXACT = "VERIFIED_EXACT"
    MISMATCH_TEXT = "MISMATCH_TEXT"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    INVERTED_OFFSETS = "INVERTED_OFFSETS"
    NON_INTEGER_OFFSETS = "NON_INTEGER_OFFSETS"


class PlaceholderCategory(str, Enum):
    """Classification of literal drafting placeholders under Policy A."""
    BRACKETED_FIELD = "BRACKETED_FIELD"        # e.g. "[Insert Name of Contractor]"
    DRAFTING_OPTION = "DRAFTING_OPTION"        # e.g. "[Option A: Institutional Arbitration]"
    REDACTION_TOKEN = "REDACTION_TOKEN"        # e.g. "[***]", "[REDACTED]"
    NUMERICAL_AMOUNT = "NUMERICAL_AMOUNT"      # e.g. "[INR 50,00,000]", "[10%]"
    DATE_PLACEHOLDER = "DATE_PLACEHOLDER"      # e.g. "[DD/MM/YYYY]", "[Insert Date]"
    BLANK_UNDERLINE = "BLANK_UNDERLINE"        # e.g. "___________"


class PlaceholderOccurrence(BaseModel):
    """Structured representation of a literal placeholder occurrence."""
    model_config = ConfigDict(extra="forbid")

    placeholder_text: str
    category: PlaceholderCategory
    char_start: int
    char_end: int


class VerificationReport(BaseModel):
    """Comprehensive report on offset slicing and placeholder preservation."""
    is_valid: bool
    status: OffsetVerificationStatus
    slice_matches: bool
    extracted_slice: Optional[str] = None
    expected_text: Optional[str] = None
    placeholders_detected: List[PlaceholderOccurrence] = Field(default_factory=list)
    placeholders_preserved: bool = True
    missing_placeholders: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class OffsetAndPlaceholderVerifier:
    """
    Verifies that text extraction preserves byte-exact Python Unicode offsets
    and maintains literal placeholder tokens without alteration or synthetic hallucination.
    """

    # Regex patterns for Policy A literal placeholders
    BRACKETED_PATTERN = re.compile(r"\[([A-Za-z0-9_\s\.\-\*:,/\(\)₹%+]{2,})\]")
    REDACTION_PATTERN = re.compile(r"^\[(?:\*{2,}|REDACTED|CONFIDENTIAL)\]$", re.IGNORECASE)
    UNDERLINE_PATTERN = re.compile(r"_{3,}")

    @classmethod
    def verify_character_offset_slice(
        cls,
        raw_text: str,
        start: int,
        end: int,
        expected_text: str,
    ) -> VerificationReport:
        """
        Verifies that raw_text[start:end] equals expected_text using Python Unicode character indices.
        Enforces strict boundary checking and detects multi-byte offset confusion.
        """
        errors = []
        warnings = []

        # 1. Type validation
        if not isinstance(start, int) or not isinstance(end, int):
            return VerificationReport(
                is_valid=False,
                status=OffsetVerificationStatus.NON_INTEGER_OFFSETS,
                slice_matches=False,
                errors=["Character offsets must be integers"]
            )

        # 2. Negative offsets or inverted offsets
        if start < 0 or end < 0:
            return VerificationReport(
                is_valid=False,
                status=OffsetVerificationStatus.OUT_OF_BOUNDS,
                slice_matches=False,
                errors=[f"Negative offset encountered: start={start}, end={end}"]
            )

        if end < start:
            return VerificationReport(
                is_valid=False,
                status=OffsetVerificationStatus.INVERTED_OFFSETS,
                slice_matches=False,
                errors=[f"Inverted offsets: end ({end}) cannot be less than start ({start})"]
            )

        # 3. Out of bounds checking
        text_len = len(raw_text)
        if start > text_len or end > text_len:
            return VerificationReport(
                is_valid=False,
                status=OffsetVerificationStatus.OUT_OF_BOUNDS,
                slice_matches=False,
                errors=[f"Offset out of bounds: range ({start}, {end}) exceeds text length {text_len}"]
            )

        # 4. Extract slice
        extracted_slice = raw_text[start:end]
        slice_matches = (extracted_slice == expected_text)

        if not slice_matches:
            # Check if failure is due to UTF-8 byte offset confusion
            try:
                raw_bytes = raw_text.encode("utf-8")
                if end <= len(raw_bytes):
                    byte_slice = raw_bytes[start:end].decode("utf-8", errors="ignore")
                    if byte_slice == expected_text:
                        errors.append(
                            "Offset Encoding Confusion Detected: Provided offsets correspond to UTF-8 byte "
                            f"offsets ({start}:{end} in bytes), but Python character slicing raw_text[{start}:{end}] "
                            "was evaluated. Offsets must strictly use Python Unicode character indices."
                        )
            except Exception:
                pass

            errors.append(
                f"Slice text mismatch: raw_text[{start}:{end}] produced {repr(extracted_slice)}, "
                f"expected {repr(expected_text)}"
            )
            return VerificationReport(
                is_valid=False,
                status=OffsetVerificationStatus.MISMATCH_TEXT,
                slice_matches=False,
                extracted_slice=extracted_slice,
                expected_text=expected_text,
                errors=errors,
                warnings=warnings
            )

        # 5. Check literal placeholders in extracted text
        placeholders = cls.detect_literal_placeholders(expected_text)

        return VerificationReport(
            is_valid=True,
            status=OffsetVerificationStatus.VERIFIED_EXACT,
            slice_matches=True,
            extracted_slice=extracted_slice,
            expected_text=expected_text,
            placeholders_detected=placeholders,
            placeholders_preserved=True,
            errors=errors,
            warnings=warnings
        )

    @classmethod
    def detect_literal_placeholders(cls, text: str) -> List[PlaceholderOccurrence]:
        """
        Detects all literal placeholders within text and categorizes them.
        """
        placeholders = []
        if not text:
            return placeholders

        # 1. Bracketed placeholders
        for match in cls.BRACKETED_PATTERN.finditer(text):
            full_match = match.group(0)
            inner_content = match.group(1).strip()
            start, end = match.start(), match.end()

            # Categorize
            if cls.REDACTION_PATTERN.match(full_match):
                category = PlaceholderCategory.REDACTION_TOKEN
            elif any(kw in inner_content.lower() for kw in ("option", "alternative", "opt")):
                category = PlaceholderCategory.DRAFTING_OPTION
            elif any(kw in inner_content.lower() for kw in ("date", "dd/mm/yyyy", "yyyy", "month")):
                category = PlaceholderCategory.DATE_PLACEHOLDER
            elif any(kw in inner_content for kw in ("INR", "Rs", "%", "Crore", "Lakh", "$")) or any(c.isdigit() for c in inner_content):
                category = PlaceholderCategory.NUMERICAL_AMOUNT
            else:
                category = PlaceholderCategory.BRACKETED_FIELD

            placeholders.append(PlaceholderOccurrence(
                placeholder_text=full_match,
                category=category,
                char_start=start,
                char_end=end
            ))

        # 2. Blank underlines
        for match in cls.UNDERLINE_PATTERN.finditer(text):
            placeholders.append(PlaceholderOccurrence(
                placeholder_text=match.group(0),
                category=PlaceholderCategory.BLANK_UNDERLINE,
                char_start=match.start(),
                char_end=match.end()
            ))

        return placeholders

    @classmethod
    def verify_placeholder_preservation(
        cls,
        original_text: str,
        processed_text: str,
    ) -> Tuple[bool, List[PlaceholderOccurrence], List[str], List[str]]:
        """
        Verifies that all literal placeholders detected in original_text remain
        verbatim in processed_text without alteration or synthetic resolution.
        """
        detected = cls.detect_literal_placeholders(original_text)
        missing = []
        errors = []

        for p in detected:
            if p.placeholder_text not in processed_text:
                missing.append(p.placeholder_text)
                errors.append(
                    f"Policy A Violation: Placeholder '{p.placeholder_text}' ({p.category.value}) "
                    "was stripped, normalized away, or synthetically altered in processed text."
                )

        preserved = len(missing) == 0
        return preserved, detected, missing, errors

    @classmethod
    def evaluate_terminal_and_dangling_cues(cls, text: str) -> Tuple[bool, List[str], List[str]]:
        """
        Evaluates terminal cues and references in clause text.
        Adheres to RDR-002: Missing terminal punctuation or external references are
        treated as WARNINGS. Only genuine structural truncation (hyphenated word break,
        dangling binary operator, unclosed open brackets) triggers ERRORS.
        """
        warnings = []
        errors = []

        if not text or not text.strip():
            errors.append("Empty or whitespace-only clause text")
            return False, warnings, errors

        cleaned = text.strip()

        # 1. Genuine Structural Truncation Checks (ERRORS)
        if re.search(r"[A-Za-z]+-\s*$", cleaned):
            errors.append("Structural Truncation: Text terminates with an incomplete hyphenated word break.")

        if re.search(r"[\/\\+=&|]\s*$", cleaned):
            errors.append("Structural Truncation: Text terminates with a dangling operator or slash.")

        open_brackets = cleaned.count("[") - cleaned.count("]")
        if open_brackets > 0 and not cleaned.endswith("]"):
            errors.append("Structural Truncation: Text terminates with an unclosed opening bracket '['.")

        # 2. Legitimate Drafting Variations (WARNINGS ONLY)
        # Missing terminal punctuation (common in headings and list items)
        if not cleaned.endswith((".", ";", ":", ")", "]", '"', "'", "”")):
            warnings.append(
                "Notice: Clause text does not conclude with terminal punctuation (period or semicolon). "
                "Permitted for headings or list items unless accompanied by structural truncation."
            )

        # Apparent dangling reference to external schedule or annexure
        if re.search(r"\b(?:as\s+set\s+forth\s+in|specified\s+in|referred\s+to\s+in)\s+(?:Schedule|Annexure|Appendix)\b", cleaned, re.IGNORECASE):
            warnings.append(
                "Reference Notice: Clause contains a reference to an external schedule or annexure. "
                "Verify schedule incorporation if substantive liability depends upon it."
            )

        is_valid = len(errors) == 0
        return is_valid, warnings, errors
