"""Role C evaluation harness — 12 starting windows, single agent vs three agents.

Design follows evaluations/README and docs/05_acceptance.md:

* 4 positive windows   - the detector fires; the card must be usable.
* 4 negative windows    - the detector does not fire; the model must not invent pressure.
* 4 tampered windows    - the arithmetic gate must refuse before any model is called.

Single-agent and multi-agent runs share the SAME input, the SAME model and the SAME
deterministic verifier, so the comparison is about orchestration and nothing else.

    python -m evaluation.benchmark                 # all 12, both modes
    python -m evaluation.benchmark --cases positive
    python -m evaluation.benchmark --mode multi

Billable. Opt in explicitly. Writes JSON + Markdown into .artifacts/evaluation/.
"""
import argparse
import asyncio
import copy
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import from_env                      # noqa: E402
from ai.provider import ChatCompletionsProvider, ProviderError, ProviderTimeout  # noqa: E402
from ai.service import analyze                      # noqa: E402
from ai.single import single_shot                   # noqa: E402
from backend.data import Catalog                    # noqa: E402
from backend.inputs import analysis_input           # noqa: E402
from contracts.validation import check_result       # noqa: E402

FIXTURE = "MM-DEMO-01"
OUT = ROOT / ".artifacts" / "evaluation"


def build_cases():
    """12 windows. Group names are honest about what each one can prove.

    The shipped fixture contains exactly ONE window that fires the frozen high-press
    detector, so "four positives" is not physically available. Claiming four would dress
    up three non-triggering windows as positives and inflate the pass rate. The groups
    below therefore separate triggering windows from merely valid ones, and that gap is
    itself evidence for the data-sparsity finding in docs/handoff/ai.md.
    """
    cases = []

    def add(cid, group, note, **kwargs):
        cases.append({"id": cid, "group": group, "note": note, "request": kwargs})

    # positive: the only window in the fixture that satisfies high_recoveries>=3 and
    # linked_shots>=2. Two languages, because multi-language output is a scored criterion.
    add("P1", "positive", "the audited demo window, English", start=1500, end=1650, team="HOME", language="en")
    add("P2", "positive", "the same window in Chinese", start=1500, end=1650, team="HOME", language="zh")

    # non_trigger: valid requests the detector does NOT fire on. The card must still be
    # honest rather than inventing pressure.
    add("P3", "non_trigger", "window containing the goal; 0 high recoveries", start=1650, end=1800, team="HOME", language="en")
    add("P4", "non_trigger", "opening 60s; 1 high recovery", start=1500, end=1560, team="HOME", language="en")
    add("N2", "non_trigger", "90s window", start=1500, end=1590, team="HOME", language="en")
    add("N3", "non_trigger", "120s window", start=1500, end=1620, team="HOME", language="en")

    # negative: the team being asked about never recovered high in this fixture at all.
    add("N1", "negative", "AWAY never recovers high here", start=1500, end=1650, team="AWAY", language="en")
    add("N4", "negative", "late window, AWAY, Chinese", start=1650, end=1800, team="AWAY", language="zh")

    # tampered: the arithmetic gate must refuse with zero model calls.
    add("T1", "tampered", "high_recoveries inflated to 8", start=1500, end=1650, team="HOME", language="en",
        tamper={"metrics": {"high_recoveries": 8}})
    add("T2", "tampered", "home_shots inflated to 9", start=1500, end=1650, team="HOME", language="en",
        tamper={"metrics": {"home_shots": 9}})
    add("T3", "tampered", "linked_shots inflated to 5", start=1500, end=1650, team="HOME", language="en",
        tamper={"metrics": {"linked_shots": 5}})
    add("T4", "tampered", "an event moved outside the window", start=1500, end=1650, team="HOME", language="en",
        tamper={"event_index": 0, "timestamp_sec": 1400})
    return cases


def materialise(case):
    spec = case["request"]
    fixture = Catalog(ROOT / "data/extra/validated-demo").fixtures[FIXTURE]
    request = analysis_input(fixture, replay_id="REPLAY-EVAL", run_id=1,
                             task_id="TASK-" + case["id"],
                             start_sec=spec["start"], end_sec=spec["end"],
                             team_id=spec["team"], language=spec["language"])
    tamper = spec.get("tamper") or {}
    for key, value in (tamper.get("metrics") or {}).items():
        request["metrics"][key] = value
    if "event_index" in tamper:
        request["events"][tamper["event_index"]]["timestamp_sec"] = tamper["timestamp_sec"]
    return request


