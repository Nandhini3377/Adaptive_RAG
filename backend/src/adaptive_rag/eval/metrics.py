"""Evaluation metrics (PRD 16). Retrieval metrics need no LLM: they compare retrieved
chunk text with the gold evidence sentences from the demo spec.

- Hit@k:    did any of the top k chunks contain gold evidence?
- Recall@k: what share of the gold sentences appear in the top k chunks?
- MRR:      1 / rank of the first chunk with gold evidence (0 if none): rewards ranking it high.
"""

import math


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def contains_evidence(chunk_text: str, sentence: str) -> bool:
    """A chunk counts as gold if it contains the gold sentence (whitespace-insensitive)."""
    return _normalize(sentence) in _normalize(chunk_text)


def hit_at_k(chunks: list[str], evidence: list[str], k: int = 5) -> float:
    top = chunks[:k]
    return float(any(contains_evidence(c, s) for c in top for s in evidence))


def recall_at_k(chunks: list[str], evidence: list[str], k: int = 5) -> float:
    if not evidence:
        return 0.0
    top = chunks[:k]
    found = sum(any(contains_evidence(c, s) for c in top) for s in evidence)
    return found / len(evidence)


def reciprocal_rank(chunks: list[str], evidence: list[str]) -> float:
    for rank, chunk in enumerate(chunks, start=1):
        if any(contains_evidence(chunk, s) for s in evidence):
            return 1 / rank
    return 0.0


def answer_correct(answer: str, keywords: list[str]) -> bool:
    """Every gold keyword appears in the answer (normalized match; no LLM judge)."""
    text = _normalize(answer)
    return bool(keywords) and all(_normalize(str(k)) in text for k in keywords)


def percentile(values: list[float], p: float) -> float:
    """p-th percentile (0-100) with linear interpolation; 0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
