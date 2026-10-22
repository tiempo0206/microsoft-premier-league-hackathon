"""Bounded, network-free tools the analyst agent may call.

Role B packs the whole window into the AnalysisRequest, so these tools read only the
request that was handed over. They never reach into a backend database, a session
store or a fixture path. Every call is scoped to the current run and time window.
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": "Return the deterministic metrics B already computed for this window.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_window",
            "description": "Return the events inside a sub-window of the current analysis window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_sec": {"type": "integer", "description": "inclusive match second"},
                    "end_sec": {"type": "integer", "description": "inclusive match second"},
                },
                "required": ["start_sec", "end_sec"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_candidate_moments",
            "description": "Return high-recovery chains for the analysed team, as ranked candidates.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


class Toolbox:
    """Scoped to one AnalysisRequest. Rejects anything outside it."""

    def __init__(self, request: dict):
        self.request = request
        self.start = request["window"]["start_sec"]
        self.end = request["window"]["end_sec"]
        self.team = request["team_id"]
        self.calls = []

    def _clamp(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("start_sec and end_sec must be integers")
        return value

    def get_metrics(self):
        self.calls.append("get_metrics")
        return dict(self.request["metrics"])

    def get_event_window(self, start_sec, end_sec):
        start, end = self._clamp(start_sec), self._clamp(end_sec)
        if start > end:
            raise ValueError("reversed window")
        # Clamp into the handed-over window instead of widening the analysis scope.
        start, end = max(start, self.start), min(end, self.end)
        self.calls.append("get_event_window")
        return [{"event_id": e["event_id"], "timestamp_sec": e["timestamp_sec"],
                 "type": e["type"], "team_id": e["team_id"], "player_id": e["player_id"],
                 "possession_id": e.get("possession_id"), "outcome": e.get("outcome"),
                 "position": e.get("position")}
                for e in self.request["events"] if start <= e["timestamp_sec"] <= end]

    def get_candidate_moments(self):
        self.calls.append("get_candidate_moments")
        events = self.request["events"]
        attacks_right = self.team == "HOME"   # frozen convention: HOME attacks right
        moments = []
        for recovery in events:
            if recovery["type"] != "recovery" or recovery["team_id"] != self.team:
                continue
            x = recovery["position"]["x"] if attacks_right else 100 - recovery["position"]["x"]
            if x < 66.67:
                continue
            following = [e for e in events
                         if e["team_id"] == self.team
                         and e.get("possession_id") == recovery.get("possession_id")
                         and 0 < e["timestamp_sec"] - recovery["timestamp_sec"] <= 15]
            moments.append({
                "recovery_event_id": recovery["event_id"],
                "timestamp_sec": recovery["timestamp_sec"],
                "attack_normalized_x": round(x, 2),
                "linked_shot_event_ids": [e["event_id"] for e in following if e["type"] == "shot"],
                "evidence_event_ids": [recovery["event_id"], *[e["event_id"] for e in following]],
            })
        return moments

    def dispatch(self, name, arguments):
        if name == "get_metrics":
            return self.get_metrics()
        if name == "get_event_window":
            return self.get_event_window(arguments.get("start_sec"), arguments.get("end_sec"))
        if name == "get_candidate_moments":
            return self.get_candidate_moments()
        raise ValueError("unknown tool: " + str(name))
