"""POST /query: run the adaptive pipeline over the user's ready documents."""

import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from adaptive_rag import services
from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.llm.base import LLMError
from adaptive_rag.models.reranker import rerank
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.router import RoutingError, available_modes
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.retrieval.graph import GraphRetriever
from adaptive_rag.retrieval.graph_hybrid import GraphHybridRetriever
from adaptive_rag.retrieval.hybrid import HybridRetriever
from adaptive_rag.retrieval.vector import VectorRetriever
from adaptive_rag.schemas import Citation, GraphPath, Mode, Recommendation
from adaptive_rag.store import db

router = APIRouter(tags=["query"])


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None  # None = all of the user's ready documents
    mode: Mode | None = None  # manual override (FR27)


class Scores(BaseModel):
    relevance: float
    relevance_history: list[float]
    grounding: float | None
    unsupported_claims: list[str] = []  # claims the checker could not find in the evidence


class QueryOut(BaseModel):
    query_id: str
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
    query_type: str
    classified_by: str
    mode: str
    ideal_mode: str
    routing_reason: str
    recommendation: Recommendation | None
    recommendation_document_ids: list[str]
    rewrites: list[str]
    graph_paths: list[GraphPath]
    scores: Scores
    regenerated: bool
    refused_reason: str
    documents: dict[str, str]  # id -> filename, for showing evidence sources
    timings: dict[str, float]
    latency_ms: float
    tokens: int
    reasoning_tokens: int
    llm_calls: int
    cost_inr: float


@router.post("/query")
def query(body: QueryIn, user: UserDep, session: SessionDep) -> QueryOut:
    started = time.perf_counter()
    documents = _ready_documents(session, user.id, body.document_ids)
    graph = services.graph_store()
    has_bm25 = all(d.has_bm25 for d in documents)
    has_graph = graph is not None and all(d.graph_status == "ready" for d in documents)

    pipeline = QueryPipeline(_retrievers(has_bm25, has_graph), services.llm(), rerank)
    try:
        state, meter = pipeline.run(
            body.question,
            user.id,
            [d.id for d in documents],
            has_bm25=has_bm25,
            has_graph=has_graph,
            requested_mode=body.mode,
        )
    except RoutingError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    except LLMError as error:  # the model was unreachable or could not finish an answer
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"The language model failed: {error}"
        ) from error

    answer, routing = state["answer"], state["routing"]
    recommendation_ids = _missing_index(documents, routing.recommendation)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    record = db.QueryRecord(
        owner_id=user.id,
        document_ids=[d.id for d in documents],
        query=body.question,
        query_type=state["classification"].query_type,
        ideal_mode=routing.ideal_mode,
        mode_used=routing.mode,
        recommendation=routing.recommendation.model_dump() if routing.recommendation else None,
        routing_reason=routing.reason,
        rewritten_queries=state["rewrites"],
        answer=answer.text,
        stage_timings=state["timings"],
        latency_ms=latency_ms,
        tokens=meter.tokens,
        cost_inr=meter.cost_inr,
    )
    session.add(record)
    session.flush()
    session.add(
        db.Evaluation(
            query_id=record.id,
            retrieval_score=state["relevance"],
            faithfulness_score=state["grounding_score"],
            retry_count=len(state["rewrites"]),
        )
    )
    return QueryOut(
        query_id=record.id,
        answer=answer.text,
        citations=answer.citations,
        insufficient_evidence=answer.insufficient_evidence,
        query_type=state["classification"].query_type,
        classified_by=state["classification"].source,
        mode=routing.mode,
        ideal_mode=routing.ideal_mode,
        routing_reason=routing.reason,
        recommendation=routing.recommendation,
        recommendation_document_ids=recommendation_ids,
        rewrites=state["rewrites"],
        graph_paths=state["graph_paths"],
        scores=Scores(
            relevance=state["relevance"],
            relevance_history=state["relevance_history"],
            grounding=state["grounding_score"],
            unsupported_claims=state["unsupported_claims"],
        ),
        regenerated=state["regenerated"],
        refused_reason=state["refused_reason"],
        documents={d.id: d.filename for d in documents},
        timings=state["timings"],
        latency_ms=latency_ms,
        tokens=meter.tokens,
        reasoning_tokens=meter.reasoning_tokens,
        llm_calls=meter.calls,
        cost_inr=round(meter.cost_inr, 4),
    )


def _retrievers(has_bm25: bool, has_graph: bool) -> dict[Mode, Retriever]:
    """Only the retrievers whose indexes exist (the router never picks others)."""
    vectors = services.vector_store()
    hybrid = HybridRetriever(vectors, services.bm25_store())
    built: dict[Mode, Retriever] = {"vector": VectorRetriever(vectors), "hybrid": hybrid}
    graph_store = services.graph_store()
    if graph_store is not None:
        graph = GraphRetriever(graph_store)
        built["graph"] = graph
        built["graph_hybrid"] = GraphHybridRetriever(graph, hybrid)
    allowed = available_modes(has_bm25, has_graph)
    return {mode: retriever for mode, retriever in built.items() if mode in allowed}


def _missing_index(
    documents: list[db.Document], recommendation: Recommendation | None
) -> list[str]:
    """Which of the searched documents the recommended index would be built for."""
    if recommendation is None:
        return []
    needs_graph = "graph" in recommendation.index_to_build
    return [
        d.id
        for d in documents
        if (needs_graph and d.graph_status != "ready") or (not needs_graph and not d.has_bm25)
    ]


def _ready_documents(
    session: Session, owner_id: str, requested: list[str] | None
) -> list[db.Document]:
    """The user's ready documents, limited to the requested ones if given."""
    query = session.query(db.Document).filter(
        db.Document.owner_id == owner_id, db.Document.status == "ready"
    )
    if requested:
        query = query.filter(db.Document.id.in_(requested))
    documents = query.all()
    if not documents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No ready documents to search")
    return documents
