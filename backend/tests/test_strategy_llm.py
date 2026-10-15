"""The LLM's strategy pick, how it combines with the rules', and building only those indexes."""

import sqlite3

from adaptive_rag import services
from adaptive_rag.ingest.strategy_llm import LLMStrategy, combine, llm_strategy
from adaptive_rag.llm.base import LLMError
from adaptive_rag.schemas import DocumentProfile, StrategyDecision
from adaptive_rag.store import db
from tests.conftest import FakeLLM
from tests.test_api import client, llm, llm_json, login, upload  # noqa: F401

PROFILE = DocumentProfile(
    page_count=3,
    word_count=1200,
    identifier_density=42.6,
    cross_ref_rate=22.9,
    relationship_density=0.5,
    sample_entities=["Ledger", "Token Vault"],
    sample_relationships=["Ledger -DEPENDS_ON-> Postgres"],
)


def rules(strategy, confidence=0.7, graph_candidate=False):
    return StrategyDecision(
        strategy=strategy,
        confidence=confidence,
        reason="The scan found ...",
        graph_candidate=graph_candidate,
    )


def pick(strategy):
    return LLMStrategy(strategy=strategy, reason="Because of the signals.")


# ------------------------------------------------------------------ the LLM call


def test_the_llm_sees_every_signal_and_the_intent():
    fake = FakeLLM(data={"strategy": "keyword", "reason": "Many IDs."})
    result = llm_strategy(PROFILE, ["exact_terms"], fake)
    assert (result.strategy, result.reason) == ("keyword", "Many IDs.")
    prompt = fake.calls[0][0]["content"]
    for shown in ("42.6", "22.9", "0.50", "Ledger, Token Vault", "Find exact terms, IDs, or codes"):
        assert shown in prompt


def test_an_unknown_strategy_or_a_failed_call_gives_no_pick():
    assert llm_strategy(PROFILE, None, FakeLLM(data={"strategy": "everything"})) is None

    class Down(FakeLLM):
        def complete_json(self, *args, **kwargs):
            raise LLMError("timeout")

    assert llm_strategy(PROFILE, None, Down()) is None


# ------------------------------------------------------------------- combining


def test_agreement_builds_the_pick_and_raises_confidence():
    decision = combine(rules("hybrid"), pick("hybrid"))
    assert (decision.strategy, decision.confidence) == ("hybrid", 0.8)
    assert decision.suggested_indexes == []
    assert "Both picked it" in decision.reason


def test_overlap_is_built_and_the_rest_suggested():
    decision = combine(rules("hybrid"), pick("graph_hybrid"))
    assert decision.strategy == "hybrid"  # vector + bm25 are shared
    assert decision.suggested_indexes == ["graph"]
    assert decision.graph_candidate is True
    assert (decision.rules_strategy, decision.llm_strategy) == ("hybrid", "graph_hybrid")
    assert decision.confidence == 0.6


def test_the_overlap_can_leave_out_vector():
    keyword = combine(rules("hybrid"), pick("keyword"))
    assert (keyword.strategy, keyword.suggested_indexes) == ("keyword", ["vector"])
    graph = combine(rules("graph_hybrid"), pick("graph"))
    assert (graph.strategy, graph.suggested_indexes) == ("graph", ["vector", "bm25"])


def test_no_shared_index_builds_the_rules_pick():
    decision = combine(rules("vector"), pick("keyword"))
    assert decision.strategy == "vector"
    assert decision.suggested_indexes == ["bm25"]
    assert "share no index" in decision.reason


def test_without_the_llm_the_rules_decide():
    decision = combine(rules("hybrid", graph_candidate=True), None)
    assert decision.strategy == "hybrid"
    assert decision.llm_strategy is None
    assert decision.suggested_indexes == ["graph"]  # the rules' own graph candidate


# ------------------------------------------------------------ end to end (API)


def llm_picks_keyword(messages):
    if "Choose how to index a document" in messages[0]["content"]:
        return {"strategy": "keyword", "reason": "Questions will name exact codes."}
    return llm_json(messages)


def test_keyword_only_document_has_no_vectors_until_asked(client, llm):  # noqa: F811
    llm.data = llm_picks_keyword
    headers = login(client)
    # Rules: hybrid (exact terms wanted). LLM: keyword. Shared: bm25 -> keyword only.
    document_id = upload(client, headers, intents=["exact_terms"]).json()["document_id"]

    document = client.get(f"/documents/{document_id}", headers=headers).json()
    assert document["strategy"] == "keyword"
    assert (document["has_vector"], document["has_bm25"]) == (False, True)
    assert services.vector_store().count(owner_id=_owner(document_id)) == 0

    analysis = client.get(f"/documents/{document_id}/analysis", headers=headers).json()
    assert (analysis["rules_strategy"], analysis["llm_strategy"]) == ("hybrid", "keyword")
    assert analysis["suggested_indexes"] == ["vector"]

    # Questions are searched by keyword, and vector is recommended for meaning questions
    answer = client.post("/query", json={"question": "How many leave days?"}, headers=headers)
    assert answer.json()["mode"] == "keyword"
    assert answer.json()["recommendation"]["index_to_build"] == "vector"

    # Taking the suggestion embeds the chunks and clears it
    built = client.post(
        f"/documents/{document_id}/build-index", json={"index": "vector"}, headers=headers
    )
    assert built.status_code == 202
    assert client.get(f"/documents/{document_id}", headers=headers).json()["has_vector"] is True
    assert services.vector_store().count(owner_id=_owner(document_id)) > 0
    analysis = client.get(f"/documents/{document_id}/analysis", headers=headers).json()
    assert analysis["suggested_indexes"] == []


def test_build_index_rejects_unknown_index_names(client):  # noqa: F811
    headers = login(client)
    document_id = upload(client, headers, intents=["facts"]).json()["document_id"]
    response = client.post(
        f"/documents/{document_id}/build-index", json={"index": "vector+magic"}, headers=headers
    )
    assert response.status_code == 422


def test_documents_with_no_shared_index_get_a_clear_error(client, llm):  # noqa: F811
    headers = login(client)
    upload(client, headers, intents=["facts"])  # rules and LLM (no pick): vector only
    llm.data = llm_picks_keyword
    upload(client, headers, "codes.md", b"# Codes\n\nAUTH-403 means expired.", ["exact_terms"])
    response = client.post("/query", json={"question": "What is AUTH-403?"}, headers=headers)
    assert response.status_code == 400
    assert "share no search index" in response.json()["detail"]


def _owner(document_id: str) -> str:
    with db.session_scope() as session:
        return session.get(db.Document, document_id).owner_id


# -------------------------------------------------------------------- migration


def test_an_existing_database_gets_has_vector_set_for_old_documents(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:  # a documents table from before has_vector
        connection.execute(
            "CREATE TABLE documents (id VARCHAR(32) PRIMARY KEY, owner_id VARCHAR(32), "
            "filename VARCHAR(255), file_type VARCHAR(10), file_hash VARCHAR(64), "
            "file_path VARCHAR(500), status VARCHAR(20), progress INTEGER, stage VARCHAR(100), "
            "error TEXT, strategy VARCHAR(20), strategy_reason TEXT, has_bm25 BOOLEAN, "
            "graph_status VARCHAR(20), created_at DATETIME)"
        )
        connection.execute("INSERT INTO documents (id, has_bm25) VALUES ('old', 0)")

    db.make_engine(f"sqlite:///{path}")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT has_vector FROM documents").fetchone() == (1,)
