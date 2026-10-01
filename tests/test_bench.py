"""Benchmark tests. No network and no model: the production code is imported from upstream."""

import io
import json
import random

import pytest

from bench import accept_runs, common, plan, score
from gold import layouts

FIELDS = [{"name": "SEQ_TAD", "type": "integer", "declaredType": "INTEGER", "declaredSize": None,
           "description": "Chave do termo"},
          {"name": "DAT_TAD", "type": "date", "declaredType": "DATA (DD/MM/AAAA)", "declaredSize": None,
           "description": "Data em que o termo foi lavrado"},
          {"name": "UF", "type": "string", "declaredType": "VARCHAR", "declaredSize": 2, "description": "Sigla da UF"},
          {"name": "VAL_MULTA", "type": "number", "declaredType": "NÚMERO DECIMAL", "declaredSize": None,
           "description": "Valor da multa em reais"}]


@pytest.fixture(scope="module")
def upstream():
    return common.import_upstream()


def test_triage_sample_is_stratified_and_fixed():
    cases = [{"id": f"real-{i}", "kind": "real", "layout": "portal"} for i in range(6)] + \
            [{"id": f"syn-{i}-{l}", "kind": "synthetic", "layout": l} for i in range(3) for l in layouts.LAYOUTS]
    ids = common.triage_ids(cases, 8)
    assert len(ids) == 8 and ids == common.triage_ids(list(reversed(cases)), 8)
    kinds = {next(c for c in cases if c["id"] == i)["layout"] for i in ids}
    assert kinds == {"portal", *layouts.LAYOUTS}


def test_cache_key_depends_on_build_code_gold_and_stage():
    e = {"backend": "ollama", "model": "qwen3:4b", "digest": "a" * 64, "options": {"think": False}}
    k = common.entry_key(e, "fp", "gold", "triage")
    assert k != common.entry_key(e, "fp", "gold", "confirm")
    assert k != common.entry_key({**e, "digest": "b" * 64}, "fp", "gold", "triage")
    assert k != common.entry_key(e, "fp2", "gold", "triage") != common.entry_key(e, "fp", "gold2", "triage")


@pytest.mark.parametrize("layout", layouts.LAYOUTS)
def test_synthetic_pdfs_are_reproducible_and_carry_every_field(layout, upstream):
    pdf_extract = upstream[0]
    a = layouts.render(FIELDS, layout, "Termos de doação", "Metadados - Termo de doação")
    b = layouts.render(FIELDS, layout, "Termos de doação", "Metadados - Termo de doação")
    assert a == b                                    # byte for byte: the gold hash only moves with content
    text = pdf_extract.pdf_text(a)
    assert all(f["name"] in text for f in FIELDS)


def test_hard_layouts_defeat_the_deterministic_stage(upstream):
    pdf_extract, _, types_map = upstream
    case = {"fields": [{"name": f["name"], "type": f["type"]} for f in FIELDS]}
    prose = pdf_extract.deterministic(layouts.render(FIELDS, "prose", "T", "S"))
    assert score.case_scores({"fields": prose}, case, pdf_extract, types_map)["f1"] < 0.5


def test_case_scores(upstream):
    pdf_extract, _, types_map = upstream
    case = {"fields": [{"name": "SEQ_TAD", "type": "integer"}, {"name": "UF", "type": "string"},
                       {"name": "DAT_TAD", "type": "date"}]}
    perfect = {"fields": [{"name": "SEQ_TAD", "type": "INTEGER"}, {"name": "UF", "type": "VARCHAR"},
                          {"name": "DAT_TAD", "type": "Data Simples"}]}
    s = score.case_scores(perfect, case, pdf_extract, types_map)
    assert s["f1"] == 1.0 and s["em"] == 1.0 and s["types"] == 1.0 and s["valid"]
    partial = {"fields": [{"name": "seq_tad", "type": "TEXTO"}, {"name": "UF", "type": "VARCHAR"},
                          {"name": "EXTRA", "type": ""}]}
    s = score.case_scores(partial, case, pdf_extract, types_map)
    assert s["recall"] == pytest.approx(2 / 3, abs=1e-3) and s["em"] < 1 and s["types"] == 0.5
    assert score.case_scores({"fields": [], "error": "timeout"}, case, pdf_extract, types_map)["f1"] == 0.0


def _shard(answers, stopped=None):
    return {"answers": answers, "stopped": stopped, "ended_at": "2026-10-01T00:00:00+00:00"}


