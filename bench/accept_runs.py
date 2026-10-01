"""Accept the result of each run job, and only that.

Each run job executes a downloaded model with a read-only token and hands over one file,
results/runs/<slug>__<key>__s<shard>of<shards>.json, in an artifact named run-<stage>-<slug>-<shard>.
A compromised job could put other files in its artifact (a fake result for another candidate, to
lower the production model or favour its own). This script takes from each artifact only the file
named after that job's planned key and shard, checks its structure and bounds its text, and
copies it into results/runs/. Everything else is ignored and reported.

  python bench/accept_runs.py <folder with one sub-folder per artifact> --stage triage|confirm
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.common import RESULTS_DIR, RUNS_DIR  # noqa: E402

MAX_BYTES = 8_000_000
MAX_FIELDS = 3000
NAME_RE = re.compile(r"^[^\x00-\x1f]{1,128}$")


def check(data: dict, job: dict) -> dict:
    if not isinstance(data, dict) or data.get("key") != job["key"] or data.get("label") != job["label"]:
        raise ValueError("key or label does not match the plan")
    if data.get("shard") != job["shard"] or data.get("shards") != job["shards"]:
        raise ValueError("shard does not match the plan")
    answers = data.get("answers")
    if not isinstance(answers, list):
        raise ValueError("no answers")
    for a in answers:
        if not isinstance(a, dict) or not isinstance(a.get("case"), str) or not isinstance(a.get("fields"), list):
            raise ValueError("malformed answer")
        if len(a["fields"]) > MAX_FIELDS or not isinstance(a.get("seconds", 0), (int, float)):
            raise ValueError("malformed answer numbers")
        for f in a["fields"]:
            if not isinstance(f, dict) or not NAME_RE.match(str(f.get("name", ""))):
                raise ValueError("malformed field")
            f["type"] = str(f.get("type", ""))[:100]
        a["error"] = None if a.get("error") is None else str(a["error"])[:300]
    data["stage"] = job["stage"]
    return data


def jobs_of(plan: dict, stage: str) -> dict[str, dict]:
    """Expected artifacts of a stage: name -> job (key, shard)."""
    out = {}
    for e in plan["entries"]:
        if stage == "triage":
            out[f"run-triage-{e['slug']}-0"] = {**e, "key": e["triage_key"], "shard": 0, "shards": 1, "stage": "triage"}
        elif e["label"] in plan.get("finalists", []):
            n = plan["selection"]["confirm_shards"]
            for s in range(n):
                out[f"run-confirm-{e['slug']}-{s}"] = {**e, "key": e["confirm_key"], "shard": s, "shards": n,
                                                      "stage": "confirm"}
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--stage", choices=["triage", "confirm"], required=True)
    args = ap.parse_args(argv)
    plan = json.loads((RESULTS_DIR / "plan.json").read_text(encoding="utf-8"))
    expected = jobs_of(plan, args.stage)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    accepted, refused = 0, []
    for art in sorted(Path(args.folder).glob("run-*")):
        job = expected.get(art.name)
        if not job:
            refused.append(f"{art.name}: not in the plan")
            continue
        name = f"{job['slug']}__{job['key']}__s{job['shard']}of{job['shards']}.json"
        for f in art.rglob("*"):
            if f.is_file() and f.name != name:
                refused.append(f"{art.name}/{f.name}: not this job's result")
        path = next((f for f in art.rglob(name) if f.is_file()), None)
        if not path:
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("too large")
            data = check(json.loads(path.read_text(encoding="utf-8")), job)
        except (ValueError, json.JSONDecodeError) as exc:
            refused.append(f"{art.name}/{path.name}: {exc}")
            continue
        (RUNS_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        accepted += 1
    for r in refused:
        print(f"::warning::refused {r}")
    print(f"accepted {accepted} result file(s); refused {len(refused)}")


if __name__ == "__main__":
    main()
