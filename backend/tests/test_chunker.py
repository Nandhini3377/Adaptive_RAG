"""Tests for structure-aware chunking."""

from adaptive_rag.ingest.chunker import chunk_elements
from adaptive_rag.ingest.parser import parse_markdown
from adaptive_rag.schemas import Element

HANDBOOK_MD = """# Leave Policy

Employees receive 20 days of annual leave.

Unused days carry over.

- Sick leave: 10 days
- Casual leave: 5 days

| Type | Days |
|------|------|
| Sick | 10   |

# Security

Never share your password.
"""


def chunk(elements, max_chars=1500):
    return chunk_elements(
        elements, document_id="handbook", owner_id="alice", max_chars=max_chars
    )


def test_small_section_text_packs_into_one_chunk():
    """Short paragraphs and lists in one section share a chunk."""
    chunks = chunk(parse_markdown(HANDBOOK_MD))
    first = chunks[0]
    assert first.section == "Leave Policy"
    assert first.text == (
        "Employees receive 20 days of annual leave.\n\n"
        "Unused days carry over.\n\n"
        "- Sick leave: 10 days\n- Casual leave: 5 days"
    )


def test_chunks_never_cross_sections():
    """Text from 'Security' never lands in a 'Leave Policy' chunk."""
    chunks = chunk(parse_markdown(HANDBOOK_MD))
    assert [c.section for c in chunks] == ["Leave Policy", "Leave Policy", "Security"]
    assert all("password" not in c.text for c in chunks if c.section == "Leave Policy")


def test_table_is_its_own_whole_chunk():
    """A table is never merged with text and never cut, even over the limit."""
    chunks = chunk(parse_markdown(HANDBOOK_MD), max_chars=20)
    tables = [c for c in chunks if c.element_type == "table"]
    assert len(tables) == 1
    assert tables[0].text == "| Type | Days |\n|------|------|\n| Sick | 10   |"


def test_headings_are_not_chunks():
    """Heading text is kept in `section`, not as a chunk of its own."""
    chunks = chunk(parse_markdown(HANDBOOK_MD))
    assert all(c.text not in ("Leave Policy", "Security") for c in chunks)


def test_text_is_packed_up_to_the_limit():
    """When the next paragraph would overflow, a new chunk starts."""
    elements = [Element(type="paragraph", text="x" * 40) for _ in range(3)]
    chunks = chunk(elements, max_chars=100)
    assert [len(c.text) for c in chunks] == [82, 40]  # 40 + 2 (blank line) + 40


def test_long_paragraph_splits_at_sentences():
    """A paragraph over the limit is cut between sentences, not mid-sentence."""
    text = "First sentence here. Second sentence here. Third sentence here."
    chunks = chunk([Element(type="paragraph", text=text)], max_chars=45)
    assert [c.text for c in chunks] == [
        "First sentence here. Second sentence here.",
        "Third sentence here.",
    ]


def test_very_long_sentence_splits_at_spaces():
    """A single sentence over the limit is cut at word boundaries."""
    text = " ".join(["word"] * 30)  # 149 characters, no full stops
    chunks = chunk([Element(type="paragraph", text=text)], max_chars=50)
    assert all(len(c.text) <= 50 for c in chunks)
    assert " ".join(c.text for c in chunks) == text


def test_chunk_metadata_and_stable_ids():
    """Chunks carry document, owner, and page; IDs repeat on re-chunking."""
    elements = [Element(type="paragraph", text="Hello.", section="Intro", page=3)]
    first = chunk(elements)
    again = chunk(elements)
    assert first[0].document_id == "handbook"
    assert first[0].owner_id == "alice"
    assert first[0].page == 3
    assert first[0].id == again[0].id


def test_no_elements_gives_no_chunks():
    """An empty document produces no chunks."""
    assert chunk([]) == []
