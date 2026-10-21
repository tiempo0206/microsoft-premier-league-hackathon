# Proposed contracts v0.1

Status: **design proposal**. No schemas, endpoints, or application code are implemented yet. This document is the interface agreement for the first vertical slice described in the [development plan](development-plan.md).

## Synthetic event

Start with a first-half fixture so the initial implementation has one unambiguous match clock. Add second-half and stoppage-time semantics explicitly before claiming full-match support. `match_time_ms` is simulated match time, not wall-clock delivery time.

```json
{
  "schema_version": "0.1",
  "match_id": "synthetic-demo-001",
  "event_id": "evt-000123",
  "sequence": 123,
  "period": 1,
  "match_time_ms": 750000,
  "event_type": "pass",
  "team_id": "northbridge",
  "player_id": "northbridge-07",
  "outcome": "complete",
  "start": {"x": 61.0, "y": 32.0},
  "end": {"x": 77.0, "y": 29.0},
  "is_synthetic": true
}
```

- Each fixture declares fictional teams, players, seed/generator version, and its modeled coverage.
- Identify an event by `(match_id, event_id)`; deduplicate before updating state. A repeated ID with a different payload is an error.
- Use `sequence` to disambiguate events at the same clock value. Validate ordering before replay; reject invalid input rather than silently changing causal order.
- Coordinates are normalized to 0–100 in the acting team's attacking direction, with the opponent's goal at x=100. Convert to a common display frame when rendering the pitch.
- Validate team/player membership, coordinate bounds, event-specific outcomes, and monotonic clock/sequence. Replay should not infer facts from rejected events.
- First event types: `pass`, `shot`, `tackle`, `possession_change`, and `pressure`. Define allowed outcomes per type in the implemented schema.
- Represent a goal as a `shot` with outcome `goal`. Count it once; do not introduce a second scoring event for the same goal.
- A generator should model possession transitions and compatible event locations. Independent random rows are not a convincing match simulation.

## Deterministic metric definitions

For a replay cutoff `t`, the current five-minute window is `(t - 300000, t]`; the previous window is `(t - 600000, t - 300000]`. Clip to the fixture's observed coverage and expose a partial-window flag when appropriate. Do not compare a short partial window as if it covered five minutes.

| Metric | Definition |
| --- | --- |
| Shots | Count valid `shot` events in the chosen window |
| Score | Cumulative count of deduplicated `shot` events with outcome `goal` up to `t` |
| Completed passes | Count `pass` events with outcome `complete` |
| Pass completion | Completed passes / attempted passes; return null when there are no attempts |
| Completed pass entries into final third | Completed passes with `start.x < 66.6667` and `end.x >= 66.6667` |

Show the final metric with that precise label. It does not include carries or every possible way of entering the final third. Do not label event-count shares as time-based possession or an uncalibrated score as xG.

Store numerator, denominator, bounds, coverage, and supporting event IDs with each metric. All tools must apply `event.match_time_ms <= replay_cutoff`.

## Insight card

```json
{
  "schema_version": "0.1",
  "insight_id": "insight-0001",
  "run_id": "run-001",
  "state_version": 123,
  "as_of_ms": 750000,
  "audience": "casual",
  "language": "en",
  "title": "Attacking activity is increasing",
  "explanation": "Northbridge has created more shooting opportunities in the observed recent window.",
  "evidence_event_ids": ["evt-000121", "evt-000122", "evt-000123"],
  "metric_refs": ["northbridge.shots.current", "northbridge.shots.previous"],
  "source_mode": "template"
}
```

This payload illustrates shape only; its evidence and metrics must be populated consistently from the actual fixture. A validator must reject it if those references are absent or do not support the intended comparison.

Candidate metrics and references are supplied by the backend. Require schema validity, existing evidence, matching run/state version, and no references beyond `as_of_ms`. Factual numeric chips are rendered from stored metrics. Free-text explanations still need semantic evaluation; a schema validator cannot guarantee truth.

`source_mode` values are `template`, `foundry_live`, `foundry_cached`, and `fallback`. A cached card must match the replay state and profile. Discard late responses from a reset run or an obsolete audience selection.

## Proposed API

| Method and path | Behavior |
| --- | --- |
| `GET /api/health` | Return application and model-provider readiness without exposing credentials |
| `GET /api/fixtures` | List available synthetic fixtures and metadata |
| `POST /api/runs` | Create an isolated run from a fixture; return `run_id` |
| `POST /api/runs/{run_id}/control` | Apply play, pause, speed, or reset with an idempotent command ID |
| `GET /api/runs/{run_id}/state` | Return the current snapshot for initial load or reconnection |
| `GET /api/runs/{run_id}/stream` | Send typed `event`, `state`, `insight`, and `error` SSE messages |
| `POST /api/runs/{run_id}/insights` | Request an explanation for a candidate, audience, and language at a specified current state |
| `POST /api/runs/{run_id}/recap` | Summarize the observed prefix without using future fixture events |

Each SSE message should have a run-scoped message ID. On reconnect, resume from a retained message ID or return a snapshot; do not replay every event into an already-counted state. Reset invalidates pending model work and creates a new state generation.

Keep model access server-side. Local development may be single-user; hosted judging access needs an explicit session/access design and bounded inference usage before deployment.
