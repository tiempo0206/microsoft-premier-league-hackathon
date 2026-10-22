"""One-command B acceptance: offline checks, analysis export and an owned loopback API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from backend.audit import ROOT
from backend.reporting import build_analysis_report, canonical, export_analysis, output_directory
from backend.settings import Settings
from deploy.preflight import build_report
from deploy.smoke_backend import probe


def run_checks(output):
    results = {}
    for name, directory in (("backend", "tests/backend"), ("common", "tests")):
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", directory,
                                 "-p", "test_*.py", "-q"], cwd=ROOT,
                                capture_output=True, timeout=120)
        log = result.stdout + result.stderr
        (output / f"tests-{name}.log").write_bytes(log)
        count = re.search(rb"Ran (\d+) tests?", log)
        results[name] = {"passed": result.returncode == 0,
                         "tests": int(count.group(1)) if count else None}
        if result.returncode != 0:
            raise ValueError(f"{name} tests failed; inspect the generated test log")
    return results


def runtime_probe(output, data_directory="data/extra/validated-demo"):
    # Reserve a candidate ephemeral loopback port; no fixed user service is stopped.
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        port = candidate.getsockname()[1]
    env = os.environ.copy()
    env.update(MATCHMIND_SERVE_FRONTEND="0", MATCHMIND_DATA_DIR=str(data_directory),
               PYTHONIOENCODING="utf-8", PORT=str(port))
    base = f"http://127.0.0.1:{port}"
    with (output / "server.log").open("wb") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app",
                                    "--host", "127.0.0.1", "--port", str(port), "--workers", "1"],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise ValueError("Owned API process exited before readiness")
                try:
                    with urlopen(base + "/api/v1/health", timeout=0.5) as response:
                        health = json.load(response)
                    if health.get("contract_version") != "2.0.0" or health.get("model_ready") is not False:
                        raise ValueError("Unexpected backend-only health state")
                    break
                except (OSError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise ValueError("Owned API startup deadline expired") from None
                    time.sleep(0.1)
            result = probe(base)
            if process.poll() is not None:
                raise ValueError("Owned API process exited during smoke verification")
            return result
        finally:
            # Windows venv python.exe can be a redirector with a real Python
            # descendant. Stop the tree rooted at our still-owned live child,
            # never enumerate/kill other Python servers by name or port.
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=10)
                else:
                    process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            deadline = time.monotonic() + 3
            while True:
                with socket.socket() as check:
                    check.settimeout(0.2)
                    if check.connect_ex(("127.0.0.1", port)) != 0:
                        break
                if time.monotonic() >= deadline:
                    raise ValueError("Owned listener did not stop")
                time.sleep(0.05)


def source_hashes():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            for directory in (ROOT / "backend", ROOT / "deploy")
            for path in sorted(directory.glob("*.py"))}


def verify_backend(output):
    output = output_directory(output)
    output.mkdir(parents=True, exist_ok=True)
    result = {"status": "running", "contract_version": "2.0.0", "mode": "backend_only_no_adapter",
              "container_image": "not_verified_by_this_command", "public_deployment": "not_performed",
              "frontend_browser": "not_verified_by_this_command", "live_model": "not_connected",
              "source_hash_normalization": "UTF-8 text with LF line endings",
              "source_sha256": source_hashes(), "completed_stages": []}
    stage = "readiness"
    try:
        settings = Settings.from_env()
        if settings.serve_frontend:
            raise ValueError("Backend-only acceptance requires MATCHMIND_SERVE_FRONTEND=0")
        directory = Path(settings.data_directory)
        if not directory.is_absolute():
            directory = ROOT / directory
        readiness = build_report(settings=settings, data_dir=directory)
        (output / "readiness.json").write_text(canonical(readiness), encoding="utf-8", newline="\n")
        if readiness["status"] != "passed":
            raise ValueError("Offline readiness failed")
        result["completed_stages"].append(stage)
        stage = "analysis_export"
        report = build_analysis_report(directory)
        result["analysis_files"] = export_analysis(report, output)
        result["completed_stages"].append(stage)
        stage = "unit_tests"
        result["tests"] = run_checks(output)
        result["completed_stages"].append(stage)
        stage = "HTTP_SSE"
        result["runtime"] = runtime_probe(output, directory)
        result["completed_stages"].append(stage)
        result["status"] = "passed"
    except Exception as error:
        # Never return raw environment values, provider errors or server output.
        result.update(status="failed", failed_stage=stage, error_type=type(error).__name__)
    (output / "acceptance.json").write_text(canonical(result), encoding="utf-8", newline="\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".artifacts/backend-delivery")
    args = parser.parse_args()
    try:
        result = verify_backend(args.output_dir)
    except (ValueError, OSError):
        result = {"status": "failed", "failed_stage": "output_setup"}
    print(canonical({key: value for key, value in result.items() if key != "source_sha256"}), end="")
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
