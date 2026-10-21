"""The Evaluation Lab: run the gold questions through every mode and the router (FR37-FR40).

Two depths:
- retrieval only (default): no LLM per question. Hit@5, Recall@5, MRR, retrieval latency,
  router accuracy, strategy accuracy, rule coverage. Cheap enough to run often.
- full (`full=True`): also generates answers, so it adds answer correctness, faithfulness,
  refusal accuracy, end-to-end latency, tokens, and cost. Spends Sarvam credits
  (cached re-runs are free).

The corpus is indexed under a dedicated evaluation user, so owner isolation keeps it
apart from real users' documents. Every index is built for every document (FR21), so
all modes can be compared on the same data. The upload decision (rules, LLM, and the
indexes both share) is recorded first, then scored against the best measured strategy.
"""

import json
import logging
import secrets
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from adaptive_rag import services
from adaptive_rag.auth import hash_password
from adaptive_rag.config import settings
from adaptive_rag.eval import metrics
from adaptive_rag.ingest import jobs
from adaptive_rag.ingest.selector import decide
from adaptive_rag.ingest.strategy_llm import combine, llm_strategy
from adaptive_rag.models.reranker import rerank
from adaptive_rag.query.classifier import classify_by_rules
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.router import available_modes, route
from adaptive_rag.retrieval.base import Retriever, rerank_hits
from adaptive_rag.retrieval.graph import GraphRetriever
from adaptive_rag.retrieval.graph_hybrid import GraphHybridRetriever
from adaptive_rag.retrieval.hybrid import HybridRetriever
from adaptive_rag.retrieval.keyword import KeywordRetriever
from adaptive_rag.retrieval.vector import VectorRetriever
from adaptive_rag.schemas import INDEX_ORDER, MODE_INDEXES, DocumentProfile, Index, Mode
from adaptive_rag.store import db, files

log = logging.getLogger(__name__)

EVAL_EMAIL = "eval@nimbus.local"
ALL_MODES: list[Mode] = ["vector", "keyword", "hybrid", "graph", "graph_hybrid"]
# Cheapest first: on a tie, the cheaper strategy is the better choice. Keyword needs no
# embeddings; the graph needs LLM calls over the whole document.
STRATEGY_ORDER: list[Mode] = ["keyword", "vector", "hybrid", "graph", "graph_hybrid"]
# The modes a strategy's indexes make available (assuming the router picks well among them)
STRATEGY_MODES: dict[str, list[Mode]] = {
    s: [m for m in ALL_MODES if m in available_modes(MODE_INDEXES[s])] for s in STRATEGY_ORDER
}
TIE_MARGIN = 0.02  # strategies within this recall of the best count as equally good

Progress = Callable[[str], None]


@dataclass
class CorpusDocument:
    filename: str
    document_id: str
    decided_strategy: str  # built: the overlap of the two picks
    rules_strategy: str
    llm_strategy: str | None  # None when the LLM call failed
    confidence: float
    expected_strategy: str
    analysis_tokens: int
    extraction_tokens: int | None


@dataclass
class ModeResult:
    mode: str
    hit: float
    recall: float
    mrr: float
    retrieval_ms: float
    top_chunks: list[str] = field(default_factory=list)
    # filled only in full runs
    answer: str | None = None
    correct: bool | None = None
    refused: bool | None = None
    faithfulness: float | None = None
    latency_ms: float | None = None
    tokens: int | None = None
    cost_inr: float | None = None
    rewrites: int | None = None
    relevance_history: list[float] = field(default_factory=list)


@dataclass
class QuestionReport:
    id: str
    type: str
    question: str
    documents: list[str]
    answerable: bool
    results: dict[str, ModeResult]
    router_mode: str
    router_ideal: str
    best_modes: list[str]


# ------------------------------------------------------------------ corpus


@dataclass(frozen=True)
class Corpus:
    """A set of test documents, their gold questions, and where its results are saved."""

    manifest: Path  # YAML with `documents: [{file, intents, expected_strategy}]`
    docs: Path
    questions: Path
    results: Path


CORPORA = ["demo", "large"]


