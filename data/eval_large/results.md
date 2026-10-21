# Evaluation results

64 questions · retrieval only · graph available · 2026-10-21T07:19:13+00:00 · 689.5 s

## Overall

| Metric | vector | keyword | hybrid | graph | graph_hybrid | router |
|---|---:|---:|---:|---:|---:|---:|
| hit_at_5 | 0.867 | 0.833 | 0.867 | 0.700 | 0.900 | 0.917 |
| recall_at_5 | 0.794 | 0.800 | 0.833 | 0.628 | 0.867 | 0.844 |
| mrr | 0.789 | 0.756 | 0.790 | 0.565 | 0.801 | 0.787 |
| retrieval_ms_p50 | 2089.400 | 1806.200 | 1760.600 | 843.500 | 1749.200 | 1773.600 |
| retrieval_ms_p95 | 4713.800 | 5256.300 | 4962.100 | 3961.700 | 4985.500 | 5397.100 |

## Recall@5 by question type

| Type | vector | keyword | hybrid | graph | graph_hybrid | router |
|---|---:|---:|---:|---:|---:|---:|
| comparison | 0.750 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact_lookup | 1.000 | 1.000 | 1.000 | 0.600 | 1.000 | 1.000 |
| keyword | 0.875 | 0.938 | 0.875 | 0.750 | 1.000 | 0.875 |
| multi_hop | 0.333 | 0.429 | 0.429 | 0.548 | 0.429 | 0.548 |
| relationship | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| semantic | 1.000 | 0.625 | 1.000 | 0.000 | 1.000 | 0.875 |

## Decisions

- Router accuracy: 0.917 (choices: {'vector': 18, 'graph': 24, 'graph_hybrid': 5, 'hybrid': 17})
- Strategy accuracy (built): 0.000 · rules alone: 0.500 · LLM alone: 0.000
- Rule coverage (questions classified without the LLM): 0.938
- Analysis cost ratio (sample tokens / full extraction tokens): 0.039
- Rewrite gain (relevance after - before, when rewritten): —

| Document | Rules | LLM | Built | Best measured | Expected by design | Confidence |
|---|---|---|---|---|---|---:|
| orion_architecture.md | graph_hybrid | hybrid | hybrid | graph_hybrid | graph_hybrid | 0.77 |
| orion_pay_reference.md | hybrid | hybrid | hybrid | graph_hybrid | hybrid | 0.93 |

Recall@5 per strategy (router picks the best mode it makes available):

| Document | keyword | vector | hybrid | graph | graph_hybrid |
|---|---:|---:|---:|---:|---:|
| orion_architecture.md | 0.765 | 0.725 | 0.765 | 0.696 | 0.814 |
| orion_pay_reference.md | 0.846 | 0.885 | 0.962 | 0.538 | 1.000 |
