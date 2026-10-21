# Evaluation results

60 questions · retrieval only · graph available · 2026-10-21T07:07:30+00:00 · 335.0 s

## Overall

| Metric | vector | keyword | hybrid | graph | graph_hybrid | router |
|---|---:|---:|---:|---:|---:|---:|
| hit_at_5 | 0.982 | 0.964 | 0.982 | 0.818 | 1.000 | 1.000 |
| recall_at_5 | 0.976 | 0.958 | 0.976 | 0.806 | 0.994 | 0.988 |
| mrr | 0.892 | 0.873 | 0.892 | 0.700 | 0.896 | 0.882 |
| retrieval_ms_p50 | 1139.200 | 365.400 | 1170.600 | 324.600 | 1151.800 | 688.200 |
| retrieval_ms_p95 | 3905.100 | 3089.400 | 3725.200 | 2070.300 | 3778.300 | 2423.800 |

## Recall@5 by question type

| Type | vector | keyword | hybrid | graph | graph_hybrid | router |
|---|---:|---:|---:|---:|---:|---:|
| comparison | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact_lookup | 1.000 | 1.000 | 1.000 | 0.750 | 1.000 | 1.000 |
| keyword | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| multi_hop | 0.867 | 0.867 | 0.867 | 0.933 | 0.967 | 0.933 |
| relationship | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| semantic | 1.000 | 0.875 | 1.000 | 0.125 | 1.000 | 1.000 |

## Decisions

- Router accuracy: 0.982 (choices: {'vector': 24, 'hybrid': 8, 'graph': 22, 'graph_hybrid': 6})
- Strategy accuracy (built): 0.000 · rules alone: 0.000 · LLM alone: 0.000
- Rule coverage (questions classified without the LLM): 0.867
- Analysis cost ratio (sample tokens / full extraction tokens): 0.328
- Rewrite gain (relevance after - before, when rewritten): —

| Document | Rules | LLM | Built | Best measured | Expected by design | Confidence |
|---|---|---|---|---|---|---:|
| employee_handbook.md | vector | vector | vector | keyword | vector | 0.95 |
| security_policy.html | hybrid | hybrid | hybrid | keyword | hybrid | 0.95 |
| architecture.docx | graph_hybrid | graph_hybrid | graph_hybrid | graph | graph_hybrid | 0.90 |
| incident_runbook.md | graph_hybrid | hybrid | hybrid | vector | graph_hybrid | 0.79 |

Recall@5 per strategy (router picks the best mode it makes available):

| Document | keyword | vector | hybrid | graph | graph_hybrid |
|---|---:|---:|---:|---:|---:|
| employee_handbook.md | 1.000 | 1.000 | 1.000 | 0.692 | 1.000 |
| security_policy.html | 1.000 | 1.000 | 1.000 | 0.615 | 1.000 |
| architecture.docx | 0.947 | 0.947 | 0.947 | 0.973 | 0.987 |
| incident_runbook.md | 0.750 | 1.000 | 1.000 | 0.750 | 1.000 |
