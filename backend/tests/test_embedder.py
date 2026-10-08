"""Tests for the embedder: do embeddings capture meaning?"""

import numpy as np

from adaptive_rag.models.embedder import embed_query, embed_texts, embedding_size

CHUNKS = [
    "Employees receive 20 days of annual leave per year.",
    "Leave the building by the nearest exit during a fire alarm.",
    "Error AUTH-403 means the user token has expired.",
    "The Payment service depends on the Auth service.",
]


def cosine(a: list[float], b: list[float]) -> float:
    """Similarity of two vectors, from -1 to 1."""
    a_arr, b_arr = np.array(a), np.array(b)
    return float(a_arr @ b_arr / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


def ranked(question: str) -> list[tuple[float, str]]:
    """Chunks sorted from most to least similar to the question."""
    q = embed_query(question)
    scores = [(cosine(q, v), text) for v, text in zip(embed_texts(CHUNKS), CHUNKS, strict=True)]
    return sorted(scores, reverse=True)


def test_every_text_becomes_384_numbers():
    """bge-small turns any text into a fixed-size list of numbers."""
    assert embedding_size() == 384
    assert len(embed_query("hello")) == 384
    assert all(len(v) == 384 for v in embed_texts(CHUNKS))


def test_meaning_beats_shared_words():
    """'vacation days' finds 'annual leave' without sharing any words."""
    results = ranked("How many vacation days do I get?")
    assert results[0][1] == CHUNKS[0]
    # The fire-alarm chunk shares the word "leave" but means something else
    fire_score = next(score for score, text in results if text == CHUNKS[1])
    assert results[0][0] > fire_score


def test_relationship_question_finds_relationship_text():
    """A dependency question lands on the dependency sentence."""
    assert ranked("Which services rely on Auth?")[0][1] == CHUNKS[3]
