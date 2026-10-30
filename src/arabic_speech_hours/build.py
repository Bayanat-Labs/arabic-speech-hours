"""Build the counter tables and feed from the configuration, the measurements and the evidence index.

Inputs (all in the repository):
  config/corpora.yaml, config/licence_classes.yaml, config/dialect_taxonomy.yaml, config/excluded.yaml
  evidence/index.jsonl                  one record per saved snapshot (URL, time, SHA-256)
  evidence/measurements/<id>.json|.parquet
  evidence/candidates.json              discovery results
  qa/second_check.csv                   the re-derivation by a separate script that does not import the package
                                        (rows enter the headline only on pass)
Outputs:
  data/corpora.{parquet,csv}, data/overlap.{parquet,csv}, data/candidates_rejected.{parquet,csv},
  data/history.{parquet,csv}, feed/latest.json, feed/badge.svg
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import re

import pandas as pd
import yaml

HEADLINE_CLASS = "open-commercial"
CLASS_ORDER = ["open-commercial", "open-noncommercial", "no-derivatives", "research-or-request", "manifests-only",
               "disputed", "unknown"]
PAGE_URL = "https://bayanatlabs.com/open/arabic-speech-hours"
DATASET_URL = "https://huggingface.co/datasets/Bayanat-Labs/arabic-speech-hours"
CHANGELOG_URL = "https://github.com/Bayanat-Labs/arabic-speech-hours/blob/v0.1.0/CHANGELOG.md"
CITATION = ("Open Arabic Speech Hours Counter, Bayanat Labs, CC BY 4.0, as of {date}. "
            "https://huggingface.co/datasets/Bayanat-Labs/arabic-speech-hours")


def load_yaml(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def classify(declared: str, rules: list[dict]) -> tuple[str, str | None]:
    d = (declared or "none").strip().lower()
    for r in rules:
        if re.search(r["pattern"], d):
            return r["class"], r.get("flag")
    return "unknown", None


def load_index(root):
    idx = {}
    p = os.path.join(root, "evidence", "index.jsonl")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                idx[r["snapshot"]] = r
    return idx


def load_measurement(root, mid):
    base = os.path.join(root, "evidence", "measurements", mid)
    rec = json.load(open(base + ".json", encoding="utf-8"))
    table = pd.read_parquet(base + ".parquet") if os.path.exists(base + ".parquet") else None
    return rec, table


def row_seconds(root, row, cache):
    m = row.get("hours_method")
    if m == "card_or_paper_stated":
        return float(row["stated_hours"]) * 3600.0, f"stated: {row.get('locator', '')}"
    mid = row["measurement"]
    if mid not in cache:
        cache[mid] = load_measurement(root, mid)
    rec, table = cache[mid]
    flt = row.get("filter")
    if flt and table is not None and all(isinstance(v, dict) for v in flt.values()):
        t = table
        for k, cond in flt.items():
            col = t[k]
            if "eq" in cond:
                t = t[col == cond["eq"]]
            elif "ne" in cond:
                t = t[(col != cond["ne"]) & col.notna()] if cond.get("notnull") else t[col != cond["ne"]]
            elif cond.get("isnull"):
                t = t[col.isna()]
            col = None
        where = ", ".join(f"{k} {json.dumps(v)}" for k, v in flt.items())
        return float(t["seconds"].sum()), f"{rec['kind']} {rec.get('repo', '')}@{str(rec.get('revision', ''))[:12]} {rec.get('pattern', '')} ({where})"
    if flt:
        parts = pd.DataFrame(rec["parts"])
        for k, v in flt.items():
            parts = parts[parts[k] == v]
        s = float(parts["seconds"].sum())
        where = ", ".join(f"{k}={v}" for k, v in flt.items())
        return s, f"{rec['kind']} {rec.get('repo', '')} column {rec.get('column', '')} ({where})"
    field = row.get("field", "seconds")
    s = float(rec[field])
    desc = rec["kind"]
    if rec.get("repo"):
        desc += f" {rec['repo']}@{str(rec.get('revision', ''))[:12]}"
    if rec.get("pattern"):
        desc += f" {rec['pattern']}"
    if rec.get("url"):
        desc += f" {rec['url']}"
    if rec.get("kind") == "delimited":
        desc += " " + ", ".join(p["url"].rsplit("/", 3)[-1] for p in rec["parts"])
    return s, f"{desc} [{field}]"


def corpus_rows(root, cfg, classes_cfg, index):
    rules = classes_cfg["string_rules"]
    cache: dict = {}
    out = []
    for c in cfg["corpora"]:
        lic = c["licence"]
        cls, flag = classify(lic.get("declared"), rules)
        snap = index.get(lic.get("snapshot"), {})
        for r in c["rows"]:
            rcls = r.get("licence_class_override") or cls
            try:
                secs, ev = row_seconds(root, r, cache)
            except FileNotFoundError:  # measurement not available in this run: the row stays pending
                secs, ev = float("nan"), f"measurement {r.get('measurement')} not available"
            part = r.get("partition")
            dialect = r.get("dialect_group", "unlabelled")
            row = {
                "row_id": ":".join(x for x in [c["corpus_id"], part, rcls, dialect, r.get("genre", "mixed"),
                                               r["hour_type"]] if x),
                "corpus_id": c["corpus_id"], "corpus_name": c["name"], "partition": part,
                "publisher": c["publisher"], "version": str(c.get("version") or ""),
                "release_date": str(c.get("release_date") or ""), "homepage_url": c["homepage_url"],
                "licence_string": lic["string"], "licence_url": lic.get("url"),
                "licence_quote": lic.get("quote"), "licence_class": rcls,
                "licence_flag": flag if rcls == cls else None,
                "licence_evidence_sha256": snap.get("sha256_text") or snap.get("sha256"),
                "licence_checked_at": snap.get("retrieved_at"),
                "access": c.get("access"), "consented": False,
                "platform_caveat": c.get("platform_caveat"),
                "dialect_group": dialect, "iso639_3": r.get("iso639_3"),
                "source_dialect_label": r.get("source_dialect_label"), "genre": r.get("genre", "mixed"),
                "hour_type": r["hour_type"], "seconds": secs, "hours": secs / 3600.0,
                "hours_method": r["hours_method"], "hours_evidence": ev,
                "hours_quote": r.get("quote"), "overlap_adjusted_hours": secs / 3600.0,
                "in_headline": False, "status": "provisional", "second_check": "pending",
                "notes": c.get("notes", ""),
            }
            out.append(row)
    df = pd.DataFrame(out)
    check_unique_row_ids(df["row_id"], "config/corpora.yaml")
    return df


def check_unique_row_ids(ids, where: str) -> None:
    """Every row needs its own id: the second check is joined back to the rows by row_id."""
    ids = pd.Series(list(ids), dtype="object")
    dup = sorted(set(ids[ids.duplicated(keep=False)]))
    if dup:
        raise ValueError(f"duplicate row_id in {where} (give each row a partition): " + ", ".join(dup))


def id_overlap(root, ov, cache):
    ra, ta = cache.setdefault(ov["a_measurement"], load_measurement(root, ov["a_measurement"]))
    rb, tb = cache.setdefault(ov["b_measurement"], load_measurement(root, ov["b_measurement"]))
    ia, ib = set(ta["id_hash"].dropna()), set(tb["id_hash"].dropna())
    shared = ia & ib
    return {"ids_a": len(ia), "ids_b": len(ib), "shared_ids": len(shared),
            "shared_hours_a": _hours(ta[ta["id_hash"].isin(shared)]["seconds"]),
            "shared_hours_b": _hours(tb[tb["id_hash"].isin(shared)]["seconds"]),
            "hours_a_scope": _hours(ta["seconds"]), "hours_b_scope": _hours(tb["seconds"])}


def _hours(seconds) -> float:
    # math.fsum is exact, so the published value does not depend on the numpy version's summation order.
    return round(math.fsum(float(x) for x in seconds.dropna()) / 3600.0, 6)


def apply_overlaps(root, rows: pd.DataFrame, cfg) -> pd.DataFrame:
    cache: dict = {}
    recs = []
    for ov in cfg.get("overlaps", []):
        a, b, m = ov["a"], ov["b"], ov["method"]
        rec = {"corpus_a": a, "corpus_b": b, "partition_b": ov.get("b_partition"), "method": m,
               "scope": ov.get("scope") or ov.get("reason") or "", "ids_a": None, "ids_b": None, "shared_ids": None,
               "shared_hours_a": None, "shared_hours_b": None, "removed_from_b_hours": 0.0,
               "same_licence_class": None, "quote": ov.get("quote")}
        ca = rows[rows.corpus_id == a]["licence_class"].unique().tolist()
        mask_b = (rows.corpus_id == b) & (rows.hour_type == "released_audio")
        if ov.get("b_partition"):
            mask_b &= rows.partition == ov["b_partition"]
        cb = rows[mask_b]["licence_class"].unique().tolist()
        same = bool(set(ca) & set(cb))
        rec["same_licence_class"] = same
        if m == "video_id_intersection":
            rec.update(id_overlap(root, ov, cache))
        elif m == "publisher_statement":
            if ov.get("shared") == "all_of_b":
                rec["shared_hours_b"] = float(rows[mask_b]["hours"].sum())
            else:
                rec["shared_hours_b"] = float(ov.get("shared_hours", 0))
            if same and rec["shared_hours_b"]:
                remaining = rec["shared_hours_b"]
                for i in rows[mask_b].index:
                    take = min(remaining, rows.at[i, "overlap_adjusted_hours"])
                    rows.at[i, "overlap_adjusted_hours"] -= take
                    remaining -= take
                rec["removed_from_b_hours"] = rec["shared_hours_b"] - remaining
        recs.append(rec)
    return pd.DataFrame(recs)


def apply_second_check(root, rows: pd.DataFrame) -> pd.DataFrame:
    p = os.path.join(root, "qa", "second_check.csv")
    if not os.path.exists(p):
        return rows
    check_unique_row_ids(rows["row_id"], "the corpus rows")
    recs = [r for r in csv.DictReader(open(p, encoding="utf-8")) if r.get("row_id")]
    check_unique_row_ids([r["row_id"] for r in recs], "qa/second_check.csv")
    chk = {r["row_id"]: r for r in recs}
    for i, r in rows.iterrows():
        c = chk.get(r["row_id"])
        if c is None or math.isnan(r["seconds"]):
            continue
        ok = c["result"] == "pass"
        rows.at[i, "second_check"] = "pass" if ok else "fail"
        rows.at[i, "status"] = "verified" if ok else "provisional"
    rows["in_headline"] = (rows.licence_class == HEADLINE_CLASS) & (rows.hour_type == "released_audio") & \
                          (rows.status == "verified")
    return rows


def aggregates(rows: pd.DataFrame, taxonomy: dict, as_of: str) -> dict:
    ra = rows[rows.hour_type == "released_audio"]
    head = rows[rows.in_headline]
    non_msa = set(taxonomy["non_msa_groups"])
    by_class = {}
    for cls in CLASS_ORDER:
        x = ra[ra.licence_class == cls]
        by_class[cls] = {"released_audio_hours_gross": round(float(x.hours.sum()), 2),
                         "released_audio_hours_overlap_adjusted": round(float(x.overlap_adjusted_hours.sum()), 2),
                         "n_corpora": int(x[x.overlap_adjusted_hours > 0].corpus_id.nunique())}
    other_types = {}
    for ht in ["transcribed", "validated", "clean", "manifest"]:
        x = rows[rows.hour_type == ht]
        if len(x):
            other_types[ht] = {cls: round(float(x[x.licence_class == cls].hours.sum()), 2)
                               for cls in CLASS_ORDER if len(x[x.licence_class == cls])}
    headline = float(head.overlap_adjusted_hours.sum())
    gross = float(head.hours.sum())
    yt = float(head[head.platform_caveat == "youtube"].overlap_adjusted_hours.sum())
    dial = float(head[head.dialect_group.isin(non_msa)].overlap_adjusted_hours.sum())
    by_dialect = {g: round(float(head[head.dialect_group == g].overlap_adjusted_hours.sum()), 2)
                  for g in sorted(head.dialect_group.unique())}
    by_genre = {g: round(float(head[head.genre == g].overlap_adjusted_hours.sum()), 2)
                for g in sorted(head.genre.unique())}
    by_corpus = (head.groupby(["corpus_id", "corpus_name"]).overlap_adjusted_hours.sum()
                 .sort_values(ascending=False).round(2))
    return {
        "as_of": as_of,
        "headline": {
            "label": "Open, commercially usable Arabic speech: released audio hours, overlap-adjusted",
            "licence_class": HEADLINE_CLASS, "hour_type": "released_audio",
            "hours": round(headline, 2), "hours_rounded": int(round(headline)), "hours_gross": round(gross, 2),
            "n_corpora": int(head[head.overlap_adjusted_hours > 0].corpus_id.nunique()),
            "youtube_derived_hours": round(yt, 2),
            "youtube_derived_share": round(yt / headline, 6) if headline else None,
            "non_msa_dialect_labelled_hours": round(dial, 2),
            "non_msa_dialect_labelled_share": round(dial / headline, 6) if headline else None,
        },
        "by_class": by_class,
        "other_hour_types": other_types,
        "open_commercial_by_dialect_group": by_dialect,
        "open_commercial_by_genre": by_genre,
        "open_commercial_by_corpus": [{"corpus_id": k[0], "corpus_name": k[1], "hours": float(v)}
                                      for k, v in by_corpus.items() if v > 0],
        "n_corpora_total": int(rows.corpus_id.nunique()),
        "n_rows": int(len(rows)),
        "n_rows_verified": int((rows.status == "verified").sum()),
    }


def badge_svg(hours: int, as_of_label: str) -> str:
    left = "open Arabic speech"
    right = f"{hours:,} h · {as_of_label}"
    cw = 6.4
    lw = int(len(left) * cw + 14)
    rw = int(len(right) * cw + 14)
    w = lw + rw
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{left}: {right}">
<title>{left}: {right} (Bayanat Labs, CC BY 4.0)</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#3a3f4b"/><rect x="{lw}" width="{rw}" height="20" fill="#0f766e"/><rect width="{w}" height="20" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="{lw / 2:.1f}" y="14">{left}</text><text x="{lw + rw / 2:.1f}" y="14">{right}</text></g>
</svg>
"""


