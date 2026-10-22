"""Ablation: what breaks when each specialist is switched off?

The Best Multi-Agent System criterion asks for "an end-to-end outcome a single agent could
not achieve as effectively". A single-vs-multi comparison hints at that; an ablation shows
it role by role, which is what the judging language actually describes. This mirrors what
the strongest rival project published (Touchline documents a five-way ablation).

Each variant patches the pipeline at exactly one point, runs the same windows, then scores
every PUBLISHED card with the real, unpatched verifier. Patching happens only inside this
harness; the shipped code is untouched.

    .\\.venv\\Scripts\\python.exe -m evaluation.ablation
    .\\.venv\\Scripts\\python.exe -m evaluation.ablation --windows 4

Billable: each non-tampered window costs several model calls. Off-peak pricing applies.
"""
import argparse
import asyncio
import copy
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai import service as service_module                     # noqa: E402
from ai.config import from_env                               # noqa: E402
from ai.provider import ChatCompletionsProvider              # noqa: E402
from ai.service import analyze                               # noqa: E402
from ai.verify import check_claims, check_narratives         # noqa: E402
from backend.data import Catalog                             # noqa: E402
from backend.inputs import analysis_input                    # noqa: E402
from contracts.validation import check_result                # noqa: E402

OUT = ROOT / ".artifacts" / "ablation"
UNIVERSAL = re.compile(r"\b(each|every|all|always|never)\b|所有|全部|每次|都", re.I)

CAVEATS = """\
This ablation is UNDERPOWERED and its published numbers do not support a per-role claim.
Read it as a measurement design, not as evidence.

1. Six windows, one run per variant. The differences between variants (fallback counts
   1/3/5/5/2) are consistent with run-to-run model variance rather than with the role that
   was removed. In the first full run, removing the auditor produced FEWER fallbacks than
   the full pipeline, which is the opposite of the expected direction and is most likely
   noise.
2. `published_with_bad_claims` is 0 for every variant, including `no_code_gate`. On clean
   input the model rarely fabricates a number, so a 6-window live run cannot show what the
   code gate is for. That is what `evaluation/factcheck_bench.py` measures instead, with
   controlled corruption: 17/17 caught, 0/4 false alarms. Use that number, not this table.
3. The real evidence for the multi-agent claim is structural, not statistical: frozen
   contract 2.0.0 forbids publishing a `live_model` card unless
   `verification.method == "agent_and_code"`, so a single self-reviewing agent cannot emit
   `passed` at all.

How to make it worth publishing: at least 3 repetitions per variant, the same seeded
windows, and report mean and spread per variant. Until then, quote the fact-check bench.
"""

WINDOWS = [
    ("P1", 1500, 1650, "HOME", "en"),
    ("P2", 1500, 1650, "HOME", "zh"),
    ("P3", 1650, 1800, "HOME", "en"),
    ("N2", 1500, 1590, "HOME", "en"),
    ("N1", 1500, 1650, "AWAY", "en"),
    ("N4", 1650, 1800, "AWAY", "zh"),
]


def build_request(name, start, end, team, language):
    fixture = Catalog(ROOT / "data/extra/validated-demo").fixtures["MM-DEMO-01"]
    return analysis_input(fixture, replay_id="REPLAY-ABL", run_id=1,
                          task_id="ABL-" + name, start_sec=start, end_sec=end,
                          team_id=team, language=language)


def _accept_claims(raw, request):
    """Stand-in for the code gate when it is ablated: accept the model's text as-is."""
    claims = []
    for index, claim in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(claim, dict):
            continue
        claims.append({"claim_id": str(claim.get("claim_id") or "C%d" % (index + 1)),
                       "kind": claim.get("kind") if claim.get("kind") in ("metric", "interpretation")
                       else "interpretation",
                       "text": str(claim.get("text") or ""),
                       "metric_key": claim.get("metric_key"),
                       "metric_value": claim.get("metric_value"),
                       "evidence_event_ids": list(claim.get("evidence_event_ids") or [])})
    return claims, [], []


