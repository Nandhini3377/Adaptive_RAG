"""Background work for a document, as a small state machine with progress in SQLite.

    scanning --(scan + sample)--> awaiting_intent --(intent or skip)--> indexing --> ready
        \\_____________ intents sent with the upload skip the wait _____/        \\-> failed

Each step runs as a FastAPI background task; the UI polls the status.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from adaptive_rag import services
from adaptive_rag.ingest.chunker import chunk_elements
from adaptive_rag.ingest.extractor import extract_graph
from adaptive_rag.ingest.intent import suggest_intents
from adaptive_rag.ingest.parser import parse_file
from adaptive_rag.ingest.sampler import analyze_sample
from adaptive_rag.ingest.scanner import group_sections, scan
from adaptive_rag.ingest.selector import decide
from adaptive_rag.ingest.strategy_llm import combine, llm_strategy
from adaptive_rag.llm.base import LLMError
from adaptive_rag.schemas import INDEX_ORDER, MODE_INDEXES, Chunk, DocumentProfile, Intent
from adaptive_rag.store import db

log = logging.getLogger(__name__)


def set_status(document_id: str, status: str, progress: int, stage: str) -> None:
    """Record where the document is in the pipeline; the UI polls this."""
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is not None:
            document.status = status
            document.progress = progress
            document.stage = stage


def _fail_on_error(step: Callable[..., None]) -> Callable[..., None]:
    """Any crash marks the document 'failed' with a readable error, instead of hanging."""

    def run(document_id: str, *args: object) -> None:
        try:
            step(document_id, *args)
        except Exception as error:
            log.exception("%s failed for %s", step.__name__, document_id)
            with db.session_scope() as session:
                document = session.get(db.Document, document_id)
                if document is not None:
                    document.status = "failed"
                    document.stage = f"Failed during {step.__name__.replace('_', ' ')}"
                    document.error = _public_error(error)

    run.__name__ = step.__name__
    return run


def _public_error(error: Exception) -> str:
    """What the uploader is shown. The real error (paths, provider replies) is in the log."""
    if isinstance(error, LLMError):
        return "The language model failed while reading this document. Try again later."
    return "Something went wrong while processing this document."


# --------------------------------------------------------------- step 1: scan


@_fail_on_error
def analyze_document(document_id: str, intents: list[Intent] | None = None) -> None:
    """Parse, scan, and sample; then wait for intent, or continue if intents were given."""
    _analyze(document_id)
    if intents is not None:
        apply_intent(document_id, intents or None)
    else:
        set_status(document_id, "awaiting_intent", 60, "Waiting for your intent")


def _analyze(document_id: str) -> None:
    """Parse, quick scan, and LLM sample; saves the analysis row."""
    path = _document_path(document_id)
    set_status(document_id, "scanning", 10, "Parsing")
    elements = parse_file(path)
    if not elements:
        raise ValueError("No text found in this document")

    set_status(document_id, "scanning", 30, "Quick scan")
    profile = scan(elements)
    sections = group_sections(elements)

    set_status(document_id, "scanning", 50, "Analyzing a sample with the LLM")
    try:
        profile = analyze_sample(sections, profile, services.llm())
        sample_note = ""
    except LLMError as error:  # the scan alone can still decide
        log.warning("Sample analysis failed for %s: %s", document_id, error)
        sample_note = f"Sample analysis failed ({error}); decided from the scan only."

    with db.session_scope() as session:
        session.merge(_analysis_row(document_id, profile, sample_note))


# ------------------------------------------------------ steps 2-3: decide + index


@_fail_on_error
def apply_intent(document_id: str, intents: list[Intent] | None) -> None:
    """Record the uploader's intents (None = skipped), decide the strategy, and index."""
    _decide(document_id, intents)
    index_document(document_id)


def _decide(document_id: str, intents: list[Intent] | None) -> None:
    """Rules and LLM each pick a strategy; store the combined decision on the document."""
    with db.session_scope() as session:
        analysis = session.get(db.DocumentAnalysis, document_id)
        if analysis is None:
            raise ValueError("Document has not been analyzed yet")
        profile = DocumentProfile.model_validate(analysis.raw_features["profile"])

    set_status(document_id, "indexing", 62, "Deciding the strategy")
    by_rules = decide(profile, intents)
    by_llm = llm_strategy(profile, intents, services.llm())
    decision = combine(by_rules, by_llm)

    with db.session_scope() as session:
        analysis = session.get(db.DocumentAnalysis, document_id)
        assert analysis is not None
        analysis.user_intents = list(intents) if intents else None
        analysis.recommended_strategy = decision.strategy
        analysis.confidence = decision.confidence
        analysis.reason = " ".join(filter(None, [decision.reason, decision.warning]))
        analysis.raw_features = {
            **analysis.raw_features,
            "decision": {
                "rules": decision.rules_strategy,
                "llm": decision.llm_strategy,
                "llm_reason": decision.llm_reason,
                "suggested_indexes": decision.suggested_indexes,
                "llm_cost_inr": by_llm.cost_inr if by_llm else 0.0,
            },
        }
        document = session.get(db.Document, document_id)
        assert document is not None
        document.strategy = decision.strategy
        document.strategy_reason = analysis.reason
        document.graph_status = "candidate" if decision.graph_candidate else "none"


@_fail_on_error
def index_document(document_id: str) -> None:
    """Build exactly the indexes the decided strategy searches (see MODE_INDEXES)."""
    chunks, owner_id, strategy = _chunk(document_id)
    indexes = set(MODE_INDEXES[strategy])  # type: ignore[index]
    if "graph" in indexes and services.graph_store() is None and indexes == {"graph"}:
        # Graph only, but Neo4j is down: nothing would be searchable. Use the safe default.
        indexes = {"vector", "bm25"}
        _note(document_id, "Graph not built: Neo4j is not running, so hybrid was built instead.")
    _build(document_id, owner_id, chunks, indexes)
    set_status(document_id, "ready", 100, "Ready")


