"""End-to-end API tests: auth, upload, background indexing, query, isolation."""

import pytest
from fastapi.testclient import TestClient

from adaptive_rag import services
from adaptive_rag.api.app import create_app
from adaptive_rag.config import settings
from adaptive_rag.store import db
from adaptive_rag.store.bm25_store import BM25Store
from adaptive_rag.store.vector_store import VectorStore
from tests.conftest import FakeLLM

HANDBOOK = b"""# Leave Policy

Employees receive 20 days of annual leave per year.

# Security

Never share your password with anyone.
"""


def llm_json(messages):
    """Structured replies: a small sample extraction, and every claim supported."""
    content = messages[0]["content"]
    if "Check an answer" in content:
        return {"claims": [{"claim": "20 days of leave", "supported": True}]}
    if "Extract named entities" in content:
        return {"entities": [{"name": "Leave Policy", "type": "policy"}], "relationships": []}
    return {}


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM("Employees receive 20 days of annual leave [1].", data=llm_json)


@pytest.fixture
def client(memory_db, tmp_path, monkeypatch, llm):
    """An app with an in-memory database, in-memory Qdrant, a fake LLM, and a temp folder."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    services.override(
        vector_store=VectorStore(location=":memory:"),
        bm25_store=BM25Store(),
        graph_store=None,  # no Neo4j in these tests
        llm=llm,
    )
    yield TestClient(create_app())
    services.reset()


def login(client: TestClient, email: str = "alice@example.com") -> dict[str, str]:
    """Register and log in; return the auth header."""
    credentials = {"email": email, "password": "correct-horse"}
    client.post("/auth/register", json=credentials)
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers, name="handbook.md", content=HANDBOOK, intents=None):
    """Upload a file; with `intents`, send them along so indexing starts at once."""
    data = {"intents": intents} if intents else None
    return client.post("/documents", files={"file": (name, content)}, data=data, headers=headers)


def upload_ready(client, headers, name="handbook.md", content=HANDBOOK) -> str:
    """Upload, skip the intent question, and return the (now ready) document id."""
    document_id = upload(client, headers, name, content).json()["document_id"]
    client.post(f"/documents/{document_id}/intent", json={"skip": True}, headers=headers)
    return document_id


# ------------------------------------------------------------------- auth


def test_register_login_and_me(client):
    headers = login(client)
    assert client.get("/auth/me", headers=headers).json()["email"] == "alice@example.com"


def test_passwords_are_hashed_not_stored(client):
    login(client)
    with db.session_scope() as session:
        user = session.query(db.User).one()
        assert user.password_hash != "correct-horse"
        assert user.password_hash.startswith("$2")  # bcrypt format


def test_duplicate_email_and_wrong_password(client):
    login(client)
    duplicate = {"email": "alice@example.com", "password": "another-pass"}
    assert client.post("/auth/register", json=duplicate).status_code == 409
    assert client.post("/auth/login", json=duplicate).status_code == 401


def test_requests_without_a_valid_token_are_rejected(client):
    assert client.get("/documents").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/documents", headers=bad).status_code == 401


# ---------------------------------------------------------------- uploads


def test_upload_is_scanned_then_waits_for_intent(client, llm):
    headers = login(client)
    response = upload(client, headers)
    assert response.status_code == 202
    document_id = response.json()["document_id"]
    document = client.get(f"/documents/{document_id}", headers=headers).json()
    assert document["status"] == "awaiting_intent"
    assert len(llm.calls) == 1  # one sampled extraction call, no full extraction

    analysis = client.get(f"/documents/{document_id}/analysis", headers=headers).json()
    assert analysis["profile"]["section_count"] == 2
    assert analysis["suggested_intents"] == ["facts"]
    assert [o["id"] for o in analysis["intent_options"] if o["suggested"]] == ["facts"]
    assert analysis["strategy"] is None  # not decided until the intent arrives


def test_intent_decides_strategy_and_indexes(client):
    headers = login(client)
    document_id = upload(client, headers).json()["document_id"]
    response = client.post(
        f"/documents/{document_id}/intent", json={"intents": ["facts"]}, headers=headers
    )
    assert response.status_code == 202
    document = client.get(f"/documents/{document_id}", headers=headers).json()
    assert document["status"] == "ready"
    assert document["strategy"] == "vector"  # small, plain, facts only -> cheapest path
    assert document["has_bm25"] is False
    analysis = client.get(f"/documents/{document_id}/analysis", headers=headers).json()
    assert analysis["user_intents"] == ["facts"]
    assert "few relationships" in analysis["reason"]
    with db.session_scope() as session:
        assert len(db.load_chunks(session, document_id)) == 2  # one per section


def test_intents_sent_with_upload_skip_the_wait(client):
    headers = login(client)
    response = upload(client, headers, intents=["facts", "exact_terms"])
    document = client.get(f"/documents/{response.json()['document_id']}", headers=headers).json()
    assert document["status"] == "ready"
    assert document["strategy"] == "hybrid"
    assert document["has_bm25"] is True


def test_intent_is_only_accepted_while_waiting(client):
    headers = login(client)
    document_id = upload_ready(client, headers)
    again = client.post(f"/documents/{document_id}/intent", json={"skip": True}, headers=headers)
    assert again.status_code == 409


def test_build_index_adds_keyword_search(client):
    headers = login(client)
    document_id = upload(client, headers, intents=["facts"]).json()["document_id"]
    response = client.post(
        f"/documents/{document_id}/build-index", json={"index": "bm25"}, headers=headers
    )
    assert response.status_code == 202
    assert client.get(f"/documents/{document_id}", headers=headers).json()["has_bm25"] is True
    graph = client.post(
        f"/documents/{document_id}/build-index", json={"index": "graph"}, headers=headers
    )
    assert graph.status_code == 503  # no Neo4j in tests


def test_same_file_twice_is_not_duplicated(client):
    headers = login(client)
    first = upload(client, headers).json()
    second = upload(client, headers, name="copy.md").json()
    assert second == {"document_id": first["document_id"], "duplicate": True}
    assert len(client.get("/documents", headers=headers).json()) == 1


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("virus.exe", b"MZ..."),
        ("fake.pdf", b"just text pretending"),
        ("fake.docx", b"PK\x03\x04not really a zip"),
        ("binary.txt", b"\xff\xfe\x00\x00"),
        ("empty.md", b""),
    ],
)
def test_bad_files_are_rejected_by_content(client, name, content):
    response = upload(client, login(client), name=name, content=content)
    assert response.status_code == 415


# ------------------------------------------------------------------ query


def test_query_returns_cited_answer_and_is_recorded(client, llm):
    headers = login(client)
    upload_ready(client, headers)
    response = client.post(
        "/query", json={"question": "How many leave days do employees get?"}, headers=headers
    ).json()
    assert response["answer"] == "Employees receive 20 days of annual leave [1]."
    assert response["citations"][0]["section"] == "Leave Policy"
    assert response["query_type"] == "fact_lookup"
    assert response["mode"] == response["ideal_mode"] == "vector"
    assert response["scores"]["relevance"] > 0.5
    assert response["scores"]["grounding"] == 1.0
    assert {"classify", "retrieve", "rerank", "generate", "ground"} <= set(response["timings"])
    answer_prompt = next(c for c in llm.calls if c[0]["role"] == "system")
    assert "Employees receive 20 days" in answer_prompt[1]["content"]  # evidence in prompt
    with db.session_scope() as session:
        record = session.get(db.QueryRecord, response["query_id"])
        assert record.mode_used == "vector"
        assert session.get(db.Evaluation, record.id).faithfulness_score == 1.0


def test_relationship_question_on_vector_document_recommends_indexes(client):
    headers = login(client)
    document_id = upload(client, headers, intents=["facts"]).json()["document_id"]
    response = client.post(
        "/query",
        json={"question": "Which policy does the leave rule depend on?"},
        headers=headers,
    ).json()
    assert response["ideal_mode"] == "graph"
    assert response["mode"] == "vector"
    assert response["recommendation"]["index_to_build"] == "bm25+graph"
    assert response["recommendation_document_ids"] == [document_id]


def test_manual_mode_needs_its_index(client):
    headers = login(client)
    upload(client, headers, intents=["facts"])
    response = client.post("/query", json={"question": "Leave?", "mode": "hybrid"}, headers=headers)
    assert response.status_code == 400


def test_query_without_ready_documents_is_a_clear_error(client):
    response = client.post("/query", json={"question": "Hi?"}, headers=login(client))
    assert response.status_code == 400


# ------------------------------------------------------------- isolation


def test_users_never_see_each_others_documents(client, llm):
    alice = login(client, "alice@example.com")
    bob = login(client, "bob@example.com")
    alice_doc = upload_ready(client, alice)
    upload_ready(client, bob, name="bob.md", content=b"# Bob\n\nBob's salary is secret.")

    assert client.get(f"/documents/{alice_doc}", headers=bob).status_code == 404
    assert client.delete(f"/documents/{alice_doc}", headers=bob).status_code == 404
    assert [d["filename"] for d in client.get("/documents", headers=bob).json()] == ["bob.md"]

    # Bob asks about Alice's leave policy: none of her text reaches the LLM
    calls_before = len(llm.calls)
    client.post("/query", json={"question": "How many leave days?"}, headers=bob)
    bob_prompts = [m["content"] for call in llm.calls[calls_before:] for m in call]
    assert bob_prompts  # the query did reach the LLM
    assert all("annual leave" not in prompt for prompt in bob_prompts)

    # Bob cannot target Alice's document by ID either
    targeted = {"question": "Leave?", "document_ids": [alice_doc]}
    assert client.post("/query", json=targeted, headers=bob).status_code == 400


def test_delete_removes_document_everywhere(client):
    headers = login(client)
    document_id = upload(client, headers, intents=["exact_terms"]).json()["document_id"]
    assert services.bm25_store().has(document_id)
    assert client.delete(f"/documents/{document_id}", headers=headers).status_code == 204
    assert not services.bm25_store().has(document_id)
    assert client.get(f"/documents/{document_id}", headers=headers).status_code == 404
    with db.session_scope() as session:
        assert db.load_chunks(session, document_id) == []
    assert services.vector_store().count(owner_id=_user_id("alice@example.com")) == 0


def _user_id(email: str) -> str:
    with db.session_scope() as session:
        return session.query(db.User).filter(db.User.email == email).one().id
