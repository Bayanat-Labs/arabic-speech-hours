#!/usr/bin/env python3
"""Discovery: list candidate Arabic speech datasets on the Hugging Face Hub, Zenodo and OpenSLR.

  python scripts/discover.py            -> evidence/candidates.json

Candidates are listed for review only; nothing is added to the count automatically.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arabic_speech_hours import discover  # noqa: E402
from arabic_speech_hours.http import Fetcher  # noqa: E402

if __name__ == "__main__":
    f = Fetcher(provenance_path=os.path.join(ROOT, "PROVENANCE.jsonl"))
    items, meta = discover.run(f)
    with open(os.path.join(ROOT, "evidence", "candidates.json"), "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "items": items}, fh, ensure_ascii=False, indent=1)
    print(f"{len(items)} candidates ({f.n_requests} requests)")