def corpus_paths(name: str = "demo") -> Corpus:
    """demo: 4 small documents (scripts/generate_demo_docs.py). large: 2 documents of
    ~20 pages, big enough that the modes stop tying (scripts/generate_large_docs.py)."""
    data = settings.data_dir
    if name == "demo":
        eval_dir = data / "eval"
        return Corpus(
            data / "demo_spec.yaml", data / "demo_docs", eval_dir / "questions.jsonl", eval_dir
        )
    if name == "large":
        root = data / "eval_large"
        return Corpus(root / "manifest.yaml", root / "docs", root / "questions.jsonl", root)
    raise ValueError(f"Unknown corpus '{name}' (use one of {CORPORA})")


def load_questions(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or corpus_paths().questions
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def prepare_corpus(
    progress: Progress = log.info, corpus_name: str = "demo"
) -> list[CorpusDocument]:
    """Upload and fully index a corpus's documents for the evaluation user (reused if done)."""
    paths = corpus_paths(corpus_name)
    spec = yaml.safe_load(paths.manifest.read_text(encoding="utf-8"))
    owner_id = _eval_user_id()
    has_graph_store = services.graph_store() is not None
    # The keyword index lives in memory; the API rebuilds it on start, this script must too
    with db.session_scope() as session:
        services.bm25_store().rebuild_from_db(session)
    corpus = []
    for entry in spec["documents"]:
        path = paths.docs / entry["file"]
        document_id = _ensure_indexed(owner_id, path, entry["intents"], progress)
        # The decision built only some indexes; build the rest so every mode can be compared
        for index in _missing_indexes(document_id, has_graph_store):
            progress(f"Building {index} for {entry['file']}")
            jobs.build_index(document_id, index)
        _require_ready(document_id, entry["file"])
        with db.session_scope() as session:
            analysis = session.get(db.DocumentAnalysis, document_id)
            assert analysis is not None
            # Always decide with the current rules and prompt: the decision saved at upload
            # used whatever code ran then, and the Lab measures the code as it is now
            decision = _decide_now(analysis, entry["intents"], progress)
            corpus.append(
                CorpusDocument(
                    filename=entry["file"],
                    document_id=document_id,
                    decided_strategy=decision.get("built", analysis.recommended_strategy),
                    rules_strategy=decision.get("rules", analysis.recommended_strategy),
                    llm_strategy=decision.get("llm"),
                    confidence=decision.get("confidence", analysis.confidence),
                    expected_strategy=entry["expected_strategy"],
                    analysis_tokens=analysis.analysis_tokens,
                    extraction_tokens=analysis.raw_features.get("extraction_tokens"),
                )
            )
    return corpus


def _decide_now(
    analysis: db.DocumentAnalysis, intents: list[str], progress: Progress
) -> dict[str, Any]:
    """Rules + LLM pick from the saved scan, with the current code (reported, not saved)."""
    progress(f"Deciding the strategy for {analysis.document_id} with the current rules")
    profile = DocumentProfile.model_validate(analysis.raw_features["profile"])
    by_rules = decide(profile, intents)  # type: ignore[arg-type]
    by_llm = llm_strategy(profile, intents, services.llm())  # type: ignore[arg-type]
    decision = combine(by_rules, by_llm)
    return {
        "rules": decision.rules_strategy,
        "llm": decision.llm_strategy,
        "built": decision.strategy,
        "confidence": decision.confidence,
    }


def _eval_user_id() -> str:
    with db.session_scope() as session:
        user = session.query(db.User).filter(db.User.email == EVAL_EMAIL).first()
        if user is None:  # nobody logs in as this user: the password is random
            user = db.User(email=EVAL_EMAIL, password_hash=hash_password(secrets.token_hex(16)))
            session.add(user)
            session.flush()
        return user.id


def _ensure_indexed(owner_id: str, path: Path, intents: list[str], progress: Progress) -> str:
    content = path.read_bytes()
    file_type = files.detect_file_type(path.name, content)
    file_hash, saved = files.save_upload(owner_id, file_type, content)
    with db.session_scope() as session:
        existing = (
            session.query(db.Document)
            .filter(db.Document.owner_id == owner_id, db.Document.file_hash == file_hash)
            .first()
        )
        if existing is not None and existing.status == "ready":
            return existing.id
        if existing is not None:  # failed or interrupted earlier: start again
            session.delete(existing)
            session.flush()
        document = db.Document(
            owner_id=owner_id,
            filename=path.name,
            file_type=file_type,
            file_hash=file_hash,
            file_path=str(saved),
        )
        session.add(document)
        session.flush()
        document_id = document.id
    progress(f"Analyzing and indexing {path.name}")
    jobs.analyze_document(document_id, intents)  # runs synchronously here
    return document_id


def _missing_indexes(document_id: str, has_graph_store: bool) -> list[Index]:
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        assert document is not None
        built = {
            "vector": document.has_vector,
            "bm25": document.has_bm25,
            "graph": document.graph_status == "ready" or not has_graph_store,
        }
    return [index for index in INDEX_ORDER if not built[index]]


def _graph_status(document_id: str) -> str:
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        return document.graph_status if document else "none"


def _require_ready(document_id: str, filename: str) -> None:
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is None or document.status != "ready":
            error = document.error if document else "missing"
            raise RuntimeError(f"Could not index {filename}: {error}")


# --------------------------------------------------------------------- run


def run_lab(
    modes: list[Mode] | None = None,
    full: bool = False,
    limit: int | None = None,
    question_types: list[str] | None = None,
    progress: Progress = log.info,
    corpus_name: str = "demo",
) -> dict[str, Any]:
    """Index the corpus, run every question through each mode, and build the report."""
    started = time.perf_counter()
    corpus = prepare_corpus(progress, corpus_name)
    by_file = {d.filename: d for d in corpus}
    owner_id = _eval_user_id()
    has_graph = services.graph_store() is not None and all(
        _graph_status(d.document_id) == "ready" for d in corpus
    )
    retrievers = _retrievers(has_graph)
    indexes: set[Index] = {"vector", "bm25", "graph"} if has_graph else {"vector", "bm25"}
    modes = [m for m in (modes or ALL_MODES) if m in retrievers]

    all_questions = load_questions(corpus_paths(corpus_name).questions)
    questions = all_questions
    if question_types:
        questions = [q for q in questions if q["type"] in question_types]
    questions = questions[:limit] if limit else questions

    reports: list[QuestionReport] = []
    for index, question in enumerate(questions, start=1):
        progress(f"[{index}/{len(questions)}] {question['id']} {question['question']}")
        document_ids = [by_file[f].document_id for f in question["documents"]]
        results = {
            mode: _run_mode(question, mode, retrievers, owner_id, document_ids, indexes, full)
            for mode in modes
        }
        routing = route(classify_by_rules(question["question"]).query_type, indexes)
        router_mode = routing.mode if routing.mode in results else modes[0]
        if full:  # the router as users get it: classify (maybe LLM) -> route -> answer
            results["router"] = _run_full(
                question, None, retrievers, owner_id, document_ids, indexes
            )
            router_mode = results["router"].mode
        reports.append(
            QuestionReport(
                id=question["id"],
                type=question["type"],
                question=question["question"],
                documents=question["documents"],
                answerable=question["answerable"],
                results=results,
                router_mode=router_mode,
                router_ideal=routing.ideal_mode,
                best_modes=_best_modes(results, modes) if question["answerable"] else [],
            )
        )

    report = _report(reports, corpus, modes, full, has_graph, time.perf_counter() - started)
    report["run"]["corpus"] = corpus_name
    return report


def _retrievers(has_graph: bool) -> dict[Mode, Retriever]:
    vectors = services.vector_store()
    hybrid = HybridRetriever(vectors, services.bm25_store())
    built: dict[Mode, Retriever] = {
        "vector": VectorRetriever(vectors),
        "keyword": KeywordRetriever(services.bm25_store()),
        "hybrid": hybrid,
    }
    graph_store = services.graph_store()
    if has_graph and graph_store is not None:
        graph = GraphRetriever(graph_store)
        built["graph"] = graph
        built["graph_hybrid"] = GraphHybridRetriever(graph, hybrid)
    return built


def _run_mode(
    question: dict[str, Any],
    mode: Mode,
    retrievers: dict[Mode, Retriever],
    owner_id: str,
    document_ids: list[str],
    indexes: set[Index],
    full: bool,
) -> ModeResult:
    if full:
        return _run_full(question, mode, retrievers, owner_id, document_ids, indexes)
    started = time.perf_counter()
    found = retrievers[mode].retrieve(
        question["question"], owner_id, document_ids, settings.candidate_k
    )
    reranked = rerank_hits(
        rerank, question["question"], found.hits, settings.top_k, found.graph_paths
    )
    top = [hit.chunk.text for hit in reranked]
    return _retrieval_result(mode, question, top, (time.perf_counter() - started) * 1000)


def _run_full(
    question: dict[str, Any],
    mode: Mode | None,
    retrievers: dict[Mode, Retriever],
    owner_id: str,
    document_ids: list[str],
    indexes: set[Index],
) -> ModeResult:
    """The whole pipeline (answer + grounding) with a fixed mode, or routed when mode is None."""
    started = time.perf_counter()
    pipeline = QueryPipeline(retrievers, services.llm(), rerank)
    state, meter = pipeline.run(
        question["question"], owner_id, document_ids, indexes, requested_mode=mode
    )
    elapsed = (time.perf_counter() - started) * 1000
    top = [hit.chunk.text for hit in state.get("reranked", [])]
    retrieval_ms = state["timings"].get("retrieve", 0.0) + state["timings"].get("rerank", 0.0)
    result = _retrieval_result(state["routing"].mode, question, top, retrieval_ms)
    answer = state["answer"]
    result.answer = answer.text
    result.refused = answer.insufficient_evidence
    result.correct = (
        metrics.answer_correct(answer.text, question["answer_keywords"])
        if question["answerable"]
        else answer.insufficient_evidence
    )
    result.faithfulness = state.get("grounding_score")
    result.latency_ms = round(elapsed, 1)
    result.tokens = meter.tokens
    result.cost_inr = round(meter.cost_inr, 4)
    result.rewrites = len(state["rewrites"])
    result.relevance_history = state["relevance_history"]
    return result


def _retrieval_result(
    mode: str, question: dict[str, Any], top: list[str], elapsed_ms: float
) -> ModeResult:
    evidence = question["gold_evidence"]
    return ModeResult(
        mode=mode,
        hit=metrics.hit_at_k(top, evidence),
        recall=metrics.recall_at_k(top, evidence),
        mrr=metrics.reciprocal_rank(top, evidence),
        retrieval_ms=round(elapsed_ms, 1),
        top_chunks=[text[:200] for text in top],
    )


def _best_modes(results: dict[str, ModeResult], modes: list[Mode]) -> list[str]:
    """Modes with the best (recall, MRR) for this question; ties all count."""
    scored = {m: (results[m].recall, results[m].mrr) for m in modes}
    best = max(scored.values())
    return [m for m, score in scored.items() if score == best]


# ------------------------------------------------------------------ report


def _summary(rows: list[ModeResult], answerable: list[bool], full: bool) -> dict[str, Any]:
    """Aggregate one mode's results (retrieval metrics over answerable questions only)."""
    graded = [r for r, ok in zip(rows, answerable, strict=True) if ok]
    summary: dict[str, Any] = {
        "questions": len(rows),
        "hit_at_5": round(metrics.mean([r.hit for r in graded]), 3),
        "recall_at_5": round(metrics.mean([r.recall for r in graded]), 3),
        "mrr": round(metrics.mean([r.mrr for r in graded]), 3),
        "retrieval_ms_p50": round(metrics.percentile([r.retrieval_ms for r in rows], 50), 1),
        "retrieval_ms_p95": round(metrics.percentile([r.retrieval_ms for r in rows], 95), 1),
    }
    if full:
        unanswerable = [r for r, ok in zip(rows, answerable, strict=True) if not ok]
        faithful = [r.faithfulness for r in graded if r.faithfulness is not None and not r.refused]
        summary |= {
            "answer_correctness": round(metrics.mean([float(bool(r.correct)) for r in graded]), 3),
            "faithfulness": round(metrics.mean(faithful), 3) if faithful else None,
            "refusal_accuracy": round(
                metrics.mean([float(bool(r.refused)) for r in unanswerable]), 3
            )
            if unanswerable
            else None,
            "false_refusals": round(metrics.mean([float(bool(r.refused)) for r in graded]), 3),
            "latency_ms_p50": round(metrics.percentile([r.latency_ms or 0 for r in rows], 50), 1),
            "latency_ms_p95": round(metrics.percentile([r.latency_ms or 0 for r in rows], 95), 1),
            "tokens_per_query": round(metrics.mean([r.tokens or 0 for r in rows])),
            "cost_inr_per_query": round(metrics.mean([r.cost_inr or 0 for r in rows]), 4),
        }
    return summary


def _report(
    reports: list[QuestionReport],
    corpus: list[CorpusDocument],
    modes: list[Mode],
    full: bool,
    has_graph: bool,
    seconds: float,
) -> dict[str, Any]:
    columns = [*modes, "router"] if full else list(modes)
    answerable = [r.answerable for r in reports]

    def rows_for(column: str, subset: list[QuestionReport]) -> list[ModeResult]:
        if column == "router" and not full:
            return [r.results[r.router_mode] for r in subset]
        return [r.results[column] for r in subset]

    mode_table: dict[str, Any] = {}
    for column in [*columns, *([] if full else ["router"])]:
        by_type: dict[str, Any] = {}
        for query_type in sorted({r.type for r in reports}):
            subset = [r for r in reports if r.type == query_type]
            by_type[query_type] = _summary(
                rows_for(column, subset), [r.answerable for r in subset], full
            )
        mode_table[column] = {
            "overall": _summary(rows_for(column, reports), answerable, full),
            "by_type": by_type,
        }

    graded = [r for r in reports if r.answerable]
    router_correct = [r.router_mode in r.best_modes for r in graded]
    rewrites = [
        res.relevance_history
        for r in reports
        for res in r.results.values()
        if len(res.relevance_history) > 1
    ]

    analysis_tokens = sum(d.analysis_tokens for d in corpus)
    extraction_tokens = [d.extraction_tokens for d in corpus if d.extraction_tokens]
    return {
        "run": {
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "modes": modes,
            "full": full,
            "questions": len(reports),
            "graph_available": has_graph,
            "seconds": round(seconds, 1),
        },
        "modes": mode_table,
        "router": {
            "accuracy": round(metrics.mean([float(c) for c in router_correct]), 3),
            "choices": dict(Counter(r.router_mode for r in reports)),
        },
        "strategy": _strategy_accuracy(reports, corpus),
        "rule_coverage": round(
            metrics.mean([float(classify_by_rules(r.question).confident) for r in reports]), 3
        ),
        "analysis_cost_ratio": round(analysis_tokens / sum(extraction_tokens), 3)
        if extraction_tokens
        else None,
        "rewrite_gain": round(metrics.mean([h[-1] - h[0] for h in rewrites]), 3)
        if rewrites
        else None,
        "questions": [
            {**asdict(r), "results": {m: asdict(v) for m, v in r.results.items()}} for r in reports
        ],
    }


def _strategy_accuracy(
    reports: list[QuestionReport], corpus: list[CorpusDocument]
) -> dict[str, Any]:
    """Compare each upload decision with the cheapest strategy that scored (near) best.

    A strategy's score on a document = mean over its questions of the best recall among the
    modes that strategy makes available (i.e. assuming the router picks well).
    """
    rows = []
    for document in corpus:
        subset = [r for r in reports if r.answerable and document.filename in r.documents]
        if not subset:
            continue
        scores = {}
        for strategy in STRATEGY_ORDER:
            usable = [m for m in STRATEGY_MODES[strategy] if m in subset[0].results]
            scores[strategy] = metrics.mean(
                [max(r.results[m].recall for m in usable) for r in subset]
            )
        top = max(scores.values())
        best = next(s for s in STRATEGY_ORDER if scores[s] >= top - TIE_MARGIN)
        rows.append(
            {
                "document": document.filename,
                "rules": document.rules_strategy,
                "llm": document.llm_strategy,
                "decided": document.decided_strategy,
                "confidence": document.confidence,
                "best_measured": best,
                "expected_by_design": document.expected_strategy,
                "scores": {s: round(v, 3) for s, v in scores.items()},
                "correct": document.decided_strategy == best,
                "rules_correct": document.rules_strategy == best,
                "llm_correct": document.llm_strategy == best,
            }
        )

    def accuracy(key: str) -> float | None:
        return round(metrics.mean([float(r[key]) for r in rows]), 3) if rows else None

    return {
        "accuracy": accuracy("correct"),
        "rules_accuracy": accuracy("rules_correct"),
        "llm_accuracy": accuracy("llm_correct"),
        "documents": rows,
    }


# ------------------------------------------------------------------ output


def write_report(report: dict[str, Any], out_dir: Path | None = None) -> tuple[Path, Path]:
    """Save results.json (everything) and results.md (the tables) (FR39)."""
    out_dir = out_dir or settings.data_dir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "results.json", out_dir / "results.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path


def to_markdown(report: dict[str, Any]) -> str:
    run, modes = report["run"], report["modes"]
    columns = list(modes)
    overall = {c: modes[c]["overall"] for c in columns}
    metric_names = [k for k in overall[columns[0]] if k != "questions"]
    lines = [
        "# Evaluation results",
        "",
        f"{run['questions']} questions · {'full answers' if run['full'] else 'retrieval only'} · "
        f"graph {'available' if run['graph_available'] else 'not available'} · "
        f"{run['created_at']} · {run['seconds']} s",
        "",
        "## Overall",
        "",
        "| Metric | " + " | ".join(columns) + " |",
        "|---|" + "---:|" * len(columns),
    ]
    for name in metric_names:
        cells = [_cell(overall[c].get(name)) for c in columns]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["", "## Recall@5 by question type", ""]
    types = list(modes[columns[0]]["by_type"])
    lines += ["| Type | " + " | ".join(columns) + " |", "|---|" + "---:|" * len(columns)]
    for query_type in types:
        if query_type == "unanswerable":
            continue
        cells = [_cell(modes[c]["by_type"][query_type]["recall_at_5"]) for c in columns]
        lines.append(f"| {query_type} | " + " | ".join(cells) + " |")

    strategy = report["strategy"]
    lines += [
        "",
        "## Decisions",
        "",
        f"- Router accuracy: {_cell(report['router']['accuracy'])} "
        f"(choices: {report['router']['choices']})",
        f"- Strategy accuracy (built): {_cell(strategy['accuracy'])} · "
        f"rules alone: {_cell(strategy['rules_accuracy'])} · "
        f"LLM alone: {_cell(strategy['llm_accuracy'])}",
        f"- Rule coverage (questions classified without the LLM): {_cell(report['rule_coverage'])}",
        f"- Analysis cost ratio (sample tokens / full extraction tokens): "
        f"{_cell(report['analysis_cost_ratio'])}",
        f"- Rewrite gain (relevance after - before, when rewritten): "
        f"{_cell(report['rewrite_gain'])}",
        "",
        "| Document | Rules | LLM | Built | Best measured | Expected by design | Confidence |",
        "|---|---|---|---|---|---|---:|",
    ]
    for row in strategy["documents"]:
        lines.append(
            f"| {row['document']} | {row['rules']} | {row['llm'] or '—'} | {row['decided']} | "
            f"{row['best_measured']} | {row['expected_by_design']} | {row['confidence']:.2f} |"
        )
    lines += ["", "Recall@5 per strategy (router picks the best mode it makes available):", ""]
    lines += ["| Document | " + " | ".join(STRATEGY_ORDER) + " |", "|---|" + "---:|" * 5]
    for row in strategy["documents"]:
        cells = [_cell(row["scores"][s]) for s in STRATEGY_ORDER]
        lines.append(f"| {row['document']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}" if isinstance(value, float) else str(value)
