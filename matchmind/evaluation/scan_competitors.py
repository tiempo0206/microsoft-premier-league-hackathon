"""Scan GitHub for projects submitted to the Microsoft x Premier League hackathon.

Writes a raw inventory to evaluation/research/competitors.json so the team can review the
same evidence. Read-only: it never clones, forks or clones-and-runs third-party code.

Run from matchmind/:
    .\\.venv\\Scripts\\python.exe -m evaluation.scan_competitors
Uses the `gh` CLI for authentication when available, else GITHUB_TOKEN, else anonymous
(rate limited to 10 search requests per minute).
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "research" / "competitors.json"
API = "https://api.github.com"

QUERIES = [
    "insidethegame",
    "insidethegamehackathon",
    "premier league hackathon",
    "microsoft premier league",
    "match intelligence football",
    "football match intelligence agent",
    "synthetic football events",
    "explainable football",
    "tactical intelligence football agent",
]
# Repos created before this are almost certainly unrelated.
SINCE = "2026-09-20"


def token():
    for env in ("GITHUB_TOKEN", "GH_TOKEN"):
        import os
        if os.getenv(env):
            return os.getenv(env)
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                             timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def get(url, auth, tries=3):
    for attempt in range(tries):
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "matchmind-research",
            **({"Authorization": "Bearer " + auth} if auth else {}),
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                time.sleep(6 + attempt * 6)
                continue
            return {"__error__": "HTTP %d" % error.code}
        except (urllib.error.URLError, TimeoutError) as error:
            time.sleep(3)
            if attempt == tries - 1:
                return {"__error__": type(error).__name__}
    return {"__error__": "rate limited"}


def search(query, auth):
    url = (API + "/search/repositories?q=" + urllib.parse.quote(query + " created:>=" + SINCE)
           + "&per_page=50&sort=updated")
    payload = get(url, auth)
    if "__error__" in payload:
        return [], payload["__error__"]
    return payload.get("items", []), None


def main():
    auth = token()
    inventory, seen, errors = {}, set(), {}
    for query in QUERIES:
        items, error = search(query, auth)
        if error:
            errors[query] = error
            print("  ! %-40s %s" % (query, error), flush=True)
            continue
        print("  %-42s %d" % (query, len(items)), flush=True)
        for item in items:
            name = item["full_name"]
            if name in seen:
                continue
            seen.add(name)
            inventory[name] = {
                "full_name": name,
                "description": (item.get("description") or "").strip(),
                "created_at": (item.get("created_at") or "")[:10],
                "pushed_at": (item.get("pushed_at") or "")[:10],
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language"),
                "size_kb": item.get("size", 0),
                "topics": item.get("topics", []),
                "fork": item.get("fork", False),
                "html_url": item.get("html_url"),
                "default_branch": item.get("default_branch"),
            }
        time.sleep(2)

    print("total candidates: %d" % len(inventory), flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"since": SINCE, "queries": QUERIES, "errors": errors,
                               "repositories": inventory}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("wrote " + str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
