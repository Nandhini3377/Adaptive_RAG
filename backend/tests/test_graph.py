"""Tests for graph extraction (offline) and the Neo4j store and retriever (need Docker).

Start Neo4j with `docker compose up -d` (and NEO4J_PASSWORD in .env) to run the
Neo4j tests; otherwise they are skipped.
"""

import pytest

from adaptive_rag.ingest.extractor import entity_key, extract_graph
from adaptive_rag.schemas import Chunk
from tests.conftest import FakeLLM

CHUNKS = [
    Chunk(
        id="c1", document_id="arch", owner_id="alice", text="Payments depends on the Auth Service."
    ),
    Chunk(
        id="c2",
        document_id="arch",
        owner_id="alice",
        text="Orders calls Payments. Auth Service is owned by the Identity team.",
    ),
]


def extraction_reply(_messages):
    return {
        "entities": [
            {"name": "Payments", "type": "service"},
            {"name": "Auth Service", "type": "service"},
            {"name": "Orders", "type": "service"},
            {"name": "Identity team", "type": "team"},
            {"name": "the auth-service", "type": "service"},  # duplicate in another spelling
        ],
        "relationships": [
            {
                "source": "Payments",
                "relation": "depends on",
                "target": "Auth Service",
                "chunk": 1,
                "confidence": 0.9,
            },
            {
                "source": "Orders",
                "relation": "CALLS",
                "target": "Payments",
                "chunk": 2,
                "confidence": 0.95,
            },
            {
                "source": "Auth Service",
                "relation": "OWNED_BY",
                "target": "Identity team",
                "chunk": 2,
                "confidence": 0.8,
            },
            {
                "source": "Payments",
                "relation": "DEPENDS_ON",
                "target": "Auth Service",
                "chunk": 1,
                "confidence": 0.7,
            },
            {
                "source": "Orders",
                "relation": "MAYBE_USES",
                "target": "Auth Service",
                "chunk": 2,
                "confidence": 0.2,
            },
            {
                "source": "Orders",
                "relation": "CALLS",
                "target": "Payments",
                "chunk": 9,
                "confidence": 0.9,
            },
        ],
    }


# ------------------------------------------------------- extraction (offline)


def test_entity_keys_normalize_spelling():
    assert entity_key("The Auth-Service") == entity_key("auth service") == "auth service"


def test_extraction_dedupes_entities_and_relations():
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    assert sorted(e.key for e in graph.entities) == [
        "auth service",
        "identity team",
        "orders",
        "payments",
    ]
    triples = sorted((r.source, r.relation, r.target) for r in graph.relations)
    assert triples == [
        ("auth service", "OWNED_BY", "identity team"),
        ("orders", "CALLS", "payments"),
        ("payments", "DEPENDS_ON", "auth service"),
    ]


def test_relations_keep_their_source_chunk_and_best_confidence():
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    depends = next(r for r in graph.relations if r.relation == "DEPENDS_ON")
    assert depends.chunk_id == "c1"
    assert depends.confidence == 0.9  # the duplicate with 0.7 was dropped


def test_low_confidence_and_bad_chunk_numbers_are_dropped():
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    assert all(r.relation != "MAYBE_USES" for r in graph.relations)  # confidence 0.2
    assert len([r for r in graph.relations if r.relation == "CALLS"]) == 1  # chunk 9 ignored


def test_mentions_link_chunks_to_entities():
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    assert graph.mentions["c1"] == ["auth service", "payments"]
    assert "identity team" in graph.mentions["c2"]


def test_later_batches_are_told_known_entity_names(monkeypatch):
    monkeypatch.setattr("adaptive_rag.ingest.extractor.settings.extraction_batch_chars", 10)
    llm = FakeLLM(data=extraction_reply)
    extract_graph(CHUNKS, llm)
    assert len(llm.calls) == 2  # one batch per chunk
    assert "Entities already found" not in llm.calls[0][0]["content"]
    assert "Auth Service" in llm.calls[1][0]["content"].split("Chunks:")[0]


# ------------------------------------------------------------ Neo4j (Docker)


@pytest.fixture
def graph_store():
    from adaptive_rag.store.graph_store import GraphStore, GraphUnavailableError

    try:
        store = GraphStore()
    except GraphUnavailableError as error:
        pytest.skip(f"Neo4j not available: {error}")
    yield store
    for document_id in ("arch", "bob-doc"):
        store.delete_document(document_id)
    store.close()


def test_graph_store_traverses_with_direction_and_owner_filter(graph_store):
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    graph_store.write_document("arch", "alice", graph, {"c1": "Overview", "c2": "Teams"})
    bob_chunk = Chunk(
        id="b1", document_id="bob-doc", owner_id="bob", text="Payments depends on Bob DB."
    )
    bob_graph = extract_graph(
        [bob_chunk],
        FakeLLM(
            data={
                "entities": [
                    {"name": "Payments", "type": "service"},
                    {"name": "Bob DB", "type": "db"},
                ],
                "relationships": [
                    {
                        "source": "Payments",
                        "relation": "DEPENDS_ON",
                        "target": "Bob DB",
                        "chunk": 1,
                        "confidence": 1,
                    }
                ],
            }
        ),
    )
    graph_store.write_document("bob-doc", "bob", bob_graph, {})

    assert graph_store.stats("arch") == {"entities": 4, "relations": 3}
    linked = graph_store.link_entities("What depends on Auth Service?", "alice", ["arch"])
    assert linked == ["arch:auth service"]

    paths = graph_store.paths_from(linked, "alice", ["arch"])
    described = {
        " ".join(f"{n} {r}" for n, r in zip(p.nodes, [*p.relations, ""], strict=True)).strip()
        for p in paths
    }
    assert "Auth Service <-DEPENDS_ON Payments" in described
    assert "Auth Service <-DEPENDS_ON Payments <-CALLS Orders" in described  # 2 hops
    assert all("Bob DB" not in p.nodes for p in paths)  # other owner's graph is invisible


def test_graph_store_delete_removes_only_that_document(graph_store):
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    graph_store.write_document("arch", "alice", graph, {})
    graph_store.delete_document("arch")
    assert graph_store.stats("arch") == {"entities": 0, "relations": 0}
