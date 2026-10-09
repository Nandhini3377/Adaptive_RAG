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


Intent = Literal["facts", "exact_terms", "connections", "compare"]
Strategy = Literal["vector", "hybrid", "graph_hybrid"]


class Section(BaseModel):
    """All elements under one heading, joined; the unit the sampler picks from."""

    id: str  # position in the document, as text ("0", "1", ...)
    title: str
    text: str
    relationship_phrases: int = 0


class DocumentProfile(BaseModel):
    """Signals from the quick scan and the sampled LLM pass (PRD FR8-FR11)."""

    page_count: int = 0
    section_count: int = 0
    heading_count: int = 0
    table_count: int = 0
    list_count: int = 0
    link_count: int = 0
    word_count: int = 0
    cross_ref_rate: float = 0.0  # per 1,000 words
    relationship_phrase_rate: float = 0.0  # per 1,000 words
    identifier_density: float = 0.0  # per 1,000 words
    table_share: float = 0.0  # 0-1, share of words inside tables
    sampled_section_ids: list[str] = []
    relationship_density: float = 0.0  # relationships per entity in the sample
    entity_repetition: float = 0.0  # 0-1, sampled entities found in 3+ sections
    analysis_tokens: int = 0
    analysis_cost_inr: float = 0.0
    sample_entities: list[str] = []
    sample_relationships: list[str] = []


class StrategyDecision(BaseModel):
    """The chosen strategy, how sure we are, and why in plain words (FR15)."""

    strategy: Strategy
    confidence: float
    reason: str
    graph_candidate: bool = False  # many relationships, but the graph was not built
    warning: str = ""
