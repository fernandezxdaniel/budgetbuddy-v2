(() => {
  "use strict";
  // Same-origin by default (works on localhost:5000 AND on Render). Only VS Code Live Server (port 5500) needs the full URL.
  const API = location.port === "5500" ? "http://127.0.0.1:5000" : "";
  const LOGO_MARK = "logo-mark.png";
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const MON = MONTHS.map(m => m.slice(0, 3));
  const CATS = ["needs", "wants", "savings"];
  const PRESETS = {
    needs: ["Rent", "Transportation", "Food", "Water"],
    wants: ["Online Shopping", "Hobbies"],
    savings: ["Emergency Fund", "Education Fund"],
  };
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const r2 = n => Math.round(n * 100) / 100;
  const cap = s => s[0].toUpperCase() + s.slice(1);
  const peso = (n, d = "auto", sp = "") => {
    const dec = d === "auto" ? (Number.isInteger(n) ? 0 : 2) : d;
    return (n < 0 ? "-" : "") + "\u20b1" + sp + Math.abs(n).toLocaleString("en-PH", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  };
 
  /* ---------- dates (always "YYYY-MM-DD" strings) ---------- */
  const pad = n => String(n).padStart(2, "0");
  const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const parts = s => s.split("-").map(Number);
  const dayNum = s => { const [y, m, d] = parts(s); return Date.UTC(y, m - 1, d) / 86400000; };
  const nDays = (a, b) => dayNum(b) - dayNum(a) + 1;
  const fmtDay = s => { const [, m, d] = parts(s); return `${MON[m - 1]} ${d}`; };
  const fmtRange = (a, b) => `${fmtDay(a)} \u2013 ${fmtDay(b)}, ${parts(b)[0]}`;
 
  /* ---------- session + server calls ---------- */
  const token = () => localStorage.getItem("bb_token");
  const user = () => { try { return JSON.parse(localStorage.getItem("bb_user")); } catch { return null; } };
  function setSession(r) {
    localStorage.setItem("bb_token", r.token);
    localStorage.setItem("bb_user", JSON.stringify(r.user));
  }
  async function api(method, path, body, auth = true) {
    let res;
    try {
      res = await fetch(API + path, {
        method, body: body ? JSON.stringify(body) : undefined,
        headers: { "Content-Type": "application/json", ...(auth && token() ? { Authorization: "Bearer " + token() } : {}) },
      });
    } catch { throw new Error("Cannot reach the BudgetBuddy server. Please try again in a moment."); }
    let data = {};
    try { data = await res.json(); } catch { /* not JSON */ }
    if (auth && res.status === 401) { localStorage.removeItem("bb_token"); location.href = "index.html"; throw new Error("Please log in again."); }
    if (!res.ok || !data.ok) {
      throw new Error(data.error || `The server returned HTTP ${res.status} for ${path}. Please retry; if it continues, check the Render logs.`);
    }
    return data;
  }
 
  /* ---------- the selected period's plan lives on the server ---------- */
  let plan = null, result = null, incomeEntries = [], chain = Promise.resolve();
  function selectedPeriod() {
    try {
      const saved = JSON.parse(localStorage.getItem("bb_period"));
      return saved && saved.email === user()?.email && saved.start && saved.end ? saved : null;
    } catch { return null; }
  }
  async function loadPlan() {
    const selected = selectedPeriod();
    const query = new URLSearchParams({ today: todayISO() });
    if (selected) { query.set("start", selected.start); query.set("end", selected.end); }
    const r = await api("GET", "/api/plan?" + query);
    plan = r.plan; result = r.result;
    if (plan.start && plan.end) {
      localStorage.setItem("bb_period", JSON.stringify({ email: user().email, start: plan.start, end: plan.end }));
      incomeEntries = (await api("GET", "/api/income?" +
        new URLSearchParams({ start: plan.start, end: plan.end }))).income;
    } else {
      incomeEntries = [];
    }
  }
  async function loadPeriod(start, end) {
    try {
      const query = new URLSearchParams({ start, end, today: todayISO() });
      const [r, incomes] = await Promise.all([
        api("GET", "/api/plan?" + query),
        api("GET", "/api/income?" + new URLSearchParams({ start, end })),
      ]);
      plan = r.plan; result = r.result; incomeEntries = incomes.income;
      localStorage.setItem("bb_period", JSON.stringify({ email: user().email, start, end }));
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }
  // Saves one change. The server (Python) checks the rules (50/30/20 limits...) and returns true/false.
  function savePlan(next) {
    chain = chain.then(async () => {
      try {
        const r = await api("PUT", "/api/plan", { plan: next, today: todayISO() });
        plan = r.plan; result = r.result; return true;
      } catch (e) { alert(e.message); return false; }
    });
    return chain;
  }
 
  /* ---------- injected styles (your own CSS files are not touched) ---------- */
  function injectCSS() {
    const s = document.createElement("style");
    s.textContent = `
      .bb-has-icon input{padding-left:30px}
      .bb-has-icon label{left:30px}
      .bb-icon{position:absolute;left:2px;top:50%;transform:translateY(-50%);width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;color:var(--text-soft,#496b86);pointer-events:none}
      .bb-list{list-style:none;margin:0;padding:8px 14px;max-height:340px;overflow:auto}
      .bb-list li{display:flex;align-items:center;gap:8px;padding:10px 6px;border-bottom:1px solid #2b303a;font-size:14px}
      .bb-list .nm{flex:1;min-width:0;overflow-wrap:anywhere}
      .bb-minus{width:26px;height:26px;padding:0;border-radius:50%;border:1px solid #f97066;background:none;color:#f97066;font-size:18px;line-height:1;cursor:pointer}
      .bb-minus:hover{background:#f97066;color:#fff}
      .bb-total{padding:10px 20px;font-size:12px;color:#a8b0be;border-bottom:1px solid #2b303a}
      .bb-addspecific{display:block;width:calc(100% - 40px);margin:12px 20px 0;padding:9px;border-radius:12px;border:1px dashed #274258;background:none;color:#40c0e7;font:inherit;font-size:13px;cursor:pointer}
      .bb-addspecific:hover{background:#101f2c}
      .bb-income-btn{position:absolute;top:20px;right:22px;padding:8px 14px;border-radius:12px;border:1px solid #274258;background:#101f2c;color:#40c0e7;font:inherit;font-size:13px;cursor:pointer}
      .bb-income-btn:hover{filter:brightness(1.3)}
      .bb-income-btn:disabled{opacity:.55;cursor:not-allowed}
      .income-period-hint{margin:8px 0 0;color:#a8b0be;font-size:11px;line-height:1.5}
      .bb-logout{margin:14px 0 0;padding:7px 12px;border:1px solid rgba(255,255,255,.35);border-radius:9px;background:transparent;color:#fff;font:inherit;font-size:12px;cursor:pointer}
      .bb-logout:hover{background:rgba(255,255,255,.1)}
      .bb-app-error{margin:0 0 20px;padding:14px 16px;border:1px solid #fda29b;border-radius:12px;background:#fff1f0;color:#912018;font-size:13px}
      .bb-app-error button{margin-left:10px;border:0;background:transparent;color:inherit;font:inherit;font-weight:600;text-decoration:underline;cursor:pointer}
      .bb-reset-period{padding:8px 12px;border:1px solid #b42318;border-radius:10px;background:#fff;color:#b42318;font:inherit;font-size:12px;cursor:pointer}
      .bb-reset-period:hover{background:#fff1f0}
      .brand img{background:#fff;border-radius:12px;padding:3px;object-fit:contain}
      .bb-income-history{margin:20px 0;padding:20px 24px;border:1px solid #dfe3ea;border-radius:20px;background:#fff}
      .bb-income-history h2{margin:0 0 12px;font-size:18px}
      .bb-income-list{list-style:none;margin:0;padding:0}
      .bb-income-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #e4e7ec}
      .bb-income-row:last-child{border-bottom:0}
      .bb-income-edit{padding:5px 9px;border:1px solid #c5cad1;border-radius:8px;background:#fff;color:#344054;font:inherit;font-size:12px;cursor:pointer}
      .bb-income-edit:hover{background:#eef4fb}
      .bb-income-source{flex:1;min-width:0;font-size:14px}
      .bb-income-source small{display:block;color:#667085;font-size:11px}
      .bb-income-amount{font-variant-numeric:tabular-nums;font-weight:600}
      .bb-trend{margin:24px 0;padding:24px;border:1px solid #dfe3ea;border-radius:20px;background:#fff}
      .bb-trend-head{display:flex;justify-content:space-between;align-items:center;gap:12px}
      .bb-trend-head h2{margin:0;font-size:20px}
      .bb-trend-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:12px 0}
      .bb-trend-controls label{display:flex;align-items:center;gap:8px;font-size:12px}
      .bb-trend-controls input,.bb-trend-controls button{padding:7px 10px;border:1px solid #c5cad1;border-radius:8px;background:#fff;color:#182230;font:inherit}
      .bb-trend-controls button{cursor:pointer}
      .bb-trend-controls button:hover{background:#eef4fb}
      .bb-trend-summary{color:#596273;font-size:12px}
      .bb-trend-compare{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px}
      .bb-trend-compare label{display:flex;align-items:center;gap:6px}
      .bb-trend-compare select{padding:6px 8px;border:1px solid #c5cad1;border-radius:8px;background:#fff;font:inherit}
      .bb-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
      .bb-compare-result{min-height:20px;margin:8px 0;color:#344054;font-size:13px;font-weight:500}
      .bb-trend-chart{display:grid;grid-template-columns:repeat(6,minmax(56px,1fr));gap:12px;align-items:end;min-height:190px;padding:16px 0}
      .bb-trend-month{display:grid;grid-template-rows:140px auto;gap:8px;text-align:center;font-size:11px}
      .bb-trend-bars{display:flex;align-items:end;justify-content:center;gap:5px;border-bottom:1px solid #b9c1ce}
      .bb-trend-bar{width:24px;min-height:2px;border-radius:5px 5px 0 0}
      .bb-trend-bar.income{background:#112d60}.bb-trend-bar.expenses{background:#0d99ff}
      .bb-trend-legend{display:flex;justify-content:center;gap:16px;font-size:12px}
      .bb-trend-legend span::before{display:inline-block;width:9px;height:9px;margin-right:6px;border-radius:2px;background:#112d60;content:""}
      .bb-trend-legend .expenses::before{background:#0d99ff}
      .bb-dialog{border:0;border-radius:18px;padding:24px;width:min(92vw,400px);font-family:Poppins,Arial,sans-serif}
      .bb-dialog::backdrop{background:rgba(0,0,0,.45)}
      .bb-dialog h3{margin:0 0 10px;text-transform:capitalize}
      .bb-dialog [hidden]{display:none!important}
      .bb-dialog label{display:block;font-size:13px;margin-bottom:12px}
      .bb-dialog input{display:block;width:100%;margin-top:4px;padding:9px 10px;border:1px solid #b8bec8;border-radius:10px;font:inherit}
      .bb-hint{margin:0 0 12px;font-size:12px;color:#596273;line-height:1.5}
      .bb-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
      .bb-dialog .bb-chip{display:inline-block;margin:0;position:relative}
      .bb-dialog .bb-chip input{position:absolute;opacity:0;width:0;height:0;margin:0;padding:0;border:0}
      .bb-chip span{display:inline-block;padding:8px 14px;border:1px solid #b8bec8;border-radius:999px;font-size:13px;cursor:pointer;user-select:none}
      .bb-chip span:hover{background:#eef2f8}
      .bb-chip input:checked + span{background:#112d60;border-color:#112d60;color:#fff}
      .bb-chip input:focus-visible + span{outline:3px solid #40c0e7;outline-offset:2px}
      .bb-row{display:flex;justify-content:flex-end;gap:10px}
      .bb-row button{padding:9px 18px;border-radius:10px;border:1px solid #b8bec8;background:#fff;font:inherit;cursor:pointer}
      .bb-row .bb-primary{background:#112d60;color:#fff;border-color:#112d60}
      .bb-cal-nav{display:flex;align-items:center;gap:6px}
      .bb-cal-nav button{width:26px;height:26px;padding:0;border:1px solid #c5cad1;border-radius:8px;background:#fff;color:#112d60;font-size:16px;line-height:1;cursor:pointer}
      .calendar-grid span.bb-day{cursor:pointer}
      .calendar-grid span.bb-day:hover{background:#e3eaf5}
      .bb-readonly .calendar-grid span.bb-day{cursor:default}
      .calendar-grid span.bb-in{background:#d4ecf8}
      .calendar-grid span.bb-edge{background:#40c0e7;color:#08243b;font-weight:600}
      .calendar-grid span.today{box-shadow:inset 0 0 0 2px #112d60}
      .bb-item-row th{padding:12px 12px 12px 44px!important;font-size:15px!important;color:#d9dfea}
      .bb-item-row td{padding:12px!important;font-size:15px!important}
      .bb-cell{width:100%;padding:6px 8px;border:1px solid #274258;border-radius:8px;background:#101f2c;color:#fff;font:inherit;font-size:14px;text-align:left}
      .bb-cell:focus{outline:2px solid #40c0e7}
      .bb-reco{margin-top:28px}
      .bb-reco h2{margin:0 0 6px;font-size:22px}
      .bb-stats{margin:0 0 14px;color:#596273;font-size:12px;line-height:1.7}
      .bb-reco-item{padding:14px 18px;margin-bottom:12px;border-radius:16px;background:#fff;border:1px solid #dfe3ea;border-left:6px solid #175cd3}
      .bb-reco-item.danger{border-left-color:#b42318}.bb-reco-item.warning{border-left-color:#b54708}.bb-reco-item.good{border-left-color:#167048}
      .bb-reco-item h3{margin:0 0 4px;font-size:15px}.bb-reco-item p{margin:0;font-size:13px;line-height:1.6;color:#344054}`;
    document.head.appendChild(s);
    let l = $("link[rel='icon']");
    if (!l) { l = document.createElement("link"); l.rel = "icon"; document.head.appendChild(l); }
    l.href = LOGO_MARK;
  }
 
  /* ---------- login + sign up ---------- */
  const ICONS = {
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  };
  function addIcons() {                       // small icons inside the input fields
    $$(".input-wrap").forEach(w => {
      const input = $("input", w); if (!input) return;
      const kind = input.type === "email" ? "mail" : input.type === "password" ? "lock" : "user";
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("class", "bb-icon"); svg.setAttribute("aria-hidden", "true");
      svg.innerHTML = ICONS[kind];
      w.classList.add("bb-has-icon"); w.prepend(svg);
    });
  }
 
  function initLogin() {
    const form = $(".login-form");
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const btn = $(".login-btn", form); btn.disabled = true;
      try {
        setSession(await api("POST", "/api/login", { email: $("#email").value.trim(), password: $("#password").value }, false));
        location.href = "dashboard.html";
      } catch (err) { alert(err.message); } finally { btn.disabled = false; }
    });
  }
 
  function initSignup() {
    const form = $(".login-form");
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const pw = $("#password").value;
      if (!(pw.length >= 8 && /[A-Z]/.test(pw) && /\d/.test(pw) && /[@$!%*?&]/.test(pw)))
        return alert("Password needs 8+ characters, an uppercase letter, a number and one of @$!%*?&");
      if (pw !== $("#confirm-password").value) return alert("Passwords do not match.");
      const btn = $(".login-btn", form); btn.disabled = true;
      try {
        // the server saves the account AND signs the user in, so we go straight to the dashboard
        setSession(await api("POST", "/api/signup", { name: $("#username").value.trim(), email: $("#email").value.trim(), password: pw }, false));
        location.href = "dashboard.html";
      } catch (err) { alert(err.message); } finally { btn.disabled = false; }
    });
  }
 
  /* ---------- shared dashboard bits ---------- */
  function shell() {
    const u = user();
    if (!u || !token()) { location.href = "index.html"; return false; }
    $$(".brand img").forEach(i => { i.src = LOGO_MARK; i.alt = "BudgetBuddy logo"; });
    $$('a[href="./index.html"]').forEach(a => a.setAttribute("href", "dashboard.html"));
    const nm = $(".profile-name"), em = $(".profile-email"), av = $(".avatar");
    if (nm) nm.textContent = u.name;
    if (em) em.textContent = u.email;
    if (av) av.textContent = u.name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");
    const logout = document.createElement("button");
    logout.type = "button";
    logout.className = "bb-logout";
    logout.textContent = "Sign out";
    logout.addEventListener("click", () => {
      localStorage.removeItem("bb_token");
      localStorage.removeItem("bb_user");
      localStorage.removeItem("bb_period");
      location.replace("/");
    });
    em?.parentElement.append(logout);
    return true;
  }
  function showAppError(message) {
    const banner = document.createElement("p");
    banner.className = "bb-app-error";
    banner.setAttribute("role", "alert");
    banner.append(document.createTextNode(`Could not load your budget: ${message}`));
    const retry = document.createElement("button");
    retry.type = "button";
    retry.textContent = "Retry";
    retry.addEventListener("click", () => location.reload());
    banner.append(retry);
    $(".page-header")?.insertAdjacentElement("afterend", banner);
  }
  function periodLabel() {
    const l = $(".month-label");
    if (l) {
      if (!plan.start || !plan.end) l.textContent = "Choose a budget period";
      else {
        const status = plan.end < todayISO() ? " \u00b7 Past period"
          : plan.start > todayISO() ? " \u00b7 Upcoming period" : "";
        l.textContent = fmtRange(plan.start, plan.end) + status;
      }
    }
    const reset = $(".bb-reset-period");
    if (reset) reset.hidden = !plan.start || !plan.end || !plan.items.length;
  }

  // Select a date range; changing it loads that period without modifying another period's data.
  function initCalendar(editable, onPick) {
    const box = $(".calendar"); if (!box) return () => {};
    const grid = $(".calendar-grid", box), h2 = $(".calendar-heading h2", box), badge = $(".calendar-badge", box);
    const nav = document.createElement("div"); nav.className = "bb-cal-nav";
    const mk = (t, label) => { const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.setAttribute("aria-label", label); return b; };
    const prev = mk("\u2039", "Previous month"), next = mk("\u203a", "Next month");
    h2.before(nav); nav.append(prev, h2, next);
    box.classList.toggle("bb-readonly", !editable);
    let [vy, vm] = parts(plan.start || todayISO());
    let pending = null;                         // first click, waiting for the end date
 
    function draw() {
      h2.textContent = `${MONTHS[vm - 1]} ${vy}`;
      const today = todayISO(), a = plan.start, b = plan.end;
      const offset = (new Date(vy, vm - 1, 1).getDay() + 6) % 7, dim = new Date(vy, vm, 0).getDate();
      const frag = document.createDocumentFragment();
      ["M", "T", "W", "T", "F", "S", "S"].forEach(l => { const s = document.createElement("span"); s.className = "weekday"; s.textContent = l; frag.append(s); });
      for (let i = 0; i < offset; i++) frag.append(document.createElement("span"));
      for (let d = 1; d <= dim; d++) {
        const ds = `${vy}-${pad(vm)}-${pad(d)}`, s = document.createElement("span");
        s.className = "bb-day"; s.textContent = d; s.dataset.date = ds;
        if (ds === today) { s.classList.add("today"); s.setAttribute("aria-current", "date"); }
        if (pending) { if (ds === pending) s.classList.add("bb-edge"); }
        else if (a && b && ds >= a && ds <= b) { s.classList.add("bb-in"); if (ds === a || ds === b) s.classList.add("bb-edge"); }
        frag.append(s);
      }
      grid.replaceChildren(frag);
      badge.textContent = pending ? "Now pick the end date"
        : (a && b ? `${fmtDay(a)} \u2013 ${fmtDay(b)} \u00b7 ${nDays(a, b)} days` : (editable ? "Pick a start date" : "No dates picked"));
    }
    prev.addEventListener("click", () => { if (--vm < 1) { vm = 12; vy--; } draw(); });
    next.addEventListener("click", () => { if (++vm > 12) { vm = 1; vy++; } draw(); });
    if (editable) grid.addEventListener("click", async e => {
      const t = e.target.closest(".bb-day"); if (!t) return;
      if (!pending) { pending = t.dataset.date; draw(); return; }
      let x = pending, y = t.dataset.date; if (y < x) [x, y] = [y, x];
      pending = null;
      await onPick(x, y);
      draw();
    });
    draw();
    return draw;
  }
 
  function renderReco(res, anchor) {
    $$(".bb-reco").forEach(x => x.remove());
    const m = res.metrics, box = document.createElement("section"); box.className = "bb-reco";
    const h = document.createElement("h2"); h.textContent = "Recommendations for you"; box.append(h);
    if (res.period.set && res.entered_any) {
      const st = document.createElement("p"); st.className = "bb-stats";
      if (res.period.start > res.period.today) {
        st.textContent = "This period has not started; actuals will be included when its dates begin.";
      } else {
        st.textContent = `Daily average in period ${peso(m.daily_average)} \u00b7 Last 7 period days ${peso(m.last_7_days)}`;
        if (res.period.active && res.period.days_left > 0 && res.period.elapsed > 0) {
          st.textContent += ` \u00b7 Projected spending ${peso(m.projected_spending)} \u00b7 ` +
            `Daily spending room ${peso(m.daily_allowance)}`;
        }
      }
      box.append(st);
    }
    res.recommendations.forEach(r => {
      const a = document.createElement("article"); a.className = "bb-reco-item " + r.level;
      const t = document.createElement("h3"); t.textContent = r.title;
      const p = document.createElement("p"); p.textContent = r.message;
      a.append(t, p); box.appendChild(a);
    });
    anchor.insertAdjacentElement("afterend", box);
  }
 
  /* ---------- dialogs ---------- */
  const ROW = `<div class="bb-row"><button value="cancel" formnovalidate>Cancel</button><button value="ok" class="bb-primary">Save</button></div>`;
  function dialog(html, read, setup) {
    return new Promise(resolve => {
      const dlg = document.createElement("dialog"); dlg.className = "bb-dialog";
      dlg.innerHTML = html; document.body.appendChild(dlg);
      dlg.addEventListener("close", () => {
        const ok = dlg.returnValue === "ok", f = new FormData($("form", dlg));
        dlg.remove(); resolve(ok ? read(f) : null);
      });
      if (setup) setup(dlg);
      dlg.showModal();
    });
  }
  // The choices are shown directly as buttons: just click one (no "choose from the list" box, no day field).
  function askItem(cat, hint, used, startOther) {
    const taken = new Set(used.map(n => n.toLowerCase()));
    const names = PRESETS[cat].filter(n => !taken.has(n.toLowerCase()));
    return dialog(`<form method="dialog"><h3>Add ${cat}</h3><p class="bb-hint"></p>
      <div class="bb-chips" role="radiogroup" aria-label="Choose an item"></div>
      <label class="bb-other" hidden>Name of the item<input name="name" maxlength="60"></label>
      <label>Budget amount (\u20b1)<input name="amount" type="number" min="0.01" max="${hint.remaining}" step="0.01" required></label>
      ${ROW}</form>`,
      f => {
        const other = f.get("preset") === "__other";
        return { name: String(other ? f.get("name") : f.get("preset")).trim(), amount: Number(f.get("amount")) };
      },
      dlg => {
        $(".bb-hint", dlg).textContent = `You can still budget ${peso(hint.remaining, 2)} of your ${peso(hint.limit, 2)} ${cat} limit (${hint.ratio}% of your income).`;
        const box = $(".bb-chips", dlg), other = $(".bb-other", dlg), nameInp = $("input[name=name]", dlg), amount = $("input[name=amount]", dlg);
        [...names, "__other"].forEach((n, i) => {
          const label = document.createElement("label"); label.className = "bb-chip";
          const radio = document.createElement("input"); radio.type = "radio"; radio.name = "preset"; radio.value = n; radio.required = i === 0;
          const text = document.createElement("span"); text.textContent = n === "__other" ? "+ Add specific item" : n;
          label.append(radio, text); box.append(label);
          radio.addEventListener("change", () => {
            const o = n === "__other"; other.hidden = !o; nameInp.required = o; (o ? nameInp : amount).focus();
          });
        });
        if (startOther) { const r = $('input[value="__other"]', box); r.checked = true; r.dispatchEvent(new Event("change")); }
      });
  }
  function askIncome(existing = null) {
    const initialDate = existing ? existing.date
      : todayISO() < plan.start ? plan.start : todayISO() > plan.end ? plan.end : todayISO();
    return dialog(`<form method="dialog"><h3>${existing ? "Edit" : "Add"} income</h3>
      <p class="bb-hint">This income is recorded on one date and included in the selected period (${fmtRange(plan.start, plan.end)}) when that date falls within it. Choose any date in the selected period.</p>
      <label>Source<input name="source" maxlength="80" placeholder="Paycheck, allowance, etc."></label>
      <label>Date<input name="date" type="date" min="${plan.start}" max="${plan.end}" value="${initialDate}" required></label>
      <label>Amount (\u20b1)<input name="amount" type="number" min="0.01" max="1000000000" step="0.01" required></label>
      ${ROW}</form>`, f => ({
        source: String(f.get("source")).trim(),
        date: String(f.get("date")),
        amount: Number(f.get("amount")),
      }), dlg => {
        if (!existing) return;
        $('input[name="source"]', dlg).value = existing.source;
        $('input[name="date"]', dlg).value = existing.date;
        $('input[name="amount"]', dlg).value = Number(existing.amount).toFixed(2);
      });
  }
 
  /* ---------- dashboard page ---------- */
  function initDashboard() {
    const cards = $$(".budget-card");
    const [incCard, balCard] = $$(".summary-card");
    const incAmt = $(".amount", incCard), balAmt = $(".amount", balCard);
    incCard.style.position = "relative";
    const incBtn = $(".bb-income-btn", incCard);
    const incomeHistory = document.createElement("section");
    incomeHistory.className = "bb-income-history";
    incomeHistory.innerHTML = '<h2>Income received in this period</h2><ul class="bb-income-list"></ul>';
    $(".summary").insertAdjacentElement("afterend", incomeHistory);
 
    const redrawCal = initCalendar(true, async (a, b) => { if (await loadPeriod(a, b)) render(); });
    addPeriodReset(async () => { if (await resetPeriod()) render(); });
 
    function render() {
      incAmt.textContent = peso(plan.income, 2, " ");
      balAmt.textContent = peso(result.totals.balance, 2, " ");
      incBtn.textContent = "+ Add income";
      incBtn.disabled = !plan.start || !plan.end;
      incBtn.title = incBtn.disabled ? "Choose a date range to add income" : "Add a dated income entry";
      $(".income-period-hint", incCard).hidden = Boolean(plan.start && plan.end);
      periodLabel(); redrawCal();
      const incomeList = $(".bb-income-list", incomeHistory);
      incomeList.replaceChildren(...incomeEntries.map(entry => {
        const li = document.createElement("li"); li.className = "bb-income-row";
        const label = document.createElement("span"); label.className = "bb-income-source";
        label.textContent = entry.source;
        const day = document.createElement("small"); day.textContent = fmtDay(entry.date) + ", " + parts(entry.date)[0];
        label.append(day);
        const amount = document.createElement("span"); amount.className = "bb-income-amount";
        amount.textContent = peso(entry.amount, 2);
        const edit = document.createElement("button"); edit.type = "button";
        edit.className = "bb-income-edit"; edit.textContent = "Edit";
        edit.setAttribute("aria-label", "Edit income from " + entry.source);
        edit.addEventListener("click", async () => {
          const updated = await askIncome(entry);
          if (!updated) return;
          try {
            await api("PUT", "/api/income/" + entry.id, { ...updated, start: plan.start, end: plan.end });
            if (await loadPeriod(plan.start, plan.end)) render();
          } catch (error) { alert(error.message); }
        });
        const remove = document.createElement("button"); remove.type = "button";
        remove.className = "bb-minus"; remove.textContent = "\u2212";
        remove.setAttribute("aria-label", "Remove income from " + entry.source);
        remove.addEventListener("click", async () => {
          if (!confirm(`Delete the ${peso(entry.amount, 2)} income entry "${entry.source}"? Actual expenses are stored separately and will not be deleted.`))
            return;
          try {
            await api("DELETE", "/api/income/" + entry.id);
            if (await loadPeriod(plan.start, plan.end)) render();
          } catch (error) { alert(error.message); }
        });
        li.append(label, amount, edit, remove);
        return li;
      }));
      if (!incomeEntries.length) {
        const empty = document.createElement("li"); empty.className = "bb-hint";
        empty.textContent = plan.start ? "No income entries in this date range yet." : "Choose a date range to record income.";
        incomeList.append(empty);
      }
      cards.forEach(card => {
        const cat = $("h3", card).textContent.trim().toLowerCase(), c = result.categories[cat];
        let t = $(".bb-total", card);
        if (!t) { t = document.createElement("div"); t.className = "bb-total"; $(".budget-header", card).after(t); }
        t.textContent = `Budgeted ${peso(c.budget, 2)} of ${peso(c.limit, 2)} limit (${c.ratio}%)`;
        t.style.color = c.limit > 0 && c.budget >= c.limit ? "#6ce9a6" : "#a8b0be";
        let ul = $(".bb-list", card);
        if (!ul) { ul = document.createElement("ul"); ul.className = "bb-list"; card.appendChild(ul); }
        const mine = plan.items.filter(i => i.category === cat);
        $(".empty-state", card).style.display = mine.length ? "none" : "";
        ul.replaceChildren(...mine.map(i => {
          const li = document.createElement("li");
          const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = i.name;
          const am = document.createElement("span"); am.textContent = peso(i.budget, 2);
          const x = document.createElement("button");
          x.type = "button"; x.className = "bb-minus"; x.textContent = "\u2212"; x.dataset.id = i.id;
          x.title = "Remove this item"; x.setAttribute("aria-label", "Remove " + i.name);
          li.append(nm, am, x); return li;
        }));
      });
    }
 
    async function addIncome() {
      if (!plan.start || !plan.end) {
        alert("Choose a budget period on the calendar before entering its income.");
        return;
      }
      const entry = await askIncome();
      if (!entry) return;
      try {
        await api("POST", "/api/income", { ...entry, start: plan.start, end: plan.end });
        if (await loadPeriod(plan.start, plan.end)) render();
      } catch (error) { alert(error.message); }
    }
    incBtn.addEventListener("click", addIncome);
 
    async function addTo(cat, startOther) {
      if (!plan.start || !plan.end)
        return alert("Please pick this budget period on the calendar first: click a start date, then an end date.");
      if (plan.income <= 0) {
        alert("Please set the income available for this period first.");
        await addIncome();
        if (plan.income <= 0) return;
      }
      const c = result.categories[cat], remaining = r2(c.limit - c.budget);
      if (remaining < 0.01)
        return alert(`${cap(cat)} is fully budgeted (limit ${peso(c.limit, 2)}). Lower another ${cat} item first.`);
      const v = await askItem(cat, { remaining, limit: c.limit, ratio: c.ratio }, plan.items.filter(i => i.category === cat).map(i => i.name), startOther);
      if (!v) return;
      if (!v.name) return alert("Please enter a name.");
      const item = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), category: cat, name: v.name, budget: v.amount, log: [] };
      if (await savePlan({ ...plan, items: [...plan.items, item] })) render();
    }
 
    cards.forEach(card => {
      const cat = $("h3", card).textContent.trim().toLowerCase();
      $(".add-button", card).addEventListener("click", () => addTo(cat, false));
      const sp = document.createElement("button");
      sp.type = "button"; sp.className = "bb-addspecific"; sp.textContent = "+ Add specific item";
      $(".budget-header", card).after(sp);
      sp.addEventListener("click", () => addTo(cat, true));
      card.addEventListener("click", async e => {
        const id = e.target.dataset && e.target.dataset.id;
        if (id && await savePlan({ ...plan, items: plan.items.filter(i => i.id !== id) })) render();
      });
    });
 
    $(".submit-button").addEventListener("click", () => {
      if (!plan.start || !plan.end) return alert("Pick your budget dates on the calendar first.");
      if (plan.income <= 0) return alert("Set the income for this period first.");
      if (!plan.items.length) return alert("Add at least one item first.");
      location.href = "dashboard2.html";
    });
    render();
  }
 
  /* ---------- Expenses Tracker page ---------- */
  function addLog(log, entry) {                 // merge entries of the same day so the list stays short
    const m = new Map();
    [...log, entry].forEach(e => m.set(e.date, r2((m.get(e.date) || 0) + e.amount)));
    return [...m].map(([date, amount]) => ({ date, amount }));
  }
 
  function initTracker() {
    const redrawCal = initCalendar(true, async (a, b) => { if (await loadPeriod(a, b)) render(); });
    addPeriodReset(async () => { if (await resetPeriod()) render(); });
    const GREEN = "#6ce9a6", RED = "#f97066", NEUTRAL = "#f8fafc", money = n => peso(n, 2);
    const catRows = $$(".expense-table tbody tr");
    const baseDesc = catRows.map(r => $(".category-description", r).textContent.trim());
 
    // Left stays "-" until an Actual has been entered.
    function leftCell(td, budget, actual, entered) {
      if (!entered) { td.textContent = "\u2014"; td.style.color = NEUTRAL; return; }
      const left = r2(budget - actual);
      td.textContent = money(left);
      if (actual === 0) td.style.color = NEUTRAL;
      else td.style.color = left > 0 ? GREEN : RED;
    }
    function cellInput(value, label, onCommit, commitOnEnter = false) {
      const inp = document.createElement("input");
      inp.type = "number"; inp.className = "bb-cell"; inp.min = "0"; inp.step = "0.01"; inp.max = "1000000000";
      inp.value = Number(value).toFixed(2); inp.setAttribute("aria-label", label);
      inp.addEventListener("focus", () => inp.select());
      if (commitOnEnter) inp.addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
      });
      inp.addEventListener("change", () => {
        const v = Number(inp.value);
        if (inp.value === "" || !Number.isFinite(v) || v < 0) { alert("Please enter an amount of 0 or more."); render(); return; }
        onCommit(r2(v));
      });
      return inp;
    }
    async function editBudget(it, v) {          // the server refuses anything over the 50/30/20 limit
      if (v !== it.budget) await savePlan({ ...plan, items: plan.items.map(i => i.id === it.id ? { ...i, budget: v } : i) });
      render();
    }
    async function addActual(it, amount) {
      if (!plan.start || !plan.end) {
        alert("Select a date range before entering actual amounts.");
        render();
        return;
      }
      const currentDay = todayISO();
      const entryDay = currentDay < plan.start ? plan.start : currentDay > plan.end ? plan.end : currentDay;
      const entry = { date: entryDay, amount };
      await savePlan({ ...plan, items: plan.items.map(i => i.id === it.id ? { ...i, log: addLog(i.log, entry) } : i) });
      render();
    }
 
    function render() {
      const res = result;
      $$(".bb-item-row").forEach(r => r.remove());
      CATS.forEach((cat, i) => {
        const row = catRows[i], c = res.categories[cat], cells = $$("td", row);
        cells[0].textContent = money(c.budget); cells[1].textContent = money(c.actual);
        leftCell(cells[2], c.budget, c.actual, c.entered);
        $(".category-description", row).textContent = `${baseDesc[i]} \u00b7 Limit ${money(c.limit)} (${c.ratio}%)`;
        let anchor = row;
        c.items.forEach(it => {                 // the items chosen on the dashboard, under their category
          const tr = document.createElement("tr"); tr.className = "bb-item-row";
          const th = document.createElement("th"); th.scope = "row"; th.textContent = it.name;
          const tdB = document.createElement("td"); tdB.className = "number"; tdB.append(cellInput(it.budget, `${it.name} budget`, v => editBudget(it, v)));
          const tdA = document.createElement("td"); tdA.className = "number";
          tdA.append(cellInput(it.actual, `Enter an additional actual amount for ${it.name}; current period total ${money(it.actual)}`, v => addActual(it, v), true));
          const tdL = document.createElement("td"); tdL.className = "number";
          leftCell(tdL, it.budget, it.actual, it.entered);
          tr.append(th, tdB, tdA, tdL); anchor.after(tr); anchor = tr;
        });
      });
      const t = res.totals, tf = $$(".expense-table tfoot td");
      tf[0].textContent = money(t.budget); tf[1].textContent = money(t.actual);
      leftCell(tf[2], t.budget, t.actual, res.entered_any);
      const a = $$(".summary-card .amount");
      if (a[0]) a[0].textContent = peso(res.income, 2, " ");
      if (a[1]) a[1].textContent = peso(t.balance, 2, " ");
      const note = $("#table-note");
      if (note) note.textContent = `Edit a Budget value to replace it. To record an Actual, type the new expense amount and press Enter; it is added to the displayed period total. Actuals are saved only to this selected period. ` +
        `Limits are ${money(res.categories.needs.limit)} (50%) for needs, ${money(res.categories.wants.limit)} (30%) for wants and ${money(res.categories.savings.limit)} (20%) for savings, based on this period's income. Left appears after you enter an Actual.`;
      periodLabel(); redrawCal();
      renderReco(res, $(".tracker"));
    }
    render();
  }
 
  /* ---------- Analytics page ---------- */
  function initAnalytics() {
    const redrawCal = initCalendar(true, async (a, b) => { if (await loadPeriod(a, b)) render(); });
    addPeriodReset(async () => { if (await resetPeriod()) render(); });
    const shiftMonth = (month, offset) => {
      const [year, monthNumber] = month.split("-").map(Number);
      const index = year * 12 + monthNumber - 1 + offset;
      const shiftedYear = Math.floor(index / 12);
      return `${shiftedYear}-${pad(index - shiftedYear * 12 + 1)}`;
    };
    const latestStart = shiftMonth(todayISO().slice(0, 7), -5);
    const previousStart = shiftMonth(latestStart, -6);
    const trend = document.createElement("section");
    trend.className = "bb-trend";
    trend.innerHTML = `
      <div class="bb-trend-head">
        <h2>Monthly cash flow</h2>
      </div>
      <div class="bb-trend-controls">
        <label>Six-month period starts
          <input class="bb-trend-start" type="month" max="${latestStart}" aria-label="First month of the six-month analysis period">
        </label>
        <button class="bb-trend-last" type="button">Last 6 months</button>
        <button class="bb-trend-previous" type="button">Previous 6 months</button>
      </div>
      <p class="bb-hint">The chart shows the selected month and the next five calendar months. The current month is month-to-date; savings are tracked separately below.</p>
      <p class="bb-trend-summary"></p>
      <div class="bb-trend-compare">
        <span>Compare needs and wants spending:</span>
        <label><span class="bb-sr-only">First month</span><select class="bb-compare-from" aria-label="First month to compare"></select></label>
        <span>to</span>
        <label><span class="bb-sr-only">Second month</span><select class="bb-compare-to" aria-label="Second month to compare"></select></label>
      </div>
      <p class="bb-compare-result" aria-live="polite"></p>
      <div class="bb-trend-chart" role="img" aria-label="Monthly income and expenses"></div>
      <div class="bb-trend-legend"><span>Income</span><span class="expenses">Needs + wants expenses</span></div>`;
    $(".chart-card").insertAdjacentElement("afterend", trend);
    const monthInput = $(".bb-trend-start", trend);
    monthInput.value = latestStart;
    let trendRequest = 0;
    async function loadTrend(startMonth) {
      const requestId = ++trendRequest;
      try {
        const data = await api("GET", "/api/analytics?" + new URLSearchParams({ start_month: startMonth }));
        if (requestId !== trendRequest) return;
        const max = Math.max(1, ...data.months.flatMap(month => [month.income, month.expenses]));
        const from = $(".bb-compare-from", trend), to = $(".bb-compare-to", trend);
        const selectedFrom = from.value, selectedTo = to.value;
        [from, to].forEach(select => {
          select.replaceChildren(...data.months.map(month => {
            const option = document.createElement("option");
            option.value = month.key; option.textContent = month.label;
            return option;
          }));
        });
        from.value = data.months.some(month => month.key === selectedFrom)
          ? selectedFrom : data.months[Math.max(0, data.months.length - 2)].key;
        to.value = data.months.some(month => month.key === selectedTo)
          ? selectedTo : data.months[data.months.length - 1].key;
        const updateComparison = () => {
          const a = data.months.find(month => month.key === from.value);
          const b = data.months.find(month => month.key === to.value);
          if (!a || !b) return;
          const difference = r2(b.expenses - a.expenses);
          const percent = a.expenses ? Math.abs(difference) / a.expenses * 100 : null;
          const direction = difference > 0 ? "increased" : difference < 0 ? "decreased" : "stayed the same";
          $(".bb-compare-result", trend).textContent = a.key === b.key
            ? `Select two different months to compare expenses.`
            : `Needs and wants expenses ${direction} from ${a.label} to ${b.label} by ${peso(Math.abs(difference), 2)}` +
              (percent === null ? (difference ? "; there was no spending in the first month." : ".")
                : ` (${percent.toFixed(1)}%).`);
        };
        from.onchange = updateComparison; to.onchange = updateComparison;
        updateComparison();
        const chart = $(".bb-trend-chart", trend);
        chart.style.gridTemplateColumns = `repeat(${data.months.length}, minmax(56px, 1fr))`;
        chart.replaceChildren(...data.months.map(month => {
          const column = document.createElement("div"); column.className = "bb-trend-month";
          const bars = document.createElement("div"); bars.className = "bb-trend-bars";
          [["income", month.income], ["expenses", month.expenses]].forEach(([kind, value]) => {
            const bar = document.createElement("span"); bar.className = "bb-trend-bar " + kind;
            bar.style.height = Math.max(value > 0 ? 3 : 0, value / max * 100) + "%";
            bar.title = `${kind === "income" ? "Income" : "Expenses"}: ${peso(value, 2)}`;
            bars.append(bar);
          });
          const label = document.createElement("span");
          label.textContent = month.label.split(" ")[0].slice(0, 3);
          label.title = month.label;
          column.append(bars, label);
          return column;
        }));
        $(".bb-trend-summary", trend).textContent =
          `${data.months[0].label} to ${data.months[data.months.length - 1].label} · Six-month average: income ${peso(data.averages.income, 2)} per month and needs plus wants spending ${peso(data.averages.expenses, 2)} per month.`;
      } catch (error) {
        if (requestId === trendRequest) alert(error.message);
      }
    }
    monthInput.addEventListener("change", () => {
      if (monthInput.value) loadTrend(monthInput.value);
    });
    $(".bb-trend-last", trend).addEventListener("click", () => {
      monthInput.value = latestStart;
      loadTrend(latestStart);
    });
    $(".bb-trend-previous", trend).addEventListener("click", () => {
      monthInput.value = previousStart;
      loadTrend(previousStart);
    });
    loadTrend(latestStart);
    function render() {
      const res = result, C = res.categories;
      const maxV = Math.max(4000, ...CATS.flatMap(c => [C[c].budget, C[c].actual]));
      const mag = Math.pow(10, Math.floor(Math.log10(maxV)));
      const top = Math.ceil(maxV * 1.1 / mag) * mag;
      $$(".tick").forEach((t, i) => { t.textContent = peso(top * (1 - i / 4)); });
      $$(".bar-pair").forEach((pair, i) => {
        const v = C[CATS[i]];
        [["budget", v.budget], ["actual", v.actual]].forEach(([k, val]) => {
          const bar = $(".bar." + k, pair);
          bar.style.setProperty("--height", (val / top * 100) + "%");
          $(".bar-value", bar).textContent = peso(val);
        });
      });
      $(".plot").setAttribute("aria-label", CATS.map(c => `${c}: budget ${C[c].budget} pesos, actual ${C[c].actual} pesos.`).join(" "));
      $$(".insight").forEach((box, i) => {
        const c = CATS[i], v = C[c], p = $("p", box), s = $("small", box);
        let cls = "", text;
        if (!v.entered) text = "No actual entered yet";
        else if (c === "savings") {
          const diff = r2(v.actual - v.budget);
          text = diff === 0 ? "Target reached" : diff > 0 ? `${peso(diff)} above target` : `${peso(-diff)} short of target`;
          cls = diff >= 0 ? "positive" : "warning";
        } else {
          text = v.left === 0 ? "Exactly on budget" : v.left > 0 ? `${peso(v.left)} below budget` : `${peso(-v.left)} over budget`;
          cls = v.left >= 0 ? "positive" : "warning";
        }
        p.textContent = text; p.className = cls;
        s.textContent = c === "savings" ? `Target ${peso(v.budget)} \u00b7 Saved ${peso(v.actual)}` : `Budget ${peso(v.budget)} \u00b7 Actual ${peso(v.actual)}`;
      });
      periodLabel(); redrawCal();
      renderReco(res, $(".insights"));
    }
    render();
  }

  function addPeriodReset(onReset) {
    const header = $(".page-header"), label = $(".month-label");
    if (!header || !label) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "bb-reset-period";
    button.textContent = "Reset this period";
    button.hidden = !plan.start || !plan.end || !plan.items.length;
    button.addEventListener("click", onReset);
    label.insertAdjacentElement("afterend", button);
  }

  async function resetPeriod() {
    if (!plan.start || !plan.end) return false;
    if (!confirm(`This will permanently clear budget items and actual entries for ${fmtRange(plan.start, plan.end)}. Dated income entries are kept and remain available to other date ranges.`))
      return false;
    try {
      const query = new URLSearchParams({ start: plan.start, end: plan.end });
      const r = await api("DELETE", "/api/plan?" + query);
      plan = r.plan; result = r.result;
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }
 
  /* ---------- start ---------- */
  document.addEventListener("DOMContentLoaded", async () => {
    injectCSS();
    if ($(".login-form")) { addIcons(); $("#username") ? initSignup() : initLogin(); return; }
    if (!$(".sidebar") || !shell()) return;
    try { await loadPlan(); } catch (e) { if (e.message !== "Please log in again.") showAppError(e.message); return; }
    periodLabel();
    if ($(".budgets")) initDashboard();
    else if ($(".expense-table")) initTracker();
    else if ($(".chart-card")) initAnalytics();
  });
})();