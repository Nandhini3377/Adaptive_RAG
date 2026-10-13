# Interview Notes — Adaptive RAG Engine

Your study guide. For each part: **what it does**, **why it's built that way**, **what we measured**, and **questions you may be asked** (with short answers). Read a section, open the file it points to, run its tests, then answer the questions out loud without looking.

Run all tests: `cd backend && .venv/bin/pytest -q`

---

## 0. The 30-second pitch

> Most RAG systems push every document through one fixed pipeline: chunk, embed, vector search. That works for simple facts but fails on exact IDs and on questions about how things connect. My system profiles each document cheaply when it's uploaded and picks an indexing strategy — Vector, Hybrid (vector + keyword), or GraphRAG — then routes every question to the best index that exists for that document. It reranks, checks relevance, rewrites the query if retrieval is weak, and verifies the answer is grounded in its citations. Every answer reports the precision and relative recall of its retrieval.

---

## 1. The pipeline at a glance

```text
upload → validate (by content) → parse → Elements → chunk → Chunks
       → embed → Qdrant (vectors)  +  SQLite (text)  +  BM25 (keywords)  [+ Neo4j graph]

question → retrieve (vector / hybrid / graph) → rerank → relevance check
         → LLM answer with [n] citations → grounding check → answer + evidence
```

---

## 2. Configuration — `config.py`

- All tunable values live in one `Settings` class (pydantic-settings), read from `.env`.
- Secrets use `SecretStr`, so printing settings shows `**********`.
- If `JWT_SECRET` is missing, a random one is generated at startup (secure, but everyone is logged out on restart). We do **not** ship a weak default: PyJWT warned our first placeholder was only 18 bytes.

**Q: Why not hard-code thresholds?** So they can be tuned against the evaluation set without code changes (PRD FR16).

---

## 3. Parsing — `ingest/parser.py`

Every format becomes the same `list[Element]` (heading, paragraph, list, table), each tagged with its **section** (nearest heading above it).

| Format | Headings found by | Tables found by |
|---|---|---|
| Markdown | `#` syntax via markdown-it tokens | `\|` rows (table rule enabled) |
| HTML | `<h1>`–`<h6>`; scripts, nav, footer removed | `<table>` → Markdown |
| DOCX | Word "Heading N" styles | Word tables → Markdown |
| PDF | **Guessed**: text ≥15% bigger than body text, or a short all-bold line | PyMuPDF `find_tables()`; text inside tables is skipped so it isn't duplicated |
| TXT | none (paragraphs at blank lines) | none |

Design: each format has a small "reader" that yields raw blocks; one shared `_assemble` function adds sections and joins list items. Section logic exists in exactly one place.

**Q: Why parse into elements instead of plain text?** Plain text loses structure. The chunker needs sections (so chunks never mix topics) and table boundaries (so tables are never cut). Citations need section names.

**Q: What's hard about PDFs?** PDFs store positioned characters, not structure. Headings must be inferred from font size and boldness. The body font size is the size used for the most characters. Known limits: two-column layouts, headers/footers repeating on every page.

**Q: Element vs Chunk?** Element = what the parser found (one paragraph). Chunk = what gets embedded and searched (sized for retrieval, carries id/document/owner).

---

## 4. Chunking — `ingest/chunker.py`

Rules (PRD FR17):
1. A chunk never crosses a section boundary.
2. A table is always its own chunk and is never split, even if long.
3. Paragraphs/lists are packed up to `chunk_max_chars` (1500 ≈ 300–400 tokens; the embedder reads at most 512 tokens).
4. A paragraph longer than the limit is split at sentence ends; a single huge sentence is split at spaces.
5. Chunk IDs are **deterministic** (`uuid5(document_id:position)`), so re-indexing overwrites instead of duplicating.

**Q: Why no overlap between chunks?** Sections are natural boundaries, so overlap adds cost with little gain. Trade-off: a fact split across two paragraphs in different chunks can be missed. Overlap could be added inside long sections.

**Q: Why characters, not tokens?** Simpler and no tokenizer dependency; 1500 chars stays safely under the 512-token model limit.

---

## 5. Embeddings + vector store — `models/embedder.py`, `store/vector_store.py`

