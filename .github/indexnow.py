#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver...) about the site's pages.

Runs after verify_live.py passes. Submits every <loc> in the deployed sitemap.xml, after
checking that the key file is served at the key location. Google does not use IndexNow.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE = os.environ["SITE_URL"].rstrip("/") + "/"
KEY = os.environ["INDEXNOW_KEY"]
REV = os.environ.get("GITHUB_SHA", "manual")
UA = {"User-Agent": "Mozilla/5.0 (DoorMath IndexNow ping)"}

key_url = SITE + KEY + ".txt"
with urllib.request.urlopen(urllib.request.Request(key_url + "?v=" + REV, headers=UA), timeout=30) as r:
    served = r.read().decode("utf-8").strip()
if served != KEY:
    sys.exit(f"key file at {key_url} does not contain the key")

urls = re.findall(r"<loc>\s*(.*?)\s*</loc>", open("sitemap.xml", encoding="utf-8").read())
bad = [u for u in urls if not u.startswith(SITE)]
if not urls or bad:
    sys.exit(f"sitemap URLs missing or outside {SITE}: {bad}")

payload = {"host": urllib.parse.urlsplit(SITE).netloc, "key": KEY, "keyLocation": key_url, "urlList": urls}
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(payload).encode("utf-8"),
                             headers={**UA, "Content-Type": "application/json; charset=utf-8"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        status, body = r.status, r.read().decode("utf-8", "replace")
except urllib.error.HTTPError as e:
    status, body = e.code, e.read().decode("utf-8", "replace")
print(f"IndexNow: HTTP {status} for {len(urls)} URLs {body[:300]}")
for u in urls:
    print("  " + u)
# 200 = received, 202 = received, key validation pending; anything else is a failure
sys.exit(0 if status in (200, 202) else 1)
