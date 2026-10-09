"""Group parsed Elements into searchable Chunks.

Rules (PRD FR17):
- A chunk never mixes two sections.
- A table is always one chunk on its own, even if it is long.
- Paragraphs and lists are packed together up to `max_chars`; a single
  paragraph longer than that is split at sentence boundaries.
"""

import re
import uuid

from adaptive_rag.config import settings
from adaptive_rag.schemas import Chunk, Element

# Fixed namespace so the same document always gets the same chunk IDs.
_CHUNK_ID_NAMESPACE = uuid.UUID("6f1c2a52-9a59-4c4e-9a43-3c1f1f0f2b7e")

# Split after ., ! or ? when followed by whitespace.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def chunk_elements(
    elements: list[Element],
    document_id: str,
    owner_id: str,
    max_chars: int | None = None,
) -> list[Chunk]:
    """Turn a document's elements into chunks ready to embed."""
    limit = max_chars or settings.chunk_max_chars
    chunks: list[Chunk] = []
    buffer: list[Element] = []  # text elements waiting to become one chunk

    def add(text: str, first: Element, element_type: str = "text") -> None:
        chunk_id = uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{document_id}:{len(chunks)}")
        chunks.append(
            Chunk(
                id=str(chunk_id),
                document_id=document_id,
                owner_id=owner_id,
                text=text,
                section=first.section,
                page=first.page,
                element_type=element_type,
            )
        )

    def flush() -> None:
        if buffer:
            add("\n\n".join(e.text for e in buffer), buffer[0])
            buffer.clear()

    for element in elements:
        if buffer and element.section != buffer[0].section:
            flush()  # new section: never mix sections
        if element.type == "heading":
            continue  # its text already lives in each chunk's `section`
        if element.type == "table":
            flush()
            add(element.text, element, "table")
            continue
        if len(element.text) > limit:
            flush()
            for piece in _split_long_text(element.text, limit):
                add(piece, element)
            continue
        if buffer and _buffer_size(buffer) + 2 + len(element.text) > limit:
            flush()  # adding this element would make the chunk too big
        buffer.append(element)

    flush()
    return chunks


def _buffer_size(buffer: list[Element]) -> int:
    """Length of the buffer's text once joined with blank lines."""
    return sum(len(e.text) for e in buffer) + 2 * (len(buffer) - 1)


def _split_long_text(text: str, limit: int) -> list[str]:
    """Pack whole sentences into pieces of at most `limit` characters."""
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        for part in _hard_split(sentence, limit):
            if current and len(current) + 1 + len(part) > limit:
                pieces.append(current)
                current = ""
            current = f"{current} {part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def _hard_split(sentence: str, limit: int) -> list[str]:
    """Split one over-long sentence at spaces (last resort)."""
    if len(sentence) <= limit:
        return [sentence]
    parts: list[str] = []
    current = ""
    for word in sentence.split():
        if current and len(current) + 1 + len(word) > limit:
            parts.append(current)
            current = ""
        current = f"{current} {word}" if current else word
    if current:
        parts.append(current)
    return parts
