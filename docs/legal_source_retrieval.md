# Legal Source Retrieval

## 1. Purpose
The Legal Source Retrieval module is an authoritative-source retrieval layer designed to find potentially relevant legal-source material for a given contract clause or risk finding. It provides decision-support evidence for human or legal review.

## 2. Scope & Verified Source Registry
The system manages a verified source registry mapping `LegalSource` objects uniquely by `source_id`. It stores essential metadata including title, jurisdiction, country, `jurisdiction_level` (e.g., CENTRAL, STATE, REGULATORY), language, publisher, source type, and verification status.

## 3. Actual Source-Content Ingestion
> [!IMPORTANT]
> **Registration of an authoritative source does not by itself constitute retrieval of its legal content.**
Currently, ACTUAL SOURCE CONTENT INGESTION = NOT_AVAILABLE. The system tests against synthetic fixtures to validate the retrieval mechanism, but actual verified India Code content has not been ingested. Passage-level retrieval will explicitly return empty results or unavailable states when querying registered sources that lack indexed content.

## 4. Authority/Verification Status
Sources must have a defined `VerificationStatus` (e.g., `VERIFIED_OFFICIAL`, `VERIFIED_AUTHORITATIVE`, `USER_SUPPLIED`, `UNVERIFIED`). The system operates in a `verified_only` configuration by default, preventing unverified or user-supplied sources from being surfaced as authoritative results.

## 5. Jurisdiction Level
Each query supports jurisdiction parameters including `country` (e.g., `IN`) and `jurisdiction_level` (e.g., `CENTRAL`, `STATE`). If jurisdiction filtering is enforced by the configuration, legal sources failing to match the precise country and jurisdiction level are strictly excluded. 

## 6. Currentness
> [!WARNING]
> The `retrieved_at` timestamp is explicitly NOT a legal currentness guarantee.
Sources are tracked via `CurrentnessStatus` (e.g., `CURRENTNESS_VERIFIED`, `CURRENTNESS_UNVERIFIED`, `HISTORICAL`, `UNKNOWN`). If the source does not provide sufficient information to establish legal validity at present, it defaults to `CURRENTNESS_UNVERIFIED`. The system makes no "current law" claims.

## 7. Passage-Level Retrieval Method
> [!CAUTION]
> The retrieval system employs a `LEXICAL` method as an engineering baseline (punctuation-stripped word intersection).
The retrieval score represents lexical similarity score, NOT "semantic legal relevance", "legal confidence", or "legal applicability". It has not been empirically validated as a legal relevance measure.

## 8. Source Metadata vs Content Separation
The legal-source index distinguishes SOURCE METADATA from SOURCE CONTENT. A registry entry alone is not treated as a retrievable legal passage. A result only contains `passage_text` when actual source content is physically indexed and available. Placeholder text is never generated.

## 9. Provenance
Every `LegalSourceRetrievalResult` retains unbroken provenance to its origin. The `source_id`, `legal_document_id`, `section_identifier`, and passage offsets (`passage_start`, `passage_end`) are passed directly from the authoritative record.

## 10. Legal-Safety Limitations
The retrieval system is explicitly designed for evidentiary support.
- MODEL OUTPUT: "The retrieval system ranked this legal source as potentially relevant."
- NOT: "The law applies to this clause."
Retrieved legal material must be reviewed by a qualified legal professional before being used for legal conclusions or advice.

## 11. Experimental-Result Status
PROJECT EXPERIMENTAL RESULTS = NONE.
No benchmarking or experimental extraction claims have been performed using real legal data due to lack of validated legal labels and unavailable dataset resources. Synthetic tests validate software functionality only.
