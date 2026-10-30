"""End-to-end on a small synthetic repository: build, then the second check (a separate script that does not import the package)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pandas as pd
import yaml

from arabic_speech_hours.build import apply_second_check, build, corpus_rows, load_index, load_yaml
from arabic_speech_hours.measure import locale_summary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPORA = {
    "version": "test",
    "priority": ["a", "b", "c"],
    "corpora": [
        {"corpus_id": "a", "name": "Corpus A", "publisher": "P", "homepage_url": "https://example.org/a",
         "access": "open download", "platform_caveat": "youtube",
         "licence": {"string": "CC BY 4.0", "declared": "cc-by-4.0", "url": "https://example.org/a",
                     "quote": "Licensed under CC BY 4.0.", "snapshot": "a/page"},
         "rows": [{"hour_type": "released_audio", "dialect_group": "unlabelled", "genre": "mixed",
                   "hours_method": "computed_from_metadata", "measurement": "ma", "field": "seconds"}]},
        {"corpus_id": "b", "name": "Corpus B", "publisher": "P", "homepage_url": "https://example.org/b",
         "access": "open download", "platform_caveat": None,
         "licence": {"string": "CC0", "declared": "cc0-1.0", "url": "https://example.org/b",
                     "quote": "Released under CC0.", "snapshot": "b/page"},
         "rows": [{"hour_type": "released_audio", "dialect_group": "Gulf", "source_dialect_label": "Emirati",
                   "genre": "read", "hours_method": "card_or_paper_stated", "stated_hours": 12.5,
                   "quote": "The corpus contains 12.5 hours of speech.", "snapshot": "b/page", "locator": "page"}]},
        {"corpus_id": "c", "name": "Corpus C", "publisher": "P", "homepage_url": "https://example.org/c",
         "access": "open download", "platform_caveat": None,
         "licence": {"string": "CC BY-NC 4.0", "declared": "cc-by-nc-4.0", "url": "https://example.org/c",
                     "quote": "CC BY-NC 4.0, non-commercial use only.", "snapshot": "c/page"},
         "rows": [{"hour_type": "released_audio", "dialect_group": "mixed", "genre": "broadcast",
                   "hours_method": "card_or_paper_stated", "stated_hours": 100,
                   "quote": "about 100 hours", "snapshot": "c/page", "locator": "page"}]},
    ],
    "overlaps": [
        {"a": "a", "b": "b", "method": "publisher_statement", "shared_hours": 2.5, "quote": "b reuses 2.5 h of a",
         "snapshot": "b/page"},
    ],
}
SNAPS = {
    "a/page": "Corpus A. Licensed under CC BY 4.0.",
    "b/page": "Corpus B. Released under CC0. The corpus contains 12.5 hours of speech.",
    "c/page": "Corpus C. CC BY-NC 4.0, non-commercial use only. It has about 100 hours of audio.",
}


def make_repo(tmp):
    os.makedirs(os.path.join(tmp, "config"))
    os.makedirs(os.path.join(tmp, "evidence", "measurements"))
    os.makedirs(os.path.join(tmp, "scripts"))
    os.makedirs(os.path.join(tmp, "snapshots"))
    for n in ["licence_classes.yaml", "dialect_taxonomy.yaml"]:
        shutil.copy(os.path.join(ROOT, "config", n), os.path.join(tmp, "config", n))
    shutil.copy(os.path.join(ROOT, "scripts", "second_check.py"), os.path.join(tmp, "scripts", "second_check.py"))
    yaml.safe_dump(CORPORA, open(os.path.join(tmp, "config", "corpora.yaml"), "w"))
    yaml.safe_dump({"excluded": []}, open(os.path.join(tmp, "config", "excluded.yaml"), "w"))
    t = pd.DataFrame({"file": ["f1", "f1", "f2"], "id_hash": ["x", "y", "z"], "seconds": [3600.0, 1800.0, 5400.0]})
    t.to_parquet(os.path.join(tmp, "evidence", "measurements", "ma.parquet"), index=False)
    rec = {"id": "ma", "kind": "hf_parquet_columns", "repo": "x/a", "revision": "0" * 40, "pattern": "*.parquet",
           "files": [{"path": "f1", "seconds": 5400.0}, {"path": "f2", "seconds": 5400.0}],
           "rows": 3, "seconds": 10800.0}
    json.dump(rec, open(os.path.join(tmp, "evidence", "measurements", "ma.json"), "w"))
    with open(os.path.join(tmp, "evidence", "index.jsonl"), "w") as f:
        for name, text in SNAPS.items():
            p = os.path.join(tmp, "snapshots", name.replace("/", "__") + ".txt")
            open(p, "w").write(text)
            f.write(json.dumps({"snapshot": name, "url": "https://example.org", "retrieved_at": "2026-10-30T00:00:00Z",
                                "sha256": "0", "sha256_text": hashlib.sha256(text.encode()).hexdigest()}) + "\n")


def run_check(tmp):
    return subprocess.run([sys.executable, "-I", os.path.join(tmp, "scripts", "second_check.py"), "--snapshots",
                           os.path.join(tmp, "snapshots")], capture_output=True, text=True)


def test_build_then_second_check(tmp_path):
    tmp = str(tmp_path)
    make_repo(tmp)
    build(tmp, "2026-10-30")                       # draft: nothing verified yet
    latest = json.load(open(os.path.join(tmp, "feed", "latest.json")))
    assert latest["headline"]["hours"] == 0
    r = run_check(tmp)
    assert r.returncode == 0, r.stdout + r.stderr
    out = build(tmp, "2026-10-30")                 # final: rows that passed enter the headline
    h = out["latest"]["headline"]
    assert h["hours_gross"] == 15.5               # 3 h (A) + 12.5 h (B); C is non-commercial
    assert h["hours"] == 13.0                     # 2.5 h of B removed as overlap with A
    assert h["youtube_derived_hours"] == 3.0
    assert h["non_msa_dialect_labelled_hours"] == 10.0
    assert out["latest"]["by_class"]["open-noncommercial"] == 100.0
    assert out["latest"]["by_class"]["open-commercial"] == 13.0
    r = run_check(tmp)                             # the headline re-derivation agrees
    assert json.load(open(os.path.join(tmp, "qa", "second_check_summary.json")))["headline_agrees"]
    hist = pd.read_csv(os.path.join(tmp, "data", "history.csv"))
    assert len(hist) == 1                          # same as-of date replaces its row
    svg = open(os.path.join(tmp, "feed", "badge.svg")).read()
    assert "13 h" in svg and "30 October 2026" in svg


def test_check_fails_on_a_wrong_quote(tmp_path):
    tmp = str(tmp_path)
    make_repo(tmp)
    open(os.path.join(tmp, "snapshots", "b__page.txt"), "w").write("Corpus B. Released under CC0. 14 hours.")
    build(tmp, "2026-10-30")
    r = run_check(tmp)
    assert r.returncode == 1
    res = pd.read_csv(os.path.join(tmp, "qa", "second_check.csv"))
    assert (res[res.corpus_id == "b"].result == "fail").all()
    out = build(tmp, "2026-10-30")
    assert out["latest"]["headline"]["hours_gross"] == 3.0   # B stays out of the headline


def test_latest_json_schema(tmp_path):
    import jsonschema
    tmp = str(tmp_path)
    make_repo(tmp)
    build(tmp, "2026-10-30")
    schema = json.load(open(os.path.join(ROOT, "feed", "latest.schema.json")))
    jsonschema.validate(json.load(open(os.path.join(tmp, "feed", "latest.json"))), schema)
    jsonschema.validate(json.load(open(os.path.join(ROOT, "feed", "latest.json"))), schema)


def test_row_ids_are_unique():
    """Every row of the real configuration has its own row_id (the second check is joined back by it)."""
    cfg = load_yaml(os.path.join(ROOT, "config", "corpora.yaml"))
    classes = load_yaml(os.path.join(ROOT, "config", "licence_classes.yaml"))
    rows = corpus_rows(ROOT, cfg, classes, load_index(ROOT))
    assert rows.row_id.is_unique
    published = pd.read_csv(os.path.join(ROOT, "data", "corpora.csv"))
    assert published.row_id.is_unique
    assert set(published.row_id) == set(rows.row_id)


def test_duplicate_row_ids_fail_loudly(tmp_path):
    import pytest
    tmp = str(tmp_path)
    make_repo(tmp)
    cfg = yaml.safe_load(open(os.path.join(tmp, "config", "corpora.yaml")))
    cfg["corpora"][2]["rows"].append(dict(cfg["corpora"][2]["rows"][0]))   # same corpus, no partition
    yaml.safe_dump(cfg, open(os.path.join(tmp, "config", "corpora.yaml"), "w"))
    with pytest.raises(ValueError, match="duplicate row_id"):
        build(tmp, "2026-10-30")
    rows = pd.DataFrame({"row_id": ["x", "x"], "seconds": [1.0, 2.0], "licence_class": ["open-commercial"] * 2,
                         "hour_type": ["released_audio"] * 2, "status": ["provisional"] * 2})
    os.makedirs(os.path.join(tmp, "qa"), exist_ok=True)
    pd.DataFrame({"row_id": ["x"], "result": ["pass"]}).to_csv(os.path.join(tmp, "qa", "second_check.csv"), index=False)
    with pytest.raises(ValueError, match="duplicate row_id"):
        apply_second_check(tmp, rows)


def test_request_override_needs_its_quote(tmp_path):
    tmp = str(tmp_path)
    make_repo(tmp)
    cfg = yaml.safe_load(open(os.path.join(tmp, "config", "corpora.yaml")))
    row = cfg["corpora"][2]["rows"][0]
    row.update({"licence_class_override": "research-or-request", "override_snapshot": "c/page",
                "override_quote": "Complete the request process to download the data."})
    yaml.safe_dump(cfg, open(os.path.join(tmp, "config", "corpora.yaml"), "w"))
    build(tmp, "2026-10-30")
    r = run_check(tmp)                             # the quote is not in the saved page yet
    assert r.returncode == 1
    res = pd.read_csv(os.path.join(tmp, "qa", "second_check.csv"))
    assert (res[res.corpus_id == "c"].result == "fail").all()
    open(os.path.join(tmp, "snapshots", "c__form.txt"), "w").write("Corpus C. Complete the request process to download the data.")
    row["override_snapshot"] = "c/form"
    yaml.safe_dump(cfg, open(os.path.join(tmp, "config", "corpora.yaml"), "w"))
    r = run_check(tmp)
    res = pd.read_csv(os.path.join(tmp, "qa", "second_check.csv"))
    assert (res[res.corpus_id == "c"].result == "pass").all(), r.stdout
    out = build(tmp, "2026-10-30")
    assert out["latest"]["by_class"]["research-or-request"] == 100.0
    assert out["latest"]["by_class"]["open-noncommercial"] == 0.0


def test_locale_summary():
    t = pd.DataFrame({"seconds": [3600.0, 7200.0, 1800.0, 1800.0], "locale_lang": ["ar", "fa", None, "ar"]})
    s = locale_summary(t, "locale_lang")
    assert s["locale_hours"] == {"ar": 1.5, "other": 2.0, "not_given": 0.5}
    assert s["locale_rows"] == {"ar": 2, "other": 1, "not_given": 1}
    rec = json.load(open(os.path.join(ROOT, "evidence", "measurements", "yodas3-ar.json")))
    tab = pd.read_parquet(os.path.join(ROOT, "evidence", "measurements", "yodas3-ar.parquet"))
    assert rec["locale_hours"] == locale_summary(tab, rec["locale_column"])["locale_hours"]
    assert abs(sum(rec["locale_seconds"].values()) - rec["seconds"]) < 1e-6
