"""Explicit OFFLINE C compatibility gate for B's denser candidate datasets.

Imports C read-only, calls bare analyze(request), blocks network connections,
and validates outputs. No model configuration, key or provider is supplied.
"""
import argparse
import asyncio
import copy
import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

from backend.reporting import output_directory
from backend.showcase import build_packet
from contracts.validation import check_result


class NetworkForbidden(RuntimeError):
    pass


def no_network(*args, **kwargs):
    raise NetworkForbidden("Offline adapter check prohibits network connections")


async def check_adapter(analyzer=None):
    packet = build_packet()
    failures, tampered = [], []
    passed = 0
    # The event loop already exists before the guard is installed (important for
    # Windows' loop initialization). This is a trusted-adapter test, not a sandbox.
    with patch("socket.create_connection", no_network), patch("socket.socket.connect", no_network), \
         patch("socket.socket.connect_ex", no_network), patch("socket.getaddrinfo", no_network):
        if analyzer is None:
            try:
                analyzer = importlib.import_module("ai.service").analyze
            except Exception:
                return {"status": "blocked", "reason": "C_adapter_unavailable", "model_calls": 0}
        if not inspect.iscoroutinefunction(analyzer):
            return {"status": "blocked", "reason": "C_adapter_must_be_async", "model_calls": 0}
        for request in packet["requests"]:
            try:
                result = await asyncio.wait_for(analyzer(copy.deepcopy(request)), timeout=5)
                check_result(request, result)
                if result["status"] == "rejected":
                    raise ValueError("Normal request was refused")
                passed += 1
            except Exception as error:
                # Do not print C's exception text/result: it could contain credentials.
                failure = {"task_id": request["task_id"], "reason": "normal_output_invalid",
                           "error_type": type(error).__name__}
                if isinstance(error, NetworkForbidden):
                    failure["reason"] = "network_attempt_blocked"
                elif "result" in locals() and isinstance(result, dict):
                    insight = result.get("insight")
                    if isinstance(insight, dict):
                        claims = insight.get("claims")
                        evidence = insight.get("evidence_event_ids")
                        if (isinstance(claims, list) and isinstance(evidence, list)
                                and all(isinstance(eid, str) for eid in evidence)):
                            known = {e["event_id"] for e in request["events"]}
                            used = {eid for claim in claims if isinstance(claim, dict)
                                    and isinstance(claim.get("evidence_event_ids"), list)
                                    for eid in claim["evidence_event_ids"] if isinstance(eid, str)}
                            failure["missing_from_insight_evidence"] = sorted((used - set(evidence)) & known)
                failures.append(failure)
            finally:
                result = None
        for case in packet["tampered"]:
            refused = False
            try:
                result = await asyncio.wait_for(analyzer(copy.deepcopy(case["request"])), timeout=5)
                refused = result["status"] == "rejected"
            except ValueError:
                refused = True  # Transport-invalid requests may raise immediately.
            except Exception:
                pass
            tampered.append({"case_id": case["case_id"], "refused": refused})
    return {"status": "passed" if not failures and all(c["refused"] for c in tampered) else "blocked",
            "valid_requests_passed": passed, "valid_request_failures": failures,
            "tampered_results": tampered, "model_calls": 0, "network_connections": "blocked",
            "scope": "offline result contract compatibility; no model-quality or browser claim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(check_adapter())
    text = json.dumps(report, ensure_ascii=False, indent=2)+"\n"
    if args.output:
        destination = output_directory(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
