"""Run one candidate over its cases (one job of the triage or confirmation stage).

  python bench/run.py --entry '<job as JSON, from the plan>'

Each case is a PDF of the gold set. The text extraction, prompt, JSON schema, temperature,
seed, context size and answer parsing are the production ones (src.pdf_extract of 5ltep-layer1);
only the model changes. The answer is kept as extracted names and types (no description), and
scored later by bench/score.py. Progress is saved after every case, so a job killed by the
runner's time limit keeps what it did, marked as partial.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.common import (GOLD_DIR, RESULTS_DIR, RUNS_DIR, gold_hash, import_upstream, load_gold,  # noqa: E402
                          run_file, upstream_ref)


def job_cases(job: dict, plan: dict, cases: list[dict]) -> list[dict]:
    if job["stage"] == "triage":
        wanted = set(plan["triage_cases"])
        return [c for c in cases if c["id"] in wanted]
    return [c for i, c in enumerate(cases) if i % job["shards"] == job["shard"]]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", required=True, help="job as JSON (from the plan)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N cases (smoke test)")
    args = ap.parse_args(argv)
    job = json.loads(args.entry)
    plan = json.loads((RESULTS_DIR / "plan.json").read_text(encoding="utf-8"))
    budget = plan["selection"].get("budget_minutes", 300)

    pdf_extract, config, _ = import_upstream()
    think = (job.get("options") or {}).get("think")
    config.LLM_THINK = "" if think is None else str(think).lower()
    config.LLM_MODEL = job["model"]
    client = pdf_extract.OllamaClient(model=job["model"])

    cases = job_cases(job, plan, load_gold()["cases"])[: args.limit]
    started = datetime.now(timezone.utc)
    deadline = time.monotonic() + budget * 60
    answers, stopped = [], None
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = run_file(job, job["shard"], job["shards"])

    def save(final: bool) -> None:
        out = {"key": job["key"], "label": job["label"], "stage": job["stage"],
               "shard": job["shard"], "shards": job["shards"],
               "upstream_ref": upstream_ref(), "gold_hash": gold_hash(),
               "cases_total": len(cases), "cases_done": len(answers),
               "stopped": stopped if final else "in progress (job ended before the run finished)",
               "server": client.info(),
               "production_parameters": {"temperature": 0, "seed": config.LLM_SEED, "num_ctx": config.LLM_NUM_CTX,
                                         "num_predict": config.LLM_NUM_PREDICT, "think": config.LLM_THINK,
                                         "prompt_version": config.EXTRACTION_PROMPT_VERSION},
               "started_at": started.isoformat(timespec="seconds"),
               "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "answers": answers}
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    for case in cases:
        if time.monotonic() > deadline:
            stopped = "time budget"
            break
        pdf = (GOLD_DIR / case["pdf"]).read_bytes()
        t0 = time.monotonic()
        try:
            fields, meta = pdf_extract.llm(pdf, client)
            error = meta.get("error")
        except Exception as exc:      # a timeout or a server error is a failed answer, not a crash
            fields, meta, error = [], {}, f"{type(exc).__name__}: {str(exc)[:300]}"
        answers.append({"case": case["id"], "seconds": round(time.monotonic() - t0, 1), "error": error,
                        "truncated": meta.get("truncated"),
                        "fields": [{"name": f["name"], "type": f.get("type", "")} for f in fields]})
        print(f"{case['id']:40s} {len(fields):3d} fields  {answers[-1]['seconds']:7.1f} s  {error or ''}", flush=True)
        save(final=False)
    save(final=True)
    print(f"{len(answers)}/{len(cases)} cases; saved {path}")


if __name__ == "__main__":
    main()
