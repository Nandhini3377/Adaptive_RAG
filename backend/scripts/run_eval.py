"""Run the Evaluation Lab from the command line and write data/eval/results.{md,json}.

Usage (from backend/):
    uv run python scripts/run_eval.py                 # retrieval only: no answer LLM calls
    uv run python scripts/run_eval.py --full          # also answers: correctness, cost
    uv run python scripts/run_eval.py --full --limit 10 --types relationship multi_hop
    uv run python scripts/run_eval.py --no-cache      # bypass the LLM response cache

First run indexes the demo corpus (one sampled LLM call per document, plus graph
extraction when Neo4j is running). Generate the corpus first with
    uv run python ../scripts/generate_demo_docs.py
"""

import argparse
import logging

from adaptive_rag.config import settings
from adaptive_rag.eval.lab import ALL_MODES, run_lab, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Evaluation Lab")
    parser.add_argument("--full", action="store_true", help="generate answers (spends credits)")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--modes", nargs="+", choices=ALL_MODES, help="modes to compare")
    parser.add_argument("--types", nargs="+", help="only these question types")
    parser.add_argument("--no-cache", action="store_true", help="bypass the LLM response cache")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "neo4j.notifications"):  # one line per LLM call / Cypher hint
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if args.no_cache:
        settings.llm_cache_enabled = False
    report = run_lab(
        modes=args.modes,
        full=args.full,
        limit=args.limit,
        question_types=args.types,
        progress=print,
    )
    json_path, md_path = write_report(report)
    print(md_path.read_text(encoding="utf-8"))
    print(f"Saved {md_path} and {json_path}")


if __name__ == "__main__":
    main()
