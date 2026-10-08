# Build Steps — Adaptive RAG Engine

Learn-while-building plan. Each step has three parts:

- **Learn** — the concept behind it (ask Claude for the lesson before starting).
- **Build** — what you write.
- **Done when** — how you know it works. Don't move on until this passes.

Steps follow the PRD milestones. Every phase ends with something you can run and see.

---

## Phase 0 — Setup

| # | Learn | Build | Done when |
|---|---|---|---|
| 0.1 | Python packaging, virtual environments, Git, secrets in `.env` | `git init`, Python 3.12 via uv, `backend/` package, `.gitignore`, `.env` | `uv run python --version` prints 3.12 |
| 0.2 | **Lesson 1:** embeddings and similarity | Skipped: learned through the real embedder and its tests in Step 1.5 | — |

## Phase 1 — Core RAG (milestone M1)

| # | Learn | Build | Done when |
|---|---|---|---|
| 1.1 | Typed config with pydantic-settings | `config.py` reading `.env` | Settings load; missing key gives a clear error |
| 1.2 | Chat-completion APIs, tokens, reasoning tokens, JSON-schema output | `llm/base.py` (interface) + `llm/sarvam.py` | A test script gets a plain answer and a valid JSON answer from Sarvam |
| 1.3 | Document structure; Pydantic models as contracts between modules | `schemas.py` (`Element`, `Chunk`); `ingest/parser.py` for PDF, DOCX, HTML, MD, TXT | A sample PDF prints its headings, paragraphs, and tables in order |
| 1.4 | Chunking trade-offs; structure-aware chunking | `ingest/chunker.py` | Chunks never cross a section; tables stay whole |
| 1.5 | Vector databases, HNSW, payload filters | `models/embedder.py`, `store/vector_store.py` (Qdrant embedded) | Search returns the right chunk and respects an `owner_id` filter |
| 1.6 | Prompting for grounded answers with citations | `scripts/ask.py`: retrieve top-k → prompt → Sarvam | A question about a sample doc gets a cited answer from the command line |
| 1.7 | Relational data, ORMs, SQLite | `store/db.py`: `users`, `documents`, `chunks` tables | Chunks are saved and read back |
| 1.8 | Hashing and caching | `llm_cache` table; cache inside `llm/` | Second identical call returns instantly with 0 tokens |
| 1.9 | REST APIs, FastAPI, `202 Accepted`, background tasks | `api/`: `POST /documents`, `GET /documents/{id}`, `POST /query` | Upload and ask through the `/docs` page in the browser |

**Phase 1 checkpoint:** a working basic RAG over your own document.

## Phase 2 — Hybrid search and reranking (part of M2/M3)

| # | Learn | Build | Done when |
|---|---|---|---|
| 2.1 | **Lesson 2:** BM25 keyword search | `store/bm25_store.py` (LangChain BM25, rebuilt from SQLite) | "AUTH-403" finds the exact chunk that vector search misses |
| 2.2 | Reciprocal rank fusion | `retrieval/hybrid.py` (vector + BM25) | Hybrid finds both meaning matches and exact-term matches |
| 2.3 | **Lesson 3:** bi-encoders vs cross-encoders; reranking | `models/reranker.py` | Reranked order is visibly better on 3 test questions |
| 2.4 | Interfaces and the strategy pattern | `retrieval/base.py` (`Retriever`), `vector.py`, `hybrid.py` | Both modes run through one interface |

## Phase 3 — Knowledge graph (M2)

| # | Learn | Build | Done when |
|---|---|---|---|
| 3.1 | **Lesson 4:** graphs, nodes, edges, Cypher; Docker basics | `docker-compose.yml` (Neo4j only); hand-written Cypher practice | You can create and query a small graph in the Neo4j browser |
| 3.2 | LLM information extraction; entity normalization | `ingest/extractor.py` (entities + relationships as JSON) | Extraction on one section gives clean, deduplicated triples |
| 3.3 | Linking graph facts back to source text | `store/graph_store.py` (all Cypher lives here) | Each edge stores its `chunk_id`; owner filter works |
| 3.4 | Entity linking; multi-hop traversal | `retrieval/graph.py` | "What depends on Auth?" returns the right services and their chunks |
| 3.5 | Fusing graph and text results | `retrieval/graph_hybrid.py` | Comparison questions use both sources |

## Phase 4 — Document analysis, the differentiator (M2)

