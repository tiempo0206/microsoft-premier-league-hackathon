# MatchMind backend — AB development

Role B implements the frozen 2.0.0 API for A1. Source data is local synthetic JSON/JSONL. No model key, cloud account or classroom database is required.

## Windows

From `matchmind/`, use this project's `.venv`, not another project's environment:

```powershell
# First setup only, if no .venv exists:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.lock
# Start the API. A may point MATCHMIND_BACKEND_URL at this address.
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Or run `deploy/start-backend.ps1` with PowerShell. It starts the existing environment without changing execution policy, installing cloud tools or creating resources.

A can run its Vite dev server separately; set `MATCHMIND_BACKEND_URL=http://127.0.0.1:8000` in that process and restart Vite. When `frontend/dist/index.html` exists, B also serves that build at the API origin. It is not a frontend source change.

## Current behavior

- health, match catalogue/detail, inclusive event-window queries and clip statistics;
- isolated replay create/get/control, server clock, 1/2/5/10 speed, pause/reset/end;
- named snapshot/event/state SSE, periodic full snapshots for A1, bounded fan-out and snapshot reconnect;
- optional UUID `Idempotency-Key`, optional positive `X-MatchMind-Expected-Run`, bounded sessions/keys/subscriptions and idle expiry;
- strict known error bodies, actual byte and deadline limits; no automatic 422/HTML error for bad API input;
- internal AI request/publish hooks, tested against the existing offline stub; no runtime model calls or scheduling.

Create replay with `{"match_id":"MM-DEMO-01","speed":5}`; it starts idle. POST `{"action":"play"}` to `/api/v1/replays/{replay_id}/control`. A1 has no playback buttons yet, so A2 needs to wire those controls. Send expected-run and a stable idempotency key on retries; header support is additive and the shared OpenAPI update is pending review.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/backend -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe tools/check_frozen.py
.\.venv\Scripts\python.exe tools/check_scope.py --role B --base f88d286092e602d73804e1afeb114ec0f126b2ff
```

State survives requests/reconnects only while this single process lives. A1 refresh currently creates a new replay; do not claim persisted refresh recovery. No database is planned. Model readiness is honestly false and health degraded while the model role is unclaimed.

Known scorer mismatch and generic 500 error-contract gap remain in `docs/handoff/backend.md`. Read `deploy/README.md` before choosing a host. No public deployment or container-image test is claimed.
