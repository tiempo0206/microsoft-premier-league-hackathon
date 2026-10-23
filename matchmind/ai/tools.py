"""Bounded, network-free tools the analyst agent may call.

Role B packs the whole window into the AnalysisRequest, so these tools read only the
request that was handed over. They never reach into a backend database, a session
store or a fixture path. Every call is scoped to the current run and time window.
"""
from .verify import high_press_chains

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
            "description": ("Return high-recovery chains for the analysed team. Each chain "
                            "reports linked_shots (within 15s, the frozen metric) and "
                            "sustained_shots (within 45s, context only, includes goals)."),
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
        """Accept what a language model actually sends.

        Observed in a live run: the analyst passed "1500" as a string, the strict check
        raised, and the tool result became an error the model had to work around. The tool
        layer is a model-facing surface, so it coerces numeric-looking input instead of
        failing. Genuinely non-numeric input still raises.
        """
        if isinstance(value, bool):
            raise ValueError("start_sec and end_sec must be integers")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value.strip()))
            except ValueError:
                raise ValueError("start_sec and end_sec must be integers") from None
        raise ValueError("start_sec and end_sec must be integers")

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
        """High-recovery chains, with both the frozen 15s link and the wider context link.

        `linked_shots` mirrors the frozen metric exactly. `sustained_shot_event_ids` is
        context: a shot or goal from the same possession within 45 seconds, which is how
        the only goal in the shipped fixture becomes visible. Reporting them separately is
        the whole point - a tool result may say more than a metric may, as long as it never
        claims to be the metric.
        """
        self.calls.append("get_candidate_moments")
        return high_press_chains(self.request)

    def dispatch(self, name, arguments):
        if name == "get_metrics":
            return self.get_metrics()
        if name == "get_event_window":
            return self.get_event_window(arguments.get("start_sec"), arguments.get("end_sec"))
        if name == "get_candidate_moments":
            return self.get_candidate_moments()
        raise ValueError("unknown tool: " + str(name))
