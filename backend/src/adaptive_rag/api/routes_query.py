"""POST /query: answer a question from the user's ready documents."""

import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from adaptive_rag import services
from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.query.answer import generate_answer
from adaptive_rag.schemas import Citation
from adaptive_rag.store import db

router = APIRouter(tags=["query"])


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None  # None = all of the user's ready documents
    mode: str | None = None  # manual override (FR27)


class QueryOut(BaseModel):
    query_id: str
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
    mode: str
    timings: dict[str, float]
    latency_ms: float
    tokens: int
    cost_inr: float


@router.post("/query")
def query(body: QueryIn, user: UserDep, session: SessionDep) -> QueryOut:
    started = time.perf_counter()
    document_ids = _ready_document_ids(session, user.id, body.document_ids)

    timings: dict[str, float] = {}
    step = time.perf_counter()
    hits = services.vector_store().search(body.question, user.id, document_ids=document_ids)
    timings["retrieve_ms"] = _ms_since(step)

    step = time.perf_counter()
    answer = generate_answer(body.question, hits, services.llm())
    timings["generate_ms"] = _ms_since(step)

    latency_ms = _ms_since(started)
    tokens = answer.input_tokens + answer.output_tokens
    record = db.QueryRecord(
        owner_id=user.id,
        document_ids=document_ids,
        query=body.question,
        mode_used="vector",
        answer=answer.text,
        stage_timings=timings,
        latency_ms=latency_ms,
        tokens=tokens,
        cost_inr=answer.cost_inr,
    )
    session.add(record)
    session.flush()
    return QueryOut(
        query_id=record.id,
        answer=answer.text,
        citations=answer.citations,
        insufficient_evidence=answer.insufficient_evidence,
        mode="vector",
        timings=timings,
        latency_ms=latency_ms,
        tokens=tokens,
        cost_inr=answer.cost_inr,
    )


def _ready_document_ids(
    session: SessionDep, owner_id: str, requested: list[str] | None
) -> list[str]:
    """The user's ready documents, limited to the requested ones if given."""
    query = session.query(db.Document.id).filter(
        db.Document.owner_id == owner_id, db.Document.status == "ready"
    )
    if requested:
        query = query.filter(db.Document.id.in_(requested))
    ids = [row.id for row in query]
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No ready documents to search")
    return ids


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)