- `BAAI/bge-small-en-v1.5` via FastEmbed (ONNX Runtime, no PyTorch), 384 dimensions.
- Questions get an instruction prefix, chunks don't (asymmetric search: BGE models are trained this way).
- Qdrant in **embedded mode** (no server). Embedded Qdrant locks its folder, so the app shares one `VectorStore` (see `services.py`).
- **Every search filters by `owner_id`** in the database query itself, not after retrieval.

**Q: Why filter inside the query, not after?** Filtering after top-k could return fewer than k results, and it's easy to forget. Inside the query, other users' data can never come back.

---

## 6. LLM client — `llm/base.py`, `llm/sarvam.py`, `llm/cache.py`

- `LLM` is an abstract interface (`complete`, `complete_json`). The app never imports the provider SDK directly → provider can be swapped.
- Sarvam 105B is called via its OpenAI-compatible API using the `openai` SDK with a custom `base_url`.
- Structured calls use `response_format: json_schema`, so the model must return JSON of a given shape.
- Retries on 429/5xx with backoff (SDK built-in), 120 s timeout, clear errors.
- Cost in ₹ is computed per call from token counts.
- **Cache:** SQLite table keyed by SHA-256 of (model, messages, schema, max_tokens, effort). A repeat call returns instantly with 0 tokens and ₹0.

**What we measured (real calls):**
- Sarvam is a *reasoning* model: "reply hello" used 40 output tokens, 35 of them reasoning.
- For a RAG answer, reasoning varied from **1,000 to 3,600 tokens** across 5 identical calls, and once exceeded 6,000. Setting `reasoning_effort` low vs unset made little difference.
- Fix: `max_tokens=8000` plus **one automatic retry** when the model runs out of tokens before answering (the variance means a retry usually succeeds). Tokens from the failed attempt are still counted in the cost.
- Typical answer cost ≈ ₹0.2–0.4; latency ≈ 10–20 s (PRD target was < 6 s — reasoning is the bottleneck).

**Q: How do you test code that calls a paid API?** A fake HTTP transport (`httpx.MockTransport`) returns canned responses, so tests are free, fast, and deterministic. They check our request (model, caps, schema) and our parsing. One opt-in live test (`RUN_LIVE_LLM=1 pytest -m live`) confirms the real API still matches.

---

## 7. Grounded answers — `query/answer.py`

- Prompt = rules + numbered evidence `[1] (Section: X, page N)` + question.
- The model must cite every fact as `[n]` and reply `NO_ANSWER` if the evidence doesn't contain it → we return the standard "I don't have enough evidence…" message.
- Citations returned are only the chunks the answer actually cites (parsed from `[n]`, `[1, 3]`, `[1][2]`; invalid numbers ignored).
- No hits → refuse without calling the LLM (saves money).
- A `strict` prompt variant exists for regenerating after a failed grounding check (FR34).

**Q: How do you reduce hallucination?** Answer only from numbered evidence, require citations, allow an explicit "no answer", and (M3) verify each claim against its cited chunk with a second LLM call.

---

## 8. Database, auth, API — `store/db.py`, `auth.py`, `api/`

- SQLAlchemy models for all PRD tables on SQLite. Foreign keys are switched on (SQLite skips them by default), so deleting a document cascades to its chunks.
- Passwords: **bcrypt** (salted, deliberately slow). Login returns a **JWT** signed with `JWT_SECRET`, expiring after 24 h.
- Same error for "unknown email" and "wrong password" → attackers can't discover which emails exist.
- Accessing someone else's document returns **404, not 403** → doesn't reveal that it exists.
- Uploads are validated **by content**: PDFs must start with `%PDF-`, DOCX must be a zip containing `word/document.xml`, text formats must be valid UTF-8 with no binary bytes. Size limit 50 MB.
- Same file uploaded twice (same SHA-256) by the same user → existing document is returned, nothing duplicated.
- `POST /documents` returns **202 Accepted** immediately; indexing runs as a FastAPI background task and writes status/progress to SQLite, which the UI polls.

**Q: Why 202 and background tasks instead of Celery?** One-user demo scale; no Redis needed. Trade-off: a server restart loses in-flight jobs (PRD v2 roadmap: Celery).

