"""Threat added — a socceraction-style expected-threat grid over our own events.

Why this exists: our seven metrics are counts, and a count cannot rank an action. A viewer
asking "why did *that* pass matter" gets no answer from `completed_passes`. The published
expected-threat (xT) model answers it by valuing how much closer a move got to scoring.

What this is **not**:

* it is not the published xT model. socceraction (MIT) trains on real provider data; we train
  on one short synthetic fixture. The numbers are therefore not comparable to any published xT
  and must never be presented as such.
* it is not a probability of scoring from here. It is a zone value estimated from this clip.

The honesty property that matters most: **`build_grid` refuses to produce a grid when the
training evidence is too thin.** A grid trained on twenty passes would yield confident-looking
numbers that mean nothing, and a number that looks authoritative is worse than no number. When
it refuses, callers get `None` and a reason, and the product simply does not rank anything.

Method, which is deliberately inspectable:

    xT(zone) = P_shoot(zone) * P_goal(zone) + sum over move zones j of P_move(zone, j) * xT(j)

solved by value iteration. Every term is counted from the events handed in; nothing is learned
from an external dataset and no weights are copied.

    python -m ai.threat                      # run over the shipped fixture and report
"""
import argparse
import json
from pathlib import Path

GRID_CANDIDATES = ((16, 12), (12, 8), (8, 6), (6, 4))
MAX_ITERATIONS = 30
TOLERANCE = 1e-6
# Observations per occupied cell before a grid resolution is considered meaningful. A 5-minute
# top-flight spell carries roughly 80-120 completed passes, which cannot populate a 16x12 grid:
# the resolution has to follow the data instead of being fixed. If even the coarsest grid cannot
# reach this density, refusing is the honest answer.
MIN_OBSERVATIONS_PER_CELL = 4

from backend.data import Catalog          # noqa: E402
from backend.stats import window_events    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extra" / "validated-demo"


def zone_of(point, attacks_right=True, grid=(16, 12)):
    """Which grid cell a normalised coordinate falls in, in the attacking direction."""
    if not point:
        return None
    cells_x, cells_y = grid
    x = point["x"] if attacks_right else 100.0 - point["x"]
    x = min(max(x, 0.0), 99.999)
    y = min(max(point["y"], 0.0), 99.999)
    return int(x * cells_x / 100.0), int(y * cells_y / 100.0)


def _attacks_right(team_id):
    return team_id == "HOME"      # frozen convention: HOME attacks right


def collect_transitions(events, grid=(16, 12)):
    """Count move and shot frequencies per zone from real event pairs."""
    moves, shots, goals = {}, {}, {}
    for event in events:
        zone = zone_of(event.get("position"), _attacks_right(event["team_id"]), grid)
        if zone is None:
            continue
        if event["type"] == "shot":
            shots[zone] = shots.get(zone, 0) + 1
            if event.get("outcome") == "goal":
                goals[zone] = goals.get(zone, 0) + 1
        elif event["type"] == "pass" and event.get("outcome") == "successful":
            target = zone_of(event.get("end_position"), _attacks_right(event["team_id"]), grid)
            if target is None or target == zone:
                continue
            moves.setdefault(zone, {})[target] = moves.setdefault(zone, {}).get(target, 0) + 1
    return moves, shots, goals


def _choose_resolution(events, min_per_cell=MIN_OBSERVATIONS_PER_CELL):
    """Pick the finest grid the sample can actually populate, or explain why none can."""
    tried = []
    for grid in GRID_CANDIDATES:
        moves, shots, goals = collect_transitions(events, grid)
        transitions = sum(sum(row.values()) for row in moves.values())
        occupied = len({z for z in set(moves) | set(shots)})
        occupied = max(occupied, len(set(shots)))
        density = (transitions / occupied) if occupied else 0.0
        tried.append({"grid": {"x": grid[0], "y": grid[1]}, "transitions": transitions,
                      "occupied_cells": occupied,
                      "observations_per_cell": round(density, 2)})
        if transitions and density >= min_per_cell:
            return grid, moves, shots, goals, tried
    return None, None, None, None, tried


