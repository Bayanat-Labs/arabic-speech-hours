"""Hour measurements from published metadata. Audio files are never fetched.

Each measurement kind reads only duration-bearing metadata: a duration column of a Parquet file
(range requests for that column chunk only), per-file duration manifests, release statistics,
TSV/CSV manifests, or the Hugging Face dataset viewer's column statistics. Every measurement
returns a JSON-serialisable record (what was read, from which revision, how many rows, how many
seconds) and, where useful, a small table of per-row values (durations, group labels and
SHA-256-truncated identifiers) that the second check (a separate script that does not import the
package) re-sums.
"""
from __future__ import annotations

import csv
import fnmatch
import hashlib
import io
import json
import urllib.parse

import pandas as pd

from .http import Fetcher, sha256_bytes, utc_now
from .remote_parquet import read_columns

HF = "https://huggingface.co"
VIEWER = "https://datasets-server.huggingface.co"


def id_hash(x: str) -> str:
    """Identifiers are published only as truncated SHA-256 hashes (enough to compare sets)."""
    return hashlib.sha256(str(x).encode("utf-8")).hexdigest()[:16]


def hf_api(f: Fetcher, repo: str, revision: str | None = None) -> dict:
    url = f"{HF}/api/datasets/{repo}" + (f"/revision/{revision}" if revision else "")
    return f.get_json(url)


def hf_api_summary(api: dict) -> dict:
    cd = api.get("cardData") or {}
    return {"id": api.get("id"), "sha": api.get("sha"), "lastModified": api.get("lastModified"),
            "gated": api.get("gated"), "private": api.get("private"), "disabled": api.get("disabled"),
            "card_license": cd.get("license"), "license_name": cd.get("license_name"),
            "license_link": cd.get("license_link"),
            "tags": [t for t in api.get("tags", []) if t.startswith(("license:", "language:", "modality:",
                                                                      "task_categories:", "size_categories:"))],
            "n_files": len(api.get("siblings", []))}


def hf_list(api: dict, pattern: str) -> list[str]:
    return sorted(s["rfilename"] for s in api.get("siblings", []) if fnmatch.fnmatch(s["rfilename"], pattern))


def resolve_url(repo: str, sha: str, path: str) -> str:
    return f"{HF}/datasets/{repo}/resolve/{sha}/{urllib.parse.quote(path)}"


def locale_summary(table: pd.DataFrame, column: str, primary: str = "ar") -> dict:
    """Hours by a locale column of a measurement table: the primary locale, any other value, and not given."""
    col = table[column]
    secs = {primary: table[col == primary]["seconds"].sum(),
            "other": table[col.notna() & (col != primary)]["seconds"].sum(),
            "not_given": table[col.isna()]["seconds"].sum()}
    return {"locale_column": column, "locale_primary": primary,
            "locale_seconds": {k: float(v) for k, v in secs.items()},
            "locale_hours": {k: round(float(v) / 3600.0, 4) for k, v in secs.items()},
            "locale_rows": {primary: int((col == primary).sum()), "other": int((col.notna() & (col != primary)).sum()),
                            "not_given": int(col.isna().sum())}}


def add_summaries(rec: dict, table: pd.DataFrame, spec: dict) -> dict:
    """Summaries computed from the saved table only (no request), e.g. YODAS v3 hours by uploader locale."""
    if spec.get("locale_col"):
        rec.update(locale_summary(table, spec["locale_col"], spec.get("locale_primary", "ar")))
    return rec


