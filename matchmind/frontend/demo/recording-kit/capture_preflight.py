"""Append a public HTTP/build snapshot without changing earlier evidence.

Run with the existing MatchMind .venv (httpx is a pinned project dependency).
Only GET requests are made; no replay or model workflow is started.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

import httpx


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing evidence snapshot")

    origin = "https://matchmind-backend-preview.onrender.com"
    dist = Path(__file__).resolve().parents[2] / "dist"
    reference = git("rev-parse", "HEAD")
    started = datetime.now(timezone.utc).isoformat()

    def paths(html: str) -> list[str]:
        return sorted(set(re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)))

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        def get(path: str) -> httpx.Response:
            response = client.get(origin + path)
            response.raise_for_status()
            return response

        root = get("/")
        health = get("/api/v1/health")
        matches = get("/api/v1/matches")
        local_paths = paths((dist / "index.html").read_text())
        public_paths = paths(root.text)
        assets = []
        for path in local_paths:
            local = (dist / path.lstrip("/")).read_bytes()
            public = get(path)
            assets.append({
                "name": path.rsplit("/", 1)[-1],
                "http_status": public.status_code,
                "local_sha256": hashlib.sha256(local).hexdigest(),
                "public_sha256": hashlib.sha256(public.content).hexdigest(),
                "byte_identical": local == public.content,
            })

    catalogue = [{key: match[key] for key in ("match_id", "home", "away", "synthetic")}
                 for match in matches.json()]
    checks = {
        "health_ok": health.json() == {
            "status": "ok", "contract_version": "2.0.0",
            "mode": "production", "model_ready": True,
        },
        "synthetic_catalogue": catalogue == [{
            "match_id": "MM-DEMO-01", "home": "Harbor FC",
            "away": "Mountain United", "synthetic": True,
        }],
        "asset_paths_match": bool(local_paths) and local_paths == public_paths,
        "asset_bytes_match": bool(assets) and all(a["byte_identical"] for a in assets),
    }
    result = {
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_date": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d"),
        "client_timezone": "Asia/Shanghai",
        "origin": origin,
        "root_http_status": root.status_code,
        "health_http_status": health.status_code,
        "matches_http_status": matches.status_code,
        "health_response": health.json(),
        "catalogue": catalogue,
        "assets": assets,
        "local_asset_paths": local_paths,
        "public_asset_paths": public_paths,
        "local_reference_commit": reference,
        "local_dist_dirty": bool(git("status", "--porcelain", "--", str(dist))),
        "deployment_revision": "Not inferred from asset equality",
        "public_browser_acceptance": "No new browser walkthrough in this HTTP snapshot",
        "new_live_model_workflows": 0,
        "video_capture_complete": False,
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "passed": result["passed"],
                      "assets": [a["name"] for a in assets]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