**Q: How do you guarantee user isolation?** `owner_id` on every row/chunk/vector, filters in every store query, and a test where Bob tries to read, delete, and search Alice's document (`tests/test_api.py::test_users_never_see_each_others_documents`).

---

## 9. Hybrid search + reranking — `store/bm25_store.py`, `retrieval/`, `models/reranker.py`

- **BM25** keyword index per document, in memory, rebuilt from SQLite chunks on start.
- Custom tokenizer: lowercase, keeps IDs like `auth-403`, `v2.1`, `user_id` whole, drops stopwords ("what", "does"), light plural stemming ("means" → "mean").
- **Reciprocal rank fusion** merges the vector and BM25 lists: `score = Σ 1/(60 + rank)`. Ranks are comparable across methods; raw scores (cosine 0–1 vs BM25 0–30) are not.
- **Reranker** (`ms-marco-MiniLM-L-12-v2`, a cross-encoder; swapped from `bge-reranker-base` — 0.12 GB vs 1.04 GB — so the API fits a 2 GB server) reads question and chunk *together* — more accurate than embeddings, too slow for the whole corpus, so it only rescores the ~20 fused candidates. Scores squashed to 0–1 with a sigmoid.
- All modes share one `Retriever` interface (strategy pattern), so the router can swap modes.

**What we measured (honest findings):**
- Our first test assumed vector search would miss "AUTH-403". **It didn't** — bge-small found exact codes, even among AUTH-401…406. The real failure case is a code **buried inside a long chunk**: vector search ranked it **3rd**, behind chunks that only *looked* similar ("403 Forbidden", "AUTH-401"). BM25 ranked it 1st, and hybrid put it 1st.
- The reranker gave the right chunk only **0.23** for "What does AUTH-403 mean?" (but 0.97 for a more specific question). → The relevance threshold must be calibrated on data, not guessed.
- Classic **BM25Okapi** gives negative scores on 1–2 chunk documents (a word in every chunk gets negative weight), so small documents were unsearchable. Switched to **BM25Plus** and filter to chunks sharing at least one word.
- Replaced LangChain's `BM25Retriever` with `rank-bm25` directly: `langchain-community` is being discontinued, and the wrapper added nothing we used.

**Q: Why hybrid instead of only vectors?** Embeddings capture meaning but blur exact tokens, especially in long chunks. Keyword search is exact but misses paraphrases. Fusion gets both.

**Q: Bi-encoder vs cross-encoder?** Bi-encoder (embedder): question and chunk embedded separately, compare vectors — fast, precomputable. Cross-encoder (reranker): reads both together — accurate, but must run per pair at query time.

---

## 10. Document analysis — `ingest/scanner.py`, `sampler.py`, `intent.py`, `selector.py`, `jobs.py`

**The differentiator.** Decide how to index a document *without* chunking/embedding/extracting all of it.

1. **Quick scan (no LLM, whole document, milliseconds):** counts pages, sections, tables, lists, links; regex rates per 1,000 words for cross-references ("see Section 4.2"), relationship phrases ("depends on", "owned by"), and identifiers (AUTH-403, v2.1.0, snake_case, acronyms); share of words in tables.
2. **LLM sample:** 5–10 sections — the most relationship-heavy half plus evenly spread ones — sent in **one** call asking for ≤ 40 entities and relationships. Gives *relationship density* (relationships per entity) and *entity repetition* (share of sampled entities appearing in 3+ sections, by string match over the full text).
3. **Intent:** "What will you mostly ask?" — pre-filled from the scan; optional (skip = scan decides).
4. **Decision table** (PRD FR15) → vector / hybrid / graph_hybrid, with a **confidence** (clear scan signal + agreeing intent = higher) and a **plain-language reason with the numbers**. "Many relationships but you only want facts" → hybrid, marked *graph candidate*.
5. **State machine** in SQLite: `scanning → awaiting_intent → indexing → ready` (or `failed` with the error). The UI polls it. Every step is wrapped so a crash marks the document failed instead of leaving it stuck.

**What we measured:** on the real PRD, the first sample call **ran out of tokens** (8K cap) — a dense spec produces a long JSON list *plus* reasoning. Fix: 16K cap and "at most 40 items". If the LLM still fails, the scan alone decides (graceful degradation), and the reason says so.