def m_hf_parquet_columns(f: Fetcher, repo: str, pattern: str, duration_col: str, scale: float = 1.0,
                         id_col: str | None = None, group_col: str | None = None,
                         extra_cols: list[str] | None = None, revision: str | None = None,
                         progress=None) -> tuple[dict, pd.DataFrame]:
    api = hf_api(f, repo, revision)
    sha = api["sha"]
    files = hf_list(api, pattern)
    if not files:
        raise RuntimeError(f"no files match {pattern} in {repo}@{sha}")
    cols = [duration_col] + [c for c in (id_col, group_col) if c] + list(extra_cols or [])
    frames, per_file = [], []
    for i, path in enumerate(files):
        tb, st = read_columns(f, resolve_url(repo, sha, path), cols)
        if duration_col not in tb.column_names:
            raise RuntimeError(f"{path}: no column {duration_col}")
        df = tb.to_pandas()
        out = pd.DataFrame({"file": path, "seconds": df[duration_col].astype("float64") * scale})
        if id_col:
            out["id_hash"] = df[id_col].map(id_hash)
        if group_col:
            out["group"] = df[group_col].astype("string")
        for c in extra_cols or []:
            if c in df:
                out[c] = df[c]
        frames.append(out)
        per_file.append({"path": path, "rows": st["rows"], "row_groups": st["row_groups"],
                         "bytes_fetched": st["bytes_fetched"], "file_bytes": st["file_bytes"],
                         "seconds": float(out["seconds"].sum(skipna=True)),
                         "null_durations": int(out["seconds"].isna().sum())})
        if progress:
            progress(i + 1, len(files), path)
    table = pd.concat(frames, ignore_index=True)
    rec = {"kind": "hf_parquet_columns", "repo": repo, "revision": sha, "pattern": pattern,
           "columns_read": cols, "duration_column": duration_col, "scale": scale, "files": per_file,
           "n_files": len(files), "rows": int(len(table)), "seconds": float(table["seconds"].sum(skipna=True)),
           "null_durations": int(table["seconds"].isna().sum()),
           "bytes_fetched": int(sum(p["bytes_fetched"] for p in per_file)),
           "bytes_in_files": int(sum(p["file_bytes"] for p in per_file)), "measured_at": utc_now(),
           "api": hf_api_summary(api)}
    return rec, table


def m_hf_duration_txt(f: Fetcher, repo: str, pattern: str, revision: str | None = None,
                      progress=None) -> tuple[dict, pd.DataFrame]:
    """Per-shard text manifests with one '<id> <seconds>' line per recording (YODAS2 layout)."""
    api = hf_api(f, repo, revision)
    sha = api["sha"]
    files = hf_list(api, pattern)
    rows, per_file = [], []
    for i, path in enumerate(files):
        b, meta = f.get_bytes(resolve_url(repo, sha, path))
        n, s = 0, 0.0
        for line in b.decode("utf-8").splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            rows.append((path, id_hash(parts[0]), float(parts[1])))
            n += 1
            s += float(parts[1])
        per_file.append({"path": path, "rows": n, "seconds": s, "sha256": meta["sha256"]})
        if progress:
            progress(i + 1, len(files), path)
    table = pd.DataFrame(rows, columns=["file", "id_hash", "seconds"])
    rec = {"kind": "hf_duration_txt", "repo": repo, "revision": sha, "pattern": pattern, "files": per_file,
           "n_files": len(files), "rows": int(len(table)), "seconds": float(table["seconds"].sum()),
           "measured_at": utc_now(), "api": hf_api_summary(api)}
    return rec, table


