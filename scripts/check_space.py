#!/usr/bin/env python3
"""Render the static page locally with Playwright at 1280 and 375 px, in English and Arabic.

Checks: no console errors, no request leaves the local server, no horizontal overflow, the headline
and charts render, the table filter works, the embedded widget renders in both directions (and in
RTL and LTR containers on a test page), the language toggle switches direction.

  python scripts/check_space.py SPACE_DIR SHOTS_DIR
"""
import functools
import http.server
import json
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

WIDGET_TEST = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>widget test</title></head><body>
<div dir="rtl" lang="ar" id="rtl"><arabic-speech-hours src="latest.json"></arabic-speech-hours></div>
<div dir="ltr" id="ltr"><arabic-speech-hours src="latest.json" lang="en"></arabic-speech-hours></div>
<div dir="rtl" id="rtl-en"><arabic-speech-hours src="latest.json" lang="en" dir="ltr" compact></arabic-speech-hours></div>
<script src="speech-hours.js"></script></body></html>"""


def serve(root):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    handler.log_message = lambda *a, **k: None
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def widget_state(page, sel):
    return page.evaluate("""(sel) => { const h = document.querySelector(sel); const r = h && h.shadowRoot;
        const b = r && r.querySelector('.box'); return b ? {dir: b.getAttribute('dir'), lang: b.getAttribute('lang'),
        num: (r.querySelector('.n') || {}).textContent || '', link: (r.querySelector('a') || {}).href || '',
        text: b.textContent.slice(0, 200)} : null; }""", sel)


def main(root, shots):
    os.makedirs(shots, exist_ok=True)
    test_page = os.path.join(root, "_widget_test.html")
    open(test_page, "w", encoding="utf-8").write(WIDGET_TEST)
    httpd = serve(root)
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    report, ok = {"runs": []}, True
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((1280, 900), (375, 812)):
                for lang in ("en", "ar"):
                    ctx = browser.new_context(viewport={"width": width, "height": height})
                    page = ctx.new_page()
                    errors, foreign, cookies_set = [], [], []
                    page.on("console", lambda m, errors=errors: errors.append(m.text) if m.type in ("error", "warning") else None)
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    page.on("request", lambda r, foreign=foreign: foreign.append(r.url)
                            if not (r.url.startswith(base) or r.url.startswith("data:")) else None)
                    page.goto(base + ("index.html?lang=ar" if lang == "ar" else "index.html"), wait_until="networkidle")
                    page.wait_for_timeout(300)
                    run = {"width": width, "lang": lang,
                           "dir": page.evaluate("document.documentElement.dir"),
                           "html_lang": page.evaluate("document.documentElement.lang"),
                           "hero": page.inner_text("#hero-num"),
                           "class_bars": page.locator("#chart-class .bar-row").count(),
                           "corpus_bars": page.locator("#chart-corpus .bar-row").count(),
                           "rows_all": page.locator("#tbl tbody tr").count(),
                           "overflow_px": page.evaluate("document.documentElement.scrollWidth - window.innerWidth")}
                    page.screenshot(path=os.path.join(shots, f"space-{width}-{lang}.png"), full_page=False)
                    page.screenshot(path=os.path.join(shots, f"space-{width}-{lang}-full.png"), full_page=True)
                    page.select_option("#f-class", "open-commercial")
                    run["rows_open_commercial"] = page.locator("#tbl tbody tr").count()
                    page.select_option("#f-class", "")
                    run["widget"] = widget_state(page, "#demo-widget")
                    page.hover("#chart-class .bar-row >> nth=0")
                    run["tooltip"] = page.inner_text("#tip") if page.is_visible("#tip") else ""
                    page.click("#lang-toggle")
                    page.wait_for_timeout(300)
                    run["dir_after_toggle"] = page.evaluate("document.documentElement.dir")
                    run["widget_after_toggle"] = widget_state(page, "#demo-widget")
                    run["overflow_after_toggle_px"] = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    cookies_set = ctx.cookies()
                    run.update({"console": errors, "foreign_requests": foreign, "cookies": len(cookies_set)})
                    good = (not errors and not foreign and run["overflow_px"] <= 0 and run["overflow_after_toggle_px"] <= 0
                            and run["class_bars"] > 0 and run["corpus_bars"] > 0 and run["rows_all"] > 0
                            and 0 < run["rows_open_commercial"] < run["rows_all"] and run["widget"]
                            and run["dir"] == ("rtl" if lang == "ar" else "ltr")
                            and run["dir_after_toggle"] == ("ltr" if lang == "ar" else "rtl")
                            and run["widget"]["dir"] == run["dir"] and not cookies_set and run["tooltip"])
                    run["ok"] = bool(good)
                    ok = ok and bool(good)
                    report["runs"].append(run)
                    ctx.close()
            # the widget in RTL and LTR containers on a third-party-style page
            ctx = browser.new_context(viewport={"width": 375, "height": 812})
            page = ctx.new_page()
            errors, foreign = [], []
            page.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
            page.on("request", lambda r: foreign.append(r.url) if not r.url.startswith(base) else None)
            page.goto(base + "_widget_test.html", wait_until="networkidle")
            page.wait_for_timeout(300)
            w = {k: widget_state(page, f"#{k} arabic-speech-hours") for k in ("rtl", "ltr", "rtl-en")}
            page.screenshot(path=os.path.join(shots, "widget-containers-375.png"), full_page=True)
            wok = (w["rtl"] and w["rtl"]["dir"] == "rtl" and w["rtl"]["lang"] == "ar" and w["ltr"]["dir"] == "ltr"
                   and w["rtl-en"]["dir"] == "ltr" and all("bayanatlabs.com/open/arabic-speech-hours" in x["link"] for x in w.values())
                   and not errors and not foreign and not ctx.cookies()
                   and page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0)
            report["widget_containers"] = {"states": w, "console": errors, "foreign_requests": foreign, "ok": bool(wok)}
            ok = ok and bool(wok)
            ctx.close()
            browser.close()
    finally:
        httpd.shutdown()
        os.remove(test_page)
    report["ok"] = ok
    with open(os.path.join(shots, "space_check.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({"ok": ok, "runs": [{k: r[k] for k in ("width", "lang", "ok", "console", "foreign_requests", "overflow_px")} for r in report["runs"]],
                      "widget_containers_ok": report["widget_containers"]["ok"]}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
