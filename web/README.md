# Adaptive RAG: web dashboard

Next.js 16 (App Router), TypeScript, Tailwind CSS 4, Recharts.

| Page | What it shows |
|---|---|
| `/login`, `/register` | Email + password; the JWT is kept in localStorage |
| `/` | Your documents, upload, live status while scanning/indexing |
| `/documents/[id]` | Quick-scan signals, the LLM sample, the intent question, the strategy decision and reason, and "Build index" buttons |
| `/chat` | Ask questions; answers with citations and a "Why did I get this answer?" panel |
| `/eval` | Evaluation Lab: run retrieval or full evals and compare modes in charts and tables |

## Run

```bash
cp .env.example .env.local   # only if the API is not on http://localhost:8000
npm install
npm run dev                   # http://localhost:3000
```

The backend must be running (`cd ../backend && uv run uvicorn adaptive_rag.api.app:app`).

## Checks

```bash
npx tsc --noEmit && npm run lint && npm run build
```
