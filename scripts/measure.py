#!/usr/bin/env python3
"""Run the hour measurements in config/measurements.yaml.

  python scripts/measure.py [--only ID ...] [--out evidence/measurements]
  python scripts/measure.py --summaries-only [--only ID ...]   # no requests: recompute summaries from saved tables

Writes <out>/<id>.json (what was read and the total) and <out>/<id>.parquet (per-row seconds, group
labels and hashed identifiers) for each measurement, and appends one provenance row per request to
PROVENANCE.jsonl. Stops at the first refusal (HTTP 401, 403 or 429).
"""
import argparse
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arabic_speech_hours.http import Fetcher, Refused  # noqa: E402
from arabic_speech_hours.measure import add_summaries, run_measurement  # noqa: E402


def summaries_only(cfg, out, only):
    """Recompute the summaries (for example YODAS v3 hours by uploader locale) from the saved tables."""
    import pandas as pd
    for mid, spec in cfg["measurements"].items():
        if (only and mid not in only) or not spec.get("locale_col"):
            continue
        jp = os.path.join(out, f"{mid}.json")
        rec = json.load(open(jp, encoding="utf-8"))
        table = pd.read_parquet(os.path.join(out, f"{mid}.parquet"))
        rec["spec"] = spec
        add_summaries(rec, table, spec)
        json.dump(rec, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  {mid}: {rec['locale_column']} hours {rec['locale_hours']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "measurements.yaml"))
    ap.add_argument("--out", default=os.path.join(ROOT, "evidence", "measurements"))
    ap.add_argument("--provenance", default=os.path.join(ROOT, "PROVENANCE.jsonl"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--summaries-only", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    if a.summaries_only:
        return summaries_only(cfg, a.out, a.only)
    os.makedirs(a.out, exist_ok=True)
    f = Fetcher(provenance_path=a.provenance)
    for mid, spec in cfg["measurements"].items():
        if a.only and mid not in a.only:
            continue
        jp = os.path.join(a.out, f"{mid}.json")
        if a.skip_existing and os.path.exists(jp):
            continue

        def prog(i, n, path, mid=mid):
            if i == n or i % 10 == 0:
                print(f"  {mid}: {i}/{n} {path}", flush=True)
        print(f"measuring {mid} ({spec['kind']})", flush=True)
        try:
            rec, table = run_measurement(f, spec, prog)
        except Refused as e:
            print(f"STOP: {e}", flush=True)
            sys.exit(3)
        except Exception as e:  # record and continue with the next measurement
            print(f"  FAILED {mid}: {type(e).__name__}: {e}", flush=True)
            json.dump({"id": mid, "spec": spec, "error": f"{type(e).__name__}: {e}"},
                      open(os.path.join(a.out, f"{mid}.error.json"), "w"), indent=1)
            continue
        rec = {"id": mid, "spec": spec, **rec}
        table.to_parquet(os.path.join(a.out, f"{mid}.parquet"), index=False)
        json.dump(rec, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  {mid}: rows={rec.get("rows", rec.get("clips"))} hours={rec['seconds'] / 3600:.3f} requests_so_far={f.n_requests}", flush=True)


if __name__ == "__main__":
    main()
