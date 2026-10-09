"""Tests for the document parsers."""

from adaptive_rag.ingest.parser import parse_txt


def test_txt_splits_paragraphs_at_blank_lines():
    """Each blank-line-separated block becomes one paragraph."""
    elements = parse_txt("First para.\n\nSecond para.")
    assert [e.text for e in elements] == ["First para.", "Second para."]
    assert all(e.type == "paragraph" for e in elements)


def test_txt_multiline_paragraph_stays_together():
    """Lines without a blank line between them belong to the same paragraph."""
    elements = parse_txt("First para.\n\nSecond para\nstill second.")
    assert len(elements) == 2
    assert elements[1].text == "Second para\nstill second."


def test_txt_ignores_extra_blank_lines():
    """Leading, trailing, and repeated blank lines create no empty elements."""
    elements = parse_txt("\n\n\nHello\n\n\n\nWorld\n\n")
    assert [e.text for e in elements] == ["Hello", "World"]


def test_txt_blank_line_with_spaces_still_splits():
    """A 'blank' line that contains spaces still separates paragraphs."""
    elements = parse_txt("A\n   \nB")
    assert [e.text for e in elements] == ["A", "B"]


def test_txt_markdown_symbols_are_plain_text():
    """In a .txt file, '#' and '-' are ordinary characters."""
    elements = parse_txt("-5 degrees tonight\n\n#1 priority is safety")
    assert [e.text for e in elements] == ["-5 degrees tonight", "#1 priority is safety"]
    assert all(e.type == "paragraph" for e in elements)


def test_txt_empty_input():
    """Empty or whitespace-only text gives no elements."""
    assert parse_txt("") == []
    assert parse_txt("  \n\n  ") == []