| # | Learn | Build | Done when |
|---|---|---|---|
| 4.1 | **Lesson 5:** cheap signals before expensive work; regex | `ingest/scanner.py` (structure counts, cross-refs, relationship phrases, IDs) | Signals look sensible on 2 very different documents |
| 4.2 | Sampling and estimating from a sample | `ingest/sampler.py` (pick 5–10 sections, LLM extraction) | Relationship density estimate is close to a full extraction on a test doc |
| 4.3 | Human-in-the-loop design | `ingest/intent.py` + `GET /analysis`, `POST /intent` | Suggested intents are pre-filled; skipping works |
| 4.4 | Rule tables, explainable decisions | `ingest/selector.py` (decision table, confidence, reason) | Each row of the PRD decision table has a passing unit test |
| 4.5 | State machines for job status | `ingest/jobs.py`: scanning → awaiting_intent → indexing → ready; `POST /build-index` | Upload flows end to end and only builds what the strategy needs |

## Phase 5 — Query intelligence and self-correction (M3)

| # | Learn | Build | Done when |
|---|---|---|---|
| 5.1 | **Lesson 6:** query classification; rules vs LLM | `query/classifier.py` (rules first, LLM fallback) | Most test questions are classified without the LLM |
| 5.2 | Routing with constraints | `query/router.py` (ideal mode, use only what's built, recommendation) | Every row of the PRD routing table has a passing unit test |
| 5.3 | **Lesson 9:** LangGraph state, nodes, conditional edges | `query/graph.py`: classify → route → retrieve → rerank → generate | One question runs through the graph and prints each step |
| 5.4 | **Lesson 7:** relevance gates and query rewriting | Relevance gate (reranker score) + rewriter loop with `MAX_RETRIES` | A vague question triggers a rewrite and improves |
| 5.5 | **Lesson 8:** hallucination, faithfulness, refusing | `eval/grounding.py` + insufficient-evidence response | An unanswerable question is refused instead of answered |
| 5.6 | Observability: traces, timings, cost | `observability.py`; `queries` table with timings, tokens, cost | Each answer shows per-step timings and cost in INR |

**Phase 5 checkpoint:** the full adaptive engine works through the API.

## Phase 6 — Evaluation Lab (M4)

| # | Learn | Build | Done when |
|---|---|---|---|
| 6.1 | **Lesson 10:** test data with known truth | `data/demo_spec.yaml` + `scripts/generate_demo_docs.py` | 4 demo documents generated from the spec |
| 6.2 | Gold labels | `data/eval/questions.jsonl` (60 questions, gold answers, gold chunks) | Every question checked by you |
| 6.3 | Hit@k, Recall@k, MRR | `eval/metrics.py` | Unit tests pass on hand-made examples |
| 6.4 | Experiment design: comparing modes fairly | `eval/lab.py` runs all modes + router; writes `results.md` and `results.json` | Results table produced |
| 6.5 | Tuning thresholds with data | Adjust decision, relevance, and routing thresholds | Strategy and router accuracy improve; numbers recorded |

## Phase 7 — UI (M5)

| # | Learn | Build | Done when |
|---|---|---|---|
| 7.1 | Next.js, React components, calling an API | `web/` app with an API client | Page lists your documents |
| 7.2 | Forms, polling for progress | Upload + analysis + intent screen | You can watch a document move through each stage |
| 7.3 | Showing explanations clearly | Chat + "Why did I get this answer?" panel + "Build index" button | Recommendations appear and the button works |
| 7.4 | Charts with Recharts | Evaluation Lab page | Mode comparison charts show real results |

## Phase 8 — Finish (M6)

| # | Learn | Build | Done when |
|---|---|---|---|
| 8.1 | **Lesson 11:** password hashing, JWT, data isolation | `auth.py`, login/register, owner filters everywhere | User B can never see user A's documents |
| 8.2 | Testing with mocks; linting | pytest suite with a fake LLM; ruff | `uv run pytest` and `ruff check` pass |
| 8.3 | CI | `.github/workflows/ci.yml` | Green check on GitHub |
| 8.4 | Presenting your work | README with diagram, results table, demo video | Someone new can run it from the README |

---

**Order note:** Step 1.5's embedder is built right after 1.1, while embeddings are fresh. Every step adds pytest tests instead of throwaway scripts.

**How we work each step:** ask for the lesson → Claude gives instructions and the why → you type and run → paste the output → Claude checks it → mark the step done here.

Progress: `[x]` 0.1 · `[-]` 0.2 · `[x]` 1.1 · `[x]` 1.5 · `[ ]` 1.2 (next)
