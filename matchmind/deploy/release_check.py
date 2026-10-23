"""Read-only assembly checks; no model calls, builds, deployment or A/C changes."""
import argparse
import ast
from html.parser import HTMLParser
from importlib import metadata
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from backend.audit import ROOT
from deploy.preflight import build_report as backend_report


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.urls.append(values["src"])
        if tag == "link" and values.get("href") and any(
                word in values.get("rel", "").split() for word in ("stylesheet", "modulepreload")):
            self.urls.append(values["href"])


def frontend_checks(directory):
    directory = Path(directory).resolve()
    entry = directory / "index.html"
    if not entry.is_file():
        return False
    try:
        references = References()
        references.feed(entry.read_text(encoding="utf-8"))
        if not any(urlsplit(url).path.endswith(".js") for url in references.urls):
            return False  # A placeholder index is not an application build.
        for url in references.urls:
            parts = urlsplit(url)
            if parts.scheme or parts.netloc:
                return False  # Runtime script/style assets must be bundled locally.
            asset = (directory / unquote(parts.path).lstrip("/")).resolve()
            if not asset.is_relative_to(directory) or not asset.is_file():
                return False
        for path in directory.rglob("*"):
            if path.is_symlink() or (path.is_file() and (
                    path.name.startswith(".env") or path.suffix.lower() in (".pem", ".key"))):
                return False
        return True
    except (OSError, ValueError, UnicodeError):
        return False


def ai_checks(directory, version=metadata.version):
    directory = Path(directory)
    try:
        for name in ("app.py", "config.py", "service.py", "provider.py", "verify.py"):
            ast.parse((directory / name).read_text(encoding="utf-8"))
        tree = ast.parse((directory / "service.py").read_text(encoding="utf-8"))
        if not any(isinstance(node, ast.AsyncFunctionDef) and node.name == "analyze" for node in tree.body):
            return False, False
        requirements = []
        for line in (directory / "requirements.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line)
            if match is None:
                return True, False
            requirements.append(match.groups())
        if not requirements:
            return True, False
        try:
            return True, all(version(name) == wanted for name, wanted in requirements)
        except metadata.PackageNotFoundError:
            return True, False
    except (OSError, ValueError, SyntaxError, UnicodeError):
        return False, False


def build_report(profile="backend", *, frontend_dist=None, ai_dir=None):
    if profile not in ("backend", "integrated"):
        raise ValueError("Unknown release profile")
    preflight = backend_report()
    checks = [{"name": "audited_reproducible_data", "passed": preflight["status"] == "passed"}]
    if profile == "integrated":
        source, dependencies = ai_checks(ai_dir or ROOT / "ai")
        checks += [{"name": "C_composition_source", "passed": source},
                   {"name": "C_pinned_dependencies_installed", "passed": dependencies},
                   {"name": "A_bundled_frontend_artifact", "passed": frontend_checks(frontend_dist or ROOT/"frontend/dist")},
                   {"name": "same_origin_frontend_enabled", "passed": preflight["runtime"]["serve_frontend"]}]
    return {"status": "passed" if all(check["passed"] for check in checks) else "blocked",
            "profile": profile, "contract_version": "2.0.0", "checks": checks,
            "blocking": [check["name"] for check in checks if not check["passed"]],
            "workers": 1, "replicas": 1, "model_calls": 0,
            "model_endpoint_verified": False, "frontend_browser_verified": False,
            "final_joint_acceptance": "assigned to the team's release integrator",
            "note": "Assembly checks do not establish model readiness or browser behaviour. Run C's explicit probe and final acceptance separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("backend", "integrated"), default="backend")
    args = parser.parse_args()
    try:
        report = build_report(args.profile)
    except (ValueError, OSError):
        report = {"status": "blocked", "blocking": ["invalid_runtime_configuration"], "model_calls": 0}
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
