"""Container entry: use the host's port, exactly one worker, no model provisioning."""
import json
import uvicorn
from backend.settings import port_from_env
from deploy.preflight import build_report


def main():
    try:
        port = port_from_env()
        report = build_report()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    if report["status"] != "passed":
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(2)
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, workers=1)


if __name__ == "__main__":
    main()
