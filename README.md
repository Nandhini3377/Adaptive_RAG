# Adaptive RAG Engine

Most RAG systems push every document through one fixed pipeline (chunk → embed → vector search). This one **profiles each document when it's uploaded**, lets **fixed rules and an LLM each pick an indexing strategy**, and builds **only the indexes both agree on**. Then it **routes every question** to the best index that document has. It reranks, measures every answer's retrieval (precision and recall), tries the other modes and then rewrites the question when the model finds no answer, and verifies answers against their citations. Document text reaches the LLM as quoted data, with instructions aimed at an AI removed (**prompt-injection defence**). An **Evaluation Lab** indexes a short text in every mode and shows whether the system's pick was the best one, and command-line evals score retrieval on 124 gold questions.

Built with FastAPI, LangGraph, Sarvam 105B, Qdrant (embedded), BM25, Neo4j, FastEmbed (ONNX), SQLite, and Next.js.

```text
upload → validate → parse → quick scan + LLM sample → intent
       → rules pick + LLM pick → build the indexes both share (the rest: suggested)
       → chunk → [embed (Qdrant)] [keywords (BM25)] [knowledge graph (Neo4j)]

question → classify (rules first) → route → retrieve (router's pick) → rerank
         → measure: one LLM call judges the fetched chunks (precision, recall)
         → answer with [n] citations → grounding check → explained answer
           no answer? → try every indexed mode, best evidence wins → still none? rewrite + retry
```

A question normally costs 3 LLM calls (judge, answer, grounding check), whatever the mode: searching itself uses none. The graph's LLM cost is paid once, when it is built.

## How a document is indexed

Each strategy builds exactly the indexes its search mode uses:

| Strategy | Indexes | Good for |
|---|---|---|
| Vector | vector | plain prose, questions in your own words |
| Keyword only | BM25 | exact IDs, codes, terms |
| Hybrid | vector + BM25 | most documents |
| Graph only | knowledge graph | questions that follow relationships |
| Graph + Hybrid | all three | many relationships, mixed questions |

1. **Quick scan** (regex, no LLM) and an **LLM sample** of a few sections measure IDs, tables, cross-references, and relationship density.
2. **The rules** pick from Vector, Hybrid, or Graph + Hybrid using fixed thresholds. "Many relationships" means dense relationships in the sample, or many cross-references *and* relationship phrases, or relationship phrases so dense (over 9 per 1,000 words) that they count on their own: dependencies written as plain "X depends on Y" sentences.
3. **The LLM** picks from all five. It gets every number, the uploader's intent, and the rules' criteria already checked in code ("cross-references 22.9 vs more than 2 → met"), but not the rules' pick, so its answer stays independent. One short call (about ₹0.01).
4. **Only the indexes both picks share are built.** If they share none, the rules' pick is built. Whatever only one side wanted is offered on the document page as a one-click addition.

The graph is the expensive index (LLM calls over the whole document), so it is only built when both sides want it.

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

Without it everything else works; the graph is offered as a suggestion until it runs.

### 3. Backend

```bash
cd backend
uv sync
uv run uvicorn adaptive_rag.api.app:app --reload    # API docs: http://localhost:8000/docs
```

The first upload downloads the embedding and reranker models (~250 MB, once).

### 4. Web dashboard

```bash
cd web
npm install
npm run dev                                          # http://localhost:3000
```

### 5. Try it

1. Register, then upload a document (PDF, DOCX, HTML, Markdown, TXT).
2. Watch the scan, answer the intent question (or skip), and read the decision: the rules' pick, the LLM's pick, what was built, and what is suggested.
3. Ask questions on **Ask**. The mode is always automatic: the router picks it from the question type and the indexes the documents have. Each answer shows its precision (relevant chunks among the 5 given to the model) and recall (relevant chunks in those 5 out of all relevant chunks among the 20 the mode fetched). If the router's pick finds no answer, every indexed mode is tried and the one with the most relevant chunks wins. Open "Why did I get this answer?" for the detail. A document whose text looks like instructions to an AI gets a warning on its page.
4. Open **Evaluation Lab**, paste up to 8,000 characters, and ask a question. Every mode searches the same text, one LLM call judges the chunks, and the page shows which mode was best and whether the rules alone, the LLM alone, and the built overlap would have used it. Use a text longer than a few paragraphs: with about 5 chunks every mode returns nearly all of it and they tie.

