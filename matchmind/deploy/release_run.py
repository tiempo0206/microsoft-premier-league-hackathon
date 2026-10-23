"""Release entry after the integrator supplies reviewed A/C artifacts."""
import json
import asyncio

import uvicorn

from backend.settings import port_from_env
from .release_check import build_report
from backend.data import read_json
from backend.audit import ROOT
from backend.settings import Settings
from pathlib import Path


def main():
    port = port_from_env()
    report = build_report("integrated")
    if report["status"] != "passed":
        print(json.dumps(report))
        raise SystemExit(2)
    directory = Path(Settings.from_env().data_directory)
    if not directory.is_absolute():
        directory = ROOT / directory
    if read_json(directory / "PROVENANCE.json")["kind"] == "original_scripted_synthetic":
        from .adapter_check import check_adapter
        compatibility = asyncio.run(check_adapter())
        if compatibility["status"] != "passed":
            print(json.dumps(compatibility))
            raise SystemExit(2)
    # C owns this composition root and all model/semantic implementation.
    uvicorn.run("ai.app:app", host="0.0.0.0", port=port, workers=1)


if __name__ == "__main__":
    main()
