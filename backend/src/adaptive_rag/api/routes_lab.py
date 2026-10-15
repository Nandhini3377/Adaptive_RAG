"""Evaluation Lab: index a short pasted text in EVERY mode and compare them on a question.

Normal uploads build only the index the analysis picks; that is the point of the system.
The Lab tests that choice: on a small snippet (cheap to index fully) every mode answers
the same question, one LLM call judges the pooled chunks, and the page shows whether the
mode Adaptive RAG would have used was the best one.
"""

import hashlib
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from adaptive_rag import services
from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.api.limits import require_query_quota
from adaptive_rag.api.routes_documents import DocumentOut, remove_document
from adaptive_rag.api.routes_query import document_indexes, retrievers_for
from adaptive_rag.config import settings
from adaptive_rag.ingest import jobs
from adaptive_rag.llm.base import LLMError
from adaptive_rag.llm.meter import MeteredLLM
from adaptive_rag.models.reranker import rerank
from adaptive_rag.query.classifier import classify
from adaptive_rag.query.quality import ModeQuality, compare_modes, search_mode
from adaptive_rag.query.router import route
from adaptive_rag.schemas import MODE_INDEXES, Index, QueryType, RoutingDecision, SearchHit
from adaptive_rag.store import db

router = APIRouter(prefix="/lab", tags=["lab"])

_BUSY = ("scanning", "indexing")


class SnippetIn(BaseModel):
    text: str = Field(min_length=1, max_length=settings.lab_max_chars)


class LabOut(BaseModel):
    document: DocumentOut
    text: str
    strategy: str | None  # what the analysis would build for a normal upload
    confidence: float | None
    reason: str
    rules_strategy: str | None  # the two picks the decision combined
    llm_strategy: str | None
    modes: list[str]  # modes searchable now (every index that was built)


class LabQueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class LabChunk(BaseModel):
    section: str
    text: str
    relevant: bool


class LabMode(ModeQuality):
    chunks: list[LabChunk]


class LabQueryOut(BaseModel):
    question: str
    query_type: str
    classified_by: str
    strategy: str  # the analysis's pick: which indexes a normal upload would have
    adaptive_mode: str  # the mode Adaptive RAG would use, given only those indexes
    # Mode each decider alone would have led to: {"final": ..., "rules": ..., "llm": ...}
    picks: dict[str, str]
    ideal_mode: str  # the router's choice if every index existed
    routing_reason: str
    best_modes: list[str]  # most relevant chunks found (ties share); empty if none found any
    relevant_in_pool: int
    pool_size: int
    modes: list[LabMode]  # adaptive mode first
    latency_ms: float
    tokens: int
    llm_calls: int
    cost_inr: float


@router.get("")
def get_lab(user: UserDep, session: SessionDep) -> LabOut | None:
    """The user's current snippet and what the analysis decided; null if there is none."""
    document = _lab_document(session, user.id)
    return None if document is None else _lab_out(session, document)


