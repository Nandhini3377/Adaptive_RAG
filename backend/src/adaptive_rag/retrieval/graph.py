"""Graph mode: find entities named in the question, walk the graph, return supporting chunks."""

import re

from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import RetrievalResult, SearchHit
from adaptive_rag.store import db
from adaptive_rag.store.graph_store import GraphStore


class GraphRetriever(Retriever):
    mode = "graph"

    def __init__(self, graph_store: GraphStore) -> None:
        self._graph = graph_store

    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        entity_ids = self._graph.link_entities(question, owner_id, document_ids)
        if not entity_ids:
            return RetrievalResult(hits=[])
        # Walk only the relations the question names ("depend" -> DEPENDS_ON); if it names
        # none, or they lead nowhere, walk every relation.
        types = matching_relations(question, self._graph.relation_types(owner_id, document_ids))
        paths = self._graph.paths_from(entity_ids, owner_id, document_ids, types) if types else []
        if not paths:
            paths = self._graph.paths_from(entity_ids, owner_id, document_ids)

        # Chunks that state the edges come first (shortest paths first), then
        # chunks that merely mention the linked entities.
        chunk_ids: list[str] = []
        for path in paths:
            chunk_ids.extend(c for c in path.chunk_ids if c not in chunk_ids)
        for chunk_id in self._graph.chunks_mentioning(entity_ids, owner_id, document_ids):
            if chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)

        with db.session_scope() as session:
            chunks = db.load_chunks_by_ids(session, chunk_ids[:k], owner_id)
        hits = [SearchHit(chunk=c, score=1 / rank) for rank, c in enumerate(chunks, start=1)]
        return RetrievalResult(hits=hits, graph_paths=paths)


def matching_relations(question: str, relation_types: list[str]) -> list[str]:
    """Relation types sharing a word with the question, compared on the first 5 letters
    so "depend", "depends" and "dependency" all match DEPENDS_ON. Short words (on, by)
    are ignored."""
    stems = {word[:5] for word in re.findall(r"[a-z]+", question.lower()) if len(word) >= 4}
    return [
        relation
        for relation in relation_types
        if any(part[:5] in stems for part in relation.lower().split("_") if len(part) >= 4)
    ]