### Command-line tools

```bash
cd backend
uv run python ../scripts/generate_demo_docs.py          # demo corpus: 4 small documents + 60 gold questions
uv run python ../scripts/generate_large_docs.py         # large corpus: 2 ~20-page documents + 64 gold questions
uv run python scripts/run_eval.py                       # score every mode on the demo corpus (retrieval only)
uv run python scripts/run_eval.py --corpus large        # ... on the large corpus
uv run python scripts/run_eval.py --full                # also generate answers (spends credits)
uv run python scripts/run_injection_eval.py --label after   # prompt-injection attacks (spends credits)
uv run python scripts/ask.py ../PRD.md "Which LLM is used?"   # one-off question, no server
```

The evals index their documents under a separate evaluation user and stop when the API is running (both use the embedded Qdrant folder). Graph modes need Neo4j up. Results go to `data/eval/` and `data/eval_large/`.

## What the evals show

Retrieval, Recall@5 against exact gold sentences:

| | Vector | Hybrid | Graph + Hybrid | Router |
|---|---:|---:|---:|---:|
| Large corpus (64 questions, ~20 pages each) | 79% | 83% | **87%** | 84% |
| Large corpus, multi-hop only | 33% | 43% | 43% | **55%** (graph) |
| Demo corpus, multi-hop (after the graph fixes) | 87% | 87% | **97%** | 93% |

- On small documents (5-20 chunks) every mode ties: the top 5 is most of the document. The large corpus is what separates them.
- Graph retrieval follows only the relation types the question names ("depend" → DEPENDS_ON), ignores generic words as entities, and keeps the chunks its paths cite in the top 5 (the reranker scored a dependency table low because it does not read like the question).
- The router was already best on 14 of 14 multi-hop questions in the large corpus, so modes are compared only when the router's pick finds no answer.
- Profiling a document costs about 4% of building its graph.
- Prompt injection (`data/eval/injection_*.md`): attacks that changed the answer fell from 47% to 0% on the 10 attack styles the defence was built from, but stayed at 40% on 5 held-out wordings. Pattern removal does not generalise; it is a first layer, not a complete defence.
- Not solved yet: indirect dependencies 3+ hops away (graph walks stop at 2), graph entities matched by exact name only, and the LLM strategy pick still refuses the graph on one document the rules now flag.

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
  api/          FastAPI routes (auth, documents, query, lab)
  ingest/       parser, scanner, sampler, intent, selector (rules), strategy_llm (LLM pick + combine),
                chunker, extractor, jobs
  store/        db (SQLite), vector_store (Qdrant), bm25_store, graph_store (Neo4j), files
  retrieval/    vector, keyword, hybrid, graph, graph_hybrid, fusion (RRF)
  query/        classifier, router, correction (rewrite/grounding), answer, quality (precision/recall), pipeline (LangGraph)
  llm/          interface, Sarvam client, response cache, usage meter, safety (prompt-injection defence)
  eval/         lab (every mode on a gold corpus, strategy accuracy), metrics (Hit@5, Recall@5, MRR)
backend/scripts/ ask.py, run_eval.py, run_injection_eval.py
scripts/        generate_demo_docs.py, generate_large_docs.py
data/           demo_spec.yaml, demo_docs/, eval/ (questions + results), eval_large/ (docs, questions, results)
web/            Next.js dashboard
docs/           PRD build steps, interview notes
```

See [PRD.md](PRD.md) for the full design and [docs/INTERVIEW_NOTES.md](docs/INTERVIEW_NOTES.md) for the reasoning behind each part.
