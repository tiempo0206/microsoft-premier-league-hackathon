"""Calibrate the synthetic clip against five minutes of real football.

Role B delivered one real match (Arsenal 4-3 Leicester City, 2017-08-11) as a research package:
1,768 events for the full match and the 96 events of the first-half window 25:00-30:00, CC BY 4.0,
verified by hash. It is deliberately **not** a runtime fixture: `synthetic=false`,
`runtime_compatible=false`, and it is outside both Dockerfiles' COPY paths.

That leaves the question this harness answers: **is our synthetic clip realistic enough to stand in
for real football?** Nobody had checked. The answer matters for the judging criterion that names
"creativity and optimized synthetic data creation", and it had been asserted rather than measured.

What this does, and what it refuses to do
----------------------------------------
It compares the two on the metrics that are genuinely comparable across the two vocabularies: event
density, how much of the play is passing, how often a shot happens, where passes start, and how far
apart events sit. Those definitions are the same on both sides, in the same 300-second span.

It **refuses** to compare the metrics the real record cannot support. Wyscout's sample has no
`possession_id` and no explicit recovery event, so the three-high-recovery / two-linked-shot trigger
cannot be computed from it. Filling that in would mean inventing exactly the fact the metric is about.
`REFUSALS` lists each one with its reason, and the report prints them rather than quietly omitting
them.

The provider mapping is stated, not assumed silently: `WYSCOUT_MAPPING` says which Wyscout event
names map to our vocabulary, which are ambiguous, and which have no counterpart at all.

    python -m evaluation.real_data_calibration
    python -m evaluation.real_data_calibration --json
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation import dense_fixture_proposal as dense   # noqa: E402

REAL_DIR = ROOT / "data" / "extra" / "real-history-wyscout"
REAL_SAMPLES = REAL_DIR / "samples"
REAL_CLIP = REAL_SAMPLES / "wyscout-2499719.1H-1500-1800.original.jsonl"
REAL_MATCH = REAL_SAMPLES / "wyscout-2499719.match.original.json"
SHIPPED = ROOT / "data" / "extra" / "validated-demo"
WINDOW = (1500, 1800)
FINAL_THIRD = 100.0 * 2 / 3

# Wyscout event name -> (our event type or None, why).
WYSCOUT_MAPPING = {
    "Pass": ("pass", "maps directly; subEventName separates simple/high/head passes"),
    "Shot": ("shot", "maps, but Wyscout's Shot class is wider than an on-target attempt"),
    "Free Kick": (None, "ambiguous: a free kick becomes a pass or a shot depending on its sub-event, "
                        "and the record does not always say which; counted but not mapped"),
    "Duel": (None, "a challenge, not a recovery: our `recovery` means a team won the ball, and this "
                   "record does not say who won it"),
    "Others on the ball": (None, "catch-all bucket with no football meaning we can defend"),
    "Save attempt": (None, "goalkeeper action; outside the contract's event vocabulary"),
    "Interruption": (None, "out of play"),
}

# Metrics the real sample cannot support, and why we will not approximate them.
REFUSALS = [
    ("high_recoveries",
     "needs an explicit recovery or a won-ball attribution; Wyscout Duel does not say who won it"),
    ("linked_shots",
     "defined as a shot within 15 s of a high recovery; with no recovery there is no chain to link"),
    ("sustained_control",
     "needs possession segments; the sample has no possession_id"),
    ("the 3-recovery / 2-linked-shot trigger",
     "it is the conjunction of the two rows above, so it cannot be computed either"),
    ("pass completion rate",
     "the tags encode outcomes inconsistently across sub-events; a rate computed from them would be "
     "a guess dressed as a number"),
]


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def real_window():
    """The real five-minute sample, as an ordered list of (sec, name, team, x)."""
    rows = _read_jsonl(REAL_CLIP)
    teams = json.loads(REAL_MATCH.read_text(encoding="utf-8")).get("teamsData", {})
    home_id = next((int(tid) for tid, t in teams.items() if t.get("side") == "home"), None)
    events = []
    for row in rows:
        position = (row.get("positions") or [{}])[0] or {}
        events.append({
            "sec": float(row["eventSec"]),
            "name": row["eventName"],
            # Wyscout coordinates run in the acting team's attacking direction, so x is already
            # "progress towards the goal being attacked" for both sides. Stated as an assumption:
            # if it is wrong, the coordinate rows below are invalid and the density rows still stand.
            "x": float(position.get("x", 0.0)),
            "team": "HOME" if row.get("teamId") == home_id else "AWAY",
        })
    events.sort(key=lambda e: e["sec"])
    return events


def shipped_window():
    from backend.data import Catalog
    from backend.stats import window_events
    fixture = Catalog(SHIPPED).fixtures["MM-DEMO-01"]
    rows = window_events(fixture, WINDOW[0], WINDOW[1])
    return [{"sec": float(e["timestamp_sec"]), "name": e["type"], "team": e["team_id"],
             # Our fixture is stored in one absolute frame with HOME attacking right, so AWAY's
             # attacking progress is mirrored.
             "x": float(e["position"]["x"]) if e["team_id"] == "HOME"
                  else 100.0 - float(e["position"]["x"])}
            for e in rows]


def dense_window(knobs=None):
    presses = dense.spread_presses(WINDOW[0], WINDOW[1], every_sec=10 ** 6, first_at=60, burst_size=3)
    rows = dense.generate(seed=11, clip_start=WINDOW[0], clip_end=WINDOW[1], presses=presses,
                          **(knobs or {}))
    picked = [e for e in rows if WINDOW[0] <= float(e["timestamp_sec"]) <= WINDOW[1]]
    return [{"sec": float(e["timestamp_sec"]), "name": e["type"], "team": e["team_id"],
             "x": dense.attacking_x(e["team_id"], float(e["position"]["x"]))}
            for e in picked]


def calibration_note():
    """The arithmetic behind the one gap a knob cannot close, stated where the numbers are."""
    real = summarise(real_window(), passes=("Pass",), shots=("Shot",))
    other = 100.0 - real["pass_share_pct"]
    return {
        "pass_share_gap": (
            "A real five-minute sample is %.1f%% passes. In our vocabulary the only non-pass action "
            "is a recovery, so reaching that share inside 300 s would mean inventing about %d "
            "recoveries in five minutes -- roughly %.0f per match, several times what a real match "
            "has. Inflating them to make a table look right would corrupt exactly the metric the "
            "product is about, so the gap stays published instead of engineered away."
            % (real["pass_share_pct"], round(other / 100.0 * real["events"]),
               (other / 100.0 * real["events"]) * 18)),
        "what_a_knob_can_fix": "the shot rate, which is a parameter of the generator (see CALIBRATED)",
        "what_it_cannot": "pass share, because the missing 34% is duels, interruptions and loose "
                          "balls that the frozen contract has no event type for",
    }


def summarise(events, passes=("pass",), shots=("shot", "goal")):
    """The same definitions on both sides. Only metrics that survive the vocabulary gap."""
    if not events:
        return {"events": 0}
    span = WINDOW[1] - WINDOW[0]
    gaps = [b["sec"] - a["sec"] for a, b in zip(events, events[1:])]
    pass_events = [e for e in events if e["name"] in passes]
    return {
        "events": len(events),
        "seconds_per_event": round(span / len(events), 2),
        "passes": len(pass_events),
        "pass_share_pct": round(100.0 * len(pass_events) / len(events), 1),
        "shots": sum(1 for e in events if e["name"] in shots),
        "shots_per_10_min": round(10.0 * sum(1 for e in events if e["name"] in shots)
                                  / (span / 60.0), 1),
        "pass_final_third_pct": round(100.0 * sum(1 for e in pass_events
                                                  if e["x"] >= FINAL_THIRD) / len(pass_events), 1)
        if pass_events else None,
        "median_gap_sec": round(statistics.median(gaps), 1) if gaps else None,
    }


def compare(columns):
    """Which metrics agree, within a tolerance stated before looking at the numbers.

    Tolerances are percentages, and the delta is a percentage of the reference value. An earlier
    version compared a fraction to a percentage (`1.5 <= 50.0`) and therefore called a +150%
    overshoot "ok" — the harness said everything was fine while the table next to it said it was
    not. Keep both sides in the same unit.
    """
    reference = columns["real sample"]
    verdicts = []
    for key, tolerance_pct in (("seconds_per_event", 30.0), ("pass_share_pct", 15.0),
                               ("shots_per_10_min", 50.0), ("pass_final_third_pct", 20.0)):
        value = reference.get(key)
        for name, column in columns.items():
            if name == "real sample":
                continue
            other = column.get(key)
            if not value or other is None:
                verdicts.append({"metric": key, "column": name, "status": "not comparable"})
                continue
            delta_pct = round(100.0 * abs(other - value) / value, 1)
            verdicts.append({"metric": key, "column": name,
                             "tolerance_pct": tolerance_pct,
                             "delta_pct": delta_pct,
                             "within_tolerance": delta_pct <= tolerance_pct})
    return verdicts


def build_report():
    real = real_window()
    columns = {
        "real sample": summarise(real, passes=("Pass",), shots=("Shot",)),
        "synthetic shipped": summarise(shipped_window()),
        "synthetic dense (proposal)": summarise(dense_window()),
        "synthetic dense (calibrated)": summarise(dense_window(dense.CALIBRATED)),
    }
    return {
        "window": {"start_sec": WINDOW[0], "end_sec": WINDOW[1], "seconds": WINDOW[1] - WINDOW[0]},
        "real_source": {
            "package": str(REAL_DIR.relative_to(ROOT)).replace("\\", "/"),
            "match": "Arsenal 4-3 Leicester City, 2017-08-11, first half 25:00-30:00",
            "licence": "CC BY 4.0 (see ATTRIBUTION.md); NOT this project's CC0 synthetic data",
            "synthetic": False,
            "runtime_compatible": False,
        },
        "event_names_in_sample": dict(Counter(e["name"] for e in real)),
        "wyscout_mapping": {name: {"maps_to": pair[0], "why": pair[1]}
                            for name, pair in WYSCOUT_MAPPING.items()},
        "columns": columns,
        "verdicts": compare(columns),
        "cannot_be_fixed_by_a_knob": calibration_note(),
        "refusals": [{"metric": metric, "reason": why} for metric, why in REFUSALS],
        "assumptions": [
            "Wyscout's x runs in the acting team's attacking direction; the coordinate rows depend "
            "on it, the density rows do not.",
            "One five-minute sample says what that match did in those five minutes. It is not a "
            "Premier League distribution and must not be quoted as one.",
            "Wyscout's Shot class is wider than our `shot`; the shot rows are indicative, not exact.",
        ],
        "model_calls": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare the synthetic clip with a real five-minute sample")
    parser.add_argument("--json", action="store_true", help="print the report instead of a table")
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    columns = report["columns"]
    order = ["real sample", "synthetic shipped", "synthetic dense (proposal)",
             "synthetic dense (calibrated)"]
    rows = ["events", "seconds_per_event", "passes", "pass_share_pct", "shots",
            "shots_per_10_min", "pass_final_third_pct", "median_gap_sec"]
    width = max(len(r) for r in rows) + 2
    print("window: %d-%d s (%d s)   real source: %s"
          % (report["window"]["start_sec"], report["window"]["end_sec"],
             report["window"]["seconds"], report["real_source"]["match"]))
    print("real sample event names:", report["event_names_in_sample"])
    print()
    print("metric".ljust(width) + "".join(name.rjust(30) for name in order))
    for row in rows:
        cells = "".join(str(columns[name].get(row, "-")).rjust(30) for name in order)
        print(row.ljust(width) + cells)
    print()
    print("verdicts (tolerance fixed before the numbers were looked at):")
    for verdict in report["verdicts"]:
        if verdict.get("status") == "not comparable":
            print("  %-24s %-28s not comparable" % (verdict["metric"], verdict["column"]))
        else:
            mark = "ok" if verdict["within_tolerance"] else "OUT OF RANGE (tolerance %g%%)" % (
                verdict["tolerance_pct"],)
            print("  %-24s %-28s %+6.1f%%  %s"
                  % (verdict["metric"], verdict["column"], verdict["delta_pct"], mark))
    failures = [v for v in report["verdicts"]
                if v.get("within_tolerance") is False]
    print()
    if failures:
        print("%d of the comparisons are OUT OF RANGE - say so before quoting the others."
              % len(failures))
    else:
        print("every comparison is inside its pre-registered tolerance.")
    print()
    print("refused, because the real record cannot support them:")
    for item in report["refusals"]:
        print("  %-32s %s" % (item["metric"], item["reason"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
