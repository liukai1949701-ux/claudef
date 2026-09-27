#!/usr/bin/env python3
"""End-to-end check of the DoorMath storefront.

Run: python3 tests/site_check.py
Serves the site folder with `python3 -m http.server` on a free localhost port and uses
Playwright's Chromium to check desktop (1280px) and mobile (375px) layouts, console
errors, failed/external requests, horizontal overflow, the calculator, the lightbox,
every store link and the worked-example pages. Saves full-page screenshots to tests/out/.

Set CHROMIUM_PATH to use a specific Chromium binary; otherwise Playwright's own
bundled Chromium is used.
"""
import math
import os
import socket
import subprocess
import sys
import time
import json
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tests", "out")
CHROME = os.environ.get("CHROMIUM_PATH") or None   # None = Playwright's bundled Chromium
BUY_URL = "https://qzgfrd-s1.myshopify.com/products/doormath-rental-property-deal-analyzer"
UTM = {"utm_source": "doormath-free-site", "utm_medium": "referral"}   # + a per-link utm_campaign
EXAMPLES = {   # page -> a figure that must appear on it
    "examples/max-offer-rental-property.html": "$181,152",
    "examples/brrrr-worked-example.html": "$69,704",
    "examples/airbnb-vs-long-term-rental.html": "65.7%",
    "examples/cash-on-cash-vs-cap-rate-vs-dscr.html": "6.84%",
}

EXAMPLE_UI = {
    "units": 2, "price": 239000, "closing_pct": 3, "repairs": 18000, "down_pct": 25,
    "rate": 7, "term_years": 30, "points_pct": 0, "rent": 2500, "other_income": 60,
    "taxes_yr": 3300, "insurance_yr": 1450, "hoa_mo": 0, "utilities_other_mo": 200,
    "vacancy_pct": 6, "maint_pct": 5, "capex_pct": 5, "mgmt_pct": 8,
}
PCT = {"closing_pct", "down_pct", "rate", "points_pct", "vacancy_pct", "maint_pct", "capex_pct", "mgmt_pct"}

failures = []
passes = 0


def check(cond, msg):
    global passes
    if cond:
        passes += 1
        print("  ok   " + msg)
    else:
        failures.append(msg)
        print("  FAIL " + msg)


def py_cash_flow(ui):
    """Independent Python version of the monthly cash flow formula."""
    d = {k: (v / 100 if k in PCT else v) for k, v in ui.items()}
    gsi = d["rent"] + d["other_income"]
    egi = gsi - gsi * d["vacancy_pct"]
    opex = (egi * d["mgmt_pct"] + gsi * d["maint_pct"] + gsi * d["capex_pct"]
            + d["taxes_yr"] / 12 + d["insurance_yr"] / 12 + d["hoa_mo"] + d["utilities_other_mo"])
    noi = egi - opex
    loan = d["price"] * (1 - d["down_pct"])
    n, i = d["term_years"] * 12, d["rate"] / 12
    if loan <= 0 or n <= 0:
        pi = 0.0
    elif i == 0:
        pi = loan / n
    else:
        pi = loan * i / (1 - (1 + i) ** -n)
    return noi - pi


def store_link_problem(href):
    """None if href is the product URL tagged with our UTM parameters, else what is wrong."""
    u = urllib.parse.urlsplit(href)
    if f"{u.scheme}://{u.netloc}{u.path}" != BUY_URL:
        return "not the product URL"
    q = dict(urllib.parse.parse_qsl(u.query))
    if any(q.get(k) != v for k, v in UTM.items()) or not q.get("utm_campaign"):
        return "missing utm_source/utm_medium/utm_campaign"
    return None


def money(v):
    r = round(v)
    return ("-" if r < 0 else "") + "${:,}".format(abs(int(r)))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", ROOT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/index.html", timeout=1)
            return proc, base
        except Exception:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("http.server did not start")


def watch(page, base, log):
    page.on("console", lambda m: log["console"].append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: log["console"].append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: log["failed"].append(f"{r.url} ({r.failure})"))

    def on_response(r):
        if r.status >= 400:
            log["failed"].append(f"{r.url} -> HTTP {r.status}")
    page.on("response", on_response)

    def on_request(r):
        if not (r.url.startswith(base) or r.url.startswith("data:")):
            log["external"].append(r.url)
    page.on("request", on_request)


