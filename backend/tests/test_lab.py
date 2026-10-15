"""Evaluation Lab: a pasted snippet indexed in every mode, compared on one question."""

from adaptive_rag import services
from adaptive_rag.api.routes_lab import best_modes
from adaptive_rag.config import settings
from adaptive_rag.query.quality import ModeQuality
from adaptive_rag.store import db
from tests.test_api import HANDBOOK, client, llm, llm_json, login  # noqa: F401

SNIPPET = HANDBOOK.decode()


def judge_first_passage(messages):
    """The relevance judge marks passage 1; everything else as in the API tests."""
    if "numbered passages" in messages[0]["content"]:
        return {"relevant": [1]}
    return llm_json(messages)


def add_snippet(client, headers, text=SNIPPET):  # noqa: F811
    return client.post("/lab/snippet", json={"text": text}, headers=headers)


def test_snippet_is_indexed_in_every_mode_but_the_decision_is_kept(client):  # noqa: F811
    headers = login(client)
    response = add_snippet(client, headers)
    assert response.status_code == 202

    lab = client.get("/lab", headers=headers).json()
    assert lab["document"]["status"] == "ready"
    assert lab["text"] == SNIPPET.strip()
    assert lab["strategy"] == "vector"  # small and plain: a normal upload builds vector only
    assert lab["modes"] == ["vector", "keyword", "hybrid"]  # the Lab built BM25 too (no Neo4j)
    assert services.bm25_store().has(lab["document"]["id"])


def test_snippet_stays_out_of_documents_quota_and_normal_questions(client, monkeypatch):  # noqa: F811
    headers = login(client)
    add_snippet(client, headers)
    assert client.get("/documents", headers=headers).json() == []
    # Not one of the user's documents for normal questions either
    response = client.post("/query", json={"question": "How many leave days?"}, headers=headers)
    assert response.status_code == 400
    # Nor for the document quota
    monkeypatch.setattr(settings, "max_documents_per_user", 1)
    upload = client.post("/documents", files={"file": ("a.md", b"# A\n\nText.")}, headers=headers)
    assert upload.status_code == 202


def test_query_compares_every_mode_on_one_judged_pool(client, llm):  # noqa: F811
    llm.data = judge_first_passage
    headers = login(client)
    add_snippet(client, headers)
    calls_before = len(llm.calls)

    response = client.post(
        "/lab/query", json={"question": "How many leave days do employees get?"}, headers=headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["strategy"] == "vector"
    assert result["adaptive_mode"] == "vector"  # what a normal upload would have used
    assert [m["mode"] for m in result["modes"]] == ["vector", "keyword", "hybrid"]  # adaptive first
    assert result["modes"][0]["used"] is True
    assert result["relevant_in_pool"] == 1
    for mode in result["modes"]:
        assert mode["found"] == len(mode["chunks"])
        assert sum(chunk["relevant"] for chunk in mode["chunks"]) == mode["relevant"]
    assert result["best_modes"]  # at least one mode found the relevant chunk
    assert len(llm.calls) - calls_before == 1  # rules classify; one judge call, no answers
    assert result["llm_calls"] == 1


def test_a_new_snippet_replaces_the_old_one_everywhere(client):  # noqa: F811
    headers = login(client)
    add_snippet(client, headers)
    old_id = client.get("/lab", headers=headers).json()["document"]["id"]

    assert (
        add_snippet(
            client, headers, "# Travel\n\nFlights over 6 hours may be business class."
        ).status_code
        == 202
    )
    new = client.get("/lab", headers=headers).json()
    assert new["document"]["id"] != old_id
    assert not services.bm25_store().has(old_id)
    with db.session_scope() as session:
        assert session.get(db.Document, old_id) is None
        assert db.load_chunks(session, old_id) == []


def test_snippet_can_be_deleted(client):  # noqa: F811
    headers = login(client)
    add_snippet(client, headers)
    assert client.delete("/lab", headers=headers).status_code == 204
    assert client.get("/lab", headers=headers).json() is None
    assert (
        client.post("/lab/query", json={"question": "Leave?"}, headers=headers).status_code == 409
    )


def test_snippet_length_is_limited(client, monkeypatch):  # noqa: F811
    headers = login(client)
    too_long = "word " * (settings.lab_max_chars // 5 + 1)
    assert add_snippet(client, headers, too_long).status_code == 422
    assert add_snippet(client, headers, "   ").status_code == 422


def test_snippet_counts_toward_the_daily_question_limit(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "max_queries_per_day", 1)
    headers = login(client)
    add_snippet(client, headers)
    assert (
        client.post("/lab/query", json={"question": "Leave?"}, headers=headers).status_code == 429
    )


def test_users_never_see_each_others_lab(client):  # noqa: F811
    alice = login(client, "alice@example.com")
    bob = login(client, "bob@example.com")
    add_snippet(client, alice)
    assert client.get("/lab", headers=bob).json() is None
    assert client.post("/lab/query", json={"question": "Leave?"}, headers=bob).status_code == 409


def mode(name, relevant, precision):
    return ModeQuality(
        mode=name, used=False, found=5, relevant=relevant, precision=precision, recall=None
    )


def test_best_modes_keep_ties_and_need_something_relevant():
    assert best_modes([mode("vector", 1, 0.2), mode("hybrid", 2, 0.4)]) == ["hybrid"]
    assert best_modes([mode("vector", 2, 0.4), mode("hybrid", 2, 0.4)]) == ["vector", "hybrid"]
    assert best_modes([mode("vector", 0, 0.0), mode("hybrid", 0, None)]) == []


def test_fewer_chunks_returned_does_not_make_a_mode_best():
    """Same evidence, but graph returned 4 chunks instead of 5: higher precision, not better."""
    assert best_modes([mode("vector", 1, 0.2), mode("graph", 1, 0.25)]) == ["vector", "graph"]
