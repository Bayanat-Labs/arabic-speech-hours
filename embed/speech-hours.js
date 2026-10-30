/*! Open Arabic Speech Hours Counter widget, Bayanat Labs. Code: Apache-2.0. Data: CC BY 4.0.
 * Usage:
 *   <arabic-speech-hours src="latest.json" lang="en"></arabic-speech-hours>
 *   <script src="speech-hours.js" defer></script>
 * Attributes: src (URL of latest.json, required), lang ("en" or "ar"; default: the page language),
 * dir ("ltr" or "rtl"; default: from lang, else inherited from the container), compact (no breakdown).
 * The widget makes one request (src), sends no cookies or credentials and stores nothing.
 */
(function () {
  "use strict";
  var PAGE = "https://bayanatlabs.com/open/arabic-speech-hours";
  var CLASSES = ["open-commercial", "open-noncommercial", "no-derivatives", "research-or-request", "manifests-only", "disputed", "unknown"];
  var T = {
    en: {
      title: "Open Arabic speech, commercial use allowed",
      unit: function (n) { return n === 1 ? "hour" : "hours"; },
      headNote: "released audio, overlap-adjusted",
      asOf: "as of",
      yt: "derived from YouTube videos (publisher statements)",
      dial: "with a non-MSA dialect label from the source",
      others: "Other licence classes (not added to the number above)",
      cls: {
        "open-commercial": "Open, commercial use allowed", "open-noncommercial": "Open, non-commercial only",
        "no-derivatives": "No derivatives", "research-or-request": "Research use or on request",
        "manifests-only": "Manifests only (no audio)", "disputed": "Disputed", "unknown": "No licence found"
      },
      corpora: function (n) { return n + (n === 1 ? " corpus" : " corpora"); },
      source: "Open Arabic Speech Hours Counter, Bayanat Labs (CC BY 4.0)",
      error: "The figures could not be loaded."
    },
    ar: {
      title: "الكلام العربي المفتوح المسموح باستخدامه تجاريًا",
      unit: arHours,
      headNote: "صوت منشور، بعد طرح التداخل",
      asOf: "حتى",
      yt: "مصدرها مقاطع يوتيوب (بحسب الناشرين)",
      dial: "موسومة من المصدر بلهجة غير الفصحى",
      others: "فئات الترخيص الأخرى (لا تُضاف إلى الرقم أعلاه)",
      cls: {
        "open-commercial": "مفتوح ويسمح بالاستخدام التجاري", "open-noncommercial": "مفتوح لغير الأغراض التجارية فقط",
        "no-derivatives": "لا يسمح بالأعمال المشتقة", "research-or-request": "للبحث أو عند الطلب",
        "manifests-only": "قوائم فقط (بلا صوت)", "disputed": "متنازع عليه", "unknown": "لا يوجد ترخيص"
      },
      corpora: function (n) { var r = n % 100; return n === 1 ? "مجموعة واحدة" : n === 2 ? "مجموعتان" : fmt(n, "ar") + " " + ((r >= 3 && r <= 10) ? "مجموعات" : (r >= 11 && r <= 99) ? "مجموعةً" : "مجموعة"); },
      source: "عدّاد ساعات الكلام العربي المفتوح، بيانات لابز (CC BY 4.0)",
      error: "تعذّر تحميل الأرقام."
    }
  };
  var MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  var MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  // Arabic number-noun agreement for "hour": 1 ساعة, 2 ساعتان, 3-10 ساعات, 11-99 ساعةً, 100+ ساعة (by the last two digits).
  function arHours(n) {
    n = Math.round(Math.abs(n));
    var r = n % 100;
    if (n === 1) return "ساعة";
    if (n === 2) return "ساعتان";
    if (r >= 3 && r <= 10) return "ساعات";
    if (r >= 11 && r <= 99) return "ساعةً";
    return "ساعة";
  }
  function fmt(n, lang) {
    try { return new Intl.NumberFormat(lang === "ar" ? "ar-EG" : "en-GB", { maximumFractionDigits: 0 }).format(n); }
    catch (e) { return String(Math.round(n)); }
  }
  function pct(x, lang) {
    try { return new Intl.NumberFormat(lang === "ar" ? "ar-EG" : "en-GB", { style: "percent", maximumFractionDigits: 1 }).format(x); }
    catch (e) { return (Math.round(x * 1000) / 10) + "%"; }
  }
  function dateLabel(iso, lang) {
    var p = String(iso || "").split("-");
    if (p.length !== 3) return iso || "";
    var d = parseInt(p[2], 10), m = parseInt(p[1], 10) - 1, y = p[0];
    return lang === "ar" ? fmt(d, "ar") + " " + MONTHS_AR[m] + " " + fmt(parseInt(y, 10), "ar").replace(/٬|,/g, "") : d + " " + MONTHS_EN[m] + " " + y;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  var CSS = [
    ":host{display:block;max-width:34rem;font:400 15px/1.5 system-ui,-apple-system,'Segoe UI','Noto Sans Arabic','Geeza Pro',Tahoma,sans-serif;color:var(--ash-ink,#0b0b0d)}",
    ".box{border:1px solid var(--ash-line,#e4e3ec);border-radius:12px;padding:14px 16px;background:var(--ash-bg,#fff)}",
    ".t{font-weight:600;margin:0 0 4px;font-size:.95rem}",
    ".n{font-size:2.1rem;font-weight:700;line-height:1.15;margin:0;unicode-bidi:isolate}",
    ".n small{font-size:1rem;font-weight:600;margin-inline-start:.35rem}",
    ".m{color:var(--ash-muted,#5f5f6b);font-size:.85rem;margin:2px 0 8px}",
    ".s{margin:0 0 10px;padding:0;list-style:none;font-size:.88rem}",
    ".s li{margin:2px 0}",
    ".o{font-size:.84rem;color:var(--ash-muted,#5f5f6b);margin:8px 0 4px}",
    "table{border-collapse:collapse;width:100%;font-size:.85rem}",
    "td{padding:2px 0;vertical-align:top}",
    "td.h{text-align:end;white-space:nowrap;unicode-bidi:isolate;padding-inline-start:12px}",
    "a{color:var(--ash-accent,#0f766e)}",
    ".f{font-size:.8rem;margin:10px 0 0;color:var(--ash-muted,#5f5f6b)}",
    "@media (prefers-color-scheme:dark){:host{color:var(--ash-ink,#ececf1)}.box{background:var(--ash-bg,#1a1a21);border-color:var(--ash-line,#2c2c37)}.m,.o,.f{color:var(--ash-muted,#a3a3b2)}a{color:var(--ash-accent,#5eead4)}}"
  ].join("");

  function render(root, data, lang, dir, compact) {
    var t = T[lang] || T.en;
    var box = el("div", "box");
    box.setAttribute("dir", dir);
    box.setAttribute("lang", lang);
    var h = data.headline || {};
    var n = Math.round(h.hours != null ? h.hours : data.headline_hours);
    box.appendChild(el("p", "t", t.title));
    var num = el("p", "n", fmt(n, lang));
    num.appendChild(el("small", null, t.unit(n)));
    box.appendChild(num);
    var meta = t.headNote + " · " + t.corpora(h.n_corpora || 0) + " · " + t.asOf + " " + dateLabel(data.as_of, lang);
    box.appendChild(el("p", "m", meta));
    var s = el("ul", "s");
    if (h.youtube_derived_share != null) s.appendChild(el("li", null, pct(h.youtube_derived_share, lang) + " " + t.yt));
    if (h.non_msa_dialect_labelled_hours != null) {
      var dh = Math.round(h.non_msa_dialect_labelled_hours);
      s.appendChild(el("li", null, fmt(dh, lang) + " " + t.unit(dh) + " " + t.dial));
    }
    box.appendChild(s);
    if (!compact && data.by_class) {
      box.appendChild(el("p", "o", t.others));
      var tb = el("table");
      CLASSES.forEach(function (c) {
        if (c === "open-commercial" || data.by_class[c] == null) return;
        var v = Math.round(data.by_class[c]);
        if (!v) return;
        var tr = el("tr");
        tr.appendChild(el("td", null, t.cls[c] || c));
        tr.appendChild(el("td", "h", fmt(v, lang) + " " + t.unit(v)));
        tb.appendChild(tr);
      });
      box.appendChild(tb);
    }
    var f = el("p", "f");
    var a = el("a", null, t.source);
    a.href = PAGE + (lang === "ar" ? "?lang=ar" : "");
    a.target = "_blank";
    a.rel = "noopener";
    f.appendChild(a);
    box.appendChild(f);
    root.appendChild(box);
  }

  function resolveLang(host) {
    var l = (host.getAttribute("lang") || (host.closest && host.closest("[lang]") && host.closest("[lang]").getAttribute("lang")) || document.documentElement.lang || "en").toLowerCase();
    return l.indexOf("ar") === 0 ? "ar" : "en";
  }
  function resolveDir(host, lang) {
    var d = host.getAttribute("dir");
    if (d === "rtl" || d === "ltr") return d;
    if (host.hasAttribute("lang")) return lang === "ar" ? "rtl" : "ltr";
    try { return getComputedStyle(host).direction === "rtl" ? "rtl" : "ltr"; } catch (e) { return lang === "ar" ? "rtl" : "ltr"; }
  }

  function mount(host) {
    if (host.__ashMounted) return;
    host.__ashMounted = true;
    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
    var sheet = null;
    try { sheet = new CSSStyleSheet(); sheet.replaceSync(CSS); } catch (e) { sheet = null; }
    if (sheet && root !== host && "adoptedStyleSheets" in root) {
      root.adoptedStyleSheets = [sheet];
    } else {
      var st = document.createElement("style");
      st.textContent = CSS;
      root.appendChild(st);
    }
    var lang = resolveLang(host), dir = resolveDir(host, lang), compact = host.hasAttribute("compact");
    var src = host.getAttribute("src") || host.getAttribute("data-src");
    var fail = function () {
      var t = T[lang] || T.en;
      var box = el("div", "box");
      box.setAttribute("dir", dir);
      box.appendChild(el("p", "m", t.error));
      var a = el("a", null, t.source);
      a.href = PAGE;
      a.target = "_blank";
      a.rel = "noopener";
      box.appendChild(a);
      root.appendChild(box);
    };
    if (!src || !window.fetch) { fail(); return; }
    fetch(src, { credentials: "omit", referrerPolicy: "no-referrer", cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { render(root, d, lang, dir, compact); })
      .catch(fail);
  }

  if (window.customElements && !window.customElements.get("arabic-speech-hours")) {
    window.customElements.define("arabic-speech-hours", class extends HTMLElement {
      connectedCallback() { mount(this); }
    });
  }
  function scan() {
    var nodes = document.querySelectorAll(".bl-speech-hours[data-src]");
    for (var i = 0; i < nodes.length; i++) mount(nodes[i]);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan); else scan();
  window.BayanatSpeechHours = { arHours: arHours, mount: mount };
})();
