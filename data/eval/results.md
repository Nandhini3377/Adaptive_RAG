# Evaluation results

5 questions · retrieval only · graph available · 2026-10-12T12:03:23+00:00 · 15.3 s

## Overall

| Metric | vector | hybrid | graph | graph_hybrid | router |
|---|---:|---:|---:|---:|---:|
| hit_at_5 | 1.000 | 1.000 | 0.800 | 1.000 | 1.000 |
| recall_at_5 | 1.000 | 1.000 | 0.800 | 1.000 | 1.000 |
| mrr | 1.000 | 1.000 | 0.800 | 1.000 | 1.000 |
| retrieval_ms_p50 | 487.300 | 459.700 | 394.600 | 524.100 | 487.300 |
| retrieval_ms_p95 | 5056.600 | 609.500 | 508.900 | 553.700 | 5056.600 |

## Recall@5 by question type

| Type | vector | hybrid | graph | graph_hybrid | router |
|---|---:|---:|---:|---:|---:|
| fact_lookup | 1.000 | 1.000 | 0.800 | 1.000 | 1.000 |

## Decisions

- Router accuracy: 1.000 (choices: {'vector': 5})
- Strategy accuracy: 1.000
- Rule coverage (questions classified without the LLM): 1.000
- Analysis cost ratio (sample tokens / full extraction tokens): 0.328
- Rewrite gain (relevance after - before, when rewritten): —

| Document | Decided | Best measured | Expected by design | Confidence |
|---|---|---|---|---:|
| employee_handbook.md | vector | vector | vector | 0.86 |