def m_hf_viewer_stats(f: Fetcher, repo: str, column: str, splits: list[tuple[str, str]],
                      scale: float = 1.0) -> tuple[dict, pd.DataFrame]:
    """Sum = mean x (non-null count) from the dataset viewer's column statistics, per config and split.

    Only used when the viewer reports full (not partial) statistics for the split."""
    api = hf_api(f, repo)
    parts = []
    for config, split in splits:
        q = urllib.parse.urlencode({"dataset": repo, "config": config, "split": split})
        d = f.get_json(f"{VIEWER}/statistics?{q}")
        if d.get("partial"):
            raise RuntimeError(f"viewer statistics are partial for {repo} {config}/{split}")
        st = next((c for c in d["statistics"] if c["column_name"] == column), None)
        if st is None:
            raise RuntimeError(f"no statistics for column {column} in {repo} {config}/{split}")
        cs = st["column_statistics"]
        n = d["num_examples"] - cs.get("nan_count", 0)
        parts.append({"config": config, "split": split, "num_examples": d["num_examples"],
                      "nan_count": cs.get("nan_count", 0), "mean": cs["mean"], "min": cs.get("min"),
                      "max": cs.get("max"), "seconds": cs["mean"] * n * scale, "partial": d.get("partial", False)})
    table = pd.DataFrame(parts)
    rec = {"kind": "hf_viewer_stats", "repo": repo, "revision": api["sha"], "column": column, "scale": scale,
           "parts": parts, "rows": int(sum(p["num_examples"] for p in parts)),
           "seconds": float(sum(p["seconds"] for p in parts)), "measured_at": utc_now(),
           "api": hf_api_summary(api),
           "note": "seconds = mean x non-null count; the viewer rounds the mean to 5 decimals"}
    return rec, table


def m_delimited(f: Fetcher, url: str, duration_field: str | int, scale: float = 1.0, delimiter: str = ",",
                header: bool = True, id_field: str | int | None = None, id_transform=None,
                group_field: str | int | None = None) -> tuple[dict, pd.DataFrame]:
    """A CSV/TSV manifest: sum of one duration column (optionally scaled, e.g. samples / 16000)."""
    b, meta = f.get_bytes(url)
    text = b.decode("utf-8-sig")
    rdr = csv.reader(io.StringIO(text), delimiter=delimiter, quoting=csv.QUOTE_NONE if delimiter == "\t" else csv.QUOTE_MINIMAL)
    rows = list(rdr)
    head = rows[0] if header else None
    body = rows[1:] if header else rows

    def idx(field):
        if field is None:
            return None
        return head.index(field) if isinstance(field, str) else field

    di, ii, gi = idx(duration_field), idx(id_field), idx(group_field)
    out = []
    for r in body:
        if len(r) <= di:
            continue
        rec = {"seconds": float(r[di]) * scale}
        if ii is not None:
            v = r[ii]
            rec["id_hash"] = id_hash(id_transform(v) if id_transform else v)
        if gi is not None:
            rec["group"] = r[gi]
        out.append(rec)
    table = pd.DataFrame(out)
    rec = {"kind": "delimited_manifest", "url": url, "sha256": meta["sha256"], "bytes": meta["bytes"],
           "duration_field": duration_field, "scale": scale, "rows": int(len(table)),
           "seconds": float(table["seconds"].sum()), "measured_at": utc_now()}
    return rec, table


