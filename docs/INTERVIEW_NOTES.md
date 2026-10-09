# Interview Notes — Adaptive RAG Engine

Your study guide. For each part: **what it does**, **why it's built that way**, **what we measured**, and **questions you may be asked** (with short answers). Read a section, open the file it points to, run its tests, then answer the questions out loud without looking.

Run all tests: `cd backend && .venv/bin/pytest -q`

---

## 0. The 30-second pitch

> Most RAG systems push every document through one fixed pipeline: chunk, embed, vector search. That works for simple facts but fails on exact IDs and on questions about how things connect. My system profiles each document cheaply when it's uploaded and picks an indexing strategy — Vector, Hybrid (vector + keyword), or GraphRAG — then routes every question to the best index that exists for that document. It reranks, checks relevance, rewrites the query if retrieval is weak, and verifies the answer is grounded in its citations. An Evaluation Lab measures every mode on quality, latency, and cost.

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
- **Reranker** (`bge-reranker-base`, a cross-encoder) reads question and chunk *together* — more accurate than embeddings, too slow for the whole corpus, so it only rescores the ~20 fused candidates. Scores squashed to 0–1 with a sigmoid.
- All modes share one `Retriever` interface (strategy pattern), so the router can swap modes.

**What we measured (honest findings):**
- Our first test assumed vector search would miss "AUTH-403". **It didn't** — bge-small found exact codes, even among AUTH-401…406. The real failure case is a code **buried inside a long chunk**: vector search ranked it **3rd**, behind chunks that only *looked* similar ("403 Forbidden", "AUTH-401"). BM25 ranked it 1st, and hybrid put it 1st.
- The reranker gave the right chunk only **0.23** for "What does AUTH-403 mean?" (but 0.97 for a more specific question). → The relevance threshold must be calibrated on data, not guessed.
- Classic **BM25Okapi** gives negative scores on 1–2 chunk documents (a word in every chunk gets negative weight), so small documents were unsearchable. Switched to **BM25Plus** and filter to chunks sharing at least one word.
- Replaced LangChain's `BM25Retriever` with `rank-bm25` directly: `langchain-community` is being discontinued, and the wrapper added nothing we used.

**Q: Why hybrid instead of only vectors?** Embeddings capture meaning but blur exact tokens, especially in long chunks. Keyword search is exact but misses paraphrases. Fusion gets both.

**Q: Bi-encoder vs cross-encoder?** Bi-encoder (embedder): question and chunk embedded separately, compare vectors — fast, precomputable. Cross-encoder (reranker): reads both together — accurate, but must run per pair at query time.

---

*More sections are added as each phase is built.*
