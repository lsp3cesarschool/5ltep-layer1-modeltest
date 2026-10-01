# 5LTEP-L1 · Model benchmark

[![Tests](https://github.com/lsp3cesarschool/5ltep-layer1-modeltest/actions/workflows/tests.yml/badge.svg)](https://github.com/lsp3cesarschool/5ltep-layer1-modeltest/actions/workflows/tests.yml) [![recommended model](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Flsp3cesarschool%2F5ltep-layer1-modeltest%2Fmain%2Fresults%2Fstatus.json)](results/recommendation.json) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**English** · [Português](LEIAME.md)

**Which local LLM best turns a PDF data dictionary into a field list, on a free CPU runner?** This
repository measures it every month for [5ltep-layer1](https://github.com/lsp3cesarschool/5ltep-layer1)
(Layer 1 of the 5L-TEP pyramid) and publishes the model its instances use.

> **Status: research demonstration**, part of a master's research project, maintained by its author.

## What the models are asked to do

Many open data portals publish their data dictionaries only as PDF. Layer 1 reads them in three
stages: a deterministic table reader, then a local LLM for the PDFs it cannot read, then people for
whatever is not confirmed. This benchmark is about the second stage: given the text of a PDF
dictionary, return every field with its name exactly as written, its declared type and size.
The prompt, JSON schema, temperature (0), seed, context size and the parsing of the answer are the
**production code** (`src/pdf_extract.py` of 5ltep-layer1), imported, not copied.

## Leaderboard

<!-- LEADERBOARD:START -->
*No results yet: the first run starts once the gold set is built.*
<!-- LEADERBOARD:END -->

## Why a separate benchmark

The model runs on the free GitHub Actions runner (4 vCPU, 16 GB, no GPU), so it must be small and
fast enough, and reading a dictionary is a different task from general chat or from the Layer 3
judge ([5ltep-layer3-modeltest](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest)). Choosing
by general leaderboards is not enough: it has to be measured **on this task, with this prompt, on
this hardware**, and again whenever a new model or a new version of the prompt appears.

## How it works

```
discover ─► triage (every candidate, sample) ─► select ─► confirm (finalists + production, all cases, shards) ─► score
 Ollama      12 stratified cases                  best 3     whole gold set, split in jobs that fit the runner    name-F1 + CI,
 library                                                                                                            budget, switch rule
```

1. **Discover** new tags of the watched families and of the newest models in the Ollama library
   (1–9 GB), as in the Layer 3 benchmark.
2. **Triage:** every candidate reads a fixed, stratified sample of the gold set.
3. **Select:** the best finalists of the triage, plus the production model (for a paired comparison).
4. **Confirm:** the finalists read the whole gold set, split in shards so that a slow model still
   fits the runner's time limit.
5. **Score:** metrics, eligibility, recommendation, and this README's table (and `LEIAME.md`).

Results are cached by model build (Ollama manifest digest), production code, gold set and stage:
a candidate runs again only when one of them changes.

## Gold set

[`gold/cases.json`](gold/cases.json), built by [`gold/build_gold.py`](gold/build_gold.py) from the
**public results of the Layer 1 instances** (IBAMA, ANEEL, Recife), pinned to their commits. Every
case has a field list known by construction:

| Kind | How it is built |
|---|---|
| real | a PDF dictionary published by a portal whose deterministic extraction the file's own header confirmed in full: two independent sources agree on every name |
| synthetic | a schema a portal declares in a machine-readable dictionary, rendered as a PDF in a harder layout ([`gold/layouts.py`](gold/layouts.py)): prose, a bulleted list, or a table with reordered columns |

Real cases are, by construction, PDFs whose tables the deterministic stage already reads: they
measure how faithfully a model copies names from real documents. Synthetic cases measure the
layouts where the LLM is actually needed. The deterministic stage is scored on the same cases as a
reference. Sources and licences of the PDFs: [`gold/SOURCES.md`](gold/SOURCES.md).

## Metrics and recommendation

| Metric | Meaning |
|---|---|
| name-F1 [95% CI] | primary: harmonic mean of recall and precision of the names (case and accents ignored), averaged over cases; bootstrap CI |
| EM, LS | exact match and Levenshtein similarity of the names (Al Hilmi et al., 2026) |
| types | share of matched fields whose declared type maps to the gold Table Schema type |
| valid | share of answers with at least one field and no error |
| latency, PDFs/h | cost on the free runner |

A finalist is **eligible** with ≥ 90% valid answers and ≥ 90% coverage, p90 latency within the
production timeout, and the **monthly budget**: its mean time per PDF times the PDFs expected per
month must fit the runner hours set in [`candidates.json`](candidates.json). The **recommended**
model is the eligible one with the highest name-F1. A **switch** from production needs a gain of at
least 0.03 name-F1 whose paired bootstrap 95% CI is above zero, and a build first seen at least 30
days before (a release has time to be noticed by others before it is adopted).

## How the Layer 1 instances use it

No token crosses repositories: each instance reads the public
[`results/recommendation.json`](results/recommendation.json) at the start of its LLM stage
(`LLM_MODEL=auto`) and uses its field `use`. Until this benchmark has published, they use
`qwen3:8b`. Every extraction records the model and digest that produced it; a new model does not
redo earlier extractions.

## Cost

Public repositories run on GitHub's standard runners at no cost. A large model may take several
minutes per PDF on CPU, which is why the full gold set runs only for the finalists and in shards.

## Reproducing

```bash
pip install -r requirements.txt -r ../5ltep-layer1/requirements.txt
UPSTREAM=../5ltep-layer1 python gold/build_gold.py
UPSTREAM=../5ltep-layer1 pytest tests/ -v
```

Runs that count are the ones on GitHub Actions (*Actions → Model benchmark → Run workflow*); the
gold set is rebuilt with *Actions → Build gold*.

## Licences

MIT for the code ([LICENSE](LICENSE)). Real PDFs in `gold/pdfs/` are copies of documents the portals
publish under open licences (see `gold/SOURCES.md`); models are used under their own licences.
