"""Score the candidates, pick a recommendation, update README.md and LEIAME.md.

Per case, the extracted field list is compared with the gold list by the production oracle
(src.pdf_extract.oracle): recall and precision of the names (case and accents ignored), exact
match (EM, same spelling) and normalised Levenshtein similarity (LS), the metrics of Al Hilmi et
al. (2026). Name-F1 = 2PR/(P+R) is the primary score. Type accuracy: share of the matched fields
whose declared type maps (src.types_map) to the gold Table Schema type. A case with no field or an
error scores 0.

Per candidate: mean name-F1 with a bootstrap 95% CI over cases, EM, LS, type accuracy, valid rate,
coverage, latency p50/p90 and PDFs per hour on the runner, and the mean F1 per layout.

Eligibility (confirmation stage): valid rate and coverage above their minimums; p90 latency
within the production per-call timeout; and the **monthly budget**: mean seconds per PDF times
the PDFs expected per month fit the runner hours the instances can spend on it. The recommended
model is the eligible, non-experimental finalist with the highest mean name-F1 (ties: EM, then
speed). A switch from production needs a gain of at least `switch_margin_f1` whose paired
bootstrap 95% CI is above zero, and a model build older than `min_age_days_to_adopt`.

The deterministic stage of production (no model) is scored on the same cases as a reference.
"""

import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.common import (CANDIDATES_FILE, GOLD_DIR, LEADERBOARD_FILE, RECOMMENDATION_FILE, RESULTS_DIR, ROOT,  # noqa: E402
                          RUNS_DIR, import_upstream, load_gold)

REPO = "lsp3cesarschool/5ltep-layer1-modeltest"
DOCS = {"en": "README.md", "pt": "LEIAME.md"}
TEXT = {
    "en": {
        "updated": "*Updated {when} UTC · {n} gold cases ({real} real, {syn} synthetic) · production code at `{commit}`*",
        "recommendation": "**Recommendation:** {reason}.",
        "header": "| # | Model | Stage | Name-F1 [95% CI] | EM | LS | Types | Valid | Latency p50 / p90 (s) | PDFs/h | Status |",
        "layouts": "Mean name-F1 per layout",
        "det": "deterministic stage (no model, reference)",
        "eligible": "eligible", "experiment": "experiment", "triage_only": "triage only",
        "not_run": "not run yet", "partial": "partial",
        "why": {"valid": "valid {v}", "coverage": "coverage {v}", "latency": "p90 {v} s",
                "budget": "{v} h/month over budget"},
        "no_eligible": "no eligible candidate yet",
        "prod_is_best": "the production model is the best eligible candidate",
        "prod_no_result": "the production model has no confirmation result yet",
        "beats": "{best} beats {current} by {diff} name-F1 (paired 95% CI {ci})",
        "not_enough": ", which is not enough to switch",
        "held_age": "; adoption held: build first seen {age} days ago (needs {need})",
        "no_gold": "the gold set is empty (run the Build gold workflow)",
    },
    "pt": {
        "updated": "*Atualizado em {when} UTC · {n} casos no gabarito ({real} reais, {syn} sintéticos) · código de produção em `{commit}`*",
        "recommendation": "**Recomendação:** {reason}.",
        "header": "| # | Modelo | Estágio | F1 dos nomes [IC 95%] | EM | LS | Tipos | Válidas | Latência p50 / p90 (s) | PDFs/h | Situação |",
        "layouts": "F1 médio dos nomes por layout",
        "det": "etapa determinística (sem modelo, referência)",
        "eligible": "elegível", "experiment": "experimento", "triage_only": "só triagem",
        "not_run": "ainda não testado", "partial": "parcial",
        "why": {"valid": "válidas {v}", "coverage": "cobertura {v}", "latency": "p90 {v} s",
                "budget": "{v} h/mês acima do orçamento"},
        "no_eligible": "nenhum candidato elegível ainda",
        "prod_is_best": "o modelo de produção é o melhor candidato elegível",
        "prod_no_result": "o modelo de produção ainda não tem resultado de confirmação",
        "beats": "{best} supera {current} em {diff} de F1 dos nomes (IC 95% pareado {ci})",
        "not_enough": ", o que não basta para trocar",
        "held_age": "; adoção suspensa: versão vista pela primeira vez há {age} dias (precisa de {need})",
        "no_gold": "o gabarito está vazio (rode o workflow Build gold)",
    },
}


