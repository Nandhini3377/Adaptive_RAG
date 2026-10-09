"""Data shapes passed between modules."""

from typing import Literal

from pydantic import BaseModel

ElementType = Literal["heading", "paragraph", "list", "table"]


class Element(BaseModel):
    """One typed piece of a parsed document: heading, paragraph, table, or list."""

    type: ElementType
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


class Citation(BaseModel):
    """One evidence chunk the answer refers to as [n]."""

    number: int
    chunk_id: str
    document_id: str
    section: str = ""
    page: int | None = None
    text: str


class Answer(BaseModel):
    """A generated answer, the chunks it cites, and what it cost."""

    text: str
    citations: list[Citation] = []
    insufficient_evidence: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_inr: float = 0.0


Mode = Literal["vector", "hybrid", "graph", "graph_hybrid"]


class GraphPath(BaseModel):
    """A chain of entities and relations found in the graph, e.g. A -DEPENDS_ON-> B."""

    nodes: list[str]
    relations: list[str]
    chunk_ids: list[str] = []


class RetrievalResult(BaseModel):
    """What a retriever found: ranked chunks, plus graph paths in graph modes."""

    hits: list[SearchHit]
    graph_paths: list[GraphPath] = []