def m_cv_release_stats(f: Fetcher, url: str, locale: str) -> tuple[dict, pd.DataFrame]:
    """Common Voice per-locale release statistics (cv-dataset repository): total and validated duration."""
    b, meta = f.get_bytes(url)
    d = json.loads(b)
    loc = d["locales"][locale]
    total_s = loc["duration"] / 1000.0  # milliseconds in the release statistics
    valid_s = float(loc["validDurationSecs"])
    rec = {"kind": "cv_release_stats", "url": url, "sha256": meta["sha256"], "locale": locale,
           "clips": loc.get("clips"), "users": loc.get("users"), "duration_ms": loc["duration"],
           "validDurationSecs": loc["validDurationSecs"], "totalHrs": loc.get("totalHrs"),
           "validHrs": loc.get("validHrs"), "seconds": total_s, "valid_seconds": valid_s,
           "variant": loc.get("splits", {}).get("variant"), "accent": loc.get("splits", {}).get("accent"),
           "measured_at": utc_now()}
    table = pd.DataFrame([{"hour_type": "released_audio", "seconds": total_s},
                          {"hour_type": "validated", "seconds": valid_s}])
    return rec, table


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def m_hf_parquet_ids(f: Fetcher, repo: str, patterns: list[str], id_col: str, id_regex: str,
                     id_time_scale: float, group_col: str | None = None, revision: str | None = None,
                     progress=None) -> tuple[dict, pd.DataFrame]:
    """Segment durations from segment IDs of the form <video>_<start>-<end> (ADI17 layout)."""
    import re
    rx = re.compile(id_regex)
    api = hf_api(f, repo, revision)
    sha = api["sha"]
    files = sorted({p for pat in patterns for p in hf_list(api, pat)})
    frames, per_file = [], []
    for i, path in enumerate(files):
        cols = [id_col] + ([group_col] if group_col else [])
        tb, st = read_columns(f, resolve_url(repo, sha, path), cols)
        df = tb.to_pandas()
        m = df[id_col].str.extract(rx)
        sec = (m["end"].astype("float64") - m["start"].astype("float64")) * id_time_scale
        out = pd.DataFrame({"file": path, "id_hash": m["vid"].map(id_hash), "seconds": sec})
        if group_col:
            out["group"] = df[group_col].astype("string")
        frames.append(out)
        per_file.append({"path": path, "rows": st["rows"], "row_groups": st["row_groups"],
                         "bytes_fetched": st["bytes_fetched"], "file_bytes": st["file_bytes"],
                         "seconds": float(sec.sum()), "unparsed_ids": int(m["vid"].isna().sum())})
        if progress:
            progress(i + 1, len(files), path)
    table = pd.concat(frames, ignore_index=True)
    rec = {"kind": "hf_parquet_ids", "repo": repo, "revision": sha, "patterns": patterns, "id_column": id_col,
           "id_regex": id_regex, "id_time_scale": id_time_scale, "files": per_file, "n_files": len(files),
           "rows": int(len(table)), "seconds": float(table["seconds"].sum()),
           "bytes_fetched": int(sum(p["bytes_fetched"] for p in per_file)),
           "bytes_in_files": int(sum(p["file_bytes"] for p in per_file)), "measured_at": utc_now(),
           "api": hf_api_summary(api)}
    return rec, table


def run_measurement(f: Fetcher, spec: dict, progress=None) -> tuple[dict, pd.DataFrame]:
    k = spec["kind"]
    if k == "cv_release_stats":
        return m_cv_release_stats(f, spec["url"], spec["locale"])
    if k == "hf_parquet_columns":
        rec, table = m_hf_parquet_columns(f, spec["repo"], spec["pattern"], spec["duration_col"], spec.get("scale", 1.0),
                                          spec.get("id_col"), spec.get("group_col"), spec.get("extra_cols"),
                                          spec.get("revision"), progress)
        return add_summaries(rec, table, spec), table
    if k == "hf_duration_txt":
        return m_hf_duration_txt(f, spec["repo"], spec["pattern"], spec.get("revision"), progress)
    if k == "hf_viewer_stats":
        return m_hf_viewer_stats(f, spec["repo"], spec["column"], [tuple(s) for s in spec["splits"]],
                                 spec.get("scale", 1.0))
    if k == "hf_parquet_ids":
        return m_hf_parquet_ids(f, spec["repo"], spec["patterns"], spec["id_col"], spec["id_regex"],
                                spec["id_time_scale"], spec.get("group_col"), spec.get("revision"), progress)
    if k == "delimited":
        n = spec.get("id_prefix_len")
        tf = (lambda v, n=n: v[:n]) if n else None
        recs, tables = [], []
        for u in spec["urls"]:
            r, t = m_delimited(f, u, spec["duration_field"], spec.get("scale", 1.0), spec.get("delimiter", ","),
                               spec.get("header", True), spec.get("id_field"), tf, spec.get("group_field"))
            t.insert(0, "file", u.rsplit("/", 1)[-1])
            recs.append(r)
            tables.append(t)
        table = pd.concat(tables, ignore_index=True)
        return ({"kind": "delimited", "parts": recs, "rows": int(len(table)),
                 "seconds": float(table["seconds"].sum()), "measured_at": utc_now()}, table)
    raise ValueError(f"unknown measurement kind {k}")
