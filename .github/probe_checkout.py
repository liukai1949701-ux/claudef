#!/usr/bin/env python3
"""Open a Shopify checkout/invoice URL in a real browser and report what a buyer would see.

Used to verify checkout availability. The URL is read from the workflow_dispatch event payload
and is never printed: secret path segments and the query string are masked.
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

def _url():
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        return json.load(f)["inputs"]["url"]


URL = _url()
PHRASES = [
    "can't accept payments", "cannot accept payments", "isn't accepting payments", "not accepting payments",
    "unable to accept payments", "no payment methods", "payment methods aren't available",
    "opening soon", "enter store using password", "password", "this store is unavailable",
    "store unavailable", "checkout is unavailable", "something went wrong",
    "pay now", "complete order", "paypal", "shop pay", "credit card", "card number",
    "bogus", "test mode", "subtotal", "total", "doormath",
]


def mask(url):
    url = url.split("?")[0].split("#")[0]
    return re.sub(r"/(invoices|checkouts|cn|c)/[^/]+", r"/\1/<redacted>", url)


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    resp = page.goto(URL, wait_until="domcontentloaded", timeout=90000)
    try:
        page.wait_for_load_state("networkidle", timeout=45000)
    except Exception:
        pass
    page.wait_for_timeout(6000)
    text = page.inner_text("body") if page.query_selector("body") else ""
    low = text.lower()
    print("HTTP status of first response:", resp.status if resp else "n/a")
    print("Final URL (masked):", mask(page.url))
    print("Page title:", page.title())
    print("Phrases found:", [ph for ph in PHRASES if ph in low])
    buttons = [t.strip() for t in page.eval_on_selector_all("button, [role=button], input[type=submit]",
                                                         "els => els.map(e => e.innerText || e.value || '')") if t.strip()]
    print("Buttons:", buttons[:25])
    radios = page.eval_on_selector_all("input[type=radio]", "els => els.map(e => e.name + ':' + (e.value || ''))")
    print("Radio inputs:", radios[:25])
    iframes = [f.url.split("?")[0] for f in page.frames if f != page.main_frame]
    print("Frames:", [mask(u) for u in iframes][:15])
    excerpt = re.sub(r"\s+", " ", text).strip()
    excerpt = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", excerpt)
    print("Visible text excerpt:", excerpt[:1500])
    os.makedirs("probe-out", exist_ok=True)
    page.screenshot(path="probe-out/checkout.png", full_page=True)
    b.close()
sys.exit(0)
