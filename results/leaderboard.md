*Updated 2026-10-02 13:50 UTC · 30 gold cases (12 real, 18 synthetic) · production code at `48f8c47`*

**Recommendation:** llama3.1:8b beats qwen3:8b by +0.065 name-F1 (paired 95% CI [-0.003, +0.164]), which is not enough to switch.

| # | Model | Stage | Name-F1 [95% CI] | EM | LS | Types | Valid | Latency p50 / p90 (s) | PDFs/h | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | llama3.1:8b | confirm | **0.99** [0.98, 1.00] | 0.99 | 1.00 | 1.00 | 100% | 146 / 403 | 16.5 | eligible |
| 2 | ministral-3:8b | confirm | **0.99** [0.97, 1.00] | 0.99 | 0.99 | 0.99 | 100% | 196 / 480 | 14.1 | eligible |
| 3 | gemma3:12b | confirm | **0.95** [0.88, 1.00] | 0.95 | 0.97 | 1.00 | 100% | 277 / 670 | 9.3 | eligible |
| 4 | qwen3:8b | confirm | **0.93** [0.83, 0.99] | 0.93 | 0.95 | 1.00 | 100% | 228 / 608 | 11.7 | eligible |
| 5 | gemma3:4b | triage | **0.97** [0.94, 0.99] | 0.97 | 1.00 | 1.00 | 100% | 54 / 128 | 52.3 | triage only |
| 6 | qwen3:1.7b | triage | **0.91** [0.80, 0.99] | 0.89 | 0.95 | 0.97 | 100% | 30 / 107 | 66.4 | triage only |
| 7 | qwen3:4b-q4_K_M | triage | **0.90** [0.73, 1.00] | 0.90 | 0.93 | 0.99 | 100% | 69 / 217 | 32.6 | triage only |
| 8 | granite4:3b | triage | **0.84** [0.67, 0.97] | 0.80 | 0.93 | 0.95 | 100% | 63 / 230 | 31.8 | triage only |
| 9 | qwen3.5:0.8b | triage | **0.82** [0.63, 0.96] | 0.78 | 0.87 | 0.88 | 100% | 23 / 56 | 95.1 | triage only |
| 10 | qwen3:4b | triage | **0.82** [0.58, 0.99] | 0.82 | 0.89 | 0.98 | 100% | 37 / 121 | 57.8 | triage only |
| 11 | phi4-mini:3.8b | triage | **0.77** [0.57, 0.93] | 0.75 | 0.85 | 0.96 | 100% | 63 / 197 | 37.3 | triage only |
| – | *deterministic stage (no model, reference)* | | 0.56 | 0.56 | | | | | | |

**Mean name-F1 per layout**

| Model | real/portal | synthetic/list | synthetic/prose | synthetic/table-reordered |
|---|---|---|---|---|
| llama3.1:8b (confirm) | 1.00 | 1.00 | 1.00 | 0.95 |
| ministral-3:8b (confirm) | 1.00 | 1.00 | 1.00 | 0.95 |
| gemma3:12b (confirm) | 1.00 | 1.00 | 1.00 | 0.77 |
| qwen3:8b (confirm) | 1.00 | 1.00 | 1.00 | 0.63 |
| gemma3:4b (triage) | 1.00 | 0.96 | 0.97 | 0.93 |
| qwen3:1.7b (triage) | 1.00 | 0.97 | 1.00 | 0.69 |
| qwen3:4b-q4_K_M (triage) | 1.00 | 1.00 | 1.00 | 0.60 |
| granite4:3b (triage) | 0.92 | 0.67 | 1.00 | 0.78 |
| qwen3.5:0.8b (triage) | 0.57 | 0.99 | 1.00 | 0.71 |
| qwen3:4b (triage) | 1.00 | 0.67 | 1.00 | 0.60 |
| phi4-mini:3.8b (triage) | 0.97 | 0.93 | 0.42 | 0.74 |
| *deterministic stage (no model, reference)* | 1.00 | 0.00 | 0.00 | 0.81 |
