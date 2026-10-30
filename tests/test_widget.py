import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "embed", "speech-hours.js")


def test_size_and_no_storage():
    src = open(JS, encoding="utf-8").read()
    assert len(src.encode("utf-8")) < 20 * 1024
    for bad in ["document.cookie", "localStorage", "sessionStorage", "indexedDB", "navigator.sendBeacon",
                "XMLHttpRequest", "import(", "createElement(\"script\")", "eval("]:
        assert bad not in src, bad
    # exactly one network call: fetch(src, ...) with credentials omitted
    assert len(re.findall(r"\bfetch\(", src)) == 1
    assert 'credentials: "omit"' in src
    assert "https://bayanatlabs.com/open/arabic-speech-hours" in src


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_arabic_hour_agreement():
    code = (
        "global.window={};global.document={readyState:'complete',querySelectorAll:()=>[],documentElement:{}};"
        f"require({JS!r});const f=window.BayanatSpeechHours.arHours;"
        "console.log([1,2,3,10,11,99,100,101,103,111,1000,33461].map(f).join(','))"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out.split(",") == ["ساعة", "ساعتان", "ساعات", "ساعات", "ساعةً", "ساعةً", "ساعة", "ساعة", "ساعات",
                              "ساعةً", "ساعة", "ساعةً"]
