"""Step 1a, the quick scan: structure counts and regex checks over the full text.

No LLM, no embeddings: this runs in milliseconds even on a 100-page PDF (FR8, FR9).
"""

import math
import re

from adaptive_rag.config import settings
from adaptive_rag.schemas import DocumentProfile, Element, Section

# "see Section 4.2", "as defined in", "refer to Appendix B"
CROSS_REFERENCE = re.compile(
    r"\b(?:see|refer to|as (?:defined|described|shown) in|according to|"
    r"(?:in|under) (?:section|chapter|appendix))\b"
    r"|\b(?:section|chapter|appendix|table|figure)\s+[A-Z0-9]+(?:\.\d+)*\b",
    re.IGNORECASE,
)

# Phrases that state a relationship between two things
RELATIONSHIP = re.compile(
    r"\b(?:depends? on|depending on|calls|called by|reports? to|owned by|owns|"
    r"part of|integrates? with|connects? to|managed by|maintained by|belongs to|"
    r"consumes|publishes to|subscribes to|sends? to|reads? from|writes? to|"
    r"relies on|requires|is used by|uses|built on|replaced by|upstream of|downstream of)\b",
    re.IGNORECASE,
)

# Codes and IDs: AUTH-403, INC-2041, v2.1.0, user_id, getUserById, SOC2, ISO 27001
IDENTIFIER = re.compile(
    r"\b[A-Z]{2,}[-_]\d+[A-Z0-9-]*\b"  # AUTH-403, INC-2041
    r"|\bv?\d+\.\d+(?:\.\d+)+\b"  # 2.1.0, v1.2.3
    r"|\bv\d+(?:\.\d+)?\b"  # v2, v2.1
    r"|\b[a-z]+_[a-z0-9_]+\b"  # snake_case
    r"|\b[a-z]+[A-Z][a-zA-Z0-9]+\b"  # camelCase
    r"|\b[A-Z]{2,6}\d*\b"  # acronyms: API, SSO, SOC2
)
# Capitalised words that are not identifiers
_NOT_IDENTIFIERS = frozenset(
    {"I", "A", "OK", "AM", "PM", "US", "UK", "EU", "TODO", "FAQ", "AND", "OR", "NOT"}
    | {"KB", "MB", "GB", "TB"}  # units
)

URL = re.compile(r"https?://\S+")
_WORD = re.compile(r"\b\w+\b")


def group_sections(elements: list[Element]) -> list[Section]:
    """Group elements by heading; text before the first heading is 'Introduction'."""
    sections: list[Section] = []
    for element in elements:
        if element.type == "heading":
            sections.append(Section(id=str(len(sections)), title=element.text, text=""))
            continue
        if not sections:  # text above the first heading
            sections.append(Section(id="0", title="Introduction", text=""))
        current = sections[-1]
        current.text = f"{current.text}\n\n{element.text}" if current.text else element.text
    for section in sections:
        section.relationship_phrases = len(RELATIONSHIP.findall(section.text))
    return [section for section in sections if section.text]


def scan(elements: list[Element], page_count: int | None = None) -> DocumentProfile:
    """Count structure and run pattern checks over the whole document."""
    full_text = "\n".join(element.text for element in elements)
    words = len(_WORD.findall(full_text))
    table_words = sum(len(_WORD.findall(e.text)) for e in elements if e.type == "table")
    per_1000 = 1000 / words if words else 0.0

    identifiers = [
        match for match in IDENTIFIER.findall(full_text) if match not in _NOT_IDENTIFIERS
    ]
    if page_count is None:
        pages = [e.page for e in elements if e.page]
        page_count = max(pages) if pages else max(1, math.ceil(words / settings.words_per_page))

    return DocumentProfile(
        page_count=page_count,
        section_count=len(group_sections(elements)),
        heading_count=sum(e.type == "heading" for e in elements),
        table_count=sum(e.type == "table" for e in elements),
        list_count=sum(e.type == "list" for e in elements),
        link_count=len(URL.findall(full_text)),
        word_count=words,
        cross_ref_rate=round(len(CROSS_REFERENCE.findall(full_text)) * per_1000, 2),
        relationship_phrase_rate=round(len(RELATIONSHIP.findall(full_text)) * per_1000, 2),
        identifier_density=round(len(identifiers) * per_1000, 2),
        table_share=round(table_words / words, 3) if words else 0.0,
    )
