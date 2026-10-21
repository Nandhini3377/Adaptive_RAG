"""Tests for graph extraction (offline) and the Neo4j store and retriever (need Docker).

Start Neo4j with `docker compose up -d` (and NEO4J_PASSWORD in .env) to run the
Neo4j tests; otherwise they are skipped.
"""

import pytest

from adaptive_rag.ingest.extractor import entity_key, extract_graph
from adaptive_rag.llm.base import LLMTruncatedError
from adaptive_rag.retrieval.graph import matching_relations
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


def test_question_words_pick_matching_relation_types():
    types = ["DEPENDS_ON", "USED_BY", "OWNS", "OWNED_BY", "CALLS"]
    assert matching_relations("Which services indirectly depend on X?", types) == ["DEPENDS_ON"]
    assert matching_relations("Who owns the Ledger?", types) == ["OWNS"]
    assert matching_relations("What is the Ledger?", types) == []


def test_generic_lowercase_names_are_not_entities():
    from adaptive_rag.store.graph_store import _is_generic

    assert _is_generic("services") and _is_generic("none")
    assert not _is_generic("Ledger") and not _is_generic("Auth Service")
    assert not _is_generic("auth service")  # several words: a real name, lower-cased


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
    monkeypatch.setattr("adaptive_rag.ingest.extractor.settings.extraction_parallel", 1)
    llm = FakeLLM(data=extraction_reply)
    extract_graph(CHUNKS, llm)
    assert len(llm.calls) == 2  # one batch per chunk
    assert "Entities already found" not in llm.calls[0][0]["content"]
    assert "Auth Service" in llm.calls[1][0]["content"].split("Chunks:")[0]


class TruncatingLLM(FakeLLM):
    """Runs out of tokens when a prompt holds more than `fits` chunks."""

    def __init__(self, fits: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fits = fits

    def complete_json(self, messages, schema, **kwargs):
        if f'<document id="{self.fits + 1}">' in messages[0]["content"]:
            self.calls.append(messages)
            raise LLMTruncatedError("Ran out of tokens before answering")
        return super().complete_json(messages, schema, **kwargs)


def one_chunk_reply(messages):
    """What the model finds in whichever single chunk it was given."""
    if "Payments depends" in messages[0]["content"]:
        return extraction_reply(messages)
    return {
        "entities": [{"name": "Orders", "type": "service"}],
        "relationships": [
            {
                "source": "Orders",
                "relation": "CALLS",
                "target": "Payments",
                "chunk": 1,
                "confidence": 0.9,
            }
        ],
    }


def test_a_batch_that_runs_out_of_tokens_is_split_in_half():
    llm = TruncatingLLM(fits=1, data=one_chunk_reply)
    graph = extract_graph(CHUNKS, llm)
    assert len(llm.calls) == 3  # the pair that failed, then each chunk alone
    calls = next(r for r in graph.relations if r.relation == "CALLS")
    assert calls.chunk_id == "c2"  # chunk [1] of the second half is c2, not c1
    assert graph.tokens == 2 * 120  # usage from the two calls that answered


def test_batches_run_in_waves_and_merge_in_document_order(monkeypatch):
    """Two batches at a time: wave 2 knows wave 1's names, and results keep batch order."""
    monkeypatch.setattr("adaptive_rag.ingest.extractor.settings.extraction_batch_chars", 10)
    monkeypatch.setattr("adaptive_rag.ingest.extractor.settings.extraction_parallel", 2)
    chunks = [
        Chunk(id=f"c{n}", document_id="arch", owner_id="alice", text=f"Service{n} calls Hub.")
        for n in range(1, 4)
    ]

    def reply(messages):
        name = messages[0]["content"].split('<document id="1">\n')[1].split(" ")[0]  # "Service2"
        return {
            "entities": [{"name": name, "type": "service"}, {"name": "Hub", "type": "service"}],
            "relationships": [
                {"source": name, "relation": "CALLS", "target": "Hub", "chunk": 1, "confidence": 1}
            ],
        }

    llm = FakeLLM(data=reply)
    graph = extract_graph(chunks, llm)
    assert [e.name for e in graph.entities] == ["Service1", "Hub", "Service2", "Service3"]
    assert [r.chunk_id for r in graph.relations] == ["c1", "c2", "c3"]
    third = next(
        c[0]["content"] for c in llm.calls if '<document id="1">\nService3' in c[0]["content"]
    )
    assert "Service1" in third.split("Chunks:")[0]  # learned from the first wave
    first_wave = [
        c[0]["content"] for c in llm.calls if '<document id="1">\nService3' not in c[0]["content"]
    ]
    assert all("Entities already found" not in prompt for prompt in first_wave)


def test_a_single_chunk_that_runs_out_of_tokens_still_fails():
    with pytest.raises(LLMTruncatedError):
        extract_graph(CHUNKS[:1], TruncatingLLM(fits=0))


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

    only_depends = graph_store.paths_from(linked, "alice", ["arch"], ["DEPENDS_ON"])
    assert {r for p in only_depends for r in p.relations} == {"<-DEPENDS_ON"}


def test_graph_store_delete_removes_only_that_document(graph_store):
    graph = extract_graph(CHUNKS, FakeLLM(data=extraction_reply))
    graph_store.write_document("arch", "alice", graph, {})
    graph_store.delete_document("arch")
    assert graph_store.stats("arch") == {"entities": 0, "relations": 0}
