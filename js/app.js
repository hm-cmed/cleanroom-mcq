/*
 * クリーンルーム5択ドリル（ブラウザだけで動く。サーバーには何も送らない）
 * - 画面は DOM API（createElement と textContent）だけで組み立てる。innerHTML は使わない
 * - 解答の記録はこのブラウザ（localStorage）と、利用者が保存するファイルにだけ残る
 */
(() => {
  "use strict";

  const C = window.MCQ_CONFIG || {};
  const D = window.MCQ_DATA || { items: [], facts: {}, domains: {} };
  const LETTERS = ["a", "b", "c", "d", "e"];
  const STORE_KEY = "crmcq.session.v1";
  const FORMAT = "crmcq-session";
  const ITEMS = (D.items || []).filter((it) => it.status === "approved" || (C.showDrafts && it.status === "draft"));
  const BY_ID = new Map(ITEMS.map((it) => [it.id, it]));
  const DOMAIN_ORDER = Object.keys(D.domains || {});
  const app = document.getElementById("app");

  /* ---------- 小さな道具 ---------- */
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const domainName = (code) => (D.domains || {})[code] || code;
  const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
  const now = () => new Date().toISOString();
  const fmtDate = (iso) => {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };
  function safeUrl(u) {
    try {
      const x = new URL(String(u || ""));
      return x.protocol === "https:" ? x.href : "";
    } catch (e) {
      return "";
    }
  }
  function shuffle(arr) {
    const a = arr.slice();
    const rnd = new Uint32Array(a.length);
    crypto.getRandomValues(rnd);
    for (let i = a.length - 1; i > 0; i--) {
      const j = rnd[i] % (i + 1);
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  // 読み込んだ JSON から、プロトタイプを書き換える危険なキーを取り除く
  function safeParse(text) {
    return JSON.parse(text, (k, v) => (k === "__proto__" || k === "constructor" || k === "prototype" ? undefined : v));
  }
  function download(name, text, type) {
    const blob = new Blob([text], { type });
    const a = h("a", { href: URL.createObjectURL(blob), download: name });
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  // CSV の1セル。Excel で数式として実行されないよう、= + - @ などで始まる値には ' を付ける
  function csvCell(v) {
    let s = v === null || v === undefined ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function stamp() {
    return fmtDate(now()).replace(/[-: ]/g, "").slice(0, 12);
  }

  /* ---------- 保存（このブラウザの中だけ） ---------- */
  const store = {
    load() {
      try { return validateSession(safeParse(localStorage.getItem(STORE_KEY) || "null")); } catch (e) { return null; }
    },
    save(s) {
      try { localStorage.setItem(STORE_KEY, JSON.stringify(s)); } catch (e) { /* 保存できない環境でも続ける */ }
    },
    clear() {
      try { localStorage.removeItem(STORE_KEY); } catch (e) { /* noop */ }
    }
  };

  // 解答の記録を検査して、安全な形に作り直す（細工したファイルを読み込んでも動作を乱さない）
  function validateSession(raw) {
    if (!raw || typeof raw !== "object") return null;
    const src = raw.format === FORMAT ? raw.session : raw;
    if (!src || typeof src !== "object" || !Array.isArray(src.order)) return null;
    const order = [];
    const seen = new Set();
    for (const id of src.order.slice(0, 2000)) {
      if (typeof id === "string" && BY_ID.has(id) && !seen.has(id)) { order.push(id); seen.add(id); }
    }
    if (!order.length) return null;
    const isPerm = (p) => Array.isArray(p) && p.length === 5 && [0, 1, 2, 3, 4].every((n) => p.includes(n));
    const perm = {};
    const answers = {};
    for (const id of order) {
      const p = src.perm && Object.prototype.hasOwnProperty.call(src.perm, id) ? src.perm[id] : null;
      perm[id] = isPerm(p) ? p.map(Number) : [0, 1, 2, 3, 4];
      const a = src.answers && Object.prototype.hasOwnProperty.call(src.answers, id) ? src.answers[id] : null;
      if (a && Number.isInteger(a.choice) && a.choice >= 0 && a.choice < 5) {
        answers[id] = { choice: a.choice, correct: a.choice === BY_ID.get(id).key, at: typeof a.at === "string" ? a.at.slice(0, 40) : "" };
      }
    }
    const st = src.settings || {};
    const pos = Number.isInteger(src.pos) ? Math.min(Math.max(src.pos, 0), order.length - 1) : 0;
    return {
      v: 1,
      id: typeof src.id === "string" ? src.id.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 40) || stamp() : stamp(),
      started: typeof src.started === "string" ? src.started.slice(0, 40) : now(),
      updated: now(),
      settings: { feedback: st.feedback === "end" ? "end" : "each", shuffle: st.shuffle !== false },
      order, perm, answers, pos,
      finished: src.finished === true && order.every((id) => answers[id])
    };
  }

  let S = store.load();

  /* ---------- 集計 ---------- */
  function summary(s) {
    const ans = s.order.filter((id) => s.answers[id]);
    const correct = ans.filter((id) => s.answers[id].correct).length;
    const group = (keyFn) => {
      const m = new Map();
      for (const id of ans) {
        const k = keyFn(BY_ID.get(id)) || "（未設定）";
        const g = m.get(k) || { n: 0, ok: 0 };
        g.n += 1;
        if (s.answers[id].correct) g.ok += 1;
        m.set(k, g);
      }
      return m;
    };
    return { total: s.order.length, answered: ans.length, correct, byDomain: group((it) => it.domain), byKokushi: group((it) => it.kokushi) };
  }

  function sessionCsv(s) {
    const rows = [["問題ID", "領域", "出題基準（医師国家試験）", "あなたの解答", "正答", "結果", "解答日時"]];
    for (const id of s.order) {
      const it = BY_ID.get(id);
      const a = s.answers[id];
      const letterOf = (orig) => LETTERS[s.perm[id].indexOf(orig)];
      rows.push([id, domainName(it.domain), it.kokushi, a ? letterOf(a.choice) : "", letterOf(it.key),
        a ? (a.correct ? "正解" : "不正解") : "未解答", a ? fmtDate(a.at) : ""]);
    }
    const sm = summary(s);
    rows.push([]);
    rows.push(["解答数", sm.answered, "正解数", sm.correct, "正答率(%)", pct(sm.correct, sm.answered)]);
    return "﻿" + rows.map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
  }
  function sessionJson(s) {
    return JSON.stringify({
      format: FORMAT, v: 1, exported_at: now(),
      app: `${C.appName || ""} ${C.version || ""}`.trim(),
      dataset: { built_at: D.built_at || "", facts_revision: D.facts_revision || "" },
      summary: (({ total, answered, correct }) => ({ total, answered, correct }))(summary(s)),
      session: s
    }, null, 1);
  }
  const saveJson = (s) => download(`5択ドリル_再開用_${stamp()}.json`, sessionJson(s), "application/json");
  const saveCsv = (s) => download(`5択ドリル_成績_${stamp()}.csv`, sessionCsv(s), "text/csv;charset=utf-8");

  /* ---------- 共通の部品 ---------- */
  function draftNotice() {
    const drafts = ITEMS.filter((it) => it.status !== "approved").length;
    if (!drafts) return null;
    return h("p", { class: "notice" },
      h("strong", { text: "試作版：" }),
      `${ITEMS.length}問のうち${drafts}問は、専門医による監修の前の問題です。学習の参考にとどめ、誤りに気づいたらお知らせください。`);
  }
  function button(label, onclick, cls = "btn") {
    return h("button", { type: "button", class: cls, onclick }, label);
  }
  function setView(title, ...nodes) {
    app.replaceChildren(...nodes.filter((n) => n !== null && n !== undefined && n !== false));
    document.title = `${title}｜${C.appName || "5択ドリル"}`;
    app.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  function sourceLine(factId) {
    const f = (D.facts || {})[factId];
    if (!f) return null;
    const link = f.doi ? safeUrl("https://doi.org/" + encodeURI(f.doi)) : safeUrl(f.url);
    return h("p", { class: "source" },
      h("span", { class: "fact-id", text: factId }), " ",
      link ? h("a", { href: link, target: "_blank", rel: "noopener noreferrer" }, f.source || link) : (f.source || ""),
      f.pmid ? `（PMID ${f.pmid}）` : "");
  }

  /* ---------- ホーム ---------- */
  function viewHome() {
    const counts = new Map();
    for (const it of ITEMS) counts.set(it.domain, (counts.get(it.domain) || 0) + 1);
    const domains = DOMAIN_ORDER.filter((d) => counts.get(d));

    const domainBoxes = domains.map((d) =>
      h("label", { class: "check" }, h("input", { type: "checkbox", name: "domain", value: d, checked: true }),
        ` ${domainName(d)}`, h("span", { class: "count", text: `${counts.get(d)}問` })));
    const countSel = h("select", { id: "count" },
      [10, 20].filter((n) => n < ITEMS.length).map((n) => h("option", { value: n, text: `${n}問` })),
      h("option", { value: "all", text: "すべて", selected: true }));
    const fbEach = h("input", { type: "radio", name: "feedback", value: "each", checked: true });
    const fbEnd = h("input", { type: "radio", name: "feedback", value: "end" });
    const shuffleBox = h("input", { type: "checkbox", id: "shuffle", checked: true });
    const msg = h("p", { class: "error", role: "alert" });

    function start() {
      const picked = domainBoxes.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
      if (!picked.length) { msg.textContent = "出題する領域を1つ以上選んでください。"; return; }
      let pool = shuffle(ITEMS.filter((it) => picked.includes(it.domain)).map((it) => it.id));
      if (countSel.value !== "all") pool = pool.slice(0, Number(countSel.value));
      const sh = shuffleBox.checked;
      S = {
        v: 1, id: stamp(), started: now(), updated: now(),
        settings: { feedback: fbEnd.checked ? "end" : "each", shuffle: sh },
        order: pool,
        perm: Object.fromEntries(pool.map((id) => [id, sh ? shuffle([0, 1, 2, 3, 4]) : [0, 1, 2, 3, 4]])),
        answers: {}, pos: 0, finished: false
      };
      store.save(S);
      location.hash = "#/quiz";
    }

    const fileInput = h("input", { type: "file", accept: ".json,application/json", class: "visually-hidden", id: "resumeFile" });
    const fileMsg = h("p", { class: "error", role: "alert" });
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) { fileMsg.textContent = "ファイルが大きすぎます（2MB まで）。"; return; }
      file.text().then((text) => {
        let s = null;
        try { s = validateSession(safeParse(text)); } catch (e) { s = null; }
        if (!s) { fileMsg.textContent = "このファイルからは再開できません。このサイトで保存した「再開用ファイル」を選んでください。"; return; }
        S = s;
        store.save(S);
        location.hash = S.finished ? "#/result" : "#/quiz";
      });
    });

    const resume = S && !S.finished ? (() => {
      const sm = summary(S);
      return h("section", { class: "card resume" },
        h("h2", { text: "前回の続き" }),
        h("p", { text: `${fmtDate(S.started)} に始めた ${sm.total}問のうち ${sm.answered}問に解答済み（正解 ${sm.correct}問）です。` }),
        h("div", { class: "actions" },
          button("続きから解く", () => { location.hash = "#/quiz"; }, "btn primary"),
          button("成績を見る・保存する", () => { location.hash = "#/suspend"; }),
          button("記録を消す", () => {
            if (confirm("このブラウザに保存している解答の記録を消します。よろしいですか。")) { store.clear(); S = null; viewHome(); }
          }, "btn ghost")));
    })() : null;

    setView("はじめる",
      h("section", { class: "hero" },
        h("h1", {}, C.appName || "5択ドリル", h("span", { class: "hero-sub", text: C.subtitle || "" })),
        h("p", { class: "lead", text: "医学教育モデル・コア・カリキュラムと医師国家試験出題基準に対応づけた5択問題です。1問ごとに自動で採点し、すべての選択肢に根拠つきの解説を表示します。" }),
        h("p", { class: "lead small", text: "解答の記録はこのブラウザの中だけに保存され、外部には送られません。途中でやめるときは、成績と再開用のファイルを保存できます。" })),
      draftNotice(),
      resume,
      h("section", { class: "card" },
        h("h2", { text: S && !S.finished ? "新しく始める" : "出題の設定" }),
        h("fieldset", {}, h("legend", { text: "出題する領域" }), h("div", { class: "checks" }, domainBoxes)),
        h("div", { class: "row" },
          h("label", { class: "field" }, "出題数", countSel),
          h("fieldset", { class: "field" }, h("legend", { text: "解説を見るタイミング" }),
            h("label", { class: "radio" }, fbEach, " 1問ごと"),
            h("label", { class: "radio" }, fbEnd, " 最後にまとめて（模擬試験向け）"))),
        h("label", { class: "check" }, shuffleBox, " 問題と選択肢の順番を毎回入れ替える"),
        msg,
        h("div", { class: "actions" }, button("はじめる", start, "btn primary big"))),
      h("section", { class: "card subtle" },
        h("h2", { text: "保存したファイルから再開する" }),
        h("p", { text: "別の端末やブラウザで解いた続きは、「再開用ファイル（.json）」を選ぶと再開できます。" }),
        h("label", { for: "resumeFile", class: "btn" }, "ファイルを選ぶ"), fileInput, fileMsg));
  }

  /* ---------- 出題 ---------- */
  function viewQuiz() {
    if (!S) { location.hash = "#/"; return; }
    if (S.finished) { location.hash = "#/result"; return; }
    const id = S.order[S.pos];
    const it = BY_ID.get(id);
    const perm = S.perm[id];
    const done = S.answers[id];
    const sm = summary(S);
    let selected = done ? done.choice : null;
    const showFeedback = !!done && S.settings.feedback === "each";

    const optButtons = perm.map((orig, i) => {
      const o = it.options[orig];
      const cls = ["option"];
      if (done && S.settings.feedback === "each") {
        if (orig === it.key) cls.push("is-key");
        else if (orig === done.choice) cls.push("is-wrong");
      }
      if (orig === selected) cls.push("is-selected");
      return h("button", {
        type: "button", class: cls.join(" "), role: "radio", "aria-checked": orig === selected ? "true" : "false",
        disabled: !!done, "data-orig": orig,
        onclick: () => choose(orig)
      }, h("span", { class: "letter", text: LETTERS[i] }), h("span", { class: "otext", text: o.text }));
    });
    function choose(orig) {
      if (done) return;
      selected = orig;
      for (const b of optButtons) {
        const on = Number(b.dataset.orig) === orig;
        b.classList.toggle("is-selected", on);
        b.setAttribute("aria-checked", on ? "true" : "false");
      }
      submit.disabled = false;
    }
    function answer() {
      if (selected === null || done) return;
      S.answers[id] = { choice: selected, correct: selected === it.key, at: now() };
      S.updated = now();
      store.save(S);
      if (S.settings.feedback === "end") next();
      else viewQuiz();
    }
    function next() {
      const remaining = S.order.findIndex((x) => !S.answers[x]);
      if (remaining === -1) { S.finished = true; store.save(S); location.hash = "#/result"; return; }
      S.pos = S.pos + 1 < S.order.length && !S.answers[S.order[S.pos + 1]] ? S.pos + 1 : remaining;
      store.save(S);
      viewQuiz();
    }
    const submit = button("解答する", answer, "btn primary big");
    submit.disabled = selected === null;
    const isLastUnanswered = S.order.filter((x) => !S.answers[x]).length === 0;

    const feedback = showFeedback ? explanation(it, perm, done) : null;
    const actions = done
      ? h("div", { class: "actions" }, button(isLastUnanswered ? "結果を見る" : "次の問題へ", next, "btn primary big"))
      : h("div", { class: "actions" }, submit);

    keyHandler = (e) => {
      if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
      const k = e.key.toLowerCase();
      const idx = LETTERS.indexOf(k) >= 0 ? LETTERS.indexOf(k) : ["1", "2", "3", "4", "5"].indexOf(k);
      if (idx >= 0 && !done) { choose(perm[idx]); e.preventDefault(); }
      else if (k === "enter") { if (done) next(); else answer(); e.preventDefault(); }
    };

    setView(`第${S.pos + 1}問`,
      h("div", { class: "progress-row" },
        h("span", { text: `第 ${S.pos + 1} 問 / 全 ${sm.total} 問` }),
        S.settings.feedback === "each" ? h("span", { text: `正解 ${sm.correct} / ${sm.answered}` }) : h("span", { text: `解答済み ${sm.answered}` })),
      h("div", { class: "bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": sm.total, "aria-valuenow": sm.answered },
        h("span", { style: null, class: "bar-fill", "data-w": pct(sm.answered, sm.total) })),
      h("article", { class: "card question" },
        h("p", { class: "meta" },
          h("span", { class: "tag", text: domainName(it.domain) }),
          it.kokushi ? h("span", { class: "tag light", text: it.kokushi }) : null,
          it.status !== "approved" ? h("span", { class: "tag warn", text: "監修前" }) : null,
          h("span", { class: "qid", text: it.id })),
        h("h1", { class: "stem", text: it.stem }),
        h("div", { class: "options", role: "radiogroup", "aria-label": "選択肢" }, optButtons),
        feedback,
        actions),
      h("div", { class: "actions split" },
        button("中断して成績を保存する", () => { location.hash = "#/suspend"; }, "btn ghost"),
        h("span", { class: "hint", text: "キーボード：a〜e（1〜5）で選択、Enter で解答・次へ" })));
    // 進み具合の棒（style 属性は CSP で使えないため、CSSOM で幅を設定する）
    const fill = app.querySelector(".bar-fill");
    if (fill) fill.style.width = fill.dataset.w + "%";
  }

  function explanation(it, perm, done) {
    const ok = done.choice === it.key;
    return h("section", { class: "feedback " + (ok ? "ok" : "ng"), "aria-live": "polite" },
      h("p", { class: "verdict", text: ok ? "正解です" : `不正解です（正答は ${LETTERS[perm.indexOf(it.key)]}）` }),
      h("ol", { class: "explain" }, perm.map((orig, i) => {
        const o = it.options[orig];
        const f = (D.facts || {})[o.fact] || {};
        const marks = [];
        if (orig === it.key) marks.push(h("span", { class: "mark key", text: "正答" }));
        if (orig === done.choice) marks.push(h("span", { class: "mark you", text: "あなたの解答" }));
        return h("li", { class: o.truth ? "true" : "false" },
          h("p", { class: "ehead" },
            h("span", { class: "letter small", text: LETTERS[i] }),
            h("strong", { text: o.truth ? "正しい記述" : "誤った記述" }), ...marks),
          h("p", { class: "otext muted", text: o.text }),
          h("p", { class: "etext" }, h("span", { class: "label", text: o.truth ? "根拠：" : "正しくは：" }), f.statement || ""),
          sourceLine(o.fact));
      })));
  }

  /* ---------- 中断（成績の保存） ---------- */
  function viewSuspend() {
    if (!S) { location.hash = "#/"; return; }
    const sm = summary(S);
    setView("成績の保存",
      h("section", { class: "card" },
        h("h1", { text: "ここまでの成績" }),
        scoreBlock(sm),
        h("p", { text: "このブラウザにも自動で保存しています。同じブラウザでこのページを開けば「続きから解く」で再開できます。別の端末で続ける場合や、記録として残す場合は、ファイルに保存してください。" }),
        h("div", { class: "actions wrap-gap" },
          button("再開用ファイル（.json）を保存", () => saveJson(S), "btn primary"),
          button("成績表（.csv）を保存", () => saveCsv(S)),
          button("印刷する", () => window.print())),
        h("div", { class: "actions wrap-gap" },
          S.finished ? button("結果を見る", () => { location.hash = "#/result"; }) : button("問題に戻る", () => { location.hash = "#/quiz"; }),
          button("はじめの画面へ", () => { location.hash = "#/"; }, "btn ghost"))),
      breakdown(sm));
  }

  function scoreBlock(sm) {
    return h("div", { class: "score" },
      h("div", { class: "score-main" }, h("span", { class: "big-num", text: `${pct(sm.correct, sm.answered)}` }), h("span", { text: "%" })),
      h("div", { class: "score-sub" },
        h("p", { text: `正解 ${sm.correct}問 / 解答 ${sm.answered}問` }),
        sm.answered < sm.total ? h("p", { class: "muted", text: `未解答 ${sm.total - sm.answered}問` }) : null));
  }

  function breakdown(sm) {
    const table = (title, map, labelFn) => h("section", { class: "card" },
      h("h2", { text: title }),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", { text: "項目" }), h("th", { text: "正解 / 解答" }), h("th", { text: "正答率" }))),
        h("tbody", {}, [...map.entries()].sort((a, b) => String(a[0]).localeCompare(String(b[0]), "ja")).map(([k, g]) =>
          h("tr", {}, h("td", { text: labelFn(k) }), h("td", { class: "num", text: `${g.ok} / ${g.n}` }),
            h("td", { class: "num" }, h("span", { class: "minibar" }, h("span", { "data-w": pct(g.ok, g.n) })), ` ${pct(g.ok, g.n)}%`)))))));
    if (!sm.answered) return null;
    const frag = document.createDocumentFragment();
    frag.append(table("領域別", sm.byDomain, domainName), table("医師国家試験出題基準の項目別", sm.byKokushi, (k) => k));
    queueMicrotask(() => app.querySelectorAll(".minibar > span").forEach((s) => { s.style.width = s.dataset.w + "%"; }));
    return frag;
  }

  /* ---------- 結果 ---------- */
  function viewResult() {
    if (!S) { location.hash = "#/"; return; }
    const sm = summary(S);
    const wrong = S.order.filter((id) => S.answers[id] && !S.answers[id].correct);
    function retry(ids) {
      const sh = S.settings.shuffle;
      const order = sh ? shuffle(ids) : ids.slice();
      S = { v: 1, id: stamp(), started: now(), updated: now(), settings: { ...S.settings },
        order, perm: Object.fromEntries(order.map((id) => [id, sh ? shuffle([0, 1, 2, 3, 4]) : [0, 1, 2, 3, 4]])),
        answers: {}, pos: 0, finished: false };
      store.save(S);
      location.hash = "#/quiz";
    }
    const list = h("ol", { class: "review" }, S.order.map((id) => {
      const it = BY_ID.get(id);
      const a = S.answers[id];
      const perm = S.perm[id];
      return h("li", { class: a ? (a.correct ? "ok" : "ng") : "na" },
        h("details", {},
          h("summary", {},
            h("span", { class: "rmark", text: a ? (a.correct ? "○" : "×") : "－" }),
            h("span", { class: "rstem", text: it.stem }),
            h("span", { class: "rans", text: a ? `解答 ${LETTERS[perm.indexOf(a.choice)]} / 正答 ${LETTERS[perm.indexOf(it.key)]}` : "未解答" })),
          h("p", { class: "meta" }, h("span", { class: "tag", text: domainName(it.domain) }), it.kokushi ? h("span", { class: "tag light", text: it.kokushi }) : null, h("span", { class: "qid", text: it.id })),
          a ? explanation(it, perm, a) : h("p", { class: "muted", text: "この問題には解答していません。" })));
    }));
    setView("結果",
      h("section", { class: "card" },
        h("h1", { text: S.finished ? "結果" : "途中までの結果" }),
        scoreBlock(sm),
        h("div", { class: "actions wrap-gap" },
          wrong.length ? button(`間違えた${wrong.length}問を解き直す`, () => retry(wrong), "btn primary") : null,
          button("同じ問題をもう一度", () => retry(S.order.slice())),
          button("成績表（.csv）を保存", () => saveCsv(S)),
          button("記録（.json）を保存", () => saveJson(S)),
          button("印刷する", () => window.print()),
          button("はじめの画面へ", () => { location.hash = "#/"; }, "btn ghost"))),
      breakdown(sm),
      h("section", { class: "card" }, h("h2", { text: "問題ごとの解説" }), h("p", { class: "muted", text: "各行を開くと、すべての選択肢の解説と根拠を確認できます。" }), list));
  }

  /* ---------- 出題範囲 ---------- */
  function viewBlueprint() {
    const byDomain = new Map();
    for (const it of ITEMS) {
      if (!byDomain.has(it.domain)) byDomain.set(it.domain, new Map());
      const m = byDomain.get(it.domain);
      const k = it.kokushi || "（未対応）";
      m.set(k, (m.get(k) || 0) + 1);
    }
    const sections = DOMAIN_ORDER.filter((d) => byDomain.has(d)).map((d) => h("section", { class: "card" },
      h("h2", { text: `${domainName(d)}（${[...byDomain.get(d).values()].reduce((a, b) => a + b, 0)}問）` }),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", { text: "医師国家試験出題基準（令和6年版）の項目" }), h("th", { text: "問題数" }))),
        h("tbody", {}, [...byDomain.get(d).entries()].sort((a, b) => a[0].localeCompare(b[0], "ja"))
          .map(([k, n]) => h("tr", {}, h("td", { text: k }), h("td", { class: "num", text: n }))))))));
    const missing = DOMAIN_ORDER.filter((d) => !byDomain.has(d)).map(domainName);
    setView("出題範囲",
      h("section", { class: "card" },
        h("h1", { text: "出題範囲" }),
        h("p", { text: `現在の問題は ${ITEMS.length}問です。各問題は、正答の根拠となる事実カードに付けた医師国家試験出題基準（令和6年版）と医学教育モデル・コア・カリキュラム（令和4年度改訂版）の番号で分類しています。` }),
        missing.length ? h("p", { class: "muted", text: `準備中の領域：${missing.join("、")}` }) : null),
      sections);
  }

  /* ---------- このサイトについて ---------- */
  function viewAbout() {
    const p = (t) => h("p", { text: t });
    setView("このサイトについて",
      h("section", { class: "card prose" },
        h("h1", { text: "このサイトについて" }),
        h("h2", { text: "クリーンルーム方式" }),
        p("問題は、教科書やガイドラインの文章を写さずに作っています。まず、論文やガイドラインから事実と数値だけを取り出して自分の言葉で書いた「事実カード」を作り、出典の実在とライセンスを照合します。問題文・選択肢・解説は、この事実カードだけを根拠にしています。"),
        p("すべての選択肢には、その正誤を決める事実カードが1枚ずつ対応しています。解説に表示しているのは、そのカードの主張文と出典です。"),
        h("h2", { text: "問題の作り方と監修" }),
        p("試作版の問題は、生成AI（Claude）が事実カードをもとに作成し、プログラムで事実カードとの一致（カードの有無、出典の照合状況、数値の一致）を確かめています。「監修前」と表示している問題は、専門医による内容の確認がまだ済んでいません。"),
        p("医師国家試験の過去問題は使っていません。出題基準とコア・カリキュラムは、項目の対応づけにだけ使っています。"),
        h("h2", { text: "個人情報と記録" }),
        p("解答の記録は、このブラウザの中（localStorage）だけに保存します。サーバーへの送信、アクセス解析、広告は一切ありません。ページには外部への通信を禁止する設定（Content-Security-Policy）を入れています。"),
        h("h2", { text: "ご注意" }),
        p("このサイトは学習の参考のためのものです。診療の判断には使わないでください。内容の誤りに気づいた場合は、問題ID（例：Q-LV-001）を添えてお知らせください。"),
        h("h2", { text: "データ" }),
        p(`問題データ作成日：${D.built_at || "不明"}　事実カードの版：${D.facts_revision || "不明"}`),
        h("p", {}, "事実カード：", h("a", { href: safeUrl(C.factsRepository), target: "_blank", rel: "noopener noreferrer" }, C.factsRepository || "")),
        h("p", {}, "プログラム：", h("a", { href: safeUrl(C.repository), target: "_blank", rel: "noopener noreferrer" }, C.repository || ""))));
  }

  /* ---------- 画面下部 ---------- */
  function renderFooter() {
    const grants = Array.isArray(C.grants) ? C.grants.filter((g) => g && g.funder) : [];
    document.getElementById("footer").replaceChildren(...[
      h("p", {}, `${C.appName || ""} ${C.subtitle || ""}　ver. ${C.version || ""}`),
      h("p", { text: `開発：${C.developer || ""}` }),
      grants.length ? h("p", { text: "助成：" + grants.map((g) => g.funder + (g.title ? `「${g.title}」` : "") + (g.number ? `（${g.number}）` : "")).join("／") }) : null,
      h("p", { class: "muted", text: `プログラム ${C.license && C.license.code || ""}／問題と解説 ${C.license && C.license.content || ""}。学習用であり、診療の判断には使わないでください。` })
    ].filter(Boolean));
    document.getElementById("brandName").textContent = C.appName || "";
    document.getElementById("brandSub").textContent = C.subtitle || "";
  }

  /* ---------- 画面の切り替え ---------- */
  let keyHandler = null;
  document.addEventListener("keydown", (e) => { if (keyHandler) keyHandler(e); });
  function route() {
    keyHandler = null;
    const r = (location.hash || "#/").replace(/^#/, "");
    for (const a of document.querySelectorAll(".nav a")) a.classList.toggle("active", a.getAttribute("href") === "#" + r);
    if (!ITEMS.length) { setView("準備中", h("p", { class: "notice", text: "公開できる問題がまだありません。" })); return; }
    if (r === "/quiz") viewQuiz();
    else if (r === "/suspend") viewSuspend();
    else if (r === "/result") viewResult();
    else if (r === "/blueprint") viewBlueprint();
    else if (r === "/about") viewAbout();
    else viewHome();
  }
  window.addEventListener("hashchange", route);
  renderFooter();
  route();
})();