def _accept_narratives(raw, request, claims):
    if not isinstance(raw, dict):
        return None, ["narrator returned a non-object"]
    casual = raw.get("casual")
    analyst = raw.get("analyst")
    if not (isinstance(casual, str) and casual.strip()
            and isinstance(analyst, str) and analyst.strip()):
        return None, ["missing narrative"]
    return {"casual": casual.strip(), "analyst": analyst.strip()}, []


def _always_approve(audit):
    return True, [], []


VARIANTS = {
    "full": {"note": "the shipped pipeline"},
    "no_code_gate": {"note": "claims and prose are accepted without deterministic checks",
                     "patch": {"check_claims": _accept_claims,
                               "check_narratives": _accept_narratives}},
    "no_auditor": {"note": "the adversarial auditor always approves",
                   "patch": {"_audit_approved": _always_approve}},
    "no_repair": {"note": "no repair round at all",
                  "patch": {"REPAIR_NARRATION_FLOOR_SEC": 10 ** 9,
                            "REPAIR_ANALYSIS_FLOOR_SEC": 10 ** 9}},
    "no_tools": {"note": "the analyst agent gets no tools",
                 "config": {"max_tool_calls": 0}},
}


def score_published(insight, request):
    """Score a published card with the REAL verifier, whatever the variant did."""
    if insight is None:
        return {"published": False, "code_rejected_claims": [], "narrative_issues": [],
                "universal_quantifier": False, "contract_valid": True}
    approved, rejected, claim_issues = check_claims(insight["claims"], request)
    narratives, narrative_issues = check_narratives(insight["narratives"], request,
                                                    approved if approved else insight["claims"])
    universal = False
    for claim in insight["claims"]:
        if claim["kind"] == "interpretation" and UNIVERSAL.search(claim["text"] or ""):
            universal = True
    for text in (insight["narratives"] or {}).values():
        if UNIVERSAL.search(text or ""):
            universal = True
    valid = True
    try:
        check_result(request, {"task_id": request["task_id"], "replay_id": request["replay_id"],
                               "run_id": request["run_id"], "status": "fallback",
                               "insight": insight, "traces": [], "error": None})
    except Exception:                                  # noqa: BLE001 - a score, not a crash
        valid = False
    return {"published": True, "code_rejected_claims": rejected,
            "narrative_issues": (claim_issues + narrative_issues)[:3],
            "universal_quantifier": universal, "contract_valid": valid}


async def run_variant(name, spec, base_config, limit):
    saved = {}
    for attribute, value in (spec.get("patch") or {}).items():
        saved[attribute] = getattr(service_module, attribute)
        setattr(service_module, attribute, value)
    config = base_config
    if spec.get("config"):
        from dataclasses import replace
        config = replace(base_config, **spec["config"])
    rows = []
    try:
        for window in WINDOWS[:limit]:
            label, start, end, team, language = window
            request = build_request(label, start, end, team, language)
            provider = ChatCompletionsProvider(config)
            started = time.monotonic()
            try:
                result = await analyze(request, config=config, provider=provider)
                elapsed = round((time.monotonic() - started) * 1000)
                call_error = None
            except Exception as error:                # noqa: BLE001 - a row, not a crash
                result, elapsed = None, round((time.monotonic() - started) * 1000)
                call_error = type(error).__name__ + ": " + str(error)[:120]
            if result is None:
                rows.append({"window": label, "status": "CRASH", "elapsed_ms": elapsed,
                             "error": call_error, "score": score_published(None, request),
                             "agent_calls": 0})
                print("  %-12s %-4s CRASH %s" % (name, label, call_error), flush=True)
                continue
            score = score_published(result.get("insight"), request)
            rows.append({"window": label, "status": result["status"], "elapsed_ms": elapsed,
                         "error": (result.get("error") or {}).get("code"),
                         "agent_calls": sum(1 for t in result["traces"]
                                            if t["agent"] != "validator" and t["duration_ms"] > 0),
                         "score": score})
            print("  %-12s %-4s %-9s %6dms  published=%s bad_claims=%d narIssues=%d uni=%s"
                  % (name, label, result["status"], elapsed, score["published"],
                     len(score["code_rejected_claims"]), len(score["narrative_issues"]),
                     score["universal_quantifier"]), flush=True)
    finally:
        for attribute, value in saved.items():
            setattr(service_module, attribute, value)
    return rows