def num(x, lang: str, spec: str = ".2f") -> str:
    if x is None:
        return "—"
    s = format(x, spec)
    return s.replace(".", ",") if lang == "pt" else s


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def case_scores(answer: dict | None, case: dict, pdf_extract, types_map) -> dict:
    """Scores of one answer against the gold field list of its case."""
    gold_names = [f["name"] for f in case["fields"]]
    fields = (answer or {}).get("fields") or []
    if not fields or (answer or {}).get("error"):
        return {"f1": 0.0, "recall": 0.0, "precision": 0.0, "em": 0.0, "ls": 0.0, "types": None, "valid": False}
    o = pdf_extract.oracle(fields, gold_names)
    p, r = o["precision"], o["recall"]
    norm = pdf_extract.dictionaries.norm
    by_name = {norm(f["name"]): f for f in fields}
    typed = [(g, by_name[norm(g["name"])]) for g in case["fields"]
             if g.get("type") not in (None, "any") and norm(g["name"]) in by_name]
    types = (sum(types_map.map_type(f.get("type", ""))[0] == g["type"] for g, f in typed) / len(typed)) if typed else None
    return {"f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "recall": r, "precision": p,
            "em": o["exact_match"], "ls": o["levenshtein"], "types": types, "valid": True}


def load_runs() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for p in sorted(RUNS_DIR.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out.setdefault(r["key"], []).append(r)
    return out


def metrics(shards: list[dict], expected_ids: list[str], cases: dict, pdf_extract, types_map, n_boot: int, rng) -> dict:
    answers = {a["case"]: a for s in shards for a in s["answers"]}
    done = [cid for cid in expected_ids if cid in answers]
    per_case = {cid: case_scores(answers[cid], cases[cid], pdf_extract, types_map) for cid in done}
    f1s = [per_case[c]["f1"] for c in done]
    secs = [answers[c]["seconds"] for c in done if answers[c].get("seconds") is not None]
    boot = []
    for _ in range(n_boot if f1s else 0):
        sample = [rng.choice(f1s) for _ in f1s]
        boot.append(mean(sample))
    boot.sort()
    layouts: dict[str, list[float]] = {}
    for c in done:
        layouts.setdefault(f"{cases[c]['kind']}/{cases[c]['layout']}", []).append(per_case[c]["f1"])
    types = [per_case[c]["types"] for c in done if per_case[c]["types"] is not None]
    mean_s = mean(secs) if secs else None
    return {
        "cases": len(done), "coverage": round(len(done) / len(expected_ids), 4) if expected_ids else 0.0,
        "f1": round(mean(f1s), 4) if f1s else None,
        "f1_ci95": [round(boot[int(0.025 * len(boot))], 4), round(boot[int(0.975 * len(boot)) - 1], 4)] if boot else None,
        "em": round(mean(per_case[c]["em"] for c in done), 4) if done else None,
        "ls": round(mean(per_case[c]["ls"] for c in done), 4) if done else None,
        "types": round(mean(types), 4) if types else None,
        "valid_rate": round(sum(per_case[c]["valid"] for c in done) / len(done), 4) if done else 0.0,
        "latency_median_s": round(median(secs), 1) if secs else None,
        "latency_p90_s": round(percentile(secs, 0.9), 1) if secs else None,
        "mean_s": round(mean_s, 1) if mean_s else None,
        "pdfs_per_hour": round(3600 / mean_s, 1) if mean_s else None,
        "per_layout": {k: round(mean(v), 4) for k, v in sorted(layouts.items())},
        "partial": any(s.get("stopped") for s in shards),
        "_per_case": {c: per_case[c]["f1"] for c in done},
        "tested_at": max(s["ended_at"] for s in shards),
    }


def triage_ranking(plan: dict) -> list[dict]:
    """Triage metrics of every candidate that has them, best first (used by plan.py --stage confirm)."""
    pdf_extract, _, types_map = import_upstream()
    cases = {c["id"]: c for c in load_gold()["cases"]}
    runs = load_runs()
    rng = random.Random(7)
    out = []
    for e in plan["entries"]:
        shards = runs.get(e["triage_key"])
        if shards:
            m = metrics(shards, plan["triage_cases"], cases, pdf_extract, types_map, 0, rng)
            out.append({"entry": e, **m})
    return sorted(out, key=lambda r: (-(r["f1"] or 0), r["mean_s"] or 1e9))


def deterministic_reference(cases: list[dict], pdf_extract, types_map) -> dict:
    scores = []
    for c in cases:
        fields = pdf_extract.deterministic((GOLD_DIR / c["pdf"]).read_bytes())
        scores.append((c, case_scores({"fields": fields}, c, pdf_extract, types_map)))
    layouts: dict[str, list[float]] = {}
    for c, s in scores:
        layouts.setdefault(f"{c['kind']}/{c['layout']}", []).append(s["f1"])
    return {"f1": round(mean(s["f1"] for _, s in scores), 4) if scores else None,
            "em": round(mean(s["em"] for _, s in scores), 4) if scores else None,
            "per_layout": {k: round(mean(v), 4) for k, v in sorted(layouts.items())}}


def paired_diff(a: dict, b: dict, n: int, rng) -> dict:
    common = sorted(set(a["_per_case"]) & set(b["_per_case"]))
    if not common:
        return {"diff": None, "ci95": None, "cases": 0}
    d = [a["_per_case"][c] - b["_per_case"][c] for c in common]
    boot = sorted(mean(rng.choice(d) for _ in d) for _ in range(n))
    return {"diff": round(mean(d), 4), "ci95": [round(boot[int(0.025 * n)], 4), round(boot[int(0.975 * n) - 1], 4)],
            "cases": len(common)}


def eligibility(m: dict, sel: dict, entry: dict) -> list[tuple[str, object]]:
    reasons = []
    if m["valid_rate"] < sel["min_valid_rate"]:
        reasons.append(("valid", f"{m['valid_rate']:.0%}"))
    if m["coverage"] < sel["min_coverage"]:
        reasons.append(("coverage", f"{m['coverage']:.0%}"))
    if m["latency_p90_s"] is not None and m["latency_p90_s"] > sel["max_call_seconds"]:
        reasons.append(("latency", m["latency_p90_s"]))
    if m["mean_s"]:
        hours = m["mean_s"] * sel["expected_pdfs_per_month"] / 3600
        if hours > sel["monthly_budget_hours"]:
            reasons.append(("budget", round(hours - sel["monthly_budget_hours"], 1)))
    if entry.get("experiment"):
        reasons.append(("experiment", None))
    return reasons


def adoption_hold(entry: dict, sel: dict):
    first = entry.get("first_seen")
    if first:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(first)).days
        if age < sel.get("min_age_days_to_adopt", 30):
            return {"age": age, "need": sel.get("min_age_days_to_adopt", 30)}
    return None