**Q: Why not just build every index for every document?** Cost and time. Graph extraction for a 100-page document is ~100K tokens; the sample is a fraction. The Evaluation Lab reports the *analysis cost ratio*. And any index can still be added later with one click.

**Q: How did you pick the thresholds?** PRD starting values in config; they're meant to be tuned against the eval set, and the lab reports *strategy accuracy* (decision vs best measured strategy) to show whether they're right.

---

## 11. Knowledge graph — `ingest/extractor.py`, `store/graph_store.py`, `retrieval/graph*.py`

- Extraction runs only for graph strategies. Chunks go to the LLM in ~12K-character batches; JSON schema returns entities and relationships, each relationship naming the **chunk number** that states it and a **confidence**.
- **Entity normalization:** `entity_key()` lowercases and strips articles/punctuation, so "The Auth-Service" and "auth service" become one node. Later batches are given the entity names already found and told to reuse them.
- Low-confidence (< 0.5) relationships, self-loops, and invalid chunk numbers are dropped; duplicate facts keep the highest confidence.
- Neo4j model: `(:Entity)-[:RELATES {type, chunk_id, confidence}]->(:Entity)` and `(:Chunk)-[:MENTIONS]->(:Entity)`. Entity ids are `document_id:key`, so documents never share nodes and deletes are clean. **All Cypher lives in `graph_store.py`.**
- **Graph retrieval:** link entities whose names appear in the question → traverse up to 2 hops in either direction → the chunks stating those edges (shortest paths first), then chunks mentioning the entities. Paths keep their real edge direction for the UI ("Auth Service ←DEPENDS_ON— Payments").
- **Graph + Hybrid:** graph hits and hybrid hits fused with RRF.

**Honest status:** the Neo4j code is unit-tested offline only where possible; the two Neo4j integration tests skip until Neo4j runs. Verify them first when you set up Docker.

**Q: Why store `chunk_id` on every edge?** So a graph answer can cite the source sentence. A graph fact without its source text can't be checked.

---

## 12. Query intelligence and self-correction — `query/`

- **Classifier (rules first):** regex rules for comparison, multi-hop (two different relationship verbs, e.g. "teams that **own** services **affected** by…"), relationship, aggregation, keyword (IDs or quoted terms), fact lookup. Only when no rule is confident is the LLM asked. On the eval set, rules cover ≥ 80% of questions — free and instant.
- **Router:** ideal mode per type (fact/semantic → vector, keyword → hybrid, relationship/multi-hop → graph, comparison/aggregation → graph_hybrid), but **only modes whose indexes exist**. Otherwise it uses the strongest available mode and attaches a **recommendation** ("Build the graph for this document?"). Nothing is built without the user.
- **Relevance gate (no LLM):** score = average of the top-1 reranker score and the mean of the top 3 (0–1). Below the threshold → **rewrite** the query (one LLM call that avoids earlier attempts) → retrieve again, up to 2 retries → otherwise refuse with the standard insufficient-evidence message.
- **Grounding check:** one LLM call splits the answer into claims and checks each against its cited chunk. Unsupported claims → regenerate once with a stricter prompt → still unsupported → refuse.
- **LangGraph** state machine wires it: classify → route → retrieve → rerank → evaluate → (rewrite ↺) → generate → ground → (regenerate ↺) → done/refuse. Each node is timed; a `MeteredLLM` wrapper adds up tokens and cost across every call in one query.

**Q: Why rerank against the original question, not the rewrite?** The rewrite is only a better search query; the answer still has to address what the user asked.

**Q: Why LangGraph instead of plain function calls?** The flow has loops (rewrite, regenerate) and conditional exits. A state machine makes every path explicit and testable — the tests cover the happy path, rewrite-then-success, retries exhausted, regenerate-then-pass, and regenerate-then-refuse.

**Q: What's the threshold?** 0.15 to start. We measured reranker scores as low as 0.23 for a *correct* top chunk, so a high threshold would refuse good answers. It must be calibrated with the Evaluation Lab.

---

## 13. Retrieval quality on every question — `query/quality.py`

