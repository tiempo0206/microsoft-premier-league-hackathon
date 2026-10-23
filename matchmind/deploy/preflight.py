"""Read-only offline backend readiness. Never starts Docker, a browser, or a cloud job."""
import argparse
import json
from pathlib import Path

from backend.audit import ROOT, audit_dataset
from backend.settings import Settings, port_from_env
from backend.data import read_json
from data.generator.prepare_demo import contents


def build_report(settings=None, data_dir=None):
    settings = settings or Settings.from_env()
    directory = Path(data_dir) if data_dir is not None else Path(settings.data_directory)
    if not directory.is_absolute():
        directory = ROOT / directory
    data = audit_dataset(directory)
    try:
        provenance = read_json(directory / "PROVENANCE.json")
        if provenance.get("kind") == "original_scripted_synthetic":
            from data.generator.showcase import contents as showcase_contents
            expected = showcase_contents(provenance["scenario"], provenance["seed"])
        else:
            expected = contents()
        mismatches = [name for name, value in expected.items()
                      if not (directory / name).is_file() or (directory / name).read_bytes() != value]
    except Exception:
        mismatches = ["source_or_prepared_files"]
    if mismatches:
        data["issues"].append({"code": "REPRODUCIBILITY_MISMATCH", "detail": ", ".join(mismatches)})
        data["status"] = "failed"
    return {"status": data["status"], "contract_version": "2.0.0", "data": data,
            "runtime": {"port": port_from_env(), "workers": 1, "serve_frontend": settings.serve_frontend,
                        "max_sessions": settings.max_sessions, "state_storage": "process_memory"},
            "required_credentials": [], "model_calls": "disabled",
            "container_build": "not_checked_by_this_offline_command",
            "public_deployment": "not_performed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination; no report is written by default")
    args = parser.parse_args(argv)
    try:
        report = build_report(data_dir=args.data_dir)
    except ValueError as error:
        # Settings errors name fields, not their values or credentials.
        report = {"status": "failed", "issues": [{"code": "INVALID_CONFIG", "detail": str(error)}]}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8", newline="\n")
    print(output, end="")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