@router.post("/snippet", status_code=status.HTTP_202_ACCEPTED)
def set_snippet(
    body: SnippetIn, user: UserDep, session: SessionDep, background: BackgroundTasks
) -> LabOut:
    """Replace the user's snippet and index it in every mode in the background.

    Analysis and graph extraction call the LLM, so a snippet counts as one question
    toward the daily limit.
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The snippet is empty")
    previous = _lab_document(session, user.id)
    if previous is not None and previous.status in _BUSY:
        raise HTTPException(status.HTTP_409_CONFLICT, "The current snippet is still indexing")
    require_query_quota(session, user.id)
    _remove_lab(session, user.id)

    content = text.encode("utf-8")
    file_hash = hashlib.sha256(content).hexdigest()
    # Own name, so deleting the snippet never removes an uploaded file with the same bytes
    path = settings.upload_dir / user.id / f"lab-{file_hash}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    document = db.Document(
        owner_id=user.id,
        filename="Lab snippet",
        file_type="md",
        file_hash=file_hash,
        file_path=str(path),
    )
    session.add(document)
    session.flush()
    session.add(db.LabSnippet(owner_id=user.id, document_id=document.id))
    session.add(
        db.QueryRecord(owner_id=user.id, document_ids=[document.id], query="(Lab snippet indexed)")
    )
    session.commit()  # the background job reads it from a separate session
    background.add_task(jobs.index_lab_snippet, document.id)
    return _lab_out(session, document)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_snippet(user: UserDep, session: SessionDep) -> Response:
    document = _lab_document(session, user.id)
    if document is not None and document.status in _BUSY:
        raise HTTPException(status.HTTP_409_CONFLICT, "The snippet is still indexing")
    _remove_lab(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/query")
def lab_query(body: LabQueryIn, user: UserDep, session: SessionDep) -> LabQueryOut:
    """Search the snippet with every mode, judge the pooled chunks once, and compare."""
    started = time.perf_counter()
    require_query_quota(session, user.id)
    document = _lab_document(session, user.id)
    if document is None or document.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Add a snippet and wait until it is ready")
    analysis = session.get(db.DocumentAnalysis, document.id)
    strategy = (analysis.recommended_strategy if analysis else "") or "hybrid"
    decision = analysis.raw_features.get("decision", {}) if analysis else {}
    deciders = {"final": strategy, "rules": decision.get("rules"), "llm": decision.get("llm")}

    built = document_indexes(document, services.graph_store() is not None)
    meter = MeteredLLM(services.llm())
    try:
        classification = classify(body.question, meter)
        # What Adaptive RAG would do with only the indexes its decision built
        adaptive = _route_for(classification.query_type, strategy, built)
        picks = {
            name: _route_for(classification.query_type, pick, built).mode
            for name, pick in deciders.items()
            if pick in MODE_INDEXES
        }
        results: dict[str, list[SearchHit]] = {}
        for mode, retriever in retrievers_for(built).items():
            results[mode] = search_mode(
                retriever, body.question, body.question, user.id, [document.id], rerank
            )
        comparison = compare_modes(body.question, results, meter, used_mode=adaptive.mode)
    except LLMError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The language model failed to judge the results. Please try again in a moment.",
        ) from error

    relevant = comparison.relevant_ids
    modes = [
        LabMode(
            **quality.model_dump(),
            chunks=[
                LabChunk(
                    section=hit.chunk.section,
                    text=hit.chunk.text,
                    relevant=hit.chunk.id in relevant,
                )
                for hit in results[quality.mode]
            ],
        )
        for quality in comparison.modes
    ]
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    session.add(
        db.QueryRecord(
            owner_id=user.id,
            document_ids=[document.id],
            query=body.question,
            query_type=classification.query_type,
            ideal_mode=adaptive.ideal_mode,
            mode_used=adaptive.mode,
            routing_reason=f"Lab: {adaptive.reason}",
            latency_ms=latency_ms,
            tokens=meter.tokens,
            cost_inr=meter.cost_inr,
        )
    )
    return LabQueryOut(
        question=body.question,
        query_type=classification.query_type,
        classified_by=classification.source,
        strategy=strategy,
        adaptive_mode=adaptive.mode,
        picks=picks,
        ideal_mode=adaptive.ideal_mode,
        routing_reason=adaptive.reason,
        best_modes=best_modes(comparison.modes),
        relevant_in_pool=len(relevant),
        pool_size=comparison.pool_size,
        modes=modes,
        latency_ms=latency_ms,
        tokens=meter.tokens,
        llm_calls=meter.calls,
        cost_inr=round(meter.cost_inr, 4),
    )


def best_modes(modes: list[ModeQuality]) -> list[str]:
    """Modes that found the most relevant chunks (highest recall); every tie counts as best.

    Precision is not a tie-breaker: on a small text a mode that returns fewer chunks gets
    higher precision with the same evidence (measured: 4 of 5 chunks vs all 5).
    """
    most = max((m.relevant for m in modes), default=0)
    return [m.mode for m in modes if m.relevant == most] if most else []


def _route_for(query_type: QueryType, strategy: str, built: frozenset[Index]) -> RoutingDecision:
    """The routing a normal upload with this strategy would get (only indexes really built)."""
    indexes = MODE_INDEXES[strategy] & built  # type: ignore[index]
    return route(query_type, indexes or built)


def _lab_document(session: Session, owner_id: str) -> db.Document | None:
    snippet = session.get(db.LabSnippet, owner_id)
    return None if snippet is None else session.get(db.Document, snippet.document_id)


def _remove_lab(session: Session, owner_id: str) -> None:
    """Delete the user's snippet row, then its document from every store."""
    snippet = session.get(db.LabSnippet, owner_id)
    if snippet is None:
        return
    document = session.get(db.Document, snippet.document_id)
    session.delete(snippet)
    session.flush()  # before the document, so the row is not also removed by the cascade
    if document is not None:
        remove_document(session, document)
        session.flush()


def _lab_out(session: Session, document: db.Document) -> LabOut:
    analysis = session.get(db.DocumentAnalysis, document.id)
    decided = analysis is not None and bool(analysis.recommended_strategy)
    try:
        with open(document.file_path, encoding="utf-8") as file:
            text = file.read()
    except OSError:
        text = ""
    built = document_indexes(document, services.graph_store() is not None)
    decision = analysis.raw_features.get("decision", {}) if analysis else {}
    return LabOut(
        document=DocumentOut.of(document),
        text=text,
        strategy=analysis.recommended_strategy if decided else None,
        confidence=analysis.confidence if decided else None,
        reason=analysis.reason if decided else "",
        rules_strategy=decision.get("rules"),
        llm_strategy=decision.get("llm"),
        modes=list(retrievers_for(built)) if document.status == "ready" else [],
    )