The Evaluation Lab (section 13b) was removed from the app on 2026-10-12: it only scored a fixed demo corpus and was heavy to run. Quality is now measured on each real question instead.

- **The problem:** a live question has no gold answer, so "which chunks are relevant" and "what did we miss" are both unknown.
- **Relevance:** one LLM call judges numbered chunks and returns the numbers that help answer the question.
- **Precision** = relevant chunks given to the model / chunks given to the model (top 5 after reranking).
- **Relative recall** uses **pooling**, the method TREC search evaluations use. The pool is the chunks used plus the top 5 from every *other* mode the documents have an index for. Relative recall = relevant chunks used / relevant chunks in the pool.
- It runs as the last pipeline node (`measure`), so its time, tokens, and cost show up with the rest. If the judge call fails, the answer is kept and the scores are shown as not measured.
- With only one index there is no pool to compare against, so recall is reported as not measured rather than a misleading 100%.

**Q: Why "relative" recall?** True recall needs every relevant chunk in the document, which nobody knows for a new question. Pooling counts only what some mode found, so it is an upper bound: a chunk every mode missed is invisible.

**Q: What does it cost?** One extra LLM call per question, plus a cheap search (no reranking) with each other mode. `retrieval_quality_enabled` turns it off.

**Q: Can you trust an LLM as the judge?** Not fully: it is noisy, like the grounding checker, and it was not calibrated against human labels. It is a signal for the user, not a gate; nothing in the pipeline acts on it.

---

## 13b. Evaluation Lab (removed; in git history) — `data/demo_spec.yaml`, `scripts/generate_demo_docs.py`, `eval/`

- **Corpus:** one YAML spec of a fictional company (Nimbus Labs: 15 services, dependencies, 7 teams, policies, error codes, incidents) → 4 documents with deliberately different profiles and formats (handbook .md, security .html, architecture .docx, runbook .md) and **60 questions** in the PRD mix (12 fact, 8 keyword, 8 semantic, 12 relationship, 10 multi-hop, 5 comparison, 5 unanswerable).
- Every fact sentence comes from one template function used by both the documents and the questions, so each question's **gold evidence** is an exact sentence. A test checks every gold sentence really sits inside one chunk — otherwise the metrics would measure nothing.
- **Metrics (no LLM):** Hit@5, Recall@5, MRR against gold sentences; retrieval latency p50/p95. **Full mode** adds answer correctness (all gold keywords present), faithfulness (grounding score), refusal accuracy on unanswerable questions, false refusals, end-to-end latency, tokens, and ₹ per query.
- **Router accuracy:** the router's pick is among the best-scoring modes for that question. Scored by reusing each mode's results, so it costs nothing extra.
- **Strategy accuracy:** each upload decision vs the *cheapest* strategy whose (router-oracle) recall is within 0.02 of the best.
- **Rule coverage, analysis cost ratio, rewrite gain** are reported too. Output: `data/eval/results.md` + `results.json`, and charts in the UI.

**Q: Isn't a generated corpus artificial?** Yes — that's the trade-off for exact gold answers with no labelling cost or licensing issues. The PRD plans one real public document as well, and the questions must still be **checked by hand** (that's your job before trusting the numbers).

**Q: Why keyword matching for answer correctness instead of an LLM judge?** Deterministic, free, explainable. The cost is false negatives when the answer paraphrases (e.g. "twenty" vs "20").

---

## 14. Web dashboard — `web/`

- Next.js 16 App Router, TypeScript strict, Tailwind 4. All pages are client components talking to the FastAPI API through one typed client (`lib/api.ts`, types mirroring the backend models).
- Background work is shown by **polling** status every 2–3 s (simple, no websockets needed at this scale).
- Next 16 with Cache Components requires a `<Suspense>` boundary around client components that read the URL (`useParams`, `useSearchParams`, `usePathname`) — the build fails otherwise.
- React 19's lint forbids `setState` directly in effects; data loads use `useEffectEvent` (`hooks/usePolling.ts`), and the auth guard reads localStorage with `useSyncExternalStore`.

**Q: Where is the JWT stored and what's the risk?** localStorage — simple for a demo, but readable by any injected script (XSS). Production would use an httpOnly cookie.