def scroll_through(page):
    h = page.evaluate("document.documentElement.scrollHeight")
    y = 0
    while y < h:
        page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
        page.wait_for_timeout(60)
        y += 500
        h = page.evaluate("document.documentElement.scrollHeight")
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)


def run_viewport(browser, base, name, width, height, mobile):
    print(f"\n[{name} {width}px]")
    ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                              is_mobile=mobile, has_touch=mobile)
    page = ctx.new_page()
    log = {"console": [], "failed": [], "external": []}
    watch(page, base, log)
    page.goto(base + "/index.html", wait_until="networkidle")
    scroll_through(page)

    # all images decoded
    imgs = "[...document.images].filter(i => i.id !== 'lb-img')"
    try:
        page.wait_for_function(f"{imgs}.every(i => i.complete && i.naturalWidth > 0)", timeout=10000)
    except Exception:
        pass
    broken = page.evaluate(f"{imgs}.filter(i => !(i.complete && i.naturalWidth > 0)).map(i => i.currentSrc || i.src)")
    check(not broken, f"all {page.evaluate(imgs + '.length')} images loaded" + (f" (broken: {broken})" if broken else ""))

    sw = page.evaluate("document.documentElement.scrollWidth")
    iw = page.evaluate("window.innerWidth")
    # On a mobile viewport an overflowing page silently widens the layout viewport, so also require innerWidth == width.
    check(sw <= iw and iw == width, f"no horizontal scroll (scrollWidth {sw} <= innerWidth {iw}, viewport {width})")

    # width/height attributes must match each image's real aspect ratio (avoids layout shift / stretching)
    bad_dims = page.evaluate("""[...document.images].filter(i => i.id !== 'lb-img' && i.getAttribute('width')).filter(i => {
        // a selected <picture><source> supplies its own width/height
        const src = i.parentElement.tagName === 'PICTURE' ? [...i.parentElement.querySelectorAll('source')]
            .find(s => i.currentSrc.endsWith(s.getAttribute('srcset'))) : null;
        const el = src || i;
        const w = +el.getAttribute('width'), h = +el.getAttribute('height');
        return Math.abs(w / h - i.naturalWidth / i.naturalHeight) > 0.01;
    }).map(i => i.currentSrc)""")
    check(not bad_dims, "img width/height match the real image aspect ratio" + (f" (bad: {bad_dims})" if bad_dims else ""))

    # free-tool-first home page: the calculator is the page's h1 and first section
    text = page.evaluate("document.body.innerText")
    stale = [t for t in ("5–50%", "5% to 50%", "exact formula", "modelled", "modelling", "Buy now", "Get the full")
             if t in text]
    check(not stale, "no stale wording" + (f" (found: {stale})" if stale else ""))
    first = page.evaluate("document.querySelector('main > section').id")
    h1_text = page.locator("#calculator h1").inner_text()
    check(first == "calculator" and "calculator" in h1_text.lower(),
          f"calculator is the first section and holds the h1 ({first}: {h1_text!r})")
    cards = page.evaluate("[...document.querySelectorAll('#examples a.example-card')].map(a => a.getAttribute('href'))")
    check(sorted(cards) == sorted(EXAMPLES), f"home page links to the {len(EXAMPLES)} worked examples ({len(cards)} cards)")

    h1 = page.locator("h1").count()
    check(h1 == 1, f"exactly one h1 (found {h1})")

    os.makedirs(OUT, exist_ok=True)
    shot = os.path.join(OUT, f"{name}.png")
    page.screenshot(path=shot, full_page=True)
    print(f"  saved {os.path.relpath(shot, ROOT)}")

    # ---- store links: product URL + UTM tags, rel=noopener ----
    hrefs = page.evaluate("""[...document.querySelectorAll('a')]
        .filter(a => a.hasAttribute('data-buy') || /buy|get the full/i.test(a.textContent) || a.href.includes('myshopify'))
        .map(a => ({href: a.getAttribute('href'), rel: a.getAttribute('rel') || '', text: a.textContent.trim()}))""")
    bad = [h for h in hrefs if store_link_problem(h["href"]) or "noopener" not in h["rel"].split()]
    check(len(hrefs) >= 2 and not bad, f"{len(hrefs)} store links use the product URL with UTM tags and rel=noopener"
          + (f" (bad: {bad})" if bad else ""))
    campaigns = [dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(h["href"]).query)).get("utm_campaign") for h in hrefs]
    check(len(set(campaigns)) == len(campaigns), f"each store link has its own utm_campaign ({campaigns})")
    check(page.evaluate("document.body.dataset.buyUrl") == BUY_URL, "body[data-buy-url] matches the buy URL")

    # ---- Calculator ----
    before_text = page.locator("#out-cf").inner_text()
    before_val = float(page.locator("#out-cf").get_attribute("data-value"))
    check(before_text == "$169" and abs(before_val - py_cash_flow(EXAMPLE_UI)) < 1e-9,
          f"calculator starts on the example deal ({before_text})")
    page.locator("#f-rent").click()
    page.locator("#f-rent").fill("")
    page.locator("#f-rent").press_sequentially("3150")
    page.wait_for_timeout(50)
    after_text = page.locator("#out-cf").inner_text()
    after_val = float(page.locator("#out-cf").get_attribute("data-value"))
    ui = dict(EXAMPLE_UI, rent=3150)
    core_val = page.evaluate("ui => DoorMathCalc.compute(DoorMathCalc.fromUI(ui)).cf", ui)
    py_val = py_cash_flow(ui)
    check(after_text != before_text, f"cash flow output changed after typing rent ({before_text} -> {after_text})")
    check(abs(after_val - core_val) < 1e-9 and abs(core_val - py_val) < 1e-9,
          f"output matches core function and Python model ({after_val:.6f} / {core_val:.6f} / {py_val:.6f})")
    check(after_text == money(py_val), f"displayed value is formatted correctly ({after_text} == {money(py_val)})")
    check(page.locator("#mini-cf").text_content() == after_text, "sticky mini result mirrors the cash flow")
    if mobile:
        vis = "document.querySelector('.calc-mini').classList.contains('is-visible')"

        def settles(expr):
            try:
                page.wait_for_function(expr, timeout=3000)
                return True
            except Exception:
                return False
        page.evaluate("document.getElementById('f-taxes_yr').scrollIntoView({block: 'center', behavior: 'instant'})")
        shown_in_form = settles(vis)
        page.evaluate("document.getElementById('results').scrollIntoView({block: 'center', behavior: 'instant'})")
        hidden_at_results = settles("!" + vis)
        page.evaluate("document.getElementById('faq').scrollIntoView({block: 'start', behavior: 'instant'})")
        hidden_past_form = settles("!" + vis)
        check(shown_in_form and hidden_at_results and hidden_past_form,
              f"mobile mini result bar shows only while the form is on screen and the results are not "
              f"({shown_in_form}/{hidden_at_results}/{hidden_past_form})")
    page.locator("#f-down_pct").fill("100")
    check(page.locator("#out-dscr").inner_text() == "No debt", "all-cash purchase shows DSCR as 'No debt'")
    page.locator("#calc-reset").click()
    check(page.locator("#out-cf").inner_text() == "$169" and page.locator("#f-rent").input_value() == "2,500",
          "reset button restores the example deal")

    # ---- Lightbox ----
    first = page.locator("a.zoom").first
    first.scroll_into_view_if_needed()
    first.click()
    page.wait_for_selector("#lightbox[open]")
    page.wait_for_function("document.getElementById('lb-img') && document.getElementById('lb-img').naturalWidth > 0")
    check(page.evaluate("document.getElementById('lightbox').open"), "lightbox opens on click and loads the full image")
    check(page.evaluate("document.activeElement.id") == "lb-close", "focus moves to the close button")
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    check(not page.evaluate("document.getElementById('lightbox').open"), "Esc closes the lightbox")
    check(page.evaluate("document.activeElement.classList.contains('zoom')"), "focus returns to the screenshot link")
    # keyboard open + close button
    page.keyboard.press("Enter")
    page.wait_for_selector("#lightbox[open]")
    check(True, "Enter on a focused screenshot opens the lightbox")
    page.locator("#lb-close").click()
    page.wait_for_timeout(100)
    check(not page.evaluate("document.getElementById('lightbox').open"), "close button closes the lightbox")

    check(not log["console"], "no console errors" + (f": {log['console']}" if log["console"] else ""))
    check(not log["failed"], "no failed requests" + (f": {log['failed']}" if log["failed"] else ""))
    check(not log["external"], "no external requests" + (f": {log['external']}" if log["external"] else ""))
    ctx.close()