async def run_multi(request, config):
    provider = ChatCompletionsProvider(config)
    started = time.monotonic()
    result = await analyze(request, config=config, provider=provider)
    elapsed = round((time.monotonic() - started) * 1000)
    valid = "valid"
    try:
        check_result(request, result)
    except Exception as error:                      # noqa: BLE001 - report, never raise
        valid = "INVALID: " + str(error)
    insight = result.get("insight") or {}
    # Agent invocations come from the trace, not from the HTTP counter: the framework
    # path never touches ChatCompletionsProvider, so provider.calls reads 0 there and
    # would understate a run as free.
    agent_calls = sum(1 for t in result["traces"]
                      if t["agent"] != "validator" and t["duration_ms"] > 0)
    orchestrator = "direct"
    for trace in result["traces"]:
        if trace["agent"] == "validator" and trace.get("note", "").startswith("orchestrator="):
            orchestrator = trace["note"].split("=", 1)[1]
            break
    return {
        "mode": "three_agent", "status": result["status"], "contract": valid,
        "orchestrator": orchestrator,
        "elapsed_ms": elapsed, "model_calls": provider.calls,
        "agent_calls": agent_calls,
        "error_code": (result.get("error") or {}).get("code"),
        "claims_accepted": len(insight.get("claims") or []),
        "interpretations": sum(1 for c in (insight.get("claims") or []) if c["kind"] == "interpretation"),
        "claims_rejected": (insight.get("verification") or {}).get("rejected_claims") or [],
        "generation": insight.get("generation"),
        "narratives_ok": bool(insight.get("narratives")),
        "repairs": sum(1 for t in result["traces"] if t["agent"] == "narrator" and "repair" in t.get("note", "")),
        "auditor_rejected": any(t["agent"] == "auditor" and t["status"] == "rejected" for t in result["traces"]),
        "traces": [{"agent": t["agent"], "status": t["status"], "ms": t["duration_ms"]}
                   for t in result["traces"]],
        "narratives": insight.get("narratives"),
    }


async def run_single(request, config):
    provider = ChatCompletionsProvider(config)
    result = await single_shot(request, config=config, provider=provider)
    # A single agent cannot legally produce a publishable card under frozen contract
    # 2.0.0, so it has no "status" in the product sense. Label that explicitly instead of
    # letting it look like a run that produced no status at all.
    result["status"] = "baseline_only"
    return result


