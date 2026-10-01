"""Decide which candidates run, in two stages.

  triage   every candidate, on a fixed stratified sample of the gold set (TRIAGE_CASES cases);
  confirm  the best `finalists` of the triage plus the production model, on the whole gold set,
           split in `confirm_shards` jobs so that a slow model fits the runner's time limit.

A result is reused when nothing that can change the answers changed: the model build (Ollama
manifest digest), the production code (fingerprint of the upstream files that build the prompt
and parse the answer), the gold set and the stage. Writes results/plan.json and, on GitHub
Actions, the matrix of jobs to run.

  python bench/plan.py --stage triage [--force] [--only labels]
  python bench/plan.py --stage confirm      # after the triage results were accepted
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.common import (CANDIDATES_FILE, DISCOVERED_FILE, PROMPT_FILES, RESULTS_DIR, entry_key, gold_hash,  # noqa: E402
                          load_gold, run_file, slug, triage_ids, upstream_path)
from bench.discover import manifest  # noqa: E402

FIRST_SEEN_FILE = RESULTS_DIR / "first_seen.json"
PLAN_FILE = RESULTS_DIR / "plan.json"
# Names that reach a shell, a URL or a job name: anything else is skipped.
SAFE = {
    "label": re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:()+/-]{0,79}$"),
    "model": re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}(/[a-z0-9][a-z0-9._-]{0,63})?(:[A-Za-z0-9][A-Za-z0-9._-]{0,63})?$"),
}


def safe_entry(entry: dict) -> bool:
    return entry.get("backend") == "ollama" and all(SAFE[k].match(str(entry.get(k, ""))) for k in SAFE)


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=upstream_path(), capture_output=True, text=True, check=True).stdout.strip()


def prompt_fingerprint(ref: str = "HEAD") -> tuple[str, str]:
    """(commit, fingerprint) of the production extraction code at `ref`."""
    commit = git("rev-parse", f"{ref}^{{commit}}")
    blobs = []
    for f in PROMPT_FILES:
        try:
            blobs.append(git("rev-parse", f"{commit}:{f}"))
        except subprocess.CalledProcessError:
            blobs.append("missing")
    return commit, hashlib.sha256("|".join(blobs).encode()).hexdigest()


def resolve_digest(entry: dict) -> str | None:
    name, _, tag = entry["model"].partition(":")
    info = manifest(name, tag or "latest")
    return info[0] if info else None


def current_entries(cfg: dict, discovered: list[dict], resolve=resolve_digest) -> tuple[list[dict], list[str]]:
    first_seen = json.loads(FIRST_SEEN_FILE.read_text(encoding="utf-8")) if FIRST_SEEN_FILE.exists() else {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries, seen, unavailable = [], set(), []
    for raw in cfg["entries"] + discovered:
        e = dict(raw)
        if not safe_entry(e):
            print(f"::warning::skipping a candidate with an unexpected name or back-end: {str(raw)[:120]}")
            continue
        e.setdefault("options", {})
        e.setdefault("experiment", False)
        try:
            e["digest"] = resolve(e)
        except Exception:
            e["digest"] = None
        if not e["digest"] or not re.match(r"^(sha256:)?[0-9a-f]{64}$", e["digest"]):
            unavailable.append(e["label"])
            continue
        dedup = (e["digest"], json.dumps(e["options"], sort_keys=True))
        if dedup in seen:
            continue                          # "latest" and a size tag pointing to the same build
        seen.add(dedup)
        e["first_seen"] = first_seen.setdefault(f"ollama|{e['model']}|{e['digest']}", now)
        e["slug"] = slug(e["label"])
        entries.append(e)
    FIRST_SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    FIRST_SEEN_FILE.write_text(json.dumps(first_seen, indent=1, sort_keys=True), encoding="utf-8")
    return entries, unavailable


def plan_triage(args, cfg: dict) -> list[dict]:
    discovered = json.loads(DISCOVERED_FILE.read_text(encoding="utf-8"))["entries"] if DISCOVERED_FILE.exists() else []
    entries, unavailable = current_entries(cfg, discovered)
    commit, p_fp = prompt_fingerprint()
    g_hash = gold_hash()
    cases = load_gold()["cases"]
    sel = cfg["selection"]
    sample = triage_ids(cases, sel["triage_cases"])
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    matrix = []
    if not cases:
        print("::warning::the gold set is empty: run the Build gold workflow first; nothing to run")
    for e in entries if cases else []:
        e["triage_key"] = entry_key(e, p_fp, g_hash, "triage")
        e["confirm_key"] = entry_key(e, p_fp, g_hash, "confirm")
        job = {**e, "stage": "triage", "key": e["triage_key"], "cases": sample, "shard": 0, "shards": 1}
        if (args.force or e["label"] in only or not run_file(job, 0, 1).exists()) and (not only or e["label"] in only):
            matrix.append(job)
    PLAN_FILE.write_text(json.dumps({
        "gold_hash": g_hash, "gold_cases": len(cases), "triage_cases": sample,
        "prompt": {"commit": commit, "fingerprint": p_fp},
        "production": cfg["production"], "selection": sel, "entries": entries, "unavailable": unavailable,
        "forced": bool(args.force), "only": sorted(only)}, indent=1), encoding="utf-8")
    print(f"{len(entries)} candidates, {len(matrix)} triage job(s); unavailable: {unavailable or 'none'}")
    return matrix


def plan_confirm(args) -> list[dict]:
    """Finalists from the accepted triage results (see score.triage_ranking)."""
    from bench.score import triage_ranking

    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    sel = plan["selection"]
    ranking = triage_ranking(plan)
    finalists = [r["entry"] for r in ranking if r["valid_rate"] >= sel["min_valid_rate"]][: sel["finalists"]]
    prod = plan["production"]
    for e in plan["entries"]:
        if e["model"] == prod["model"] and e not in finalists:
            finalists.append(e)              # the production model is always confirmed (paired comparison)
    shards = sel["confirm_shards"]
    all_ids = [c["id"] for c in load_gold()["cases"]]
    matrix = []
    for e in finalists:
        for s in range(shards):
            job = {**e, "stage": "confirm", "key": e["confirm_key"], "shard": s, "shards": shards,
                   "cases": [cid for i, cid in enumerate(all_ids) if i % shards == s]}
            if args.force or plan.get("forced") or not run_file(job, s, shards).exists():
                matrix.append(job)
    plan["finalists"] = [e["label"] for e in finalists]
    PLAN_FILE.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"finalists: {plan['finalists']}; {len(matrix)} confirmation job(s)")
    return matrix


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["triage", "confirm"], required=True)
    ap.add_argument("--force", action="store_true", help="run every candidate again")
    ap.add_argument("--only", default="", help="comma-separated labels to (re)run")
    args = ap.parse_args(argv)
    cfg = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    matrix = plan_triage(args, cfg) if args.stage == "triage" else plan_confirm(args)
    # The matrix carries no case lists (job names and outputs stay small); run.py reads them from the plan.
    slim = [{k: v for k, v in j.items() if k != "cases"} for j in matrix]
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"matrix={json.dumps(slim)}\n")
            fh.write(f"count={len(slim)}\n")


if __name__ == "__main__":
    main()
