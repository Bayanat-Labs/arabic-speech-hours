"""Find candidate Arabic speech corpora for review. Candidates are never added to the count
automatically: each one is listed with a reason until it has been reviewed and given an entry in
config/corpora.yaml.
"""
from __future__ import annotations

import html
import re
import urllib.parse

from .http import Fetcher, utc_now

HF_QUERIES = [
    {"filter": ["language:ar", "modality:audio"]},
    {"filter": ["language:ar", "task_categories:automatic-speech-recognition"]},
    {"filter": ["language:ar", "task_categories:text-to-speech"]},
]
ZENODO_QUERY = ("https://zenodo.org/api/records?q=arabic%20AND%20(speech%20OR%20audio%20OR%20ASR)"
                "&type=dataset&sort=mostrecent&size=25")
OPENSLR_INDEX = "https://openslr.org/resources.php"


def hf_candidates(f: Fetcher) -> list[dict]:
    seen: dict[str, dict] = {}
    for q in HF_QUERIES:
        params = [("filter", x) for x in q["filter"]] + [("limit", "1000"), ("sort", "downloads"), ("direction", "-1"),
                                                         ("full", "false")]
        url = "https://huggingface.co/api/datasets?" + urllib.parse.urlencode(params)
        for d in f.get_json(url):
            rid = d["id"]
            tags = d.get("tags", [])
            rec = seen.setdefault(rid, {
                "source": "huggingface", "candidate_id": rid, "url": f"https://huggingface.co/datasets/{rid}",
                "licence_tag": ",".join(t.split(":", 1)[1] for t in tags if t.startswith("license:")) or None,
                "n_languages": sum(1 for t in tags if t.startswith("language:")),
                "gated": bool(d.get("gated")), "downloads_30d": d.get("downloads"),
                "last_modified": d.get("lastModified"), "found_by": []})
            rec["found_by"].append("+".join(q["filter"]))
    for r in seen.values():
        r["found_by"] = ";".join(r["found_by"])
    return list(seen.values())


def zenodo_candidates(f: Fetcher) -> list[dict]:
    d = f.get_json(ZENODO_QUERY)
    out = []
    for h in d.get("hits", {}).get("hits", []):
        m = h.get("metadata", {})
        title = m.get("title") or ""
        if not (re.search(r"(?i)arab|\bara\d", title) and re.search(r"(?i)speech|spoken|audio|voice|\btts\b|recit", title)):
            continue  # the full-text query also matches unrelated records; keep titles naming Arabic speech or audio
        lic = (m.get("license") or {}).get("id")
        out.append({"source": "zenodo", "candidate_id": f"zenodo:{h.get('id')}", "url": h.get("links", {}).get("self_html")
                    or f"https://zenodo.org/records/{h.get('id')}", "title": m.get("title"), "licence_tag": lic,
                    "n_languages": None, "gated": False, "downloads_30d": None,
                    "last_modified": h.get("updated"), "found_by": "zenodo query"})
    return out


def openslr_candidates(f: Fetcher) -> list[dict]:
    b, _ = f.get_bytes(OPENSLR_INDEX)
    text = b.decode("utf-8", "replace")
    out = []
    cell = lambda x: html.unescape(re.sub("<[^>]+>", "", x)).strip()  # noqa: E731
    for m in re.finditer(r'<a href="/?(\d+)/?">\s*(SLR\d+)\s*</a>\s*</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>'
                         r'\s*<td[^>]*>(.*?)</td>', text, flags=re.S | re.I):
        num, slr, name, category, summary = m.group(1), m.group(2), cell(m.group(3)), cell(m.group(4)), cell(m.group(5))
        if category.lower().startswith("speech") and re.search(r"(?i)\barab", name + " " + summary):
            out.append({"source": "openslr", "candidate_id": slr, "url": f"https://www.openslr.org/{num}/",
                        "title": f"{name}: {summary}"[:200], "licence_tag": None, "n_languages": None, "gated": False,
                        "downloads_30d": None, "last_modified": None, "found_by": "openslr index"})
    return out


def run(f: Fetcher) -> tuple[list[dict], dict]:
    items = hf_candidates(f) + zenodo_candidates(f) + openslr_candidates(f)
    meta = {"discovered_at": utc_now(), "hf_queries": HF_QUERIES, "zenodo_query": ZENODO_QUERY,
            "openslr_index": OPENSLR_INDEX, "n": len(items)}
    return items, meta