@_fail_on_error
def index_lab_snippet(document_id: str) -> None:
    """Evaluation Lab: analyze and decide as for an upload, then build EVERY index.

    The decision is recorded (it is what the Lab tests) but not obeyed, so each mode can
    be compared on the same text. The scan decides, as if the uploader skipped the intent.
    """
    _analyze(document_id)
    _decide(document_id, None)
    chunks, owner_id, _strategy = _chunk(document_id)
    _build(document_id, owner_id, chunks, set(INDEX_ORDER))
    set_status(document_id, "ready", 100, "Ready")


def _chunk(document_id: str) -> tuple[list[Chunk], str, str]:
    """Chunk the file and keep the text in SQLite (every index and citation reads it).

    Returns (chunks, owner_id, strategy).
    """
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        assert document is not None
        path, owner_id, strategy = Path(document.file_path), document.owner_id, document.strategy

    set_status(document_id, "indexing", 65, "Chunking")
    chunks = chunk_elements(parse_file(path), document_id=document_id, owner_id=owner_id)
    with db.session_scope() as session:
        db.save_chunks(session, chunks)
    return chunks, owner_id, strategy


def _build(document_id: str, owner_id: str, chunks: list[Chunk], indexes: set[str]) -> None:
    """Build the given indexes, cheapest first."""
    if "vector" in indexes:
        set_status(document_id, "indexing", 75, f"Embedding {len(chunks)} chunks")
        _build_vector(document_id, chunks)
    if "bm25" in indexes:
        _build_bm25(document_id, chunks)
    if "graph" in indexes:
        set_status(document_id, "indexing", 85, "Extracting the knowledge graph")
        _build_graph(document_id, owner_id, chunks)


@_fail_on_error
def build_index(document_id: str, index: str) -> None:
    """Add indexes later, from a suggestion or recommendation: e.g. 'vector', 'bm25+graph'."""
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        assert document is not None
        owner_id = document.owner_id
        chunks = db.load_chunks(session, document_id)
    set_status(document_id, "indexing", 50, f"Building {index}")
    _build(document_id, owner_id, chunks, set(index.split("+")))
    _drop_built_suggestions(document_id)
    set_status(document_id, "ready", 100, "Ready")


def _build_vector(document_id: str, chunks: list[Chunk]) -> None:
    services.vector_store().add_chunks(chunks)
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is not None:
            document.has_vector = True


def _note(document_id: str, text: str) -> None:
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is not None:
            document.strategy_reason += f" ({text})"


def _drop_built_suggestions(document_id: str) -> None:
    """A suggested index that now exists is no longer a suggestion."""
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        analysis = session.get(db.DocumentAnalysis, document_id)
        if document is None or analysis is None or "decision" not in analysis.raw_features:
            return
        built = {
            "vector": document.has_vector,
            "bm25": document.has_bm25,
            "graph": document.graph_status == "ready",
        }
        decision = dict(analysis.raw_features["decision"])
        decision["suggested_indexes"] = [
            index for index in decision.get("suggested_indexes", []) if not built.get(index)
        ]
        analysis.raw_features = {**analysis.raw_features, "decision": decision}


def _build_bm25(document_id: str, chunks: list[Chunk]) -> None:
    services.bm25_store().build(document_id, chunks)
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is not None:
            document.has_bm25 = True


def _build_graph(document_id: str, owner_id: str, chunks: list[Chunk]) -> None:
    """Extract and store the graph; without Neo4j, keep it as a candidate."""
    graph = services.graph_store()
    if graph is None:
        with db.session_scope() as session:
            document = session.get(db.Document, document_id)
            if document is not None:
                document.graph_status = "candidate"
        _note(document_id, "Graph not built: Neo4j is not running.")
        return
    _set_graph_status(document_id, "building")
    extraction = extract_graph(chunks, services.llm())
    graph.write_document(document_id, owner_id, extraction, {c.id: c.section for c in chunks})
    _set_graph_status(document_id, "ready")
    with db.session_scope() as session:  # kept to compare the sample's cost with full extraction
        analysis = session.get(db.DocumentAnalysis, document_id)
        if analysis is not None:
            analysis.raw_features = {
                **analysis.raw_features,
                "extraction_tokens": extraction.tokens,
                "extraction_cost_inr": extraction.cost_inr,
                "graph_entities": len(extraction.entities),
                "graph_relations": len(extraction.relations),
            }


def _set_graph_status(document_id: str, status: str) -> None:
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is not None:
            document.graph_status = status


def _document_path(document_id: str) -> Path:
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        return Path(document.file_path)


def _analysis_row(document_id: str, profile: DocumentProfile, note: str) -> db.DocumentAnalysis:
    return db.DocumentAnalysis(
        document_id=document_id,
        page_count=profile.page_count,
        section_count=profile.section_count,
        table_count=profile.table_count,
        word_count=profile.word_count,
        sampled_section_ids=profile.sampled_section_ids,
        relationship_density=profile.relationship_density,
        entity_repetition=profile.entity_repetition,
        cross_ref_rate=profile.cross_ref_rate,
        relationship_phrase_rate=profile.relationship_phrase_rate,
        identifier_density=profile.identifier_density,
        table_share=profile.table_share,
        suggested_intents=suggest_intents(profile),
        analysis_tokens=profile.analysis_tokens,
        reason=note,
        raw_features={"profile": profile.model_dump()},
    )