def test_metrics_budget_eligibility_and_paired_difference(upstream):
    pdf_extract, _, types_map = upstream
    cases = {f"c{i}": {"id": f"c{i}", "kind": "real", "layout": "portal",
                       "fields": [{"name": "A", "type": "string"}, {"name": "B", "type": "integer"}]} for i in range(4)}
    good = _shard([{"case": f"c{i}", "seconds": 60, "fields": [{"name": "A"}, {"name": "B"}]} for i in range(4)])
    bad = _shard([{"case": f"c{i}", "seconds": 600, "fields": [{"name": "A"}]} for i in range(4)])
    rng = random.Random(1)
    mg = score.metrics([good], list(cases), cases, pdf_extract, types_map, 200, rng)
    mb = score.metrics([bad], list(cases), cases, pdf_extract, types_map, 200, rng)
    assert mg["f1"] == 1.0 and mg["coverage"] == 1.0 and mg["pdfs_per_hour"] == 60.0
    sel = {"min_valid_rate": 0.9, "min_coverage": 0.9, "max_call_seconds": 1800, "monthly_budget_hours": 10,
           "expected_pdfs_per_month": 100}
    assert score.eligibility(mg, sel, {}) == []
    assert [k for k, _ in score.eligibility(mb, sel, {})] == ["budget"]       # 600 s x 100 = 16.7 h > 10 h
    d = score.paired_diff(mg, mb, 200, rng)
    assert d["diff"] > 0 and d["ci95"][0] > 0 and d["cases"] == 4


def test_unsafe_or_duplicate_candidates_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(plan, "FIRST_SEEN_FILE", tmp_path / "first_seen.json")
    cfg = {"entries": [{"label": "qwen3:4b", "backend": "ollama", "model": "qwen3:4b"},
                       {"label": "qwen3:latest", "backend": "ollama", "model": "qwen3:latest"},
                       {"label": "x", "backend": "ollama", "model": "x; rm -rf /"},
                       {"label": "gguf", "backend": "llamacpp", "model": "a"}]}
    entries, unavailable = plan.current_entries(cfg, [], resolve=lambda e: "d" * 64)
    assert [e["label"] for e in entries] == ["qwen3:4b"]       # same digest as qwen3:4b -> deduplicated


def test_only_each_jobs_own_result_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(accept_runs, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(accept_runs, "RUNS_DIR", tmp_path / "runs")
    entry = {"label": "qwen3:4b", "slug": "qwen3_4b", "triage_key": "k1", "confirm_key": "k2", "model": "qwen3:4b"}
    (tmp_path / "plan.json").write_text(json.dumps({"entries": [entry], "selection": {"confirm_shards": 2}}))
    art = tmp_path / "in" / "run-triage-qwen3_4b-0"
    art.mkdir(parents=True)
    good = {"key": "k1", "label": "qwen3:4b", "shard": 0, "shards": 1,
            "answers": [{"case": "c1", "seconds": 3, "fields": [{"name": "A", "type": "x" * 500}]}]}
    (art / "qwen3_4b__k1__s0of1.json").write_text(json.dumps(good))
    (art / "other__k9__s0of1.json").write_text(json.dumps({**good, "key": "k9"}))      # a forged extra file
    rogue = tmp_path / "in" / "run-triage-ghost-0"
    rogue.mkdir()
    accept_runs.main([str(tmp_path / "in"), "--stage", "triage"])
    files = sorted(p.name for p in (tmp_path / "runs").glob("*.json"))
    assert files == ["qwen3_4b__k1__s0of1.json"]
    kept = json.loads((tmp_path / "runs" / files[0]).read_text())
    assert len(kept["answers"][0]["fields"][0]["type"]) == 100


def test_readme_and_leiame_stay_parallel():
    def structure(text):
        headings, fences, in_code = [], 0, False
        for line in text.splitlines():
            if line.startswith("```"):
                fences += 1
                in_code = not in_code
            elif not in_code and line.startswith("#"):
                headings.append(len(line) - len(line.lstrip("#")))
        return headings, fences // 2

    readme = (common.ROOT / "README.md").read_text(encoding="utf-8")
    leiame = (common.ROOT / "LEIAME.md").read_text(encoding="utf-8")
    assert structure(readme) == structure(leiame)
    assert "(LEIAME.md)" in readme and "(README.md)" in leiame
    assert "<!-- LEADERBOARD:START -->" in readme and "<!-- LEADERBOARD:START -->" in leiame
