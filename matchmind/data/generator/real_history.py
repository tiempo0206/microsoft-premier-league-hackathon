"""Offline checks and optional original-archive fetch for historical research.

Not imported by the app. Never writes a runtime fixture or changes configuration.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "data/extra/real-history-wyscout"
DEFAULT_CACHE = ROOT / ".artifacts/real-history-source-cache"


def digest(path):
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024*1024):
            size += len(chunk)
            sha.update(chunk)
            md5.update(chunk)
    return {"bytes": size, "sha256": sha.hexdigest(), "md5": md5.hexdigest()}


def read_json(path):
    def invalid(value):
        raise ValueError("Non-finite number")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=invalid)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(package=PACKAGE):
    package = Path(package).resolve()
    manifest = read_json(package / "manifest.json")
    if (manifest.get("kind") != "historical_real_research_only" or manifest.get("synthetic") is not False
            or manifest.get("runtime_compatible") is not False):
        raise ValueError("Research source must not masquerade as a runtime fixture")
    for name, expected in manifest["payload_files"].items():
        path = (package / name).resolve()
        if not path.is_relative_to(package) or not path.is_file():
            raise ValueError("Payload path escapes the research package")
        actual = digest(path)
        if actual["bytes"] != expected["bytes"] or actual["sha256"] != expected["sha256"]:
            raise ValueError("Research payload checksum mismatch")
    sample = manifest["sample"]
    if any(sample[key] not in manifest["payload_files"] for key in ("match_file", "events_file", "clip_file")):
        raise ValueError("Sample references must be checksummed package payloads")
    match = read_json(package / sample["match_file"])
    rows = read_rows(package / sample["events_file"])
    clip = read_rows(package / sample["clip_file"])
    if (match["wyId"] != sample["match_id"] or len(rows) != sample["full_match_events"]
            or len(clip) != sample["clip_events"] or len({e["id"] for e in rows}) != len(rows)):
        raise ValueError("Sample identity/count mismatch")
    for event in rows:
        if event["matchId"] != match["wyId"] or not math.isfinite(event["eventSec"]) or event["eventSec"] < 0:
            raise ValueError("Invalid original event identity/time")
        for point in event["positions"]:
            if not all(isinstance(point[k], (int, float)) and math.isfinite(point[k])
                       and 0 <= point[k] <= 100 for k in ("x", "y")):
                raise ValueError("Invalid original event position")
    start, end = sample["clip_sec"]
    expected_clip = [e for e in rows if e["matchPeriod"] == sample["clip_period"]
                     and start <= e["eventSec"] <= end]
    if clip != expected_clip:
        raise ValueError("Clip is not the original closed-interval selection")
    return {"status": "passed", "kind": manifest["kind"], "synthetic": False,
            "runtime_compatible": False, "match_id": match["wyId"],
            "full_match_events": len(rows), "clip_events": len(clip), "model_calls": 0}


def cache_directory(directory):
    directory = Path(directory).resolve()
    repository = ROOT.parent.resolve()
    if directory.is_relative_to(repository) and not directory.is_relative_to((ROOT / ".artifacts").resolve()):
        raise ValueError("Original downloads belong outside tracked source/runtime data")
    return directory


def fetch_archive(spec, directory):
    directory = cache_directory(directory)
    parts = urlsplit(spec["source"])
    if (parts.scheme != "https" or parts.hostname != "ndownloader.figshare.com"
            or parts.username or parts.password or parts.query or parts.fragment
            or not re.fullmatch(r"/files/[0-9]+", parts.path)
            or spec["file"] not in ("events.zip", "matches.zip")
            or not 0 < spec["bytes"] < 100_000_000):
        raise ValueError("Unexpected original download specification")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / spec["file"]
    def matches(path):
        actual = digest(path)
        return all(actual[key] == spec[key] for key in ("bytes", "md5", "sha256"))
    if target.exists():
        if not matches(target):
            raise ValueError("Existing archive differs; preserve it and select a clean cache directory")
        return {"file": target.name, "status": "verified_cached"}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".source-", suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            total = 0
            with urlopen(spec["source"], timeout=30) as response:
                while chunk := response.read(1024*1024):
                    total += len(chunk)
                    if total > spec["bytes"]:
                        raise ValueError("Download exceeds published size")
                    output.write(chunk)
        if not matches(temporary):
            raise ValueError("Original archive checksum mismatch")
        if target.exists():
            raise ValueError("Cache changed during download; preserve existing target")
        temporary.replace(target)
        return {"file": target.name, "status": "downloaded_and_verified"}
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()  # Only this function's disposable partial file.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Read the committed samples; default, no network")
    parser.add_argument("--fetch-full", action="store_true", help="Optional original archives, not required for samples")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()
    try:
        report = verify()
        if args.fetch_full:
            manifest = read_json(PACKAGE / "manifest.json")
            report["archives"] = [fetch_archive(spec, args.cache_dir) for spec in manifest["archives"]]
        print(json.dumps(report))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__,
                          "runtime_changed": False, "model_calls": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
