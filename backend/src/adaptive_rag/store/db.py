"""SQLite tables (via SQLAlchemy) and the session factory.

Swapping to PostgreSQL later only means changing DATABASE_URL.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Engine, ForeignKey, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from adaptive_rag.config import settings
from adaptive_rag.schemas import Chunk


def new_id() -> str:
    """A random ID for a new row."""
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Parent of every table."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    # scanning -> awaiting_intent -> indexing -> ready (or failed)
    status: Mapped[str] = mapped_column(String(20), default="scanning")
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(100), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    # vector | hybrid | graph_hybrid (empty until decided)
    strategy: Mapped[str] = mapped_column(String(20), default="")
    strategy_reason: Mapped[str] = mapped_column(Text, default="")
    # Which indexes exist: the router only uses these
    has_bm25: Mapped[bool] = mapped_column(default=False)
    # none | candidate | building | ready
    graph_status: Mapped[str] = mapped_column(String(20), default="none")
    created_at: Mapped[datetime] = mapped_column(default=now)


class LabSnippet(Base):
    """Marks a user's Evaluation Lab text: a hidden document indexed in every mode.

    One per user; it is left out of the document list, the quota, and normal questions.
    """

    __tablename__ = "lab_snippets"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )


def lab_document_ids(session: Session, owner_id: str) -> set[str]:
    """IDs of this user's Lab documents (to keep them out of normal views)."""
    rows = session.query(LabSnippet.document_id).filter(LabSnippet.owner_id == owner_id)
    return {row.document_id for row in rows}


class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    page_count: Mapped[int] = mapped_column(default=0)
    section_count: Mapped[int] = mapped_column(default=0)
    table_count: Mapped[int] = mapped_column(default=0)
    word_count: Mapped[int] = mapped_column(default=0)
    sampled_section_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    relationship_density: Mapped[float] = mapped_column(default=0.0)
    entity_repetition: Mapped[float] = mapped_column(default=0.0)
    cross_ref_rate: Mapped[float] = mapped_column(default=0.0)
    relationship_phrase_rate: Mapped[float] = mapped_column(default=0.0)
    identifier_density: Mapped[float] = mapped_column(default=0.0)
    table_share: Mapped[float] = mapped_column(default=0.0)
    suggested_intents: Mapped[list[str]] = mapped_column(JSON, default=list)
    user_intents: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    recommended_strategy: Mapped[str] = mapped_column(String(20), default="")
    confidence: Mapped[float] = mapped_column(default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    analysis_tokens: Mapped[int] = mapped_column(default=0)
    raw_features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ChunkRow(Base):
    """Chunk text lives here too, so BM25 can be rebuilt without Qdrant."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[str] = mapped_column(String(32), index=True)
    section: Mapped[str] = mapped_column(Text, default="")
    page: Mapped[int | None] = mapped_column(default=None)
    element_type: Mapped[str] = mapped_column(String(10), default="text")
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(default=0)  # order inside the document

    def to_chunk(self) -> Chunk:
        return Chunk(
            id=self.id,
            document_id=self.document_id,
            owner_id=self.owner_id,
            text=self.text,
            section=self.section,
            page=self.page,
            element_type=self.element_type,  # type: ignore[arg-type]
        )


class QueryRecord(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)
    document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    query: Mapped[str] = mapped_column(Text)
    query_type: Mapped[str] = mapped_column(String(20), default="")
    ideal_mode: Mapped[str] = mapped_column(String(20), default="")
    mode_used: Mapped[str] = mapped_column(String(20), default="")
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    routing_reason: Mapped[str] = mapped_column(Text, default="")
    rewritten_queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text, default="")
    stage_timings: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float] = mapped_column(default=0.0)
    tokens: Mapped[int] = mapped_column(default=0)
    cost_inr: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=now)


class Evaluation(Base):
    __tablename__ = "evaluations"

    query_id: Mapped[str] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), primary_key=True
    )
    retrieval_score: Mapped[float] = mapped_column(default=0.0)
    faithfulness_score: Mapped[float | None] = mapped_column(default=None)
    answer_relevance: Mapped[float | None] = mapped_column(default=None)
    citation_score: Mapped[float | None] = mapped_column(default=None)
    retry_count: Mapped[int] = mapped_column(default=0)


class LLMCacheEntry(Base):
    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(100))
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)


# ------------------------------------------------------------------ engine


def make_engine(url: str | None = None) -> Engine:
    """Create the engine; SQLite gets foreign keys switched on."""
    url = url or settings.db_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    if url.startswith("sqlite"):
        # In-memory SQLite is one database per connection, so share one connection
        pool = {"poolclass": StaticPool} if ":memory:" in url else {}
        engine = create_engine(url, connect_args={"check_same_thread": False}, **pool)

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(connection: Any, _record: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")  # SQLite skips them by default
            cursor.close()

    else:
        engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure(url: str | None = None) -> None:
    """(Re)connect the app to a database. Tests pass an in-memory URL."""
    global _engine, _session_factory
    _engine = make_engine(url)
    _session_factory = sessionmaker(_engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session that commits on success and rolls back on error."""
    if _session_factory is None:
        configure()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ----------------------------------------------------------------- chunks


def save_chunks(session: Session, chunks: list[Chunk]) -> None:
    """Store chunk text so keyword search and citations can read it."""
    for position, chunk in enumerate(chunks):
        session.merge(
            ChunkRow(
                id=chunk.id,
                document_id=chunk.document_id,
                owner_id=chunk.owner_id,
                section=chunk.section,
                page=chunk.page,
                element_type=chunk.element_type,
                text=chunk.text,
                position=position,
            )
        )


def load_chunks(session: Session, document_id: str) -> list[Chunk]:
    """All chunks of one document, in document order."""
    rows = (
        session.query(ChunkRow)
        .filter(ChunkRow.document_id == document_id)
        .order_by(ChunkRow.position)
    )
    return [row.to_chunk() for row in rows]


def load_chunks_by_ids(session: Session, chunk_ids: list[str], owner_id: str) -> list[Chunk]:
    """Chunks by ID, in the order given; other owners' chunks are never returned."""
    if not chunk_ids:
        return []
    rows = session.query(ChunkRow).filter(ChunkRow.id.in_(chunk_ids), ChunkRow.owner_id == owner_id)
    by_id = {row.id: row.to_chunk() for row in rows}
    return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]
