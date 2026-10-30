/* Open Arabic Speech Hours Counter, static page. Bayanat Labs. Code: Apache-2.0; data and text: CC BY 4.0.
   Reads window.ASH_DATA (data.js). The only request it makes is the widget's read of this Space's latest.json. */
(function () {
  "use strict";
  var D = window.ASH_DATA;
  var CLASSES = ["open-commercial", "open-noncommercial", "no-derivatives", "research-or-request", "manifests-only", "disputed", "unknown"];
  var HOUR_TYPES = ["released_audio", "transcribed", "validated", "clean", "manifest"];
  var MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  var MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function arHours(n) {
    n = Math.round(Math.abs(n)); var r = n % 100;
    if (n === 1) return "ساعة"; if (n === 2) return "ساعتان";
    if (r >= 3 && r <= 10) return "ساعات"; if (r >= 11 && r <= 99) return "ساعةً"; return "ساعة";
  }
  function arCount(n, one, two, few, many) {
    var r = n % 100;
    if (n === 1) return one; if (n === 2) return two;
    return num(n, 0) + " " + ((r >= 3 && r <= 10) ? few : many);
  }

  var I = {
    en: {
      skip: "Skip to the figures", brand: "Bayanat Labs", title: "Open Arabic Speech Hours Counter",
      heroLabel: "Open, commercially usable Arabic speech: released audio, overlap-adjusted",
      unit: function (n) { return n === 1 ? "hour" : "hours"; },
      clsH: "Released audio hours by licence class", clsSub: "Each class is its own figure. The classes are never added together.",
      ocH: "Open, commercial use allowed: hours by corpus", ocSub: "Released audio, overlap-adjusted.",
      tblH: "All rows", fClass: "Licence class", fType: "Hour type", all: "All",
      cCorpus: "Corpus", cClass: "Licence class", cLic: "Licence as stated", cType: "Hour type", cDial: "Dialect (as stated)",
      cGenre: "Genre", cHours: "Hours", cAdj: "Overlap-adjusted", cMethod: "Method",
      ovH: "Overlap between corpora", howH: "How the figures are computed", embH: "Embed the counter",
      embSub: "The widget loads one file (latest.json), sends no cookies and stores nothing. Below: the widget on this page, reading this Space's copy of latest.json.",
      lede: function (d) {
        return "As of " + dateLabel(d.as_of, "en") + ", " + num(d.headline.hours_rounded, 0) + " hours of released Arabic speech audio carry an open licence that allows commercial use, across " +
          d.headline.n_corpora + " corpora, after removing overlap that the publishers state. Every other licence class is shown beside that figure and never added to it. The counter reads published metadata (duration columns, manifests, release statistics) and quoted publisher statements; it does not download audio.";
      },
      meta: function (d) { return "As of " + dateLabel(d.as_of, "en") + " · " + d.headline.n_corpora + " corpora · gross before overlap adjustment: " + num(d.headline.hours_gross, 0) + " hours"; },
      ytL: "of these hours are derived from YouTube videos (as their publishers state)",
      dialL: function (d) { return "hours carry a dialect label other than MSA from the source (" + pct(d.headline.non_msa_dialect_labelled_share) + ")"; },
      locL: function (x) { return "hours of the YODAS v3 Arabic subset (" + num(x.total, 0) + " h, filed by caption-track language) come from uploads whose uploader locale is also Arabic; another locale: " + num(x.other, 0) + " h; not given: " + num(x.not_given, 0) + " h"; },
      cls: { "open-commercial": "Open, commercial use allowed", "open-noncommercial": "Open, non-commercial only", "no-derivatives": "No derivatives",
             "research-or-request": "Research use or on request", "manifests-only": "Manifests only (no audio)", "disputed": "Disputed", "unknown": "No licence found" },
      ht: { released_audio: "Released audio", transcribed: "Transcribed", validated: "Validated", clean: "Clean", manifest: "Manifest" },
      method: { computed_from_metadata: "computed from metadata", computed_from_release_stats: "computed from release statistics", card_or_paper_stated: "stated on the card or in a paper" },
      corpora: function (n) { return n + (n === 1 ? " corpus" : " corpora"); },
      rows: function (n, m) { return n + " of " + m + " rows"; },
      shownH: "hours", notCounted: "not in the headline",
      ovIntro: "Hours that two corpora share are removed once, from the later corpus in the priority order, and only when both are in the same licence class. Publisher statements and published video IDs are used; YODAS recording IDs are publisher IDs, so overlap with YODAS could not be measured.",
      ovMeth: { publisher_statement: "publisher statement", video_id_intersection: "shared video IDs", not_measured: "not measured" },
      ovShared: function (o) {
        if (o.method === "video_id_intersection") return o.shared_ids + " shared video IDs (" + num(o.ids_a, 0) + " and " + num(o.ids_b, 0) + " IDs in scope); " + num(o.shared_hours_b, 2) + " h of the second corpus's segments; reported only (different licence classes)";
        if (o.method === "publisher_statement") return !o.shared_hours_b ? "the publisher states that the two hold different recordings; nothing removed" : num(o.shared_hours_b, 2) + " h shared" + (o.removed_from_b_hours ? "; " + num(o.removed_from_b_hours, 2) + " h removed" : "; nothing removed (different licence classes)");
        return o.scope;
      },
      how: function (d) {
        return "<h3>What is counted</h3><ul><li>Hours of Arabic speech audio that a publisher has released, one row per corpus, partition and hour type. Hour types (released audio, transcribed, validated) are stored separately and never added together; the headline uses released audio only.</li>" +
          "<li>Each corpus has one licence class for its audio, read from the publisher's own page and saved with its SHA-256 hash and retrieval time. Copies elsewhere that declare another licence are noted, and the publisher's licence is used. Two different licences stated by the publisher would make the class “disputed”. When the publisher requires a signed agreement or a request process before sharing the audio, the class is “research use or on request”.</li>" +
          "<li>Hours are computed from published metadata where it exists (duration columns read with range requests, duration manifests, Common Voice release statistics, the Hub dataset viewer's duration statistics) or taken from a quoted publisher statement. Each row records its method.</li>" +
          "<li>Dialect is recorded only as the source states it; a country label is marked “source-stated country”. Quran recitation is a separate genre.</li>" +
          "<li>Bayanat Labs releases are counted only for released recorded speech; the Bayanat Labs channel-pairs set renders FLEURS recordings and is listed as excluded.</li></ul>" +
          notes(D.licence_notes && D.licence_notes.en, "Licence notes") +
          "<h3>Second check</h3><p>A separate script that does not import the package re-derives every row's hours and licence class from the evidence files (measurement tables and saved pages). Only rows that agree (hours within 0.1 %, identical class) enter the headline: " + d.n_rows_verified + " of " + d.n_rows + " rows agree.</p>" +
          "<h3>Candidates</h3><p>" + num(d.n_candidates_listed, 0) + " other datasets found on the Hugging Face Hub, Zenodo and OpenSLR are listed with a reason (copy of a counted corpus, synthetic speech, no released audio, gated, or not yet reviewed). They are not counted.</p>" +
          "<p>Licence classes are informational and are not legal advice.</p>";
      },
      foot: function (d) {
        return "<p>Data: <a href=\"" + d.dataset_url + "\">Bayanat-Labs/arabic-speech-hours</a> (CC BY 4.0) · Code: <a href=\"https://github.com/Bayanat-Labs/arabic-speech-hours\">GitHub</a> (Apache-2.0) · Page: <a href=\"" + d.page_url + "\">bayanatlabs.com</a></p>" +
          "<p>Cite as: " + esc(d.citation) + "</p><p>Corrections: hello@bayanatlabs.com</p><p>Font: IBM Plex Sans Arabic (SIL OFL 1.1).</p>";
      }
    },
    ar: {
      skip: "انتقل إلى الأرقام", brand: "بيانات لابز", title: "عدّاد ساعات الكلام العربي المفتوح",
      heroLabel: "الكلام العربي المفتوح المسموح باستخدامه تجاريًا: صوت منشور بعد طرح التداخل",
      unit: arHours,
      clsH: "ساعات الصوت المنشور حسب فئة الترخيص", clsSub: "لكل فئة رقمها الخاص، ولا تُجمع الفئات معًا أبدًا.",
      ocH: "مفتوح ويسمح بالاستخدام التجاري: الساعات حسب المجموعة", ocSub: "صوت منشور، بعد طرح التداخل.",
      tblH: "كل الصفوف", fClass: "فئة الترخيص", fType: "نوع الساعات", all: "الكل",
      cCorpus: "المجموعة", cClass: "فئة الترخيص", cLic: "الترخيص كما ورد", cType: "نوع الساعات", cDial: "اللهجة (كما وردت)",
      cGenre: "النوع", cHours: "الساعات", cAdj: "بعد طرح التداخل", cMethod: "الطريقة",
      ovH: "التداخل بين المجموعات", howH: "كيف تُحسب الأرقام", embH: "تضمين العدّاد",
      embSub: "تحمّل الأداة ملفًا واحدًا (latest.json) ولا ترسل ملفات تعريف الارتباط ولا تخزّن شيئًا. أدناه الأداة في هذه الصفحة تقرأ نسخة هذه المساحة من latest.json.",
      lede: function (d) {
        var n = d.headline.hours_rounded;
        return "حتى " + dateLabel(d.as_of, "ar") + "، يحمل " + num(n, 0) + " " + arHours(n) + " من الصوت العربي المنشور ترخيصًا مفتوحًا يسمح بالاستخدام التجاري، في " +
          arCount(d.headline.n_corpora, "مجموعة واحدة", "مجموعتين", "مجموعات", "مجموعة") + "، بعد طرح التداخل الذي يذكره الناشرون. تظهر كل فئات الترخيص الأخرى بجانب هذا الرقم ولا تُضاف إليه. يقرأ العدّاد البيانات الوصفية المنشورة (أعمدة المدة والقوائم وإحصاءات الإصدار) وأقوال الناشرين المقتبسة، ولا ينزّل الصوت.";
      },
      meta: function (d) { return "حتى " + dateLabel(d.as_of, "ar") + " · " + arCount(d.headline.n_corpora, "مجموعة واحدة", "مجموعتان", "مجموعات", "مجموعة") + " · قبل طرح التداخل: " + num(d.headline.hours_gross, 0) + " " + arHours(d.headline.hours_gross); },
      ytL: "من هذه الساعات مصدرها مقاطع يوتيوب (بحسب ناشريها)",
      dialL: function (d) { return "ساعات موسومة من المصدر بلهجة غير الفصحى (" + pct(d.headline.non_msa_dialect_labelled_share) + ")"; },
      locL: function (x) { return "ساعات من الجزء العربي في YODAS v3 (" + num(x.total, 0) + " ساعة، مصنّفة حسب لغة الترجمة النصية) مصدرها رفعٌ لغة الرافع فيه عربية أيضًا؛ ولغة أخرى: " + num(x.other, 0) + " ساعة؛ وغير مذكورة: " + num(x.not_given, 0) + " ساعة"; },
      cls: { "open-commercial": "مفتوح ويسمح بالاستخدام التجاري", "open-noncommercial": "مفتوح لغير الأغراض التجارية فقط", "no-derivatives": "لا يسمح بالأعمال المشتقة",
             "research-or-request": "للبحث أو عند الطلب", "manifests-only": "قوائم فقط (بلا صوت)", "disputed": "متنازع عليه", "unknown": "لا يوجد ترخيص" },
      ht: { released_audio: "صوت منشور", transcribed: "مفرّغ نصيًا", validated: "مُتحقَّق منه", clean: "نظيف", manifest: "قائمة" },
      method: { computed_from_metadata: "محسوب من البيانات الوصفية", computed_from_release_stats: "محسوب من إحصاءات الإصدار", card_or_paper_stated: "كما ورد في البطاقة أو الورقة" },
      corpora: function (n) { return arCount(n, "مجموعة واحدة", "مجموعتان", "مجموعات", "مجموعة"); },
      rows: function (n, m) { return num(n, 0) + " من " + num(m, 0) + " صفًا"; },
      shownH: "ساعة", notCounted: "خارج الرقم الرئيسي",
      ovIntro: "تُطرح الساعات المشتركة بين مجموعتين مرة واحدة من المجموعة اللاحقة في ترتيب الأولوية، وفقط عندما تكون المجموعتان في فئة الترخيص نفسها. تُستخدم أقوال الناشرين ومعرّفات الفيديو المنشورة؛ ومعرّفات التسجيلات في YODAS معرّفات خاصة بالناشر، فلم يمكن قياس التداخل معها.",
      ovMeth: { publisher_statement: "قول الناشر", video_id_intersection: "معرّفات فيديو مشتركة", not_measured: "لم يُقس" },
      ovShared: function (o) {
        if (o.method === "video_id_intersection") return num(o.shared_ids, 0) + " معرّفًا مشتركًا (" + num(o.ids_a, 0) + " و" + num(o.ids_b, 0) + " معرّفًا في النطاق)؛ " + num(o.shared_hours_b, 1) + " ساعة من مقاطع المجموعة الثانية في النطاق";
        if (o.method === "publisher_statement") return !o.shared_hours_b ? "يذكر الناشر أن المجموعتين تضمّان تسجيلات مختلفة؛ لم يُطرح شيء" : num(o.shared_hours_b, 2) + " ساعة مشتركة" + (o.removed_from_b_hours ? "؛ طُرحت " + num(o.removed_from_b_hours, 2) + " ساعة" : "؛ لم يُطرح شيء (فئتا ترخيص مختلفتان)");
        return o.scope;
      },
      how: function (d) {
        return "<h3>ما الذي يُعدّ</h3><ul><li>ساعات الصوت العربي التي نشرها ناشر، بصف لكل مجموعة وجزء ونوع ساعات. تُحفظ أنواع الساعات (الصوت المنشور والمفرّغ والمتحقَّق منه) منفصلة ولا تُجمع؛ ويعتمد الرقم الرئيسي على الصوت المنشور وحده.</li>" +
          "<li>لكل مجموعة فئة ترخيص واحدة لصوتها، تُقرأ من صفحة الناشر نفسه وتُحفظ مع بصمة SHA-256 ووقت الجلب. تُذكر النسخ الأخرى التي تعلن ترخيصًا مختلفًا، ويُعتمد ترخيص الناشر. ولو ذكر الناشر ترخيصين مختلفين لصارت الفئة «متنازعًا عليها». وإذا اشترط الناشر توقيع اتفاقية أو إجراء طلب قبل مشاركة الصوت فالفئة «للبحث أو عند الطلب».</li>" +
          "<li>تُحسب الساعات من البيانات الوصفية المنشورة حيث وُجدت (أعمدة المدة بطلبات جزئية، وقوائم المدد، وإحصاءات إصدار Common Voice، وإحصاءات المدة في عارض بيانات Hugging Face)، أو تؤخذ من قول مقتبس للناشر. ويسجّل كل صف طريقته.</li>" +
          "<li>تُسجَّل اللهجة كما يذكرها المصدر فقط؛ ويوسم اسم البلد بأنه «بلد يذكره المصدر». وتلاوة القرآن نوع مستقل.</li>" +
          "<li>لا تُعدّ إصدارات بيانات لابز إلا للكلام المسجّل المنشور؛ ومجموعة أزواج القنوات من بيانات لابز تعيد معالجة تسجيلات FLEURS، فهي مدرجة ضمن المستبعد.</li></ul>" +
          notes(D.licence_notes && D.licence_notes.ar, "ملاحظات على التراخيص") +
          "<h3>التحقق الثاني</h3><p>يعيد نص برمجي منفصل لا يستورد الحزمة اشتقاقَ ساعات كل صف وفئة ترخيصه من ملفات الأدلة (جداول القياس والصفحات المحفوظة). ولا تدخل الرقم الرئيسي إلا الصفوف المتطابقة (فرق الساعات ضمن 0.1٪ وفئة مطابقة): " + num(d.n_rows_verified, 0) + " من " + num(d.n_rows, 0) + " صفًا متطابقة.</p>" +
          "<h3>المرشّحات</h3><p>أُدرجت " + num(d.n_candidates_listed, 0) + " مجموعة أخرى وُجدت على Hugging Face وZenodo وOpenSLR مع سبب (نسخة من مجموعة معدودة، أو كلام مركّب، أو بلا صوت منشور، أو مقيّدة الوصول، أو لم تُراجع بعد). ولا تُعدّ.</p>" +
          "<p>فئات الترخيص للعلم فقط وليست استشارة قانونية.</p>";
      },
      foot: function (d) {
        return "<p>البيانات: <a href=\"" + d.dataset_url + "\">Bayanat-Labs/arabic-speech-hours</a> (CC BY 4.0) · الشيفرة: <a href=\"https://github.com/Bayanat-Labs/arabic-speech-hours\">GitHub</a> (Apache-2.0) · الصفحة: <a href=\"" + d.page_url + "?lang=ar\">bayanatlabs.com</a></p>" +
          "<p lang=\"en\" dir=\"ltr\">Cite as: " + esc(d.citation) + "</p><p>للتصحيحات: hello@bayanatlabs.com</p><p>الخط: IBM Plex Sans Arabic (SIL OFL 1.1).</p>";
      }
    }
  };

  var lang = "en";
  function num(x, digits) {
    try { return new Intl.NumberFormat(lang === "ar" ? "ar-EG" : "en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x); }
    catch (e) { return Number(x).toFixed(digits); }
  }
  function pct(x) {
    if (x == null) return "";
    var digits = x > 0 && x < 0.001 ? 3 : 1;
    try { return new Intl.NumberFormat(lang === "ar" ? "ar-EG" : "en-GB", { style: "percent", maximumFractionDigits: digits }).format(x); }
    catch (e) { return (Math.round(x * 1000) / 10) + "%"; }
  }
  function dateLabel(iso, l) {
    var p = iso.split("-"), d = parseInt(p[2], 10), m = parseInt(p[1], 10) - 1;
    return l === "ar" ? num(d, 0) + " " + MONTHS_AR[m] + " " + String(num(parseInt(p[0], 10), 0)).replace(/٬|,/g, "") : d + " " + MONTHS_EN[m] + " " + p[0];
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]; }); }
  function $(id) { return document.getElementById(id); }
  function notes(list, title) {
    if (!list || !list.length) return "";
    return "<h3>" + esc(title) + "</h3><ul>" + list.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>";
  }

  var tip = null;
  function bars(container, items, highlight) {
    container.textContent = "";
    var max = Math.max.apply(null, items.map(function (x) { return x.value; }).concat([1]));
    items.forEach(function (it) {
      var row = document.createElement("div");
      row.className = "bar-row";
      row.setAttribute("role", "listitem");
      row.tabIndex = 0;
      var name = document.createElement("span");
      name.className = "bar-name";
      name.textContent = it.label;
      var track = document.createElement("span");
      track.className = "bar-track";
      var fill = document.createElement("span");
      fill.className = "bar-fill" + (highlight(it) ? " hl" : "");
      fill.style.width = (100 * it.value / max).toFixed(3) + "%";
      track.appendChild(fill);
      var val = document.createElement("span");
      val.className = "bar-val";
      val.textContent = num(it.value, it.value < 100 ? 1 : 0) + " " + (lang === "ar" ? arHours(it.value) : "h");
      row.appendChild(name); row.appendChild(track); row.appendChild(val);
      row.setAttribute("aria-label", it.label + ": " + val.textContent + (it.note ? ". " + it.note : ""));
      function show(ev) {
        if (!tip) return;
        tip.textContent = it.label + " · " + val.textContent + (it.note ? " · " + it.note : "");
        tip.hidden = false;
        var r = row.getBoundingClientRect();
        var x = ev && ev.clientX ? ev.clientX : r.left + r.width / 2;
        tip.style.left = Math.max(8, Math.min(window.innerWidth - tip.offsetWidth - 8, x - tip.offsetWidth / 2)) + "px";
        tip.style.top = Math.max(8, r.top - tip.offsetHeight - 6) + "px";
      }
      function hide() { if (tip) tip.hidden = true; }
      row.addEventListener("mousemove", show);
      row.addEventListener("mouseleave", hide);
      row.addEventListener("focus", show);
      row.addEventListener("blur", hide);
      container.appendChild(row);
    });
  }

  function render() {
    var t = I[lang];
    var L = D.latest;
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.title = t.title + " – " + t.brand;
    Array.prototype.forEach.call(document.querySelectorAll("[data-i18n]"), function (e) {
      var v = t[e.getAttribute("data-i18n")];
      if (typeof v === "string") e.textContent = v;
    });
    var btn = $("lang-toggle");
    btn.textContent = lang === "ar" ? "English" : "العربية";
    btn.lang = lang === "ar" ? "en" : "ar";
    btn.dir = lang === "ar" ? "ltr" : "rtl";
    $("ar-note").hidden = lang !== "ar";
    $("lede").textContent = t.lede(L);
    var hn = L.headline.hours_rounded;
    $("hero-num").textContent = num(hn, 0);
    $("hero-unit").textContent = t.unit(hn);
    $("hero-meta").textContent = t.meta(L);
    $("t-yt").textContent = pct(L.headline.youtube_derived_share);
    $("t-yt-l").textContent = t.ytL;
    $("t-dial").textContent = num(L.headline.non_msa_dialect_labelled_hours, 1);
    $("t-dial-l").textContent = t.dialL(L);
    var loc = D.yodas3_locale;
    $("t-loc").textContent = num(loc.ar, 0);
    $("t-loc-l").textContent = t.locL(loc);
    tip = $("tip");
    bars($("chart-class"), CLASSES.filter(function (c) { return D.by_class_detail[c].n_corpora > 0; }).map(function (c) {
      var x = D.by_class_detail[c];
      return { key: c, label: t.cls[c], value: x.released_audio_hours_overlap_adjusted, note: t.corpora(x.n_corpora) + (c === "open-commercial" ? "" : " · " + t.notCounted) };
    }), function (it) { return it.key === "open-commercial"; });
    bars($("chart-corpus"), L.by_corpus.map(function (x) { return { label: x.corpus_name, value: x.hours }; }), function () { return true; });
    // filters
    var fc = $("f-class"), ft = $("f-type");
    var cv = fc.value, tv = ft.value;
    fc.innerHTML = "<option value=\"\">" + esc(t.all) + "</option>" + CLASSES.filter(function (c) { return D.rows.some(function (r) { return r.licence_class === c; }); }).map(function (c) { return "<option value=\"" + c + "\">" + esc(t.cls[c]) + "</option>"; }).join("");
    ft.innerHTML = "<option value=\"\">" + esc(t.all) + "</option>" + HOUR_TYPES.filter(function (h) { return D.rows.some(function (r) { return r.hour_type === h; }); }).map(function (h) { return "<option value=\"" + h + "\">" + esc(t.ht[h]) + "</option>"; }).join("");
    fc.value = cv; ft.value = tv;
    table();
    $("ov").innerHTML = "<p>" + esc(t.ovIntro) + "</p><ul>" + D.overlap.map(function (o) {
      return "<li><strong>" + esc(D.names[o.corpus_a] || o.corpus_a) + "</strong> · <strong>" + esc(D.names[o.corpus_b] || o.corpus_b) + (o.partition_b ? " (" + esc(o.partition_b) + ")" : "") + "</strong>: " + esc(t.ovMeth[o.method] || o.method) + "; " + esc(t.ovShared(o)) + "</li>";
    }).join("") + "</ul>";
    $("how").innerHTML = t.how(Object.assign({}, L, { n_rows: D.rows.length, n_rows_verified: D.rows.filter(function (r) { return r.status === "verified"; }).length }));
    $("foot").innerHTML = t.foot(L);
    var w = $("demo-widget");
    var nw = document.createElement("arabic-speech-hours");
    nw.id = "demo-widget";
    nw.setAttribute("src", "latest.json");
    nw.setAttribute("lang", lang);
    w.parentNode.replaceChild(nw, w);
    $("badge-img").alt = lang === "ar" ? "شارة العدّاد" : "Counter badge";
    $("embed-code").textContent = D.embed_snippet;
  }

  function table() {
    var t = I[lang];
    var fc = $("f-class").value, ft = $("f-type").value;
    var rows = D.rows.filter(function (r) { return (!fc || r.licence_class === fc) && (!ft || r.hour_type === ft); });
    var tb = document.querySelector("#tbl tbody");
    tb.innerHTML = rows.map(function (r) {
      return "<tr><td><a href=\"" + esc(r.homepage_url) + "\" rel=\"noopener\" target=\"_blank\" title=\"" + esc(r.publisher) + "\">" + esc(r.corpus_name) + "</a>" + (r.partition ? "<span class=\"small id\">" + esc(r.partition) + "</span>" : "") + "</td>" +
        "<td><span class=\"pill" + (r.licence_class === "open-commercial" ? " oc" : "") + "\">" + esc(t.cls[r.licence_class]) + "</span></td>" +
        "<td><span class=\"id\">" + esc(r.licence_string) + "</span></td>" +
        "<td>" + esc(t.ht[r.hour_type] || r.hour_type) + "</td>" +
        "<td>" + esc(r.dialect_group) + (r.source_dialect_label ? "<span class=\"small id\">" + esc(r.source_dialect_label) + "</span>" : "") + "</td>" +
        "<td>" + esc(r.genre) + "</td>" +
        "<td class=\"num\">" + num(r.hours, 1) + "</td><td class=\"num\">" + (r.hour_type === "released_audio" ? num(r.overlap_adjusted_hours, 1) : "") + "</td>" +
        "<td>" + esc(t.method[r.hours_method] || r.hours_method) + "</td></tr>";
    }).join("");
    $("count").textContent = t.rows(rows.length, D.rows.length);
  }

  function init() {
    if (!D) return;
    var q = new URLSearchParams(location.search);
    lang = q.get("lang") === "ar" ? "ar" : "en";
    $("lang-toggle").addEventListener("click", function () {
      lang = lang === "ar" ? "en" : "ar";
      var u = new URL(location.href);
      if (lang === "ar") u.searchParams.set("lang", "ar"); else u.searchParams.delete("lang");
      history.replaceState(null, "", u.toString());
      render();
    });
    $("f-class").addEventListener("change", table);
    $("f-type").addEventListener("change", table);
    render();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
