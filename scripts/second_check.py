#!/usr/bin/env python3
"""Second check of every row of data/corpora.csv, by a separate script that does not import the package.

The counter's package is not imported here. For each row it re-derives:
  * the hours, from the evidence files only: per-row seconds re-summed from the measurement tables
    (evidence/measurements/*.parquet), the release statistics or viewer statistics saved in the
    measurement records, or, for stated rows, the number re-read from a quote that must appear
    verbatim in the saved snapshot text;
  * the licence class, from the licence quote or the declared licence string, with its own keyword
    rules (not the counter's rule table). A research-or-request override must carry a quote that names
    an agreement or a request process and appears in its saved page.
Row ids must be unique; a duplicate id stops the check.
A row passes when the hours agree within 0.1 % (and 0.01 h) and the class is identical. It also
re-computes the video-ID overlaps and the headline. Results go to qa/second_check.csv and
qa/second_check_summary.json. Exit status 1 if any row fails, 2 on a duplicate row id.
The uploader-locale summary written into a measurement record (locale_hours) is re-summed from its
table as well, and the licence each recorded third-party copy declares is looked up in its saved page.

  python scripts/second_check.py [--snapshots DIR]

--snapshots: a folder with <snapshot name with / replaced by __>.txt (and .html) files. Without it,
quote checks are reported as "not run" and stated rows fail.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def numbers(s):
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", s or "")]


def class_from_text(declared, quote, override=None):
    """Keyword rules, written separately from config/licence_classes.yaml."""
    if override:
        return override
    t = f"{declared or ''} {quote or ''}".lower()
    if declared in (None, "", "none") and ("not documented" in t or not quote):
        return "unknown"
    if "research" in t or "agreement" in t:
        return "research-or-request"
    if re.search(r"\bnd\b|-nd-|-nd$|noderiv|no derivatives", t):
        return "no-derivatives"
    if re.search(r"non-?commercial|-nc-|-nc$|\bnc\b", t):
        return "open-noncommercial"
    if re.search(r"cc0|zero v1\.0", t):
        return "open-commercial"
    if re.search(r"cc-by|cc by|licenses/by/|attribution", t):
        return "open-commercial"
    if re.search(r"\b(mit|apache|bsd)\b", t):
        return "open-commercial"
    return "unknown"


def load_snapshot(snapdir, name, part="text"):
    if not snapdir:
        return None
    base = os.path.join(snapdir, name.replace("/", "__"))
    if part == "html":
        for ext in (".html", ".bin"):
            if os.path.exists(base + ext):
                return open(base + ext, encoding="utf-8", errors="replace").read()
        return None
    p = base + ".txt"
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rederive_seconds(row_cfg, meas_dir, snapdir, notes):
    m = row_cfg["hours_method"]
    if m == "card_or_paper_stated":
        text = load_snapshot(snapdir, row_cfg["snapshot"])
        if text is None:
            notes.append("snapshot not available")
            return None
        q = ws(row_cfg["quote"])
        if q not in ws(text):
            notes.append("quote not found in snapshot")
            return None
        if row_cfg.get("stated_sum_of"):
            parts = row_cfg["stated_sum_of"]
            nums_text = numbers(text)
            if not all(any(abs(p - n) < 1e-9 for n in nums_text) for p in parts):
                notes.append("a summed figure is not in the snapshot")
                return None
            return sum(parts) * 3600.0
        nums = numbers(q)
        target = float(row_cfg["stated_hours"])
        if not any(abs(n - target) < 1e-9 for n in nums):
            notes.append(f"stated figure {target} not in quote numbers {nums}")
            return None
        return target * 3600.0
    mid = row_cfg["measurement"]
    rec = json.load(open(os.path.join(meas_dir, mid + ".json"), encoding="utf-8"))
    kind = rec["kind"]
    field = row_cfg.get("field", "seconds")
    if kind == "cv_release_stats":
        return rec["duration_ms"] / 1000.0 if field == "seconds" else float(rec["validDurationSecs"])
    if kind == "hf_viewer_stats":
        parts = pd.DataFrame(rec["parts"])
        for k, v in (row_cfg.get("filter") or {}).items():
            parts = parts[parts[k] == v]
        scale = float(rec.get("scale", 1.0))
        return float(((parts["num_examples"] - parts["nan_count"]) * parts["mean"]).sum() * scale)
    t = pd.read_parquet(os.path.join(meas_dir, mid + ".parquet"))
    for k, cond in (row_cfg.get("filter") or {}).items():
        if not isinstance(cond, dict):
            t = t[t[k] == cond]
        elif "eq" in cond:
            t = t[t[k] == cond["eq"]]
        elif "ne" in cond:
            t = t[t[k].notna() & (t[k] != cond["ne"])] if cond.get("notnull") else t[t[k] != cond["ne"]]
        elif cond.get("isnull"):
            t = t[t[k].isna()]
    if row_cfg.get("filter"):
        return float(t["seconds"].sum())
    per_file = t.groupby("file")["seconds"].sum() if "file" in t else None
    if per_file is not None and rec.get("files"):
        for fr in rec["files"]:
            if abs(per_file.get(fr["path"], 0.0) - fr["seconds"]) > 1e-6 * max(1.0, fr["seconds"]):
                notes.append(f"per-file sum differs for {fr['path']}")
    return float(t["seconds"].sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "corpora.yaml"), encoding="utf-8"))
    meas_dir = os.path.join(ROOT, "evidence", "measurements")
    index = {}
    for line in open(os.path.join(ROOT, "evidence", "index.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        index[r["snapshot"]] = r
    pub = pd.read_csv(os.path.join(ROOT, "data", "corpora.csv"))
    pub_by_key = {}
    for _, r in pub.iterrows():
        pub_by_key[(r["corpus_id"], r["partition"] if isinstance(r["partition"], str) else None,
                    r["hour_type"], r["source_dialect_label"] if isinstance(r["source_dialect_label"], str) else None)] = r
    results = []
    snap_checks = {}
    if a.snapshots:
        for name, r in index.items():
            p = os.path.join(a.snapshots, name.replace("/", "__") + ".txt")
            snap_checks[name] = os.path.exists(p) and sha256_file(p) == r["sha256_text"]
    for c in cfg["corpora"]:
        lic = c["licence"]
        for rc in c["rows"]:
            key = (c["corpus_id"], rc.get("partition"), rc["hour_type"], rc.get("source_dialect_label"))
            p = pub_by_key.get(key)
            notes = []
            if p is None:
                results.append({"row_id": "", "corpus_id": c["corpus_id"], "result": "fail",
                                "detail": "row missing from data/corpora.csv"})
                continue
            try:
                secs = rederive_seconds(rc, meas_dir, a.snapshots, notes)
            except FileNotFoundError:
                secs = None
                notes.append("measurement files missing")
            # licence quote must be in its snapshot (raw HTML when the quote is page metadata)
            if lic.get("quote"):
                text = load_snapshot(a.snapshots, lic["snapshot"], lic.get("snapshot_part", "text"))
                if text is None:
                    notes.append("licence snapshot not available")
                elif ws(lic["quote"]) not in ws(text):
                    notes.append("licence quote not found in snapshot")
            if a.snapshots and lic.get("snapshot") in snap_checks and not snap_checks[lic["snapshot"]]:
                notes.append("licence snapshot hash differs from evidence/index.jsonl")
            override = rc.get("licence_class_override")
            if override:
                oq = rc.get("override_quote") or rc.get("quote") or ""
                if override != "research-or-request" or not re.search(r"agreement|request", oq.lower()):
                    notes.append("override without an agreement or request quote")
                else:
                    otext = load_snapshot(a.snapshots, rc.get("override_snapshot") or rc.get("snapshot"))
                    if otext is not None and ws(oq) not in ws(otext):
                        notes.append("override quote not found in snapshot")
            cls = class_from_text(lic.get("declared"), lic.get("quote"), override)
            pub_h = float(p["hours"])
            re_h = None if secs is None else secs / 3600.0
            ok_h = re_h is not None and pub_h == pub_h and abs(re_h - pub_h) <= max(0.01, 0.001 * max(abs(pub_h), 1e-9))
            ok_c = cls == p["licence_class"]
            hard = [n for n in notes if n not in ("snapshot not available",)]
            ok = ok_h and ok_c and not [n for n in hard if "not found" in n or "differs" in n or "missing" in n
                                        or "not in" in n or "without" in n]
            results.append({"row_id": p["row_id"], "corpus_id": c["corpus_id"], "hour_type": rc["hour_type"],
                            "published_hours": round(pub_h, 4), "rederived_hours": None if re_h is None else round(re_h, 4),
                            "published_class": p["licence_class"], "rederived_class": cls,
                            "result": "pass" if ok else "fail", "detail": "; ".join(notes)})
    ids = [r["row_id"] for r in results if r["row_id"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        print("STOP: duplicate row_id in data/corpora.csv: " + ", ".join(dup))
        return 2
    # overlaps
    ov_pub = pd.read_csv(os.path.join(ROOT, "data", "overlap.csv"))
    ov_res = []
    for ov in cfg.get("overlaps", []):
        if ov["method"] != "video_id_intersection":
            continue
        ta = pd.read_parquet(os.path.join(meas_dir, ov["a_measurement"] + ".parquet"))
        tb = pd.read_parquet(os.path.join(meas_dir, ov["b_measurement"] + ".parquet"))
        shared = set(ta["id_hash"].dropna()) & set(tb["id_hash"].dropna())
        hb = tb[tb["id_hash"].isin(shared)]["seconds"].sum() / 3600.0
        pr = ov_pub[(ov_pub.corpus_a == ov["a"]) & (ov_pub.corpus_b == ov["b"])].iloc[0]
        ok = int(pr["shared_ids"]) == len(shared) and abs(float(pr["shared_hours_b"]) - hb) < 0.01
        ov_res.append({"a": ov["a"], "b": ov["b"], "shared_ids": len(shared), "shared_hours_b": round(hb, 3),
                       "result": "pass" if ok else "fail"})
    # licences declared by third-party copies, as recorded in config/corpora.yaml
    copy_res = []
    for c in cfg["corpora"]:
        for cp in c["licence"].get("copies") or []:
            text = load_snapshot(a.snapshots, cp["snapshot"])
            spdx = cp["licence"].lower().replace(" ", "-")
            ok = text is not None and re.search(r"(?<![\w-])" + re.escape(spdx) + r"(?![\w-])", text.lower()) is not None
            copy_res.append({"corpus_id": c["corpus_id"], "copy": cp["repo"], "licence": cp["licence"],
                             "result": "pass" if ok else ("not run" if text is None else "fail")})
    # locale summaries kept in measurement records (YODAS v3: hours by uploader locale)
    loc_res = []
    for fn in sorted(os.listdir(meas_dir)):
        if not fn.endswith(".json"):
            continue
        rec = json.load(open(os.path.join(meas_dir, fn), encoding="utf-8"))
        if not rec.get("locale_column"):
            continue
        t = pd.read_parquet(os.path.join(meas_dir, fn[:-5] + ".parquet"))
        col, prim = t[rec["locale_column"]], rec.get("locale_primary", "ar")
        re_loc = {prim: t[col == prim]["seconds"].sum() / 3600.0,
                  "other": t[col.notna() & (col != prim)]["seconds"].sum() / 3600.0,
                  "not_given": t[col.isna()]["seconds"].sum() / 3600.0}
        ok = set(re_loc) == set(rec["locale_hours"]) and all(abs(re_loc[k] - rec["locale_hours"][k]) < 0.01 for k in re_loc)
        loc_res.append({"measurement": fn[:-5], "column": rec["locale_column"],
                        "hours": {k: round(v, 2) for k, v in re_loc.items()}, "result": "pass" if ok else "fail"})
    # headline: re-derived open-commercial released audio minus same-class publisher-stated overlaps
    res = pd.DataFrame(results)
    latest = json.load(open(os.path.join(ROOT, "feed", "latest.json"), encoding="utf-8"))
    oc = res[(res.rederived_class == "open-commercial") & (res.hour_type == "released_audio") & (res.result == "pass")]
    total = float(oc["rederived_hours"].sum())
    removed = 0.0
    for ov in cfg.get("overlaps", []):
        if ov["method"] != "publisher_statement":
            continue
        ca = set(res[res.corpus_id == ov["a"]].rederived_class)
        rb = res[(res.corpus_id == ov["b"]) & (res.hour_type == "released_audio")]
        if ov.get("b_partition"):
            rb = rb[rb.row_id.str.contains(f":{ov['b_partition']}:")]
        if "open-commercial" in ca and (rb.rederived_class == "open-commercial").any():
            removed += float(rb.rederived_hours.sum()) if ov.get("shared") == "all_of_b" else float(ov.get("shared_hours", 0))
    head_re = total - removed
    head_ok = abs(head_re - latest["headline"]["hours"]) < 0.05
    os.makedirs(os.path.join(ROOT, "qa"), exist_ok=True)
    res.to_csv(os.path.join(ROOT, "qa", "second_check.csv"), index=False)
    summary = {"rows": len(res), "pass": int((res.result == "pass").sum()), "fail": int((res.result == "fail").sum()),
               "overlaps": ov_res, "locale_summaries": loc_res, "licence_copies": copy_res, "headline_published": latest["headline"]["hours"],
               "headline_rederived": round(head_re, 2), "headline_agrees": head_ok,
               "snapshot_hashes_checked": len(snap_checks), "snapshot_hashes_ok": sum(snap_checks.values())}
    json.dump(summary, open(os.path.join(ROOT, "qa", "second_check_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    bad = res[res.result != "pass"]
    if len(bad):
        print(bad.to_string())
    return 0 if (summary["fail"] == 0 and all(o["result"] == "pass" for o in ov_res + loc_res)
                and not any(x["result"] == "fail" for x in copy_res)) else 1


if __name__ == "__main__":
    sys.exit(main())
