"""Data shapes passed between modules."""

from typing import Literal

from pydantic import BaseModel


class Element(BaseModel):
    """One typed piece of a parsed document: heading, paragraph, table, or list."""

    type: Literal["list", "table", "heading", "paragraph"]
    text: str
    page: int | None = None
    section: str = ""


class Chunk(BaseModel):
    """One searchable piece of a document."""

    id: str  # UUID string; Qdrant point IDs must be UUIDs or integers
    document_id: str
    owner_id: str
    text: str
    section: str = ""
    page: int | None = None
    element_type: Literal["text", "table"] = "text"


class SearchHit(BaseModel):
    """A chunk returned by a search, with its similarity score."""

    chunk: Chunk
    score: float
