"""Scan the open-source football analytics ecosystem for reusable parts.

Read-only: queries the GitHub API for the projects C would actually consider and records
licence, activity and size so the team can judge reuse rather than guess. Writes to
evaluation/research/football_oss.json.

    .\\.venv\\Scripts\\python.exe -m evaluation.scan_football_oss
"""
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "research" / "football_oss.json"
API = "https://api.github.com"

# Chosen by what they could actually give us, not by popularity.
CANDIDATES = [
    ("ML-KULeuven/socceraction", "event data to SPADL actions, expected threat and VAEP"),
    ("probberechts/soccerdata", "scrapers for many public football data sources"),
    ("PySport/kloppy", "one interface over event and tracking providers"),
    ("andrewRowlinson/mplsoccer", "pitch plotting, xG plots, radar charts"),
    ("statsbomb/statsbombpy", "StatsBomb open data client"),
    ("statsbomb/open-data", "StatsBomb open event data and its licence"),
    ("koenvoetbal/floodlight", "unified event data model, successor to kloppy ideas"),
    ("Alek050/databallpy", "tracking and event data synchronisation"),
    ("eddwebster/football_analytics", "curated list of football analytics sources"),
    ("deepsport-analytics/deepsport", "broadcast video tracking pipeline"),
    ("UnravelSports/SoccerMap", "pitch control and space valuation"),
    ("karangandhi1/football-analytics", "xT and pitch control notebooks"),
    ("openfootball/football.json", "plain-JSON results and fixtures"),
    ("mfyz/expected-goals", "simple xG models"),
    ("soccer-analytics/soccer-analytics", "community reference implementations"),
]


def token():
    import os
    for env in ("GITHUB_TOKEN", "GH_TOKEN"):
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


def get(url, auth):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "matchmind-research",
        **({"Authorization": "Bearer " + auth} if auth else {})})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return {"__error__": "HTTP %d" % error.code}
    except (urllib.error.URLError, TimeoutError) as error:
        return {"__error__": type(error).__name__}


def _ascii(text, limit=60):
    """Console-safe rendering: some upstream descriptions carry emoji and this shell is GBK."""
    safe = (text or "").encode("ascii", "replace").decode("ascii")
    return safe[:limit]


def main():
    auth = token()
    if not auth:
        print("no GitHub token; requests are heavily rate limited")
    inventory = {}
    for full_name, why in CANDIDATES:
        meta = get(API + "/repos/" + full_name, auth)
        if "__error__" in meta:
            inventory[full_name] = {"why": why, "error": meta["__error__"]}
            print("  ! %-42s %s" % (full_name, meta["__error__"]), flush=True)
            continue
        licence = (meta.get("license") or {}).get("spdx_id")
        inventory[full_name] = {
            "why": why,
            "description": (meta.get("description") or "").strip(),
            "stars": meta.get("stargazers_count"),
            "language": meta.get("language"),
            "size_kb": meta.get("size"),
            "licence": licence,
            "licence_name": (meta.get("license") or {}).get("name"),
            "archived": meta.get("archived"),
            "pushed_at": (meta.get("pushed_at") or "")[:10],
            "topics": meta.get("topics", []),
            "html_url": meta.get("html_url"),
        }
        print("  %-42s %6s stars  %-14s %s"
              % (full_name, meta.get("stargazers_count"), licence or "NO LICENCE",
                 _ascii(meta.get("description"))), flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote " + str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
