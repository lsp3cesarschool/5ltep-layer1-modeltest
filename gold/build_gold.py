"""Build the gold set from the public results of the Layer 1 instances.

  python gold/build_gold.py [--real 12] [--synthetic 6]

Cases, with the gold field list known by construction:

- real: a PDF dictionary published by a portal whose deterministic extraction the file's own
  header confirmed in full (outcome "extracted" in results/extraction.json of an instance):
  two independent sources agree on every name. The gold types are the ones read from the PDF.
  Bias, stated in the README: these are PDFs whose tables the deterministic stage already reads.
- synthetic: a schema a portal declares in a machine-readable dictionary (schemas/*.declared.json
  of an instance), rendered as a PDF in a harder layout (gold/layouts.py), where the deterministic
  stage is expected to fail and the LLM is needed.

Everything is read over HTTPS from the public repositories, pinned to their current commits (no
token); the commits are recorded in gold/cases.json, so the set can be rebuilt exactly. PDFs are
stored in gold/pdfs/ with their sources in gold/SOURCES.md (the portals publish them under open
licences).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.common import GOLD_DIR, GOLD_FILE  # noqa: E402
from gold.layouts import LAYOUTS, render  # noqa: E402

INSTANCES = ["lsp3cesarschool/5ltep-layer1", "lsp3cesarschool/5ltep-layer1-aneel", "lsp3cesarschool/5ltep-layer1-recife"]
UA = {"User-Agent": "5ltep-layer1-modeltest (+https://github.com/lsp3cesarschool/5ltep-layer1-modeltest)"}
MIN_FIELDS, MAX_FIELDS = 3, 40


def head_commit(repo: str) -> str | None:
    r = requests.get(f"https://api.github.com/repos/{repo}/commits/main", headers=UA, timeout=30)
    return r.json().get("sha") if r.status_code == 200 else None


def raw(repo: str, sha: str, path: str):
    r = requests.get(f"https://raw.githubusercontent.com/{repo}/{sha}/{path}", headers=UA, timeout=60)
    return r.json() if r.status_code == 200 else None


def gold_fields(schema: dict) -> list[dict]:
    return [{"name": f["name"], "type": f.get("type", "any"), "declaredType": f.get("declaredType", ""),
             "declaredSize": f.get("declaredSize"), "description": (f.get("description") or "")[:300]}
            for f in schema.get("fields", [])]


def real_candidates(repo: str, sha: str) -> list[dict]:
    census, extraction = raw(repo, sha, "results/census.json"), raw(repo, sha, "results/extraction.json")
    if not census or not extraction:
        return []
    dicts = {d["id"]: (ds, d) for ds in census["datasets"] for d in ds["dictionaries"]}
    out = []
    for did, rec in sorted(extraction.items()):
        if rec.get("outcome") != "extracted" or did not in dicts or not rec.get("linked_resources"):
            continue
        ds, d = dicts[did]
        schema = raw(repo, sha, f"schemas/{ds['name']}/{rec['linked_resources'][0]}.extracted.json")
        if not schema or not MIN_FIELDS <= len(schema.get("fields", [])) <= MAX_FIELDS:
            continue
        out.append({"repo": repo, "commit": sha, "dataset": ds["name"], "title": ds["title"], "dictionary": d,
                    "sha256": rec["sha256"], "fields": gold_fields(schema)})
    return out


def synthetic_sources(repo: str, sha: str) -> list[dict]:
    census = raw(repo, sha, "results/census.json")
    if not census:
        return []
    out = []
    for ds in census["datasets"]:
        for d in ds["dictionaries"]:
            if d.get("kind") != "machine" or not d.get("readable") or not d.get("linked_resources"):
                continue
            schema = raw(repo, sha, f"schemas/{ds['name']}/{d['linked_resources'][0]}.declared.json")
            if schema and MIN_FIELDS + 1 <= len(schema.get("fields", [])) <= 30:
                out.append({"repo": repo, "commit": sha, "dataset": ds["name"], "title": ds["title"],
                            "dictionary": d, "fields": gold_fields(schema)})
                break                                  # one schema per dataset: variety
    return out


def round_robin(groups: list[list[dict]], n: int) -> list[dict]:
    out, i = [], 0
    while len(out) < n and any(i < len(g) for g in groups):
        for g in groups:
            if i < len(g) and len(out) < n:
                out.append(g[i])
        i += 1
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=int, default=12)
    ap.add_argument("--synthetic", type=int, default=6, help="schemas; each is rendered in every layout")
    args = ap.parse_args(argv)
    commits = {repo: head_commit(repo) for repo in INSTANCES}
    commits = {r: s for r, s in commits.items() if s}
    pdf_dir = GOLD_DIR / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for old in pdf_dir.glob("*.pdf"):
        old.unlink()
    cases, sources = [], []

    for i, c in enumerate(round_robin([real_candidates(r, s) for r, s in commits.items()], args.real), 1):
        resp = requests.get(c["dictionary"]["url"], headers=UA, timeout=120)
        if resp.status_code != 200 or hashlib.sha256(resp.content).hexdigest() != c["sha256"]:
            print(f"skipped {c['dataset']}: the PDF changed since the instance extracted it")
            continue
        cid = f"real-{i:02d}"
        (pdf_dir / f"{cid}.pdf").write_bytes(resp.content)
        cases.append({"id": cid, "kind": "real", "layout": "portal", "pdf": f"pdfs/{cid}.pdf",
                      "source": {"repo": c["repo"], "commit": c["commit"], "dataset": c["dataset"],
                                 "dictionary_url": c["dictionary"]["url"], "sha256": c["sha256"]},
                      "fields": [{"name": f["name"], "type": f["type"]} for f in c["fields"]]})
        sources.append(f"- `{cid}`: {c['dictionary']['url']} ({c['dataset']}, via {c['repo']}@{c['commit'][:7]})")

    for i, c in enumerate(round_robin([synthetic_sources(r, s) for r, s in commits.items()], args.synthetic), 1):
        origin = f"{c['dictionary']['name']} ({c['dataset']})"
        for layout in LAYOUTS:
            cid = f"syn-{i:02d}-{layout}"
            (pdf_dir / f"{cid}.pdf").write_bytes(render(c["fields"], layout, c["title"], origin))
            cases.append({"id": cid, "kind": "synthetic", "layout": layout, "pdf": f"pdfs/{cid}.pdf",
                          "source": {"repo": c["repo"], "commit": c["commit"], "dataset": c["dataset"],
                                     "dictionary_url": c["dictionary"]["url"]},
                          "fields": [{"name": f["name"], "type": f["type"]} for f in c["fields"]]})
        sources.append(f"- `syn-{i:02d}-*`: schema of {c['dictionary']['url']} ({c['dataset']}, via "
                       f"{c['repo']}@{c['commit'][:7]}), rendered by gold/layouts.py")

    GOLD_FILE.write_text(json.dumps({"instances": commits, "cases": cases}, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    (GOLD_DIR / "SOURCES.md").write_text(
        "# Sources of the gold set\n\nReal PDFs are copies of data dictionaries published by the portals under "
        "their open data licences (cite the portal when reusing). Synthetic PDFs are generated by this repository "
        "from schemas the portals declare.\n\n" + "\n".join(sources) + "\n", encoding="utf-8")
    real = sum(c["kind"] == "real" for c in cases)
    print(f"{len(cases)} cases ({real} real, {len(cases) - real} synthetic) from {list(commits)}")


if __name__ == "__main__":
    main()
