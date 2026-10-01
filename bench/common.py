"""Shared helpers: paths, the upstream (production) code, the gold set, cache keys.

The benchmark never re-implements the extraction: it imports `src.pdf_extract` from a checkout
of the main repository (5ltep-layer1) at a chosen ref, placed in ./upstream by the workflow (or
pointed to by the UPSTREAM variable). Prompt, JSON schema, temperature, seed, context size and
the parsing of the answer are therefore exactly what runs in production.
"""

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD_FILE = ROOT / "gold" / "cases.json"
GOLD_DIR = ROOT / "gold"
CANDIDATES_FILE = ROOT / "candidates.json"
RESULTS_DIR = ROOT / "results"
RUNS_DIR = RESULTS_DIR / "runs"
DISCOVERED_FILE = RESULTS_DIR / "discovered.json"
LEADERBOARD_FILE = RESULTS_DIR / "leaderboard.json"
RECOMMENDATION_FILE = RESULTS_DIR / "recommendation.json"
# The production code whose changes invalidate earlier results.
PROMPT_FILES = ["src/pdf_extract.py", "src/config.py", "src/types_map.py", "src/dictionaries.py"]


def upstream_path() -> Path:
    return Path(os.environ.get("UPSTREAM", ROOT / "upstream")).resolve()


def import_upstream():
    """(src.pdf_extract, src.config, src.types_map) from the upstream checkout."""
    path = str(upstream_path())
    if path not in sys.path:
        sys.path.insert(0, path)
    for name in [m for m in sys.modules if m == "src" or m.startswith("src.")]:
        del sys.modules[name]  # a different ref may have been imported before
    return (importlib.import_module("src.pdf_extract"), importlib.import_module("src.config"),
            importlib.import_module("src.types_map"))


def upstream_ref() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=upstream_path(), capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return os.environ.get("UPSTREAM_REF", "unknown")


def load_gold() -> dict:
    return json.loads(GOLD_FILE.read_text(encoding="utf-8")) if GOLD_FILE.exists() else {"cases": []}


def gold_hash() -> str:
    """Hash of the case list and of every PDF it points to (line endings normalised)."""
    if not GOLD_FILE.exists():
        return "none"
    h = hashlib.sha256(GOLD_FILE.read_bytes().replace(b"\r\n", b"\n"))
    for case in load_gold()["cases"]:
        h.update((GOLD_DIR / case["pdf"]).read_bytes())
    return h.hexdigest()


def triage_ids(cases: list[dict], n: int) -> list[str]:
    """A fixed, stratified sample: cases taken in turn from each (kind, layout) group."""
    groups: dict[str, list[dict]] = {}
    for c in sorted(cases, key=lambda c: c["id"]):
        groups.setdefault(f"{c['kind']}/{c['layout']}", []).append(c)
    ordered, i = [], 0
    while len(ordered) < min(n, len(cases)):
        for g in sorted(groups):
            if i < len(groups[g]) and len(ordered) < n:
                ordered.append(groups[g][i]["id"])
        i += 1
    return ordered


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def entry_key(entry: dict, prompt_fp: str, g_hash: str, stage: str) -> str:
    """Cache key: a result is reused only for the same model build, production code, gold set and stage."""
    raw = "|".join([entry["backend"], entry["model"], entry.get("digest") or "", prompt_fp, g_hash, stage,
                    json.dumps(entry.get("options", {}), sort_keys=True)])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def run_file(entry: dict, shard: int, shards: int) -> Path:
    return RUNS_DIR / f"{entry['slug']}__{entry['key']}__s{shard}of{shards}.json"