def status_text(r: dict, lang: str) -> str:
    t = TEXT[lang]
    if r.get("stage") is None:
        return t["not_run"]
    if r["stage"] == "triage":
        return t["triage_only"]
    reasons = r.get("_reasons") or []
    if not reasons:
        return t["eligible"] + (f" ({t['partial']})" if r.get("partial") else "")
    return "; ".join(t["experiment"] if k == "experiment" else t["why"][k].format(v=v) for k, v in reasons)


def card(r: dict | None) -> dict | None:
    if not r:
        return None
    e = r["entry"]
    return {"label": e["label"], "backend": "ollama", "model": e["model"], "digest": e["digest"],
            "options": e.get("options", {}), "name_f1": r["f1"], "name_f1_ci95": r["f1_ci95"], "em": r["em"],
            "types": r["types"], "valid_rate": r["valid_rate"], "latency_p90_s": r["latency_p90_s"],
            "pdfs_per_hour": r["pdfs_per_hour"], "tested_at": r["tested_at"]}


def main() -> None:
    plan = json.loads((RESULTS_DIR / "plan.json").read_text(encoding="utf-8"))
    sel = plan["selection"]
    gold_cases = load_gold()["cases"]
    cases = {c["id"]: c for c in gold_cases}
    all_ids = [c["id"] for c in gold_cases]
    pdf_extract, _, types_map = import_upstream()
    rng = random.Random(7)
    runs = load_runs()
    rows = []
    for e in plan["entries"]:
        if e["confirm_key"] in runs:
            m = metrics(runs[e["confirm_key"]], all_ids, cases, pdf_extract, types_map, sel["bootstrap_resamples"], rng)
            row = {"entry": e, "stage": "confirm", **m}
            row["_reasons"] = eligibility(m, sel, e)
            row["eligible"] = not row["_reasons"]
        elif e["triage_key"] in runs:
            m = metrics(runs[e["triage_key"]], plan["triage_cases"], cases, pdf_extract, types_map,
                        sel["bootstrap_resamples"], rng)
            row = {"entry": e, "stage": "triage", "eligible": False, **m}
        else:
            row = {"entry": e, "stage": None, "eligible": False}
        rows.append(row)
    rank = lambda r: (r["stage"] != "confirm", -(r.get("f1") or 0), -(r.get("em") or 0), r.get("mean_s") or 1e9)
    scored = sorted([r for r in rows if r["stage"]], key=rank)
    prod = plan["production"]
    current = next((r for r in scored if r["stage"] == "confirm" and r["entry"]["model"] == prod["model"]), None)
    eligible = [r for r in scored if r["eligible"]]
    best = eligible[0] if eligible else None
    switch, comparison = False, None
    if not gold_cases:
        reasons = {lang: TEXT[lang]["no_gold"] for lang in TEXT}
    elif best and current:
        if best is current:
            reasons = {lang: TEXT[lang]["prod_is_best"] for lang in TEXT}
        else:
            comparison = paired_diff(best, current, sel["bootstrap_resamples"], rng)
            switch = bool(comparison["diff"] is not None and comparison["diff"] >= sel["switch_margin_f1"]
                          and comparison["ci95"] and comparison["ci95"][0] > 0)
            held = adoption_hold(best["entry"], sel) if switch else None
            reasons = {lang: TEXT[lang]["beats"].format(
                best=best["entry"]["label"], current=current["entry"]["label"], diff=num(comparison["diff"], lang, "+.3f"),
                ci=f"[{num(comparison['ci95'][0], lang, '+.3f')}, {num(comparison['ci95'][1], lang, '+.3f')}]")
                + ("" if switch else TEXT[lang]["not_enough"])
                + (TEXT[lang]["held_age"].format(**held) if held else "") for lang in TEXT}
            if held:
                switch = False
    elif best:
        reasons = {lang: TEXT[lang]["prod_no_result"] for lang in TEXT}
    else:
        reasons = {lang: TEXT[lang]["no_eligible"] for lang in TEXT}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    det = deterministic_reference(gold_cases, pdf_extract, types_map) if gold_cases else None
    public = [{"label": r["entry"]["label"], "model": r["entry"]["model"], "digest": r["entry"]["digest"],
               "stage": r["stage"], "eligible": r["eligible"],
               **{k: v for k, v in r.items() if k not in ("entry", "stage", "eligible") and not k.startswith("_")}}
              for r in rows]
    LEADERBOARD_FILE.write_text(json.dumps({"generated_at": now, "gold_hash": plan["gold_hash"],
                                            "gold_cases": len(gold_cases), "prompt": plan["prompt"],
                                            "selection": sel, "finalists": plan.get("finalists", []),
                                            "deterministic_reference": det, "rows": public,
                                            "unavailable": plan.get("unavailable", [])}, indent=1), encoding="utf-8")
    use = card(best) if switch else (card(current) or prod)
    rec = {"generated_at": now, "benchmark": f"https://github.com/{REPO}", "task": "PDF data dictionary -> field list",
           "gold_cases": len(gold_cases), "gold_hash": plan["gold_hash"], "prompt_commit": plan["prompt"]["commit"],
           # "use" is what Layer 1 instances with LLM_MODEL=auto run: the production model, replaced only
           # when a switch is recommended.
           "use": use, "production": card(current) or prod, "recommended": card(best),
           "switch_recommended": switch, "comparison": comparison, "reason": reasons["en"]}
    RECOMMENDATION_FILE.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    write_status(rec)
    if switch:
        adopt(best, now)
    write_markdown(scored, rows, rec, gold_cases, det, now, reasons)
    print(reasons["en"])