def summarise(all_rows):
    summary = {}
    for name, rows in all_rows.items():
        published = [r for r in rows if r["score"]["published"]]
        summary[name] = {
            "windows": len(rows),
            "published": len(published),
            "fallback": sum(1 for r in rows if r["status"] == "fallback"),
            "rejected": sum(1 for r in rows if r["status"] == "rejected"),
            "crashes": sum(1 for r in rows if r["status"] == "CRASH"),
            "agent_calls": sum(r["agent_calls"] for r in rows),
            "median_ms": sorted([r["elapsed_ms"] for r in rows])[len(rows) // 2] if rows else None,
            # The two numbers that make an ablation worth reading: how many cards carried a
            # number or citation the events contradict, and how many carried an
            # unadjudicable universal claim.
            "published_with_bad_claims": sum(1 for r in published
                                             if r["score"]["code_rejected_claims"]),
            "published_with_narrative_issues": sum(1 for r in published
                                                   if r["score"]["narrative_issues"]),
            "published_with_universal_quantifier": sum(1 for r in published
                                                       if r["score"]["universal_quantifier"]),
        }
    return summary


def render(summary):
    order = ["full", "no_code_gate", "no_auditor", "no_repair", "no_tools"]
    head = ("| variant | windows | published | fallback | agent calls | cards with contradicted "
            "numbers | cards with prose issues | cards with universal claim |")
    lines = [head, "| " + " | ".join("---" for _ in range(9)) + " |"]
    for name in order:
        cell = summary.get(name)
        if not cell:
            continue
        lines.append("| %s | %d | %d | %d | %d | %d | %d | %d |" % (
            name, cell["windows"], cell["published"], cell["fallback"], cell["agent_calls"],
            cell["published_with_bad_claims"], cell["published_with_narrative_issues"],
            cell["published_with_universal_quantifier"]))
    return "\n".join(lines)


async def main_async(config, limit):
    all_rows = {}
    for name, spec in VARIANTS.items():
        print("\n== %s: %s" % (name, spec["note"]), flush=True)
        all_rows[name] = await run_variant(name, copy.deepcopy(spec), config, limit)
    summary = summarise(all_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    # VARIANTS holds function objects for the monkeypatch; serialise only what describes it.
    described = {name: {"note": spec["note"],
                        "patched": sorted(spec.get("patch") or {}),
                        "config_overrides": sorted(spec.get("config") or {})}
                 for name, spec in VARIANTS.items()}
    (OUT / "report.json").write_text(
        json.dumps({"config": config.public(), "variants": described, "summary": summary,
                    "rows": all_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = ("# Ablation\n\n" + CAVEATS + "\n## Numbers\n\n" + render(summary) + "\n")
    (OUT / "report.md").write_text(markdown, encoding="utf-8")
    print("\n" + render(summary))
    print("\nNOTE: this table is underpowered on its own. See evaluation/README.md.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Role C ablation study")
    parser.add_argument("--windows", type=int, default=len(WINDOWS),
                        help="how many of the predefined windows to run per variant")
    return asyncio.run(main_async(from_env(), max(1, min(args_windows(argv), len(WINDOWS)))))


def args_windows(argv):
    if not argv:
        return len(WINDOWS)
    for index, item in enumerate(argv):
        if item == "--windows" and index + 1 < len(argv):
            try:
                return int(argv[index + 1])
            except ValueError:
                return len(WINDOWS)
    return len(WINDOWS)


if __name__ == "__main__":
    sys.exit(main())
