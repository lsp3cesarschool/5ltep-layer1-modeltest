"""Find new Ollama models worth testing.

Looks at the families listed in candidates.json and at the library's "newest"
page, lists each model's tags, keeps plain size tags (e.g. "4b", "e4b",
"8b-a1b-q4_K_M"), checks their real download size in the registry, and adds the
ones between min_size_gb and max_size_gb that are not tested yet to
results/discovered.json (at most max_new_per_run per run).

Scraping the library page can break when ollama.com changes; failures are
logged and never stop the benchmark (the curated list still runs).
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.common import CANDIDATES_FILE, DISCOVERED_FILE  # noqa: E402

UA = {"User-Agent": "5ltep-layer1-modeltest (+https://github.com/lsp3cesarschool/5ltep-layer1-modeltest)"}
SIZE_TAG = re.compile(r"^(e?\d+(\.\d+)?[bm])(-a\d+(\.\d+)?b)?(-h)?(-q4_k_m)?$|^latest$", re.I)
MANIFEST_ACCEPT = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}


def library_tags(name: str) -> list[str]:
    resp = requests.get(f"https://ollama.com/library/{name}/tags", headers=UA, timeout=30)
    if resp.status_code != 200:
        return []
    return sorted(set(re.findall(rf'href="/library/{re.escape(name)}:([^"]+)"', resp.text)))


def newest_models() -> list[str]:
    resp = requests.get("https://ollama.com/search?o=newest", headers=UA, timeout=30)
    resp.raise_for_status()
    return list(dict.fromkeys(re.findall(r'href="/library/([a-z0-9._-]+)"', resp.text)))


def manifest(model: str, tag: str) -> tuple[str, float] | None:
    """(digest, size in GB) from the registry; the digest matches what `ollama list` shows."""
    r = requests.get(f"https://registry.ollama.ai/v2/library/{model}/manifests/{tag}",
                     headers={**UA, **MANIFEST_ACCEPT}, timeout=30)
    if r.status_code != 200:
        return None
    size = sum(layer.get("size", 0) for layer in r.json().get("layers", []))
    return hashlib.sha256(r.content).hexdigest(), size / 1e9


def candidate_tags(tags: list[str], exclude: list[str]) -> list[str]:
    keep = [t for t in tags if SIZE_TAG.match(t) and not any(w in t.lower() for w in exclude)]
    sized = [t for t in keep if t != "latest"]
    return sized or keep


def main() -> None:
    cfg = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    disc = cfg["discovery"]
    if not disc.get("enabled", True):
        print("discovery disabled")
        return
    found = json.loads(DISCOVERED_FILE.read_text(encoding="utf-8")) if DISCOVERED_FILE.exists() else {"entries": []}
    known_models = {e["model"] for e in cfg["entries"] + found["entries"] if e["backend"] == "ollama"}
    known_digests = {e.get("digest") for e in found["entries"]}
    families = list(disc["families"])
    try:
        families += [m for m in newest_models() if m not in families]
    except requests.RequestException as exc:
        print(f"warning: could not read the newest models page: {exc}")
    added = []
    for name in families:
        if len(added) >= disc["max_new_per_run"]:
            break
        if any(w in name.lower() for w in disc["exclude_words"]):
            continue
        try:
            tags = candidate_tags(library_tags(name), disc["exclude_words"])
        except requests.RequestException as exc:
            print(f"warning: {name}: {exc}")
            continue
        for tag in tags:
            model = f"{name}:{tag}"
            if model in known_models or len(added) >= disc["max_new_per_run"]:
                continue
            try:
                info = manifest(name, tag)
            except requests.RequestException:
                info = None
            if not info:
                continue
            digest, size_gb = info
            if not disc["min_size_gb"] <= size_gb <= disc["max_size_gb"] or digest in known_digests:
                continue
            entry = {"label": model, "backend": "ollama", "model": model, "size_gb": round(size_gb, 2),
                     "digest": digest, "source": "discovered",
                     "discovered_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if name.startswith(("qwen3", "deepseek-r1", "gemma4", "granite4.2")):
                entry["options"] = {"think": False}  # families with a thinking mode
            found["entries"].append(entry)
            known_models.add(model)
            known_digests.add(digest)
            added.append(entry)
            print(f"discovered {model} ({size_gb:.1f} GB)")
    DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVERED_FILE.write_text(json.dumps(found, indent=1), encoding="utf-8")
    print(f"{len(added)} new model(s); {len(found['entries'])} discovered in total")


if __name__ == "__main__":
    main()
