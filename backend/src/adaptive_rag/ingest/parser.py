"""Turn raw documents into typed Elements.

Every format follows the same two steps:
1. A format-specific reader yields raw blocks: (type, text, page).
2. `_assemble` turns them into Elements, stamping each with its section
   (the closest heading above it) and joining list items that belong together.
"""

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

import docx
import pymupdf
from bs4 import BeautifulSoup, Tag
from docx.table import Table as DocxTable
from markdown_it import MarkdownIt

from adaptive_rag.schemas import Element, ElementType

Block = tuple[ElementType, str, int | None]  # (type, text, page number or None)

# A blank line: a newline, any spaces or tabs, then another newline.
_BLANK_LINE = re.compile(r"\n\s*\n")

# CommonMark has no tables, so switch on the GitHub-style table rule.
_MARKDOWN = MarkdownIt("commonmark").enable("table")

# Top-level Markdown blocks we keep, and the Element type each becomes.
_MARKDOWN_BLOCKS: dict[str, ElementType] = {
    "paragraph_open": "paragraph",
    "blockquote_open": "paragraph",
    "fence": "paragraph",
    "code_block": "paragraph",
    "bullet_list_open": "list",
    "ordered_list_open": "list",
    "table_open": "table",
}

# HTML tags that become Elements. Anything nested inside one of these is
# already part of its text, so it is not read again.
_HTML_BLOCKS: dict[str, ElementType] = {
    **{f"h{n}": "heading" for n in range(1, 7)},
    "p": "paragraph",
    "pre": "paragraph",
    "blockquote": "paragraph",
    "ul": "list",
    "ol": "list",
    "table": "table",
}
_HTML_NOISE = ["script", "style", "noscript", "nav", "header", "footer", "aside"]

# A line that starts like a list item: a bullet symbol or "1." / "1)".
_LIST_ITEM = re.compile(r"^\s*([•·▪◦‣\-–*]|\d{1,3}[.)])\s+")

# PDF text this much bigger than normal body text is treated as a heading.
_PDF_HEADING_SIZE_RATIO = 1.15
_PDF_HEADING_MAX_CHARS = 150


def parse_file(path: Path) -> list[Element]:
    """Parse a file, choosing the parser from its extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix in (".html", ".htm"):
        return parse_html(text)
    if suffix in (".md", ".markdown"):
        return parse_markdown(text)
    if suffix == ".txt":
        return parse_txt(text)
    raise ValueError(f"Unsupported file type: {suffix or path.name}")


def parse_txt(text: str) -> list[Element]:
    """Split plain text into paragraphs at blank lines."""
    return _assemble(("paragraph", block, None) for block in _BLANK_LINE.split(text))


def parse_markdown(text: str) -> list[Element]:
    """Split Markdown into headings, paragraphs, lists, and tables.

    Lists and tables keep their original Markdown so they stay whole.
    """
    return _assemble(_markdown_blocks(text))


def parse_html(html: str) -> list[Element]:
    """Split an HTML page into headings, paragraphs, lists, and tables."""
    return _assemble(_html_blocks(html))


def parse_docx(path: Path) -> list[Element]:
    """Split a Word document into headings, paragraphs, lists, and tables."""
    return _assemble(_docx_blocks(path))


def parse_pdf(path: Path) -> list[Element]:
    """Split a PDF into headings, paragraphs, lists, and tables.

    PDFs store positioned text, not structure, so structure is guessed:
    larger or bold short lines are headings, bullet lines are lists, and
    PyMuPDF's table finder detects tables.
    """
    with pymupdf.open(path) as pdf:
        return _assemble(_pdf_blocks(pdf))


# ---------------------------------------------------------------- shared steps


def _assemble(blocks: Iterable[Block]) -> list[Element]:
    """Turn raw blocks into Elements with sections; join adjacent list items."""
    elements: list[Element] = []
    section = ""
    for type_, text, page in blocks:
        text = text.strip()
        if not text:
            continue
        if type_ == "heading":
            section = text
        previous = elements[-1] if elements else None
        if type_ == "list" and previous and previous.type == "list":
            previous.text += "\n" + text  # next item of the same list
            continue
        elements.append(Element(type=type_, text=text, section=section, page=page))
    return elements


def _table_to_markdown(rows: list[list[str]]) -> str:
    """Write table rows as a Markdown table; the first row is the header."""
    rows = [[" ".join(cell.split()) for cell in row] for row in rows if any(row)]
    if not rows:
        return ""
    lines = ["| " + " | ".join(row) + " |" for row in rows]
    lines.insert(1, "|" + "---|" * len(rows[0]))
    return "\n".join(lines)


# ------------------------------------------------------------ format readers


def _markdown_blocks(text: str) -> Iterator[Block]:
    """Yield top-level Markdown blocks as written in the source."""
    lines = text.splitlines()
    tokens = _MARKDOWN.parse(text)
    for i, token in enumerate(tokens):
        # Only top-level blocks; a paragraph inside a list is already covered
        # by the list's source lines.
        if token.level != 0 or token.map is None:
            continue
        if token.type == "heading_open":
            yield "heading", tokens[i + 1].content, None  # next token holds the text
        elif token.type in _MARKDOWN_BLOCKS:
            start, end = token.map
            yield _MARKDOWN_BLOCKS[token.type], "\n".join(lines[start:end]), None


def _html_blocks(html: str) -> Iterator[Block]:
    """Yield HTML block tags in page order, skipping scripts and menus."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_HTML_NOISE):
        tag.decompose()
    for tag in soup.find_all(list(_HTML_BLOCKS)):
        if tag.find_parent(list(_HTML_BLOCKS)):
            continue  # nested, e.g. a <p> inside an <li>
        type_ = _HTML_BLOCKS[tag.name]
        if type_ == "table":
            yield "table", _html_table(tag), None
        elif type_ == "list":
            yield "list", _html_list(tag), None
        elif tag.name == "pre":
            yield "paragraph", tag.get_text(), None  # keep code line breaks
        else:
            yield type_, " ".join(tag.get_text(" ").split()), None


