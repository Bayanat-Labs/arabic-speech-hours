"""Command line: arabic-speech-hours {measure,discover,build,check} [--root DIR]."""
from __future__ import annotations

import argparse
import os
import runpy
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="arabic-speech-hours",
                                 description="Count released Arabic speech hours by licence class from public metadata.")
    ap.add_argument("command", choices=["measure", "discover", "build", "check", "snapshot"])
    ap.add_argument("--root", default=os.getcwd(), help="repository checkout with config/ and evidence/ (default: .)")
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    script = {"measure": "measure.py", "discover": "discover.py", "build": "build.py", "check": "second_check.py",
              "snapshot": "snapshot.py"}[a.command]
    path = os.path.join(a.root, "scripts", script)
    if not os.path.exists(path):
        print(f"arabic-speech-hours: {path} not found; run from a checkout of the repository or pass --root",
              file=sys.stderr)
        return 2
    sys.argv = [path] + a.rest
    try:
        runpy.run_path(path, run_name="__main__")
    except SystemExit as e:
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
