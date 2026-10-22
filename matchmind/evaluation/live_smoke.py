"""One real end-to-end analysis against the shipped fixture. Billable, so opt-in.

    .\\.venv\\Scripts\\python.exe -m evaluation.live_smoke
    .\\.venv\\Scripts\\python.exe -m evaluation.live_smoke --team AWAY --language zh

Prints a sanitised report. Never prints the API key. Writes nothing to disk unless
--out is given, and the output contains no credential by construction.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import from_env                      # noqa: E402
from ai.provider import ChatCompletionsProvider     # noqa: E402
from ai.service import analyze                      # noqa: E402
from backend.data import Catalog                    # noqa: E402
from backend.inputs import analysis_input           # noqa: E402
from contracts.validation import can_publish, check_result   # noqa: E402


def build_request(team, language, start, end, task_id):
    fixture = Catalog(ROOT / "data/extra/validated-demo").fixtures["MM-DEMO-01"]
    return analysis_input(fixture, replay_id="REPLAY-LIVE", run_id=1, task_id=task_id,
                          start_sec=start, end_sec=end, team_id=team, language=language)


def summarise(result):
    insight = result.get("insight")
    return {
        "status": result["status"],
        "error": result.get("error"),
        "generation": None if not insight else insight["generation"],
        "verification": None if not insight else insight["verification"],
        "claims": [] if not insight else [
            {"id": c["claim_id"], "kind": c["kind"], "metric": c["metric_key"],
             "value": c["metric_value"], "evidence": len(c["evidence_event_ids"])}
            for c in insight["claims"]],
        "narratives": None if not insight else insight["narratives"],
        "evidence_event_ids": None if not insight else insight["evidence_event_ids"],
        "traces": [{"agent": t["agent"], "status": t["status"], "ms": t["duration_ms"]}
                   for t in result["traces"]],
    }


async def main_async(args):
    config = from_env()
    report = {"config": config.public(), "args": vars(args)}
    if not config.configured:
        report["error"] = "no model configured; run ai.probe first"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    request = build_request(args.team, args.language, args.start, args.end, args.task_id)
    report["request"] = {"match_id": request["match_id"], "window": request["window"],
                         "team": request["team_id"], "language": request["language"],
                         "events": len(request["events"]), "metrics": request["metrics"]}
    provider = ChatCompletionsProvider(config)
    started = time.monotonic()
    result = await analyze(request, config=config, provider=provider)
    outcome = None
    try:
        check_result(request, result)
        outcome = "contract_valid"
    except Exception as error:                      # noqa: BLE001 - report, never raise
        outcome = "CONTRACT_INVALID: " + type(error).__name__ + ": " + str(error)
    published = False
    if result.get("insight"):
        published = can_publish(result, {"replay_id": "REPLAY-LIVE", "run_id": 1,
                                         "clock_sec": request["window"]["end_sec"]})
    report.update({
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "contract": outcome,
        "publishable": published,
        "model_calls": provider.calls,
        "usage": provider.last_usage,
        "result": summarise(result),
    })
    if args.debug:
        report["raw_agent_outputs"] = getattr(provider, "raw_outputs", [])
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote " + args.out)
    print(text)
    return 0 if outcome == "contract_valid" and result["status"] in ("passed", "fallback") else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="MatchMind live analysis smoke test")
    parser.add_argument("--team", default="HOME", choices=["HOME", "AWAY"])
    parser.add_argument("--language", default="en", choices=["en", "zh"])
    parser.add_argument("--start", type=int, default=1500)
    parser.add_argument("--end", type=int, default=1650)
    parser.add_argument("--task-id", default="TASK-LIVE-01")
    parser.add_argument("--out", default=None)
    parser.add_argument("--debug", action="store_true",
                        help="include the raw output of each agent")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