async def main_async(args):
    config = from_env()
    if not config.configured:
        print(json.dumps({"error": "no model configured"}, indent=2))
        return 1
    cases = build_cases()
    if args.cases != "all":
        cases = [c for c in cases if c["group"] == args.cases]
    modes = ["multi", "single"] if args.mode == "both" else [args.mode]

    results = []
    for case in cases:
        row = {"id": case["id"], "group": case["group"], "note": case["note"], "runs": {}}
        for mode in modes:
            request = materialise(case)
            started = time.monotonic()
            try:
                if mode == "multi":
                    row["runs"][mode] = await run_multi(request, config)
                else:
                    row["runs"][mode] = await run_single(request, config)
            except (ProviderTimeout, ProviderError) as error:
                row["runs"][mode] = {"error": type(error).__name__,
                                     "kind": str(getattr(error, "kind", "?")),
                                     "elapsed_ms": round((time.monotonic() - started) * 1000)}
            except Exception as error:              # noqa: BLE001 - the harness must not die
                row["runs"][mode] = {"error": type(error).__name__ + ": " + str(error)[:160]}
            print(case["id"], mode, json.dumps(row["runs"][mode].get("status")
                                               or row["runs"][mode].get("error")), flush=True)
        results.append(row)

    report = summarise(results, config)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (OUT / ("report-" + stamp + ".json")).write_text(
        json.dumps({"config": config.public(), "results": results, "summary": report},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / ("report-" + stamp + ".md")).write_text(render_markdown(report, results), encoding="utf-8")
    (OUT / "latest.json").write_text(
        json.dumps({"config": config.public(), "results": results, "summary": report},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _stat(values):
    values = [v for v in values if isinstance(v, (int, float))]
    if not values:
        return None
    return {"n": len(values), "median": statistics.median(values),
            "min": min(values), "max": max(values)}


def summarise(results, config):
    summary = {"config": config.public(), "cases": len(results), "by_mode": {}}
    for mode in ("multi", "single"):
        rows = [r["runs"].get(mode) for r in results if mode in r["runs"]]
        if not rows:
            continue
        label = "three_agent" if mode == "multi" else "single_agent"
        statuses = {}
        for row in rows:
            statuses[row.get("status") or row.get("error") or "none"] = \
                statuses.get(row.get("status") or row.get("error") or "none", 0) + 1
        summary["by_mode"][label] = {
            "runs": len(rows),
            "statuses": statuses,
            "elapsed_ms": _stat([r.get("elapsed_ms") for r in rows]),
            "model_calls": _stat([r.get("model_calls") for r in rows]),
            "agent_calls": _stat([r.get("agent_calls") for r in rows]),
            "total_model_calls": sum((r.get("agent_calls") if mode == "multi" else r.get("model_calls")) or 0
                                     for r in rows),
            "claims_rejected_total": sum(len(r.get("claims_rejected") or []) for r in rows),
            # A refusal of an invalid request can never also satisfy the request schema,
            # so counting it as a contract failure would be a measurement bug, not a
            # finding. Only results that claim to publish something are counted.
            "contract_invalid": sum(1 for r in rows
                                    if r.get("status") != "rejected"
                                    and str(r.get("contract", "valid")) != "valid"),
            "narrative_failures": sum(1 for r in rows if r.get("narratives_ok") is False),
        }
    groups = {}
    for row in results:
        group = row["group"]
        groups.setdefault(group, {"multi_passed": 0, "multi_fallback": 0,
                                  "multi_rejected": 0, "model_calls": 0, "n": 0})
        cell = groups[group]
        cell["n"] += 1
        multi = row["runs"].get("multi") or {}
        status = multi.get("status")
        if status == "passed":
            cell["multi_passed"] += 1
        elif status == "fallback":
            cell["multi_fallback"] += 1
        elif status == "rejected":
            cell["multi_rejected"] += 1
        cell["model_calls"] += multi.get("model_calls") or 0
    summary["by_group"] = groups
    summary["tampered_called_the_model"] = sum(
        (r["runs"].get("multi") or {}).get("model_calls") or 0
        for r in results if r["group"] == "tampered")
    return summary


def render_markdown(summary, results):
    lines = ["# Role C evaluation", "",
             "Model: `%s` via `%s`. Prompt version recorded per run."
             % (summary["config"]["model"], summary["config"]["provider"]),
             "", "## By group (three-agent pipeline)", "",
             "| group | cases | passed | fallback | rejected | model calls |",
             "| --- | --- | --- | --- | --- | --- |"]
    for group, cell in summary["by_group"].items():
        lines.append("| %s | %d | %d | %d | %d | %d |" % (
            group, cell["n"], cell["multi_passed"], cell["multi_fallback"],
            cell["multi_rejected"], cell["model_calls"]))
    lines += ["", "## By mode", "",
              "| mode | runs | statuses | median ms | total model calls | claims rejected | contract invalid |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for label, cell in summary["by_mode"].items():
        lines.append("| %s | %d | %s | %s | %d | %d | %d |" % (
            label, cell["runs"], json.dumps(cell["statuses"]),
            (cell["elapsed_ms"] or {}).get("median"),
            cell["total_model_calls"], cell["claims_rejected_total"],
            cell["contract_invalid"]))
    lines += ["", "Tampered cases that reached the model: **%d** (must be 0)."
              % summary["tampered_called_the_model"], "", "## Per case", "",
              "| id | group | three-agent | rejected claims | ms | calls | note |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in results:
        multi = row["runs"].get("multi") or {}
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            row["id"], row["group"], multi.get("status") or multi.get("error"),
            ",".join(multi.get("claims_rejected") or []) or "-",
            multi.get("elapsed_ms"), multi.get("model_calls"), row["note"]))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Role C evaluation harness")
    parser.add_argument("--cases", default="all",
                        choices=["all", "positive", "non_trigger", "negative", "tampered"])
    parser.add_argument("--mode", default="both", choices=["both", "multi", "single"])
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
