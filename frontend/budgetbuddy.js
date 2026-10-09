(() => {
  "use strict";
  // Same-origin by default (works on localhost:5000 AND on Render). Only VS Code Live Server (port 5500) needs the full URL.
  const API = location.port === "5500" ? "http://127.0.0.1:5000" : "";
  const LOGO_FULL = "logo.png";        // ant + BudgetBuddy text (login / sign up)
  const LOGO_MARK = "logo-mark.png";   // ant only (sidebar + browser tab icon)
  const MONTHS = ["january","february","march","april","may","june","july","august","september","october","november","december"];
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const store = {
    get(k, d = null) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { localStorage.setItem(k, JSON.stringify(v)); },
  };
  const r2 = n => Math.round(n * 100) / 100;
  const peso = (n, d = "auto", sp = "") => {
    const dec = d === "auto" ? (Number.isInteger(n) ? 0 : 2) : d;
    return (n < 0 ? "-" : "") + "\u20b1" + sp + Math.abs(n).toLocaleString("en-PH", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  };
 
  async function api(path, body) {
    let res;
    try {
      res = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } catch { throw new Error("Cannot reach the BudgetBuddy server. Is app.py running?"); }
    let data = {};
    try { data = await res.json(); } catch { /* ignore */ }
    if (!data.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  }
 
  /* ---------- state ---------- */
  const user = () => store.get("bb_user");
  const dataKey = () => "bb_data_" + (user() ? user().email : "guest");
  const load = () => store.get(dataKey(), { income: 0, items: [] });
  const save = d => store.set(dataKey(), d);
 
  function period() {
    const now = new Date(), lbl = $(".month-label");
    let y = now.getFullYear(), m = now.getMonth() + 1;
    if (lbl) {
      const t = lbl.textContent.trim().split(/\s+/), i = MONTHS.indexOf((t[0] || "").toLowerCase());
      if (i >= 0 && +t[1]) { m = i + 1; y = +t[1]; }
    }
    const dim = new Date(y, m, 0).getDate();
    let today = now.getDate();
    if (y !== now.getFullYear() || m !== now.getMonth() + 1)
      today = y * 12 + m < now.getFullYear() * 12 + now.getMonth() + 1 ? dim : 1;
    return { year: y, month: m, today, dim };
  }
 
  async function calculate(data) {
    const d = data || load(), p = period();
    const res = await api("/api/calculate", { year: p.year, month: p.month, today: p.today, income: d.income, items: d.items });
    if (!data) store.set("bb_result", res);
    return res;
  }
 
  /* ---------- shared look ---------- */
  function injectCSS() {
    const s = document.createElement("style");
    s.textContent = `
      .bb-logo{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:12px}
      .bb-logo img{width:min(70%,230px);height:auto}
      .brand img{background:#fff;border-radius:12px;padding:3px;object-fit:contain}
      .bb-list{list-style:none;margin:0;padding:8px 14px;max-height:340px;overflow:auto}
      .bb-list li{display:flex;align-items:center;gap:8px;padding:10px 6px;border-bottom:1px solid #2b303a;font-size:14px}
      .bb-list .nm{flex:1;min-width:0;overflow-wrap:anywhere}
      .bb-list small{color:#a8b0be}
      .bb-minus{width:26px;height:26px;padding:0;border-radius:50%;border:1px solid #f97066;background:none;color:#f97066;font-size:18px;line-height:1;cursor:pointer}
      .bb-minus:hover{background:#f97066;color:#fff}
      .bb-addspecific{display:block;width:calc(100% - 40px);margin:12px 20px 0;padding:9px;border-radius:12px;border:1px dashed #274258;background:none;color:#40c0e7;font:inherit;font-size:13px;cursor:pointer}
      .bb-addspecific:hover{background:#101f2c}
      .bb-removeopt{border:0;background:none;color:#b42318;font:inherit;font-size:12px;cursor:pointer;margin:-6px 0 10px;padding:0}
      .bb-dialog{border:0;border-radius:18px;padding:24px;width:min(92vw,360px);font-family:Poppins,Arial,sans-serif}
      .bb-dialog::backdrop{background:rgba(0,0,0,.45)}
      .bb-dialog h3{margin:0 0 12px;text-transform:capitalize}
      .bb-dialog label{display:block;font-size:13px;margin-bottom:12px}
      .bb-dialog [hidden]{display:none!important}
      .bb-dialog input,.bb-dialog select{display:block;width:100%;margin-top:4px;padding:9px 10px;border:1px solid #b8bec8;border-radius:10px;font:inherit}
      .bb-row{display:flex;justify-content:flex-end;gap:10px}
      .bb-row button{padding:9px 18px;border-radius:10px;border:1px solid #b8bec8;background:#fff;font:inherit;cursor:pointer}
      .bb-row .bb-primary{background:#112d60;color:#fff;border-color:#112d60}
      .bb-income-btn{position:absolute;top:20px;right:22px;padding:8px 14px;border-radius:12px;border:1px solid #274258;background:#101f2c;color:#40c0e7;font:inherit;font-size:13px;cursor:pointer}
      .bb-income-btn:hover{filter:brightness(1.3)}
      .bb-total{padding:10px 20px;font-size:12px;color:#a8b0be;border-bottom:1px solid #2b303a}
      .bb-reco{margin-top:28px}
      .bb-reco h2{margin:0 0 6px;font-size:22px}
      .bb-stats{margin:0 0 14px;color:#596273;font-size:12px;line-height:1.7}
      .bb-reco-item{padding:14px 18px;margin-bottom:12px;border-radius:16px;background:#fff;border:1px solid #dfe3ea;border-left:6px solid #175cd3}
      .bb-reco-item.danger{border-left-color:#b42318}.bb-reco-item.warning{border-left-color:#b54708}
      .bb-reco-item.good{border-left-color:#167048}
      .bb-reco-item h3{margin:0 0 4px;font-size:15px}.bb-reco-item p{margin:0;font-size:13px;line-height:1.6;color:#344054}`;
    document.head.appendChild(s);
    const l = document.createElement("link"); l.rel = "icon"; l.href = LOGO_MARK; document.head.appendChild(l);
  }
 
  /* ---------- login / sign up ---------- */
  function initLogin() {
    const form = $(".login-form");
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const btn = $(".login-btn", form); btn.disabled = true;
      try {
        const r = await api("/api/login", { email: $("#email").value.trim(), password: $("#password").value });
        store.set("bb_user", r.user);
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
        await api("/api/signup", { name: $("#username").value.trim(), email: $("#email").value.trim(), password: pw });
        alert("Account created! Please log in.");
        location.href = "index.html";
      } catch (err) { alert(err.message); } finally { btn.disabled = false; }
    });
  }
 
  /* ---------- dashboard shell (sidebar, logo, calendar) ---------- */
  function shell() {
    const u = user();
    if (!u) { location.href = "index.html"; return false; }
    $$(".brand img").forEach(i => { i.src = LOGO_MARK; i.alt = "BudgetBuddy logo"; });
    $$('a[href="./index.html"]').forEach(a => a.setAttribute("href", "dashboard.html"));
    const nm = $(".profile-name"), em = $(".profile-email"), av = $(".avatar");
    if (nm) nm.textContent = u.name;
    if (em) em.textContent = u.email;
    if (av) av.textContent = u.name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");
    return true;
  }
 
  function moveToday(p) {
    const grid = $(".calendar-grid");
    if (!grid) return;
    const cells = $$("span:not(.weekday)", grid).filter(s => s.textContent.trim());
    cells.forEach(s => { s.classList.remove("today"); s.removeAttribute("aria-current"); });
    const t = cells.find(s => +s.textContent === p.today);
    if (t) { t.classList.add("today"); t.setAttribute("aria-current", "date"); }
    const b = $(".calendar-badge");
    if (b) b.textContent = (b.textContent.startsWith("Selected") ? "Selected: " : "Today: ") +
      MONTHS[p.month - 1].slice(0, 3).replace(/^./, c => c.toUpperCase()) + " " + p.today;
  }
 
  function renderReco(res, anchor) {
    const m = res.metrics, box = document.createElement("section");
    box.className = "bb-reco";
    const h = document.createElement("h2"); h.textContent = "Recommendations for you";
    const st = document.createElement("p"); st.className = "bb-stats";
    st.textContent = `Daily average ${peso(m.daily_average)} \u00b7 Last 7 days ${peso(m.last_7_days)} \u00b7 ` +
      `Projected month-end spending ${peso(m.projected_spending)} \u00b7 Safe daily allowance ${peso(m.daily_allowance)}`;
    box.append(h, st);
    res.recommendations.forEach(r => {
      const a = document.createElement("article"); a.className = "bb-reco-item " + r.level;
      const t = document.createElement("h3"); t.textContent = r.title;
      const p = document.createElement("p"); p.textContent = r.message;
      a.append(t, p); box.appendChild(a);
    });
    anchor.insertAdjacentElement("afterend", box);
  }
 
  /* ---------- dashboard (needs / wants / savings cards) ---------- */
  const PRESETS = {
    needs: ["Rent", "Transportation", "Food", "Water"],
    wants: ["Online Shopping", "Hobbies"],
    savings: ["Emergency Fund", "Education Fund"],
  };
  const customKey = () => "bb_custom_" + (user() ? user().email : "guest");
  const loadCustom = () => Object.assign({ needs: [], wants: [], savings: [] }, store.get(customKey(), {}));
  const saveCustom = c => store.set(customKey(), c);
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
 
  function askItem(cat, p, startOther) {
    const custom = loadCustom();
    return dialog(`<form method="dialog"><h3>Add ${cat}</h3>
      <label>What is it for?
        <select name="preset" required>
          <option value="" disabled selected>Choose from the list\u2026</option>
          <option value="__other">+ Add a specific item\u2026</option>
        </select></label>
      <button type="button" class="bb-removeopt" hidden>\u2212 Remove this option from my list</button>
      <label class="bb-other" hidden>Name of the item<input name="name" maxlength="60"></label>
      <label>Amount (\u20b1)<input name="amount" type="number" min="0.01" max="1000000000" step="0.01" required></label>
      <label>Day of month<input name="day" type="number" min="1" max="${p.dim}" step="1" value="${p.today}" required></label>
      ${ROW}</form>`,
      f => {
        const other = f.get("preset") === "__other";
        return { name: String(other ? f.get("name") : f.get("preset")).trim(),
                 amount: Number(f.get("amount")), day: parseInt(f.get("day"), 10), isNew: other };
      },
      dlg => {
        const sel = $("select", dlg), box = $(".bb-other", dlg), inp = $("input[name=name]", dlg), rm = $(".bb-removeopt", dlg);
        const otherOpt = $('option[value="__other"]', sel);
        const fill = () => {
          $$("option.bb-opt", sel).forEach(o => o.remove());
          [...PRESETS[cat], ...custom[cat]].forEach(n => {
            const o = document.createElement("option"); o.className = "bb-opt"; o.value = n; o.textContent = n; otherOpt.before(o);
          });
        };
        fill();
        sel.addEventListener("change", () => {
          const other = sel.value === "__other";
          box.hidden = !other; inp.required = other; if (other) inp.focus();
          rm.hidden = !custom[cat].includes(sel.value);
        });
        rm.addEventListener("click", () => {
          custom[cat] = custom[cat].filter(n => n !== sel.value); saveCustom(custom);
          fill(); sel.value = ""; rm.hidden = true;
        });
        if (startOther) { sel.value = "__other"; sel.dispatchEvent(new Event("change")); }
      });
  }
 
  function askIncome(current) {
    return dialog(`<form method="dialog"><h3>Monthly income</h3>
      <label>Allowance or earnings per month (\u20b1)
        <input name="income" type="number" min="0.01" max="1000000000" step="0.01" value="${current > 0 ? current : ""}" required></label>
      ${ROW}</form>`, f => Number(f.get("income")));
  }
 
  function askConfirm(msg) {
    return dialog(`<form method="dialog"><h3>Heads up</h3><p style="font-size:14px;line-height:1.6"></p>
      <div class="bb-row"><button value="cancel" formnovalidate>Go back</button><button value="ok" class="bb-primary">Add anyway</button></div></form>`,
      () => true, d => { $("p", d).textContent = msg; }).then(v => v === true);
  }
 
  function initDashboard() {
    const p = period(); moveToday(p);
    const cards = $$(".budget-card");
    const [incCard, balCard] = $$(".summary-card");
    const incAmt = $(".amount", incCard), balAmt = $(".amount", balCard);
    incCard.style.position = "relative";
    const incBtn = document.createElement("button");
    incBtn.type = "button"; incBtn.className = "bb-income-btn"; incBtn.textContent = "+ Set income";
    incCard.appendChild(incBtn);
 
    async function refreshBalance() {
      try {
        const res = await calculate();
        balAmt.textContent = peso(res.totals.balance, 2, " ");
        cards.forEach(card => {
          const cat = $("h3", card).textContent.trim().toLowerCase(), c = res.categories[cat];
          let t = $(".bb-total", card);
          if (!t) { t = document.createElement("div"); t.className = "bb-total"; $(".budget-header", card).after(t); }
          t.textContent = `Total ${peso(c.actual, 2)} of ${peso(c.budget, 2)} plan (${c.ratio}%)`;
          const bad = cat !== "savings" && c.actual > c.budget;
          t.style.color = bad ? "#f97066" : (cat === "savings" && c.budget > 0 && c.actual >= c.budget ? "#6ce9a6" : "#a8b0be");
        });
      } catch (e) { console.warn(e.message); }
    }
 
    function render() {
      const d = load();
      incAmt.textContent = peso(d.income, 2, " ");
      incBtn.textContent = d.income > 0 ? "Edit income" : "+ Set income";
      cards.forEach(card => {
        const cat = $("h3", card).textContent.trim().toLowerCase();
        let ul = $(".bb-list", card);
        if (!ul) { ul = document.createElement("ul"); ul.className = "bb-list"; card.appendChild(ul); }
        const mine = d.items.filter(i => i.category === cat);
        $(".empty-state", card).style.display = mine.length ? "none" : "";
        ul.replaceChildren(...mine.map(i => {
          const li = document.createElement("li");
          const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = i.name;
          const sm = document.createElement("small"); sm.textContent = "day " + i.day;
          const am = document.createElement("span"); am.textContent = peso(i.amount, 2);
          const x = document.createElement("button");
          x.type = "button"; x.className = "bb-minus"; x.textContent = "\u2212"; x.dataset.id = i.id;
          x.title = "Remove this entry"; x.setAttribute("aria-label", "Remove " + i.name);
          li.append(nm, sm, am, x); return li;
        }));
      });
      refreshBalance();
    }
 
    async function setIncome() {
      const v = await askIncome(load().income);
      if (v === null) return;
      const d = load(); d.income = v; save(d); render();
    }
    incBtn.addEventListener("click", setIncome);
 
    async function addTo(cat, startOther) {
      if (load().income <= 0) {
        alert("Please set your monthly income first.");
        await setIncome();
        if (load().income <= 0) return;
      }
      const v = await askItem(cat, p, startOther);
      if (!v) return;
      if (!v.name) return alert("Please enter a name.");
      const item = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), category: cat, name: v.name, amount: v.amount, day: v.day };
      // let the Python calculation warn before the entry breaks the plan
      try {
        const d0 = load(), res = await calculate({ ...d0, items: [...d0.items, item] });
        let msg = "";
        if (res.totals.balance < 0) msg = `This puts you ${peso(-res.totals.balance, 2)} over your income.`;
        else if (cat !== "savings" && res.categories[cat].left < 0)
          msg = `${cat[0].toUpperCase() + cat.slice(1)} would be ${peso(-res.categories[cat].left, 2)} over your ${res.categories[cat].ratio}% plan.`;
        if (msg && !(await askConfirm(msg))) return;
      } catch (e) { console.warn(e.message); }
      if (v.isNew) {            // remember specific items so they appear in the list next time
        const c = loadCustom(), known = [...PRESETS[cat], ...c[cat]].map(n => n.toLowerCase());
        if (!known.includes(v.name.toLowerCase())) { c[cat].push(v.name); saveCustom(c); }
      }
      const d = load(); d.items.push(item); save(d); render();
    }
 
    cards.forEach(card => {
      const cat = $("h3", card).textContent.trim().toLowerCase();
      $(".add-button", card).addEventListener("click", () => addTo(cat, false));
      const sp = document.createElement("button");
      sp.type = "button"; sp.className = "bb-addspecific"; sp.textContent = "+ Add specific item";
      $(".budget-header", card).after(sp);
      sp.addEventListener("click", () => addTo(cat, true));
      card.addEventListener("click", e => {
        const id = e.target.dataset && e.target.dataset.id;
        if (!id) return;
        const d = load(); d.items = d.items.filter(i => i.id !== id); save(d); render();
      });
    });
 
    $(".submit-button").addEventListener("click", async () => {
      const d = load();
      if (d.income <= 0) return alert("Set your income first (click Set income).");
      if (!d.items.length) return alert("Add at least one expense or saving first.");
      try { await calculate(); location.href = "dashboard2.html"; } catch (e) { alert(e.message); }
    });
    render();
  }
 
  /* ---------- result pages ---------- */
  async function getResult() {
    try { return await calculate(); }
    catch (e) { const c = store.get("bb_result"); if (c) return c; alert(e.message); return null; }
  }
  function fillSummary(res) {
    const a = $$(".summary-card .amount");
    if (a[0]) a[0].textContent = peso(res.income, 2, " ");
    if (a[1]) a[1].textContent = peso(res.totals.balance, 2, " ");
  }
 
  async function initTracker() {
    moveToday(period());
    const res = await getResult(); if (!res) return;
    fillSummary(res);
    const rows = $$(".expense-table tbody tr"), RED = "#f97066", GREEN = "#6ce9a6";
    const put = (cells, b, a, l, color) => {
      cells[0].textContent = peso(b, 2); cells[1].textContent = peso(a, 2);
      cells[2].textContent = peso(l, 2); cells[2].style.color = color || "";
    };
    ["needs", "wants", "savings"].forEach((c, i) => {
      const v = res.categories[c];
      put($$("td", rows[i]), v.budget, v.actual, v.left, c === "savings" ? (v.left <= 0 ? GREEN : "") : (v.left < 0 ? RED : GREEN));
    });
    const t = res.totals;
    put($$(".expense-table tfoot td"), t.budget, t.actual, t.left, t.left < 0 ? RED : GREEN);
    const note = $("#table-note");
    if (note) note.textContent = `Plan: 50% needs, 30% wants, 20% savings of your ${peso(res.income, 2)} income. Left = Budget \u2212 Actual.`;
    renderReco(res, $(".tracker"));
  }
 
  async function initAnalytics() {
    const res = await getResult(); if (!res) return;
    const cats = ["needs", "wants", "savings"], C = res.categories;
    const maxV = Math.max(1, ...cats.flatMap(c => [C[c].budget, C[c].actual]));
    const mag = Math.pow(10, Math.floor(Math.log10(maxV)));
    const top = Math.ceil(maxV * 1.1 / mag) * mag;
    $$(".tick").forEach((t, i) => { t.textContent = peso(top * (1 - i / 4)); });
    $$(".bar-pair").forEach((pair, i) => {
      const v = C[cats[i]];
      [["budget", v.budget], ["actual", v.actual]].forEach(([k, val]) => {
        const bar = $(".bar." + k, pair);
        bar.style.setProperty("--height", (val / top * 100) + "%");
        $(".bar-value", bar).textContent = peso(val);
      });
    });
    $(".plot").setAttribute("aria-label", cats.map(c => `${c}: budget ${C[c].budget} pesos, actual ${C[c].actual} pesos.`).join(" "));
    $$(".insight").forEach((box, i) => {
      const c = cats[i], v = C[c], p = $("p", box), s = $("small", box);
      let ok, text;
      if (c === "savings") {
        const diff = r2(v.actual - v.budget); ok = diff >= 0;
        text = diff === 0 ? "Target reached" : ok ? `${peso(diff)} above target` : `${peso(-diff)} short of target`;
      } else {
        ok = v.left >= 0;
        text = v.left === 0 ? "Exactly on budget" : ok ? `${peso(v.left)} below budget` : `${peso(-v.left)} over budget`;
      }
      p.textContent = text; p.className = ok ? "positive" : "warning";
      s.textContent = c === "savings" ? `Target ${peso(v.budget)} \u00b7 Saved ${peso(v.actual)}` : `Budget ${peso(v.budget)} \u00b7 Actual ${peso(v.actual)}`;
    });
    renderReco(res, $(".insights"));
  }
 
  /* ---------- start ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    injectCSS();
    if ($(".login-form")) { $("#username") ? initSignup() : initLogin(); return; }
    if (!$(".sidebar") || !shell()) return;
    if ($(".budgets")) initDashboard();
    else if ($(".expense-table")) initTracker();
    else if ($(".chart-card")) initAnalytics();
  });
})();