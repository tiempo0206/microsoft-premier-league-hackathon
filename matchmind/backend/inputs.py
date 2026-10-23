"""One B-owned builder for runtime and offline example AnalysisRequest values."""
import copy

from contracts.validation import check_request
from .stats import window_events, window_metrics


def analysis_input(fixture, *, replay_id, run_id, task_id, start_sec=1500,
                   end_sec=1650, team_id="HOME", language="en"):
    request = {"contract_version": "2.0.0", "task_id": task_id, "replay_id": replay_id,
               "run_id": run_id, "match_id": fixture.match["match_id"],
               "window": {"start_sec": start_sec, "end_sec": end_sec},
               "type": "high_press", "team_id": team_id, "language": language,
               "events": copy.deepcopy(window_events(fixture, start_sec, end_sec)),
               "metrics": window_metrics(fixture, start_sec, end_sec, team_id)}
    check_request(request)
    return request
