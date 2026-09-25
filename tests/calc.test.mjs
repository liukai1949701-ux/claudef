// Run: node tests/calc.test.mjs
// Checks assets/calc-core.js against fixtures produced by the product's Python reference model.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const core = require(join(here, "..", "assets", "calc-core.js"));
const cases = JSON.parse(readFileSync(join(here, "fixtures.json"), "utf8"));

const REL = 1e-9;
const ABS = 1e-6;
let checks = 0;
const failures = [];

function close(actual, expected) {
  if (expected === null || actual === null) return expected === actual;
  if (typeof actual !== "number" || !Number.isFinite(actual)) return false;
  const diff = Math.abs(actual - expected);
  return diff <= ABS || diff <= REL * Math.abs(expected);
}

for (const c of cases) {
  const got = core.compute(c.inputs);
  const keys = Object.keys(c.expected);
  for (const k of keys) {
    checks++;
    if (!(k in got)) {
      failures.push(`${c.name}.${k}: missing from compute() output`);
      continue;
    }
    if (!close(got[k], c.expected[k])) {
      failures.push(`${c.name}.${k}: expected ${c.expected[k]}, got ${got[k]}`);
    }
  }
}

// UI conversion: percent fields entered as 7 = 7% must give the same result as fractions.
const ex = core.EXAMPLE;
const ui = {};
for (const f of core.FIELDS) ui[f] = core.PERCENT_FIELDS.includes(f) ? ex[f] * 100 : ex[f];
const viaUI = core.compute(core.fromUI(ui));
const direct = core.compute(ex);
for (const k of Object.keys(direct)) {
  checks++;
  if (!close(viaUI[k], direct[k])) failures.push(`fromUI.${k}: ${viaUI[k]} != ${direct[k]}`);
}

// Formatting of the example deal (the numbers quoted on the page).
const fmtChecks = [
  [core.format.money(direct.cf), "$169"],
  [core.format.money(direct.cf_door), "$85"],
  [core.format.pct(direct.coc), "2.4%"],
  [core.format.pct(direct.cap), "6.8%"],
  [core.format.ratio(direct.dscr, 2, "x"), "1.14x"],
  [core.format.pct(direct.one_pct, 2), "0.97%"],
  [core.format.money(direct.noi), "$1,362"],
  [core.format.money(direct.pi, 2), "$1,192.55"],
  [core.format.money(direct.cash_in), "$84,920"],
  [core.format.money(-1044.3), "-$1,044"],
  [core.format.money(-0.4), "$0"],
  [core.format.pct(null), "n/a"],
];
for (const [got, want] of fmtChecks) {
  checks++;
  if (got !== want) failures.push(`format: expected ${want}, got ${got}`);
}

if (failures.length) {
  console.error(`FAIL: ${failures.length} of ${checks} checks failed`);
  for (const f of failures.slice(0, 50)) console.error("  " + f);
  process.exit(1);
}
console.log(`PASS: ${cases.length} fixture cases, ${checks} checks`);
