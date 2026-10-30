#!/usr/bin/env python3
"""Build data/, feed/latest.json and feed/badge.svg from config/ and evidence/.

  python scripts/build.py --as-of 2026-10-30
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arabic_speech_hours.build import build  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    a = ap.parse_args()
    out = build(ROOT, a.as_of)
    print(json.dumps(out["latest"]["headline"], indent=1))
    print(json.dumps(out["latest"]["by_class"], indent=1))
