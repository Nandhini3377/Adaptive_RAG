# Adaptive RAG Engine

Most RAG systems push every document through one fixed pipeline (chunk → embed → vector search). This one **profiles each document when it's uploaded** and picks an indexing strategy (**Vector**, **Hybrid** = vector + keyword, or **Graph + Hybrid** = knowledge graph too), then **routes every question** to the best index that document has. It reranks, checks relevance, rewrites weak queries, verifies answers against their citations, and explains every decision. An **Evaluation Lab** measures each mode on 60 questions with known answers.

Built with FastAPI, LangGraph, Sarvam 105B, Qdrant (embedded), BM25, Neo4j, FastEmbed (ONNX), SQLite, and Next.js.

```text
upload → validate → parse → quick scan + LLM sample → intent → strategy decision
       → chunk → embed (Qdrant) + keywords (BM25) [+ knowledge graph (Neo4j)]

question → classify (rules first) → route → retrieve → rerank → relevance gate
         → (rewrite + retry) → answer with [n] citations → grounding check → explained answer
```

## Run it locally

You need: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20+, Docker Desktop (only for the graph), and a [Sarvam](https://dashboard.sarvam.ai) API key.

### 1. Secrets

```bash
cp .env.example .env
```

Fill in `.env`:

| Key | Needed for | How |
|---|---|---|
| `SARVAM_API_KEY` | answers, analysis | from the Sarvam dashboard |
| `JWT_SECRET` | logins that survive restarts | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `NEO4J_PASSWORD` | the knowledge graph | any long password you choose |

### 2. Neo4j (optional, for Graph modes)

```bash
docker compose up -d          # Neo4j browser: http://localhost:7474
```

Without it everything else works; graph strategies become "graph recommended" until it runs.

### 3. Backend

```bash
cd backend
uv sync
uv run uvicorn adaptive_rag.api.app:app --reload    # API docs: http://localhost:8000/docs
```

The first upload downloads the embedding and reranker models (~350 MB, once).

### 4. Web dashboard

```bash
cd web
npm install
npm run dev                                          # http://localhost:3000
```

### 5. Try it

1. Register, then upload a document (PDF, DOCX, HTML, Markdown, TXT).
2. Watch the scan, answer the intent question (or skip), and read the decision.
3. Ask questions on **Ask**; each answer shows its precision and relative recall. Open "Why did I get this answer?" for the detail.

### Command-line tools

```bash
cd backend
uv run python ../scripts/generate_demo_docs.py          # rebuild the demo corpus + 60 questions
uv run python scripts/ask.py ../PRD.md "Which LLM is used?"   # one-off question, no server
```

## Tests

```bash
cd backend
uv run pytest -m "not slow"                # fast offline suite (fake LLM, no network)
uv run pytest                              # + slow tests (real local models)
RUN_LIVE_LLM=1 uv run pytest -m live       # one real Sarvam call
uv run ruff check . && uv run ruff format --check .

cd web && npx tsc --noEmit && npm run lint && npm run build
```

Neo4j tests run automatically when `NEO4J_PASSWORD` is set and Neo4j is up; otherwise they're skipped.

## Project layout

```text
backend/src/adaptive_rag/
  api/          FastAPI routes (auth, documents, query)
  ingest/       parser, scanner, sampler, intent, selector, chunker, extractor, jobs
  store/        db (SQLite), vector_store (Qdrant), bm25_store, graph_store (Neo4j), files
  retrieval/    vector, hybrid, graph, graph_hybrid, fusion (RRF)
  query/        classifier, router, correction (relevance/rewrite/grounding), answer, quality (precision/recall), pipeline (LangGraph)
  llm/          interface, Sarvam client, response cache, usage meter
data/           demo_spec.yaml, demo_docs/, eval/questions.jsonl
web/            Next.js dashboard
docs/           PRD build steps, interview notes
```

See [PRD.md](PRD.md) for the full design and [docs/INTERVIEW_NOTES.md](docs/INTERVIEW_NOTES.md) for the reasoning behind each part.
