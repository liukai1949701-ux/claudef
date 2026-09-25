#!/usr/bin/env python3
"""Build the deployable GitHub Pages copy of the storefront into ./_site.

Copies the site, substitutes the placeholder tokens, and leaves out development-only
files (tests, full-size source screenshots). Usage:
    python3 tools/build_site.py --site-url https://USER.github.io/REPO --repo-url https://github.com/USER/REPO \
        --test-workbooks 271 --test-checks 238,564
"""
import argparse
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"tests", "tools", "_site", ".git", os.path.join("assets", "shots")}
SKIP_FILES = {".gitignore", "README.md"}
TEXT_EXT = (".html", ".xml", ".txt", ".js", ".css", ".json", ".webmanifest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-url", required=True)
    ap.add_argument("--repo-url", required=True)
    ap.add_argument("--test-workbooks", required=True)
    ap.add_argument("--test-checks", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"))
    a = ap.parse_args()
    tokens = {"{{SITE_URL}}": a.site_url.rstrip("/"), "{{REPO_URL}}": a.repo_url.rstrip("/"),
              "{{TEST_WORKBOOKS}}": a.test_workbooks, "{{TEST_CHECKS}}": a.test_checks}
    if os.path.isdir(a.out):
        shutil.rmtree(a.out)
    n = 0
    for dp, dirs, files in os.walk(ROOT):
        rel_dir = os.path.relpath(dp, ROOT)
        dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(rel_dir, d)) not in SKIP_DIRS]
        for f in files:
            rel = os.path.normpath(os.path.join(rel_dir, f))
            if rel in SKIP_FILES:
                continue
            dst = os.path.join(a.out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if f.endswith(TEXT_EXT):
                text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
                for k, v in tokens.items():
                    text = text.replace(k, v)
                assert "{{" not in text or f.endswith((".js", ".css")), f"unreplaced token in {rel}"
                open(dst, "w", encoding="utf-8").write(text)
            else:
                shutil.copy2(os.path.join(ROOT, rel), dst)
            n += 1
    for bad in (".xlsx", ".xls", ".zip"):
        for dp, _, files in os.walk(a.out):
            assert not any(f.lower().endswith(bad) for f in files), f"paid-file type {bad} in build"
    print(f"built {n} files into {a.out}")


if __name__ == "__main__":
    main()
