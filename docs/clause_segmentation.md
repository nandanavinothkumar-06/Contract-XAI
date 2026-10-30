# Clause and Section Segmentation Layer

## Problem Definition
Legal contract segmentation differs fundamentally from standard NLP sentence splitting. A sentence boundary is insufficient because a single legal clause can span multiple sentences or physical lines, and hierarchical structure (e.g. `1.1(a)(i)`) defines semantic scope. This layer identifies observable document structure. It does not determine legal meaning or legal risk.

## Algorithm & Structural Rules
The segmentation pipeline relies on conservative, deterministic rules applied to preprocessed text:
1. **Structural Scanner**: Extracts non-whitespace blocks split by structural delimiters (`\n\n`). It preserves exact character offsets by avoiding string mutation during extraction.
2. **Numbering Detection**: Matches common legal enumeration patterns (`Article IV.`, `Section 5`, `1.1`, `(a)`, `(i)`).
3. **Heading Detection**: Heuristically detects headings based on casing, length, numbering, and trailing punctuation.
4. **Definition Detection**: Uses structural heuristics (`"Term" means...`) to flag definitions.

## Hierarchy Representation
The `build_hierarchy` module interprets detected numbering strings into a structured tree (parent/child relationships) with an explicit `level` and hierarchical `path` for each segment.

## Offset & Provenance Handling
- `original_start` and `original_end` offsets mapping to the original dataset text are maintained. Offsets are validated against the source-text substring invariant.
- Existing CUAD or ContractNLI evidence spans are left untouched.
- `processed_start` maps to the normalized text buffer. If preprocessing destroyed 1:1 mapping length equivalence, it safely defaults to `None`.
- Each segment traces back to its parent `DatasetRecord` via `source_document_id`. Offsets were verified for the tested structural fixtures.

## Quality Flags
The pipeline identifies issues and surfaces them in `quality_flags`:
- `INVALID_OFFSET` (start >= end)
- `OVERLAPPING_SEGMENTS` (structural bounding box collision)
- `LOW_COVERAGE` (when >50% of original text byte boundaries are unmapped to any segment).

## Limitations
This system operates on raw text heuristics. It does not perform OCR recovery on broken line breaks or use semantic ML classifiers.

## Test Strategy
The test suite utilizes synthetic non-data-leaking string fixtures to validate regex numbering patterns, hierarchy trees, definition capture, offset bounds logic, and strict output determinism.
