import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    return yaml.safe_load(open(os.path.join(ROOT, "config", name), encoding="utf-8"))


def test_every_row_has_a_source_for_its_hours():
    cfg = load("corpora.yaml")
    meas = load("measurements.yaml")["measurements"]
    snaps = load("snapshots.yaml")["snapshots"]
    hour_types = set(load("licence_classes.yaml")["hour_types"])
    groups = set(load("dialect_taxonomy.yaml")["groups"])
    genres = set(load("dialect_taxonomy.yaml")["genres"])
    ids = [c["corpus_id"] for c in cfg["corpora"]]
    assert len(ids) == len(set(ids))
    for c in cfg["corpora"]:
        assert c["licence"]["snapshot"] in snaps, c["corpus_id"]
        for r in c["rows"]:
            assert r["hour_type"] in hour_types
            assert r["dialect_group"] in groups
            assert r["genre"] in genres
            if r["hours_method"] == "card_or_paper_stated":
                assert r["snapshot"] in snaps
                assert r["quote"]
                nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", r["quote"])]
                if r.get("stated_sum_of"):
                    assert abs(sum(r["stated_sum_of"]) - r["stated_hours"]) < 1e-9
                else:
                    assert any(abs(n - r["stated_hours"]) < 1e-9 for n in nums), (c["corpus_id"], r["quote"])
            else:
                assert r["measurement"] in meas, (c["corpus_id"], r["measurement"])


def test_priority_lists_every_corpus():
    cfg = load("corpora.yaml")
    assert set(cfg["priority"]) == {c["corpus_id"] for c in cfg["corpora"]}


def test_no_consented_or_commercial_inventory_rows():
    cfg = load("corpora.yaml")
    for c in cfg["corpora"]:
        assert "bayanat" not in c["corpus_id"]
        assert not c.get("consented")
