"""One real end-to-end analysis against the shipped fixture. Billable, so opt-in.

    .\\.venv\\Scripts\\python.exe -m evaluation.live_smoke
    .\\.venv\\Scripts\\python.exe -m evaluation.live_smoke --team AWAY --language zh
    .\\.venv\\Scripts\\python.exe -m evaluation.live_smoke --record live-run.json

Prints a sanitised report. Never prints the API key. With `--record NAME` it also writes a
redacted evidence file into `evaluation/evidence/`, which is committed, so a reviewer can see that a
real model produced a real card without taking anyone's word for it. Acceptance criterion 5 in
`docs/05_acceptance.md` asks for exactly that: "真实模型至少完成一次实际解释与审核流程，保留经过脱敏的
模型和耗时证据". The recorded file carries the model name, the per-agent traces, the usage figures and
the contract outcome; it does not carry the key, the endpoint credentials, or anything whose absence
would let the file stand in for a fresh run.
"""
import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import from_env                      # noqa: E402
from ai.prompts import PROMPT_VERSION               # noqa: E402
from ai.provider import ChatCompletionsProvider     # noqa: E402
from ai.service import analyze                      # noqa: E402
from ai.usage import describe as describe_usage     # noqa: E402
from backend.data import Catalog                    # noqa: E402
from backend.inputs import analysis_input           # noqa: E402
from contracts.validation import can_publish, check_result   # noqa: E402

EVIDENCE_DIR = ROOT / "evaluation" / "evidence"
_KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9]{16,}")


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
        # Keep the note. It is where the orchestrator announces itself ("orchestrator=framework"),
        # and an evidence file that cannot show which path ran is not evidence of the framework.
        "traces": [{"agent": t["agent"], "status": t["status"], "ms": t["duration_ms"],
                    **({"note": t["note"]} if t.get("note") else {})}
                   for t in result["traces"]],
        "agent_invocations": sum(1 for t in result["traces"] if t["status"] == "completed"),
    }


def provenance():
    """Enough context that the record can be checked, not just read."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    return {
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_head": head or "unknown",
        "prompt_version": PROMPT_VERSION,
        "contract_version": (ROOT / "contracts" / "VERSION").read_text(encoding="utf-8").strip(),
        "synthetic_data": True,
    }


def record(report, name):
    """Write a credential-free evidence file into the committed evidence directory.

    Refuses rather than redacts: if a key-shaped string or the configured key itself appears
    anywhere in the payload, nothing is written and the caller gets an error. Silently scrubbing
    would leave a file whose provenance nobody can vouch for.
    """
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    secret = report.get("_api_key") or ""
    if secret and secret in text:
        raise ValueError("refusing to record: the API key is present in the report")
    if _KEY_SHAPE.search(text):
        raise ValueError("refusing to record: a key-shaped string is present in the report")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / name
    path.write_text(text + "\n", encoding="utf-8")
    return path


async def main_async(args):
    config = from_env()
    report = {"config": config.public(), "args": {k: v for k, v in vars(args).items()
                                                  if k != "record"}}
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
    orchestrator = config.public().get("orchestrator")
    report.update({
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "contract": outcome,
        "publishable": published,
        # The framework path never touches ChatCompletionsProvider, so this counter reads 0 there.
        # Printing a bare "model_calls: 0" next to a live_model card is worse than printing nothing:
        # it looks like no model was called. Say which counter this is and give the number that
        # actually counts, taken from the trace.
        "model_calls_direct_provider": provider.calls,
        "model_calls_note": ("Counter on the direct Chat Completions provider. The Agent Framework "
                             "orchestrator calls the model through its own client, so this reads 0 "
                             "on a framework run; use result.agent_invocations there."),
        "usage": provider.last_usage,
        "usage_line": describe_usage(provider.usage),
        "result": summarise(result),
    })
    if orchestrator == "framework" and report["model_calls_direct_provider"] == 0:
        report["usage_line"] = ("not measured on this path: the Agent Framework client owns the "
                                "HTTP call, so the provider ledger is empty by construction")
    if args.debug:
        report["raw_agent_outputs"] = getattr(provider, "raw_outputs", [])
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote " + args.out)
    print(text)
    if args.record:
        payload = dict(report)
        payload.pop("_api_key", None)
        payload["provenance"] = provenance()
        payload["note"] = ("A single real run, kept as evidence that a live model produced a card "
                           "through the three-agent pipeline and the code gate. It is not a "
                           "benchmark, not a reliability figure, and it is not a substitute for "
                           "running the harnesses in evaluation/.")
        try:
            print("recorded " + str(record(payload, args.record)))
        except ValueError as error:
            print("NOT RECORDED: " + str(error))
            return 3
    return 0 if outcome == "contract_valid" and result["status"] in ("passed", "fallback") else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="MatchMind live analysis smoke test")
    parser.add_argument("--team", default="HOME", choices=["HOME", "AWAY"])
    parser.add_argument("--language", default="en", choices=["en", "zh"])
    parser.add_argument("--start", type=int, default=1500)
    parser.add_argument("--end", type=int, default=1650)
    parser.add_argument("--task-id", default="TASK-LIVE-01")
    parser.add_argument("--out", default=None)
    parser.add_argument("--record", default=None, metavar="NAME.json",
                        help="also write a redacted evidence file into evaluation/evidence/")
    parser.add_argument("--debug", action="store_true",
                        help="include the raw output of each agent")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