def build_grid(events, min_per_cell=MIN_OBSERVATIONS_PER_CELL):
    """Return (grid, resolution, report). grid is None when the evidence is too thin.

    The refusal is the interesting case. A five-minute synthetic clip carries roughly 70-90
    completed moves, which is under four observations per cell even at 6x4. That is a real
    finding, not a bug: **a short clip cannot support an expected-threat grid.** The grid needs a
    full match, so the product should not promise xT on a clip.
    """
    report = {"events": len(events), "resolution_trials": [],
              "min_observations_per_cell": min_per_cell}
    resolution, moves, shots, goals, tried = _choose_resolution(events, min_per_cell)
    report["resolution_trials"] = tried
    if resolution is None:
        report["refused"] = ("no grid resolution reaches %d observations per cell on this "
                             "sample; a grid from that is noise, not a model. A five-minute clip "
                             "is too short for this technique." % min_per_cell)
        return None, None, report
    if sum(shots.values()) == 0:
        report["refused"] = "no shots in the sample, so there is no zone value to converge to"
        return None, None, report

    cells_x, cells_y = resolution
    report["grid"] = {"x": cells_x, "y": cells_y}
    report["transitions"] = sum(sum(row.values()) for row in moves.values())
    report["shots"] = sum(shots.values())
    report["goals"] = sum(goals.values())

    grid = {}
    converged = 0
    for _ in range(MAX_ITERATIONS):
        delta = 0.0
        updated = {}
        for x in range(cells_x):
            for y in range(cells_y):
                zone = (x, y)
                total = shots.get(zone, 0) + sum(moves.get(zone, {}).values())
                if not total:
                    updated[zone] = grid.get(zone, 0.0)
                    continue
                shoot_p = shots.get(zone, 0) / total
                goal_p = (goals.get(zone, 0) / shots[zone]) if shots.get(zone) else 0.0
                value = shoot_p * goal_p
                for target, count in moves.get(zone, {}).items():
                    value += (count / total) * grid.get(target, 0.0)
                updated[zone] = value
                delta = max(delta, abs(updated[zone] - grid.get(zone, 0.0)))
        grid = updated
        converged = _ + 1
        if delta < TOLERANCE:
            break
    report["converged_after"] = converged
    report["max_value"] = max(grid.values()) if grid else 0.0
    return grid, resolution, report


def threat_added(event, grid, resolution):
    """How much zone value a completed move adds. None when the grid cannot say."""
    if grid is None or resolution is None or event.get("type") != "pass":
        return None
    if event.get("outcome") != "successful":
        return None
    start = zone_of(event.get("position"), _attacks_right(event["team_id"]), resolution)
    end = zone_of(event.get("end_position"), _attacks_right(event["team_id"]), resolution)
    if start is None or end is None:
        return None
    return round(grid.get(end, 0.0) - grid.get(start, 0.0), 6)


def rank_threat(events, limit=5, min_per_cell=MIN_OBSERVATIONS_PER_CELL):
    """Rank completed passes by threat added, or explain why it cannot be ranked."""
    grid, resolution, report = build_grid(events, min_per_cell)
    if grid is None:
        return {"available": False, "reason": report.get("refused"), "report": report,
                "ranked": []}
    scored = []
    for event in events:
        added = threat_added(event, grid, resolution)
        if added is None:
            continue
        scored.append({"event_id": event["event_id"], "timestamp_sec": event["timestamp_sec"],
                       "team_id": event["team_id"], "player_id": event["player_id"],
                       "threat_added": added})
    scored.sort(key=lambda row: row["threat_added"], reverse=True)
    return {
        "available": True,
        "report": report,
        "ranked": scored[:limit],
        "label": ("Threat added, heuristic socceraction-style grid re-estimated on this clip at "
                  "%dx%d resolution. Not comparable to published xT."
                  % (resolution[0], resolution[1])),
        # A caveat that must travel with the number: the grid is trained on the same clip it
        # scores, so a high value here means "this zone was productive in this sample", not
        # "this was a good decision".
        "caveat": ("The grid is estimated from the same events it ranks, so treat it as a "
                   "within-clip ranking device, never as a probability of scoring."),
    }


def analyse_fixture(match_id="MM-DEMO-01", start=1500, end=1800):
    fixture = Catalog(DATA_DIR).fixtures[match_id]
    events = window_events(fixture, start, end)
    return rank_threat(events)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Threat-added heuristic")
    parser.add_argument("--match", default="MM-DEMO-01")
    parser.add_argument("--start", type=int, default=1500)
    parser.add_argument("--end", type=int, default=1800)
    args = parser.parse_args(argv)
    fixture = Catalog(DATA_DIR).fixtures[args.match]
    events = window_events(fixture, args.start, args.end)
    print(json.dumps(rank_threat(events), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
