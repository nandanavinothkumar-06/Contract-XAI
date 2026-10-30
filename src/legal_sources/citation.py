"""
Citation Engine for Authoritative Indian Statutes.

Constructs canonical, verifiable Indian legal citations strictly from stored metadata.
Guarantees that no citation strings or section numbers are fabricated or hallucinated.
"""

from typing import Optional
from src.legal_sources.schema import LegalSource, LegalPassage

def construct_statutory_citation(
    source: LegalSource,
    passage: LegalPassage
) -> str:
    """
    Constructs an authoritative statutory citation string from verified source and passage metadata.
    
    Standard Indian legislative format:
    'Section {section}, {title} ({act_number})'
    e.g. 'Section 27, The Indian Contract Act, 1872 (Act No. 9 of 1872)'
    or with subsection:
    'Section 7(1), The Arbitration and Conciliation Act, 1996 (Act No. 26 of 1996)'
    """
    # 1. Section representation
    sec_id = passage.section_identifier or ""
    if passage.section_number:
        sec_label = f"Section {passage.section_number}"
        if passage.subsection_identifier:
            sec_label = f"{sec_label}({passage.subsection_identifier})"
    elif sec_id.lower().startswith("section"):
        sec_label = sec_id
    elif sec_id.lower().startswith("sec"):
        sec_label = f"Section {sec_id.split()[-1]}" if len(sec_id.split()) > 1 else sec_id
    elif sec_id:
        sec_label = f"Section {sec_id}"
    else:
        sec_label = "Provision"

    # 2. Title representation
    statute_title = source.title or passage.statute_title or "Unknown Statute"
    
    # 3. Act Number representation
    act_num_part = f" ({source.act_number})" if source.act_number else ""

    citation = f"{sec_label}, {statute_title}{act_num_part}"
    return citation.strip()

def format_citation_with_heading(
    source: LegalSource,
    passage: LegalPassage
) -> str:
    """
    Returns citation string accompanied by official marginal heading if available.
    e.g. 'Section 27: Agreement in restraint of trade, void, The Indian Contract Act, 1872 (Act No. 9 of 1872)'
    """
    base_citation = construct_statutory_citation(source, passage)
    if passage.heading:
        # Strip trailing dot/dash
        clean_heading = passage.heading.rstrip(" .—–-")
        return f"{base_citation} [{clean_heading}]"
    return base_citation