def _html_table(table: Tag) -> str:
    rows = [
        [cell.get_text(" ") for cell in row.find_all(["th", "td"])]
        for row in table.find_all("tr")
    ]
    return _table_to_markdown(rows)


def _html_list(list_tag: Tag) -> str:
    items = list_tag.find_all("li", recursive=False)
    numbered = list_tag.name == "ol"
    return "\n".join(
        f"{f'{n}.' if numbered else '-'} {' '.join(item.get_text(' ').split())}"
        for n, item in enumerate(items, start=1)
    )


def _docx_blocks(path: Path) -> Iterator[Block]:
    """Yield Word paragraphs and tables in document order."""
    document = docx.Document(str(path))
    for item in document.iter_inner_content():
        if isinstance(item, DocxTable):
            rows = [[cell.text for cell in row.cells] for row in item.rows]
            yield "table", _table_to_markdown(rows), None
            continue
        style = item.style.name if item.style is not None else ""
        if style == "Title" or style.startswith("Heading"):
            yield "heading", item.text, None
        elif style.startswith("List"):
            yield "list", f"- {item.text.strip()}", None
        else:
            yield "paragraph", item.text, None


def _pdf_blocks(pdf: pymupdf.Document) -> Iterator[Block]:
    """Yield headings, paragraphs, lists, and tables page by page."""
    pages = [page.get_text("dict", sort=True)["blocks"] for page in pdf]
    body_size = _pdf_body_font_size(pages)

    for page_number, (page, blocks) in enumerate(zip(pdf, pages, strict=True), 1):
        tables = page.find_tables().tables
        table_boxes = [pymupdf.Rect(table.bbox) for table in tables]
        # (top position, block) so text and tables come out in reading order
        found: list[tuple[float, Block]] = [
            (
                box.y0,
                ("table", _table_to_markdown(_clean_rows(t.extract())), page_number),
            )
            for t, box in zip(tables, table_boxes, strict=True)
        ]
        for block in blocks:
            if block["type"] != 0:  # 0 = text; 1 = image
                continue
            box = pymupdf.Rect(block["bbox"])
            if any(box.intersects(table) for table in table_boxes):
                continue  # this text is inside a table, already captured
            found.append((box.y0, _pdf_text_block(block, body_size, page_number)))
        for _, item in sorted(found, key=lambda pair: pair[0]):
            yield item


def _pdf_text_block(block: dict, body_size: float, page_number: int) -> Block:
    """Classify one PDF text block as heading, list, or paragraph."""
    lines = [
        "".join(span["text"] for span in line["spans"]).strip()
        for line in block["lines"]
    ]
    lines = [line for line in lines if line]
    spans = [
        span
        for line in block["lines"]
        for span in line["spans"]
        if span["text"].strip()
    ]
    text = " ".join(lines)
    if not spans or text.isdigit():
        return "paragraph", "", page_number  # empty, or just a page number

    size = max(span["size"] for span in spans)
    all_bold = all(span["flags"] & 16 for span in spans)  # bit 16 = bold
    short = len(text) <= _PDF_HEADING_MAX_CHARS
    if short and (
        size >= body_size * _PDF_HEADING_SIZE_RATIO or (all_bold and len(lines) == 1)
    ):
        return "heading", text, page_number
    if _LIST_ITEM.match(lines[0]):
        return (
            "list",
            "\n".join(_LIST_ITEM.sub("- ", line, count=1) for line in lines),
            page_number,
        )
    return "paragraph", text, page_number


def _pdf_body_font_size(pages: list[list[dict]]) -> float:
    """The font size used for the most characters: normal body text."""
    sizes: Counter[float] = Counter()
    for blocks in pages:
        for block in blocks:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    sizes[round(span["size"], 1)] += len(span["text"].strip())
    return sizes.most_common(1)[0][0] if sizes else 0.0


def _clean_rows(rows: list[list[str | None]]) -> list[list[str]]:
    """Table finders return None for empty or merged cells."""
    return [[cell or "" for cell in row] for row in rows]