def check_widths(browser, base):
    print("\n[overflow sweep]")
    for w in (320, 360, 414, 768, 1024, 1440):
        ctx = browser.new_context(viewport={"width": w, "height": 900}, is_mobile=w < 700, has_touch=w < 700)
        page = ctx.new_page()
        for path in ["index.html", *EXAMPLES]:
            page.goto(f"{base}/{path}", wait_until="networkidle")
            sw, iw = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
            wide = page.evaluate(f"""[...document.querySelectorAll('body *')].filter(e => {{
                const r = e.getBoundingClientRect(); return r.width > 0 && r.right > {w} + 1
                    && !e.closest('.sheet-tabs, .table-wrap, .formula');
            }}).slice(0, 5).map(e => e.tagName + '.' + (e.className.baseVal ?? e.className))""")
            check(sw <= iw and iw == w, f"{w}px {path}: no horizontal scroll (scrollWidth {sw}, innerWidth {iw})"
                  + (f" {wide}" if wide else ""))
        ctx.close()


def check_examples(browser, base):
    for path, figure in EXAMPLES.items():
        for name, w, h, mobile in (("desktop", 1280, 800, False), ("mobile", 375, 812, True)):
            print(f"\n[{path} {name} {w}px]")
            ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
            page = ctx.new_page()
            log = {"console": [], "failed": [], "external": []}
            watch(page, base, log)
            page.goto(f"{base}/{path}", wait_until="networkidle")
            sw, iw = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
            check(sw <= iw and iw == w, f"no horizontal scroll (scrollWidth {sw}, innerWidth {iw})")
            check(page.locator("h1").count() == 1, "exactly one h1")
            check(figure in page.evaluate("document.body.innerText"), f"shows the worked figure {figure}")
            if not mobile:   # page-level checks once per page
                ld = json.loads(page.locator('script[type="application/ld+json"]').text_content())
                canon = page.locator('link[rel="canonical"]').get_attribute("href")
                check(ld.get("@type") == "Article" and canon.endswith("/" + path), f"Article JSON-LD and canonical ({canon})")
                links = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))")
                internal = [l for l in links if not l.startswith(("http:", "https:", "mailto:", "{{", "#"))]
                broken = []
                for l in sorted(set(internal)):
                    url = urllib.parse.urljoin(f"{base}/{path}", l)
                    target, frag = urllib.parse.urldefrag(url)
                    try:
                        body = urllib.request.urlopen(target, timeout=5).read().decode("utf-8", "replace")
                    except Exception as e:
                        broken.append(f"{l} ({e})")
                        continue
                    if frag and f'id="{frag}"' not in body:
                        broken.append(f"{l} (no #{frag})")
                check(not broken, f"{len(set(internal))} internal links resolve, anchors included" + (f" (broken: {broken})" if broken else ""))
                store = [l for l in links if "myshopify" in l]
                check(all(store_link_problem(l) is None for l in store), f"{len(store)} store links carry UTM tags")
                os.makedirs(OUT, exist_ok=True)
                page.screenshot(path=os.path.join(OUT, os.path.basename(path).replace(".html", ".png")), full_page=True)
            check(not log["console"], "no console errors" + (f": {log['console']}" if log["console"] else ""))
            check(not log["failed"], "no failed requests" + (f": {log['failed']}" if log["failed"] else ""))
            check(not log["external"], "no external requests" + (f": {log['external']}" if log["external"] else ""))
            ctx.close()


def check_404(browser, base):
    print("\n[404.html]")
    ctx = browser.new_context(viewport={"width": 375, "height": 700})
    page = ctx.new_page()
    log = {"console": [], "failed": [], "external": []}
    watch(page, base, log)
    page.goto(base + "/404.html", wait_until="networkidle")
    check("doesn't exist" in page.content(), "404 page renders")
    check(not log["console"] and not log["external"], "404 page: no console errors or external requests")
    check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "404 page: no horizontal scroll")
    page.screenshot(path=os.path.join(OUT, "404.png"), full_page=True)
    ctx.close()


def main():
    proc, base = start_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, args=[
                "--disable-background-networking", "--disable-component-update", "--no-first-run"])
            run_viewport(browser, base, "desktop", 1280, 800, False)
            run_viewport(browser, base, "mobile", 375, 812, True)
            check_examples(browser, base)
            check_widths(browser, base)
            check_404(browser, base)
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    print(f"\n{passes} passed, {len(failures)} failed")
    if failures:
        for f in failures:
            print("FAIL: " + f)
        sys.exit(1)


if __name__ == "__main__":
    main()
