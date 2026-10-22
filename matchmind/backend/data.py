"""Load versioned local fixtures; never fetch a real match or external database."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

from contracts.validation import check_shape


def decode_json(raw):
    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(raw, parse_constant=invalid_constant)


def read_json(path: Path):
    return decode_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Fixture:
    match: dict
    events: tuple[dict, ...]
    warnings: tuple[str, ...] = ()

    @classmethod
    def load(cls, match_path: Path):
        match = read_json(match_path)
        check_shape("Match", match)
        if match["clip_start_sec"] >= match["clip_end_sec"]:
            raise ValueError(f"{match_path.name}: empty or reversed clip")
        event_path = match_path.with_name(match_path.name.replace(".match.json", ".events.jsonl"))
        rows, ids, players, possessions = [], {}, {}, {}
        previous = None
        allowed = {"pass": {"successful", "failed"}, "recovery": {"successful"},
                   "shot": {"on_target", "off_target", "goal"}, "goal": {"goal"}}
        for line, raw in enumerate(event_path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                event = decode_json(raw)
                check_shape("Event", event)
                if event["match_id"] != match["match_id"] or event["period"] != match["period"]:
                    raise ValueError("event belongs to another match or period")
                if not match["clip_start_sec"] <= event["timestamp_sec"] <= match["clip_end_sec"]:
                    raise ValueError("event time outside clip")
                old = ids.get(event["event_id"])
                if old is not None:
                    if old != event:
                        raise ValueError("same event_id has different content")
                    continue
                order = event["timestamp_sec"], event["event_id"]
                if previous is not None and order < previous:
                    raise ValueError("events must be ordered by time and event_id")
                if event["type"] not in allowed or event["outcome"] not in allowed[event["type"]]:
                    raise ValueError("event/outcome is outside this MVP's supported semantics")
                if event["type"] == "pass" and event["end_position"] is None:
                    raise ValueError("pass needs end_position")
                for point in (event["position"], event["end_position"]):
                    if point and not all(math.isfinite(point[k]) for k in ("x", "y")):
                        raise ValueError("non-finite coordinate")
                for mapping, key in ((players, "player_id"), (possessions, "possession_id")):
                    if key_value := mapping.get(event[key]):
                        if key_value != event["team_id"]:
                            raise ValueError(f"{key} changes team")
                    mapping[event[key]] = event["team_id"]
            except Exception as exc:
                raise ValueError(f"{event_path.name}:{line}: invalid event: {exc}") from exc
            previous = order
            ids[event["event_id"]] = event
            rows.append(event)
        warnings = []
        for event in rows:
            if event["type"] != "goal":
                continue
            shots = [e for e in rows if e["type"] == "shot" and e["outcome"] == "goal"
                     and e["team_id"] == event["team_id"] and e["possession_id"] == event["possession_id"]
                     and 0 <= event["timestamp_sec"] - e["timestamp_sec"] <= 1]
            if len(shots) != 1 or shots[0]["player_id"] != event["player_id"]:
                warnings.append(f"{event['event_id']}: goal/scoring-shot player mismatch; shared fixture review required")
        return cls(match, tuple(rows), tuple(warnings))


class Catalog:
    def __init__(self, directory: Path):
        self.fixtures = {}
        for path in sorted(directory.glob("*.match.json")):
            fixture = Fixture.load(path)
            key = fixture.match["match_id"]
            if key in self.fixtures:
                raise ValueError(f"Duplicate match_id: {key}")
            self.fixtures[key] = fixture
        if not self.fixtures:
            raise ValueError("No local match fixtures found")