def as_of_label(as_of: str) -> str:
    d = dt.date.fromisoformat(as_of)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def candidates_table(root, rows: pd.DataFrame, excluded: dict) -> pd.DataFrame:
    p = os.path.join(root, "evidence", "candidates.json")
    disc = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"items": []}
    counted_urls = {u.rstrip("/").lower() for u in rows.homepage_url}
    manual = {e["candidate_id"].lower(): e for e in excluded.get("excluded", [])}
    out = []
    used = set()
    for it in disc["items"]:
        cid = it["candidate_id"]
        key = cid.lower()
        rec = {"candidate_id": cid, "source": it["source"], "url": it["url"], "title": it.get("title"),
               "licence_tag": it.get("licence_tag"), "gated": it.get("gated"),
               "downloads_30d": it.get("downloads_30d"), "found_by": it.get("found_by")}
        if it["url"].rstrip("/").lower() in counted_urls:
            continue
        if key in manual:
            rec.update({"reason_code": manual[key]["reason_code"], "reason": manual[key]["reason"]})
            used.add(key)
        elif it.get("gated"):
            rec.update({"reason_code": "gated", "reason": "Gated repository; access terms were not accepted and the files were not opened."})
        elif not it.get("licence_tag"):
            rec.update({"reason_code": "not_reviewed_no_licence",
                        "reason": "Not reviewed in this run; no licence declared on the card."})
        elif (it.get("n_languages") or 0) > 3:
            rec.update({"reason_code": "not_reviewed_multilingual",
                        "reason": "Not reviewed in this run; multilingual set, Arabic hours not separated."})
        else:
            rec.update({"reason_code": "not_reviewed",
                        "reason": "Not reviewed in this run; hours, provenance and licence not yet verified."})
        out.append(rec)
    for key, e in manual.items():
        if key not in used:
            out.append({"candidate_id": e["candidate_id"], "source": e.get("source", "manual"), "url": e["url"],
                        "title": e.get("title"), "licence_tag": e.get("licence_tag"), "gated": e.get("gated", False),
                        "downloads_30d": None, "found_by": "seed list or review",
                        "reason_code": e["reason_code"], "reason": e["reason"]})
    cols = ["candidate_id", "source", "url", "title", "licence_tag", "gated", "downloads_30d", "found_by", "reason_code", "reason"]
    df = pd.DataFrame(out, columns=cols)
    order = {"excluded_derived_audio": 0, "excluded_synthetic": 0, "no_released_audio": 0, "same_audio_as_counted": 1,
             "copy_of_counted": 1, "compilation_not_reviewed": 2, "provenance_not_verified": 2}
    df["_o"] = df.reason_code.map(order).fillna(5)
    df = df.sort_values(["_o", "source", "downloads_30d"], ascending=[True, True, False]).drop(columns="_o")
    return df.reset_index(drop=True)


