/*!
 * DoorMath free long-term rental calculator: pure math core.
 * Same long-term-rental formulas as the workbook's Rental tab.
 * All rates are fractions here (0.07 = 7%). null = undefined for these inputs.
 * UMD: window.DoorMathCalc in the browser, module.exports in Node.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.DoorMathCalc = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var FIELDS = [
    "units", "price", "closing_pct", "repairs", "down_pct", "rate", "term_years",
    "points_pct", "rent", "other_income", "taxes_yr", "insurance_yr", "hoa_mo",
    "utilities_other_mo", "vacancy_pct", "maint_pct", "capex_pct", "mgmt_pct"
  ];

  /** Fields entered as percentages in the UI (7 = 7%). */
  var PERCENT_FIELDS = [
    "closing_pct", "down_pct", "rate", "points_pct",
    "vacancy_pct", "maint_pct", "capex_pct", "mgmt_pct"
  ];

  /** The worked example deal: "Example: 1418 Linden Ave (duplex)". */
  var EXAMPLE = {
    units: 2, price: 239000, closing_pct: 0.03, repairs: 18000, down_pct: 0.25,
    rate: 0.07, term_years: 30, points_pct: 0, rent: 2500, other_income: 60,
    taxes_yr: 3300, insurance_yr: 1450, hoa_mo: 0, utilities_other_mo: 200,
    vacancy_pct: 0.06, maint_pct: 0.05, capex_pct: 0.05, mgmt_pct: 0.08
  };

  function num(v) {
    var x = Number(v);
    return isFinite(x) ? x : 0;
  }

  /** Monthly principal & interest payment. */
  function payment(loan, rateYr, termYears) {
    var n = termYears * 12;
    var i = rateYr / 12;
    if (loan <= 0 || n <= 0) return 0;
    if (i === 0) return loan / n;
    return loan * i / (1 - Math.pow(1 + i, -n));
  }

  /**
   * Compute the long-term rental metrics.
   * @param {Object} inp inputs with rates as fractions (see FIELDS)
   * @returns {Object} gsi, vacancy, egi, opex, noi, loan, pi, cf, cf_door, cf_yr,
   *   cash_in, coc, cap, dscr, one_pct, grm, break_even_occ (monthly unless _yr)
   */
  function compute(inp) {
    var d = {};
    for (var k = 0; k < FIELDS.length; k++) d[FIELDS[k]] = num(inp[FIELDS[k]]);

    var gsi = d.rent + d.other_income;
    var vacancy = gsi * d.vacancy_pct;
    var egi = gsi - vacancy;
    var opex = egi * d.mgmt_pct + gsi * d.maint_pct + gsi * d.capex_pct +
      d.taxes_yr / 12 + d.insurance_yr / 12 + d.hoa_mo + d.utilities_other_mo;
    var noi = egi - opex;
    var loan = d.price * (1 - d.down_pct);
    var pi = payment(loan, d.rate, d.term_years);
    var cf = noi - pi;
    var cf_yr = 12 * cf;
    var cash_in = d.price * d.down_pct + d.price * d.closing_pct +
      loan * d.points_pct + d.repairs;
    var onePctDen = d.price + d.repairs;

    return {
      gsi: gsi,
      vacancy: vacancy,
      egi: egi,
      opex: opex,
      noi: noi,
      loan: loan,
      pi: pi,
      cf: cf,
      cf_door: d.units === 0 ? null : cf / d.units,
      cf_yr: cf_yr,
      cash_in: cash_in,
      coc: cash_in === 0 ? null : cf_yr / cash_in,
      cap: d.price === 0 ? null : 12 * noi / d.price,
      dscr: pi === 0 ? null : noi / pi,
      one_pct: onePctDen === 0 ? null : d.rent / onePctDen,
      grm: d.rent === 0 ? null : d.price / (12 * d.rent),
      break_even_occ: gsi === 0 ? null : (opex + pi) / gsi
    };
  }

  /** Convert UI values (percent fields as 7 = 7%) into compute() inputs. */
  function fromUI(values) {
    var out = {};
    for (var k = 0; k < FIELDS.length; k++) {
      var f = FIELDS[k];
      var v = num(values[f]);
      out[f] = PERCENT_FIELDS.indexOf(f) >= 0 ? v / 100 : v;
    }
    return out;
  }

  /* ---------- display formatting (matches the workbook's number formats) ---------- */

  function group(n, decimals) {
    var fixed = Math.abs(n).toFixed(decimals);
    var parts = fixed.split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join(".");
  }

  function signed(n, decimals, body) {
    var r = Number(n.toFixed(decimals));
    return (r < 0 ? "-" : "") + body(Math.abs(r));
  }

  var format = {
    money: function (n, decimals) {
      if (n === null || n === undefined || !isFinite(n)) return "n/a";
      var dp = decimals || 0;
      return signed(n, dp, function (a) { return "$" + group(a, dp); });
    },
    pct: function (n, decimals) {
      if (n === null || n === undefined || !isFinite(n)) return "n/a";
      var dp = decimals === undefined ? 1 : decimals;
      return signed(n * 100, dp, function (a) { return group(a, dp) + "%"; });
    },
    ratio: function (n, decimals, suffix) {
      if (n === null || n === undefined || !isFinite(n)) return "n/a";
      var dp = decimals === undefined ? 2 : decimals;
      return signed(n, dp, function (a) { return group(a, dp) + (suffix || ""); });
    }
  };

  return {
    FIELDS: FIELDS,
    PERCENT_FIELDS: PERCENT_FIELDS,
    EXAMPLE: EXAMPLE,
    payment: payment,
    compute: compute,
    fromUI: fromUI,
    format: format
  };
});
