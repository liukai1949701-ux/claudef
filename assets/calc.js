/* DoorMath free calculator UI. Depends on assets/calc-core.js (window.DoorMathCalc). */
(function () {
  "use strict";
  var core = window.DoorMathCalc;
  var form = document.getElementById("calc-form");
  if (!core || !form) return;

  var fmt = core.format;
  var PCT = core.PERCENT_FIELDS;

  function $(id) { return document.getElementById(id); }

  function parse(raw) {
    var s = String(raw == null ? "" : raw).replace(/[\s,$%]/g, "");
    if (s === "" || s === "-" || s === ".") return { value: 0, valid: s === "" };
    var v = Number(s);
    return isFinite(v) ? { value: v, valid: true } : { value: 0, valid: false };
  }

  function groupInput(v) {
    // format a money input with thousands separators, keep up to 2 decimals
    var r = Math.round(v * 100) / 100;
    var parts = Math.abs(r).toString().split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (r < 0 ? "-" : "") + parts.join(".");
  }

  /** Read the form as UI values (percent fields as entered, e.g. 7 = 7%). */
  function readUI() {
    var ui = {};
    core.FIELDS.forEach(function (f) {
      var el = form.elements[f];
      if (!el) { ui[f] = 0; return; }
      var p = parse(el.value);
      el.setAttribute("aria-invalid", p.valid ? "false" : "true");
      ui[f] = p.value;
    });
    return ui;
  }

  function setText(id, text, value, negative) {
    var el = $(id);
    if (!el) return;
    el.textContent = text;
    if (value !== undefined) el.setAttribute("data-value", value === null ? "null" : String(value));
    if (negative !== undefined) el.classList.toggle("is-neg", !!negative);
  }

  function neg(v) { return v !== null && Number(v.toFixed(2)) < 0; }

  var liveTimer = null;

  function render() {
    var r = core.compute(core.fromUI(readUI()));

    setText("out-cf", fmt.money(r.cf), r.cf, neg(r.cf));
    setText("out-cf-door", fmt.money(r.cf_door), r.cf_door);
    setText("out-cf-yr", fmt.money(r.cf_yr), r.cf_yr);
    setText("out-coc", fmt.pct(r.coc, 1), r.coc, neg(r.coc));
    setText("out-cap", fmt.pct(r.cap, 1), r.cap, neg(r.cap));
    setText("out-dscr", r.dscr === null ? "No debt" : fmt.ratio(r.dscr, 2, "x"), r.dscr);
    setText("out-onepct", fmt.pct(r.one_pct, 2), r.one_pct);
    setText("out-noi", fmt.money(r.noi), r.noi, neg(r.noi));
    setText("out-pi", fmt.money(r.pi, 2), r.pi);
    setText("out-cashin", fmt.money(r.cash_in), r.cash_in);
    setText("out-beo", fmt.pct(r.break_even_occ, 1), r.break_even_occ);
    setText("out-grm", fmt.ratio(r.grm, 1), r.grm);

    setText("w-gsi", fmt.money(r.gsi));
    setText("w-vac", fmt.money(-r.vacancy));
    setText("w-opex", fmt.money(-r.opex));
    setText("w-noi", fmt.money(r.noi));
    setText("w-pi", fmt.money(-r.pi));
    setText("w-cf", fmt.money(r.cf));

    setText("mini-cf", fmt.money(r.cf), undefined, neg(r.cf));
    setText("mini-coc", fmt.pct(r.coc, 1), undefined, neg(r.coc));

    // polite screen-reader summary, debounced so typing isn't read key by key
    clearTimeout(liveTimer);
    liveTimer = setTimeout(function () {
      var live = $("calc-live");
      if (live) {
        live.textContent = "Monthly cash flow " + fmt.money(r.cf) + ", cash-on-cash " +
          fmt.pct(r.coc, 1) + ", cap rate " + fmt.pct(r.cap, 1) + ".";
      }
    }, 900);
    return r;
  }

  function loadExample() {
    var ex = core.EXAMPLE;
    core.FIELDS.forEach(function (f) {
      var el = form.elements[f];
      if (!el) return;
      var v = PCT.indexOf(f) >= 0 ? Math.round(ex[f] * 100 * 1e6) / 1e6 : ex[f];
      if (f === "rate") el.value = v.toFixed(2);
      else el.value = el.hasAttribute("data-money") ? groupInput(v) : String(v);
    });
    render();
  }

  form.addEventListener("input", render);
  form.addEventListener("change", render);
  form.addEventListener("submit", function (e) { e.preventDefault(); render(); });
  form.addEventListener("focusout", function (e) {
    var el = e.target;
    if (!el || !el.hasAttribute || !el.hasAttribute("data-money")) return;
    var p = parse(el.value);
    if (p.valid && el.value.trim() !== "") el.value = groupInput(p.value);
  });

  var reset = $("calc-reset");
  if (reset) reset.addEventListener("click", loadExample);

  // Small screens: show the sticky mini result only while the form is on screen
  // and the big cash-flow number in the results card is not fully visible.
  var mini = form.querySelector(".calc-mini");
  var bigValue = $("out-cf");
  if (mini && bigValue && "IntersectionObserver" in window) {
    var formIn = false, valueIn = false;
    var update = function () { mini.classList.toggle("is-visible", formIn && !valueIn); };
    new IntersectionObserver(function (entries) {
      formIn = entries[entries.length - 1].isIntersecting; update();
    }).observe(form);
    new IntersectionObserver(function (entries) {
      var en = entries[entries.length - 1];
      valueIn = en.isIntersecting && en.intersectionRatio > 0.99; update();
    }, { threshold: [0, 1] }).observe(bigValue);
  }

  // Expose for tests / curious visitors.
  window.DoorMathCalcUI = { readUI: readUI, render: render, loadExample: loadExample };

  render();
})();
