#!/usr/bin/env python3
"""Fetch the evidence pages in config/snapshots.yaml for a refresh run.

  python scripts/snapshot.py --out snapshots/ [--index evidence/index.refresh.jsonl]

Saves <name>.html (or .bin) as served and <name>.txt (tags stripped, whitespace kept) for each page,
with one index record per page (URL, UTC time, status, SHA-256 of the body and of the text). Pages
that need a browser to render their text (some publisher pages build the page with JavaScript) give
little text here; the second check then reports their quotes as not found, which blocks those rows
until the page is checked by other means. Stops at the first refusal (HTTP 401, 403 or 429).
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arabic_speech_hours.http import Fetcher, Refused, utc_now  # noqa: E402


def to_text(body: bytes) -> str:
    s = body.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d|td|th)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--index", default=None)
    a = ap.parse_args()
    snaps = yaml.safe_load(open(os.path.join(ROOT, "config", "snapshots.yaml"), encoding="utf-8"))["snapshots"]
    os.makedirs(a.out, exist_ok=True)
    f = Fetcher(provenance_path=os.path.join(ROOT, "PROVENANCE.jsonl"))
    recs = []
    for name, url in snaps.items():
        base = os.path.join(a.out, name.replace("/", "__"))
        try:
            r = f.request(url)
        except Refused as e:
            print(f"STOP: {e}")
            sys.exit(3)
        body = r.content
        ctype = r.headers.get("content-type", "")
        is_html = "html" in ctype or body.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
        with open(base + (".html" if is_html else ".bin"), "wb") as fh:
            fh.write(body)
        text = to_text(body) if is_html else ""
        with open(base + ".txt", "w", encoding="utf-8") as fh:
            fh.write(text)
        recs.append({"snapshot": name, "url": url, "retrieved_at": utc_now(), "http_status": r.status_code,
                     "content_type": ctype, "sha256": hashlib.sha256(body).hexdigest(),
                     "sha256_text": hashlib.sha256(text.encode("utf-8")).hexdigest(), "text_chars": len(text)})
        print(f"{r.status_code} {name}")
    idx = a.index or os.path.join(a.out, "index.jsonl")
    with open(idx, "w", encoding="utf-8") as fh:
        for rec in recs:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