def write_status(rec: dict) -> None:
    use = rec.get("use") or {}
    for lang, label in (("en", "recommended model"), ("pt", "modelo recomendado")):
        name = "status.json" if lang == "en" else "status.pt.json"
        msg = f"{use['label']} · {rec['generated_at'][:10]}" if use.get("label") else (use.get("model") or "–")
        (RESULTS_DIR / name).write_text(json.dumps({"schemaVersion": 1, "label": label, "message": msg,
                                                    "color": "brightgreen" if use.get("label") else "lightgrey"}),
                                        encoding="utf-8")


def adopt(best: dict, now: str) -> None:
    """A recommended switch becomes the benchmark's new production reference."""
    cfg = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    previous = cfg["production"].get("model")
    if previous == best["entry"]["model"]:
        return
    cfg["production"] = {"backend": "ollama", "model": best["entry"]["model"],
                         "options": best["entry"].get("options", {}), "since": now[:10], "previous": previous}
    CANDIDATES_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def leaderboard(scored, rows, rec, gold_cases, det, now, reason: str, lang: str) -> str:
    t = TEXT[lang]
    real = sum(c["kind"] == "real" for c in gold_cases)
    lines = [t["updated"].format(when=now[:16].replace("T", " "), n=len(gold_cases), real=real,
                                 syn=len(gold_cases) - real, commit=(rec.get("prompt_commit") or "")[:7]), "",
             t["recommendation"].format(reason=reason), "", t["header"], "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(scored, 1):
        ci = f"[{num(r['f1_ci95'][0], lang)}, {num(r['f1_ci95'][1], lang)}]" if r.get("f1_ci95") else ""
        lines.append(f"| {i} | {r['entry']['label']} | {r['stage']} | **{num(r['f1'], lang)}** {ci} | {num(r['em'], lang)} | "
                     f"{num(r['ls'], lang)} | {num(r['types'], lang)} | {r['valid_rate']:.0%} | "
                     f"{num(r['latency_median_s'], lang, '.0f')} / {num(r['latency_p90_s'], lang, '.0f')} | "
                     f"{num(r['pdfs_per_hour'], lang, '.1f')} | {status_text(r, lang)} |")
    for r in rows:
        if not r["stage"]:
            lines.append(f"| – | {r['entry']['label']} | | | | | | | | | {status_text(r, lang)} |")
    if det:
        lines.append(f"| – | *{t['det']}* | | {num(det['f1'], lang)} | {num(det['em'], lang)} | | | | | | |")
    layouts = sorted({k for r in scored for k in r.get("per_layout", {})} | set((det or {}).get("per_layout", {})))
    if layouts:
        lines += ["", f"**{t['layouts']}**", "", "| Model | " + " | ".join(layouts) + " |",
                  "|---|" + "---|" * len(layouts)]
        for r in scored:
            lines.append(f"| {r['entry']['label']} ({r['stage']}) | "
                         + " | ".join(num(r["per_layout"].get(k), lang) for k in layouts) + " |")
        if det:
            lines.append(f"| *{t['det']}* | " + " | ".join(num(det["per_layout"].get(k), lang) for k in layouts) + " |")
    return "\n".join(lines)


def write_markdown(scored, rows, rec, gold_cases, det, now, reasons) -> None:
    for lang, name in DOCS.items():
        doc = ROOT / name
        if not doc.exists():
            continue
        table = leaderboard(scored, rows, rec, gold_cases, det, now, reasons[lang], lang)
        if lang == "en":
            (RESULTS_DIR / "leaderboard.md").write_text(table + "\n", encoding="utf-8")
        text = doc.read_text(encoding="utf-8")
        doc.write_text(re.sub(r"(<!-- LEADERBOARD:START -->)(.*?)(<!-- LEADERBOARD:END -->)",
                              lambda m: f"{m.group(1)}\n{table}\n{m.group(3)}", text, flags=re.S), encoding="utf-8")


if __name__ == "__main__":
    main()