def build(root: str, as_of: str) -> dict:
    cfg = load_yaml(os.path.join(root, "config", "corpora.yaml"))
    classes_cfg = load_yaml(os.path.join(root, "config", "licence_classes.yaml"))
    taxonomy = load_yaml(os.path.join(root, "config", "dialect_taxonomy.yaml"))
    excluded = load_yaml(os.path.join(root, "config", "excluded.yaml"))
    index = load_index(root)
    rows = corpus_rows(root, cfg, classes_cfg, index)
    overlap = apply_overlaps(root, rows, cfg)
    rows = apply_second_check(root, rows)
    agg = aggregates(rows, taxonomy, as_of)
    cands = candidates_table(root, rows, excluded)
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    os.makedirs(os.path.join(root, "feed"), exist_ok=True)
    for name, df in [("corpora", rows), ("overlap", overlap), ("candidates_rejected", cands)]:
        df.to_parquet(os.path.join(root, "data", f"{name}.parquet"), index=False)
        df.to_csv(os.path.join(root, "data", f"{name}.csv"), index=False, quoting=csv.QUOTE_MINIMAL)
    # history: one row per as-of date (re-running on the same date replaces that row)
    hp = os.path.join(root, "data", "history.csv")
    h = agg["headline"]
    hrow = {"as_of": as_of, "headline_hours": h["hours"], "headline_hours_gross": h["hours_gross"],
            "headline_n_corpora": h["n_corpora"], "youtube_derived_hours": h["youtube_derived_hours"],
            "non_msa_dialect_labelled_hours": h["non_msa_dialect_labelled_hours"],
            **{f"{k}_hours": v["released_audio_hours_overlap_adjusted"] for k, v in agg["by_class"].items()},
            "n_corpora_total": agg["n_corpora_total"], "n_rows": agg["n_rows"],
            "n_candidates_listed": int(len(cands))}
    hist = pd.read_csv(hp) if os.path.exists(hp) else pd.DataFrame()
    if len(hist):
        hist = hist[hist.as_of != as_of]
    hist = pd.concat([hist, pd.DataFrame([hrow])], ignore_index=True).sort_values("as_of")
    hist.to_csv(hp, index=False)
    hist.to_parquet(os.path.join(root, "data", "history.parquet"), index=False)
    latest = {
        "schema_version": "1.0",
        "as_of": as_of,
        "as_of_label": as_of_label(as_of),
        "headline_hours": h["hours_rounded"],
        "headline": h,
        "by_class": {k: v["released_audio_hours_overlap_adjusted"] for k, v in agg["by_class"].items()},
        "by_class_detail": agg["by_class"],
        "other_hour_types": agg["other_hour_types"],
        "by_dialect_group": agg["open_commercial_by_dialect_group"],
        "by_genre": agg["open_commercial_by_genre"],
        "by_corpus": agg["open_commercial_by_corpus"],
        "n_corpora": agg["n_corpora_total"],
        "n_candidates_listed": int(len(cands)),
        "page_url": PAGE_URL,
        "dataset_url": DATASET_URL,
        "changelog_url": CHANGELOG_URL,
        "licence": "CC-BY-4.0",
        "citation": CITATION.format(date=as_of_label(as_of)),
        "publisher": "Bayanat Labs",
    }
    with open(os.path.join(root, "feed", "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(os.path.join(root, "feed", "badge.svg"), "w", encoding="utf-8") as f:
        f.write(badge_svg(h["hours_rounded"], as_of_label(as_of)))
    return {"rows": rows, "overlap": overlap, "candidates": cands, "aggregates": agg, "latest": latest}
