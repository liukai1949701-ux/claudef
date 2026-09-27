#!/usr/bin/env python3
"""Verify the live DoorMath storefront on GitHub Pages.

Checks: every deployed file is served; every link and image on every page resolves;
store links point at the product URL with this site's UTM tags; no paid deliverable is
reachable or committed anywhere in the repository history; no placeholder tokens remain.
"""
import html.parser
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ["SITE_URL"].rstrip("/") + "/"
BUY = os.environ["BUY_URL"]
SITE_DIR = os.environ.get("SITE_DIR", "site")
UA = {"User-Agent": "Mozilla/5.0 (DoorMath live check)"}
UTM = {"utm_source": "doormath-free-site", "utm_medium": "referral"}   # + a per-link utm_campaign
# The product URL answers 200 (open store, or the /password page), or 503 when Shopify answers an
# automated request to a password-protected store with "unavailable". 404 means the product is gone.
STORE_OK = (200, 503)
failures = []


def get(url, method="GET"):
    req = urllib.request.Request(url, headers=UA, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl(), r.read() if method == "GET" else b""
    except urllib.error.HTTPError as e:
        return e.code, url, b""
    except Exception as e:  # network error
        return str(e), url, b""


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in ("href", "src", "srcset", "content"):
            v = a.get(k)
            if not v:
                continue
            if k == "srcset":
                for part in v.split(","):
                    self.links.append((tag, part.strip().split(" ")[0]))
            elif k == "content":
                if v.startswith("http"):
                    self.links.append((tag, v))
            else:
                self.links.append((tag, v))


def fail(msg):
    print("FAIL", msg)
    failures.append(msg)


REV = os.environ.get("GITHUB_SHA", str(int(time.time())))


def fresh(url):
    """Same-site URL with a per-commit query, so a CDN-cached older copy is never checked."""
    if not url.startswith(BASE):
        return url
    return url + ("&" if "?" in url else "?") + "v=" + REV


# 1. the deployed files, as committed
files = []
for root, dirs, fs in os.walk(SITE_DIR):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "tests"]
    for f in fs:
        if f.startswith("."):
            continue
        rel = os.path.relpath(os.path.join(root, f), SITE_DIR).replace(os.sep, "/")
        files.append(rel)
files.sort()

# 2. wait until Pages serves this commit: every file answers 200 with the committed bytes.
#    A push starts this check before the Pages build finishes, and the previous deployment
#    also answers 200, so status codes alone can't tell the two apart.
deadline = time.time() + 15 * 60
while True:
    stale = []
    for rel in files:
        code, _, body = get(fresh(BASE + rel))
        with open(os.path.join(SITE_DIR, rel), "rb") as fh:
            if code != 200 or body != fh.read():
                stale.append(f"{rel} (HTTP {code})")
    if not stale or time.time() > deadline:
        break
    print(f"waiting for Pages to serve this commit: {len(stale)} file(s) not current, e.g. {stale[:3]}")
    time.sleep(20)
for s_ in stale:
    fail(f"deployed file not served as committed: {s_}")
for rel in files:
    if rel.endswith((".html", ".xml", ".txt")):
        with open(os.path.join(SITE_DIR, rel), "rb") as fh:
            if b"{{" in fh.read():
                fail(f"placeholder token left in {rel}")
print(f"{len(files)} deployed files served as committed")

# 3. links on every page
checked = {}
for rel in [f for f in files if f.endswith(".html")]:
    page_url = BASE + rel
    code, _, body = get(fresh(page_url))
    p = Links()
    p.feed(body.decode("utf-8", "replace"))
    buys = 0
    for tag, link in p.links:
        if link.startswith(("mailto:", "tel:", "data:", "javascript:")):
            continue
        url = urllib.parse.urljoin(page_url, link)
        frag = urllib.parse.urlparse(url).fragment
        base = url.split("#")[0]
        if "myshopify.com" in url:
            buys += 1
            u = urllib.parse.urlsplit(url)
            q = dict(urllib.parse.parse_qsl(u.query))
            if f"{u.scheme}://{u.netloc}{u.path}" != BUY:
                fail(f"{rel}: store link {url} is not {BUY}")
            if any(q.get(k) != v for k, v in UTM.items()) or not q.get("utm_campaign"):
                fail(f"{rel}: store link {url} lacks utm_source/utm_medium/utm_campaign")
            base = BUY   # fetch without the UTM query so this check never counts as a tagged visit
        if any(base.lower().endswith(x) for x in (".xlsx", ".zip", ".xls")):
            fail(f"{rel}: links to a downloadable deliverable {base}")
        if base not in checked:
            checked[base] = get(fresh(base))[0]
        ok = STORE_OK if base == BUY else (200,)
        if checked[base] not in ok:
            fail(f"{rel}: broken link {url} -> {checked[base]}")
    print(f"{rel}: {len(p.links)} links, {buys} store links")
    if rel == "index.html" and buys < 2:
        fail("index.html has fewer than 2 store links")

# 4. the product URL itself
code, final, body = get(BUY)
print(f"BUY URL {BUY} -> HTTP {code}, final URL {final}")
if "/password" in final or code == 503:
    print("NOTE: the Shopify storefront is password-protected or unavailable (not open for sales yet).")
if code not in STORE_OK:
    fail(f"buy URL not reachable: {code}")

# 5. paid deliverable must not be reachable on the site
for path in ("DoorMath-Deal-Analyzer.xlsx", "DoorMath-Deal-Analyzer-Blank.xlsx",
             "DoorMath-Deal-Analyzer-v1.0.0.zip", "dist/DoorMath-Deal-Analyzer-v1.0.0.zip",
             "assets/DoorMath-Deal-Analyzer.xlsx", "src/build_workbook.py"):
    code = get(BASE + path)[0]
    print(f"paid path {path} -> {code}")
    if code == 200:
        fail(f"paid file reachable: {path}")

# 6. nothing paid was ever committed to any branch
out = subprocess.run(["git", "log", "--all", "--name-only", "--pretty=format:"], capture_output=True, text=True,
                     check=True).stdout.split()
bad = sorted({f for f in out if f.lower().endswith((".xlsx", ".xls", ".zip")) or f.endswith(
    ("build_workbook.py", "reference.py", "inject_values.py", "package.py"))})
print(f"history scan: {len(set(out))} paths across all branches")
if bad:
    fail(f"paid/private files in git history: {bad}")

print("RESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
sys.exit(1 if failures else 0)
