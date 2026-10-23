"""Pull the README of selected competitor repositories for design review.

Read-only. Writes to evaluation/research/readmes/ so the team reviews the same evidence.
No third-party code is executed, vendored or installed.

    .\\.venv\\Scripts\\python.exe -m evaluation.fetch_readmes
    .\\.venv\\Scripts\\python.exe -m evaluation.fetch_readmes --repo owner/name
"""
import argparse
import base64
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "research" / "readmes"
API = "https://api.github.com"

# Chosen for one specific reason each, not as a popularity list.
TARGETS = [
    ("Wael-Akhdar/InsideTheGame", "Agent Framework + MCP + Foundry fine-tune"),
    ("likalight/touchline", "multi-agent explainability, closest structural rival"),
    ("pshah208/matchlens", "evidence-first grounded claims, our own thesis"),
    ("Zhiyilang/matchlens", "cited insights"),
    ("Adamzuckk/Rematch", "counterfactual comparison"),
    ("dhruvkulkarni02/second-act", "self-checking tactical read"),
    ("diego-sicignano/soundpitch", "accessibility angle for impact"),
    ("iSharaf6/regista", "match director framing"),
    ("abhiiiesh/MatchMind", "identical product name"),
    ("TheNeuralWars/matchmind", "identical product name"),
    ("sagitta414/before-the-roar", "personalisation depth"),
    ("lauramiro/the-dugout", "explains a manager's decisions"),
    ("TomThomasPrintac/live-sub-intel", "substitution intelligence niche"),
    ("Zidup123/ShapeShift-Explainable-Tactical-Shape-Intelligence", "tactical shape"),
    ("bradhack/lasso", "live playable match intelligence"),
    ("enniob/pitchlens", "same hackathon, TypeScript"),
    ("GOkwori/matchdesk", "production-studio framing"),
    ("SairajBandre16/tacticlens", "Azure deployment angle"),
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


def get_json(url, auth):
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


def readme(full_name, auth):
    for name in ("README.md", "readme.md", "README.MD", "README.rst", "README.txt"):
        payload = get_json(API + "/repos/" + full_name + "/contents/" + urllib.parse.quote(name), auth)
        if "__error__" in payload or not isinstance(payload, dict) or "content" not in payload:
            continue
        return base64.b64decode(payload["content"]).decode("utf-8", "replace")
    return None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action="append", default=None)
    args = parser.parse_args(argv)
    targets = [(r, "ad-hoc") for r in args.repo] if args.repo else TARGETS
    auth = token()
    if not auth:
        print("no GitHub token available; anonymous requests are heavily rate limited")
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for full_name, why in targets:
        meta = get_json(API + "/repos/" + full_name, auth)
        if "__error__" in meta:
            report[full_name] = {"why": why, "error": meta["__error__"]}
            print("  ! %-52s %s" % (full_name, meta["__error__"]), flush=True)
            continue
        text = readme(full_name, auth)
        if text is None:
            report[full_name] = {"why": why, "error": "no readme"}
            print("  - %-52s no readme" % full_name, flush=True)
            continue
        safe = full_name.replace("/", "__")
        (OUT / (safe + ".md")).write_text(text, encoding="utf-8")
        report[full_name] = {
            "why": why, "description": meta.get("description"), "stars": meta.get("stargazers_count"),
            "created_at": (meta.get("created_at") or "")[:10], "language": meta.get("language"),
            "size_kb": meta.get("size"), "topics": meta.get("topics", []),
            "readme_chars": len(text), "file": safe + ".md",
        }
        print("  ok %-52s %6d chars" % (full_name, len(text)), flush=True)
    (ROOT / "evaluation" / "research" / "readme-index.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
