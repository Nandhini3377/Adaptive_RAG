"""Ask a question about one document from the command line (no server needed).

Usage:
    uv run python scripts/ask.py path/to/document.pdf "Your question?"
"""

import argparse
import time
from pathlib import Path

from adaptive_rag.ingest.chunker import chunk_elements
from adaptive_rag.ingest.parser import parse_file
from adaptive_rag.llm.cache import get_llm
from adaptive_rag.query.answer import generate_answer
from adaptive_rag.store.vector_store import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("document", type=Path)
    parser.add_argument("question")
    args = parser.parse_args()

    started = time.perf_counter()
    elements = parse_file(args.document)
    chunks = chunk_elements(elements, document_id=args.document.stem, owner_id="cli")
    store = VectorStore(location=":memory:")
    store.add_chunks(chunks)
    hits = store.search(args.question, owner_id="cli")
    print(f"Indexed {len(elements)} elements into {len(chunks)} chunks.\n")

    answer = generate_answer(args.question, hits, get_llm())
    print(answer.text, "\n")
    for citation in answer.citations:
        where = citation.section or "(no section)"
        page = f", page {citation.page}" if citation.page else ""
        print(f"[{citation.number}] {where}{page}: {citation.text[:100]!r}")
    print(
        f"\n{time.perf_counter() - started:.1f}s | tokens in {answer.input_tokens}, "
        f"out {answer.output_tokens} (reasoning {answer.reasoning_tokens}) | "
        f"₹{answer.cost_inr:.4f}"
    )


if __name__ == "__main__":
    main()
