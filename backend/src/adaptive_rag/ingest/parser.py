"""Turn raw documents into typed Elements."""

import re

from adaptive_rag.schemas import Element

# A blank line: a newline, any spaces or tabs, then another newline.
_BLANK_LINE = re.compile(r"\n\s*\n")


def parse_txt(text: str) -> list[Element]:
    """Split plain text into paragraphs at blank lines."""
    blocks = _BLANK_LINE.split(text)
    return [
        Element(type="paragraph", text=block.strip())
        for block in blocks
        if block.strip()
    ]
