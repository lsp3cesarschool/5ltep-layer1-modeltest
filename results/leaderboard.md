*Updated 2026-10-24 11:18 UTC · 30 gold cases (12 real, 18 synthetic) · production code at `2266143`*

**Recommendation:** llama3.1:8b beats qwen3:8b by +0.059 name-F1 (paired 95% CI [-0.003, +0.154]), which is not enough to switch.

| # | Model | Stage | Name-F1 [95% CI] | EM | LS | Types | Valid | Latency p50 / p90 (s) | PDFs/h | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | llama3.1:8b | confirm | **0.99** [0.98, 1.00] | 0.99 | 1.00 | 1.00 | 100% | 198 / 511 | 14.4 | eligible |
| 2 | ministral-3:8b | confirm | **0.99** [0.97, 1.00] | 0.99 | 0.99 | 0.99 | 100% | 211 / 516 | 13.0 | eligible |
| 3 | qwen3:8b | confirm | **0.93** [0.84, 0.99] | 0.93 | 0.96 | 1.00 | 100% | 159 / 396 | 18.1 | eligible |
| 4 | gemma3:4b | confirm | **0.87** [0.76, 0.97] | 0.88 | 0.92 | 1.00 | 100% | 77 / 184 | 39.8 | eligible |
| 5 | gemma3:12b | triage | **0.97** [0.92, 1.00] | 0.97 | 0.98 | 1.00 | 100% | 219 / 611 | 10.9 | triage only |
| 6 | qwen3:1.7b | triage | **0.91** [0.80, 0.99] | 0.89 | 0.96 | 0.98 | 100% | 47 / 171 | 43.1 | triage only |
| 7 | qwen3:4b-q4_K_M | triage | **0.90** [0.73, 1.00] | 0.90 | 0.93 | 0.99 | 100% | 69 / 217 | 32.2 | triage only |
| 8 | granite4:3b | triage | **0.84** [0.67, 0.97] | 0.80 | 0.93 | 0.95 | 100% | 69 / 242 | 30.2 | triage only |
| 9 | qwen3.5:0.8b | triage | **0.83** [0.65, 0.96] | 0.78 | 0.88 | 0.80 | 100% | 28 / 70 | 94.0 | triage only |
| 10 | qwen3:4b | triage | **0.82** [0.58, 0.99] | 0.82 | 0.89 | 0.98 | 100% | 82 / 237 | 28.4 | triage only |
| 11 | phi4-mini:3.8b | triage | **0.77** [0.57, 0.92] | 0.75 | 0.85 | 0.96 | 100% | 39 / 124 | 59.6 | triage only |
| – | *deterministic stage (no model, reference)* | | 0.56 | 0.56 | | | | | | |

**Mean name-F1 per layout**

| Model | real/portal | synthetic/list | synthetic/prose | synthetic/table-reordered |
|---|---|---|---|---|
| llama3.1:8b (confirm) | 1.00 | 1.00 | 1.00 | 0.95 |
| ministral-3:8b (confirm) | 1.00 | 1.00 | 1.00 | 0.95 |
| qwen3:8b (confirm) | 1.00 | 1.00 | 1.00 | 0.66 |
| gemma3:4b (confirm) | 0.95 | 0.99 | 1.00 | 0.48 |
| gemma3:12b (triage) | 1.00 | 1.00 | 1.00 | 0.88 |
| qwen3:1.7b (triage) | 1.00 | 0.97 | 1.00 | 0.68 |
| qwen3:4b-q4_K_M (triage) | 1.00 | 1.00 | 1.00 | 0.60 |
| granite4:3b (triage) | 0.92 | 0.67 | 1.00 | 0.78 |
| qwen3.5:0.8b (triage) | 0.60 | 0.99 | 1.00 | 0.71 |
| qwen3:4b (triage) | 1.00 | 0.67 | 1.00 | 0.60 |
| phi4-mini:3.8b (triage) | 0.97 | 0.93 | 0.42 | 0.74 |
| *deterministic stage (no model, reference)* | 0.99 | 0.00 | 0.00 | 0.81 |
