# MatchMind — Role B data processing and deployment

Role B implements the frozen 2.0.0 backend API. Runtime data is the B-owned validated synthetic revision under `data/extra/validated-demo`; the original shared fixture and contract remain untouched. No model key, cloud account or classroom database is required for development and preflight.

The single Role B delivery plan is `backend/B_DELIVERY_PLAN.md`: fixed B1–B6 scope, one development branch, synthetic regression coverage, final PR baseline and account requirements. Continue all B work on `codex/backend-ab-mvp`; PR/merge are deferred.

## Windows

From `matchmind/`, use this project's `.venv`, not another project's environment:

```powershell
# First setup only, if no .venv exists:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.lock
# Read-only offline checks, then start only the backend API.
.\.venv\Scripts\python.exe data/generator/prepare_demo.py --check
.\.venv\Scripts\python.exe -m deploy.preflight --output .artifacts/backend-preflight.json
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Or run `deploy/start-backend.ps1` with PowerShell. It starts the existing environment without changing execution policy, installing cloud tools or creating resources.

Default mode is API-only. Check `http://127.0.0.1:8000/api/v1/health`; `/` returns a JSON 404. No page assets are needed, read or built. Existing optional static hosting is disabled with `MATCHMIND_SERVE_FRONTEND=0`; future integration owners may opt in separately.

## Data preparation

The original frozen excerpt contains a scorer mismatch. `data/generator/prepare_demo.py` applies one explicit correction in the B-owned output: E023's player becomes H01 to match the scoring shot. It updates generator_version to `fixture-2.0.1`; all timestamps, event IDs, coordinates and statistics stay the same. The first 20 event objects stay identical to the frozen example.

The roster, manually audited totals and provenance/hash manifest travel with the output. Preflight validates event structure/order, player membership, one-to-one shot/goal relations, totals and hashes. It also checks byte reproducibility against the original source. Invalid data is rejected before startup. Rebuild only the five managed output files with `python data/generator/prepare_demo.py --write`; this is deterministic preparation, not a football simulator or model job.

## Current behavior

- health, match catalogue/detail, inclusive event-window queries and clip statistics;
- isolated replay create/get/control, server clock, 1/2/5/10 speed, pause/reset/end;
- named snapshot/event/state SSE, periodic full snapshots for A1, bounded fan-out and snapshot reconnect;
- optional UUID `Idempotency-Key`, optional positive `X-MatchMind-Expected-Run`, bounded sessions/keys/subscriptions and idle expiry;
- strict known error bodies, actual byte and deadline limits; no automatic 422/HTML error for bad API input;
- optional bounded AI dispatch to an injected async adapter, once per replay generation at the fixed 1500–1650 window; queue/deadline/budget/reset guards are tested with the unchanged offline stub;
- the default API-only entrypoint injects no adapter and makes no model calls. Model clients, prompts and semantic analysis remain C's responsibility.

Create replay with `{"match_id":"MM-DEMO-01","speed":5}`; it starts idle. POST `{"action":"play"}` to `/api/v1/replays/{replay_id}/control`. Send expected-run and a stable idempotency key on retries; header support is additive and the shared OpenAPI update is pending review.

## Checks

For the complete B-only pipeline, run once from `matchmind/`:

```powershell
.\.venv\Scripts\python.exe -m deploy.verify_backend
```

This checks reproducible data/readiness, exports evidence-based JSON/Markdown and a contract-valid offline AI input, runs the fixed 512-normal/72-invalid synthetic regression plus backend/common tests, launches its own loopback API, verifies HTTP/control/SSE and stops only that child. Artifacts are under `.artifacts/backend-delivery/`. Acceptance records source-code hashes and explicitly leaves cloud, container and frontend/live-AI checks outstanding. It does not leave a development server running. Separate generated datasets and detailed regression results are under `backtest/`; they are not model-training or production match data.

For analysis export alone, without starting an API:

```powershell
.\.venv\Scripts\python.exe -m backend.reporting --output-dir .artifacts/backend-analysis
```

See `backend/DATA_PIPELINE.md` for definitions, acceptance and the Chinese handoff. These files are engineering artifacts; the HTTP contract is unchanged.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/backend -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe tools/check_frozen.py
.\.venv\Scripts\python.exe tools/check_scope.py --role B --base f88d286092e602d73804e1afeb114ec0f126b2ff
```

State survives requests/reconnects only while this single process lives. No database or durable refresh recovery is claimed. Model readiness remains false and health degraded because no model is configured; a 200 health response plus a passed data preflight is the backend-only readiness check.

The frozen original's scorer mismatch is preserved for shared compatibility tests; the runtime derivative fixes it without editing shared data. The generic 500 error-contract gap is unchanged and recorded in `docs/handoff/backend.md`. Read `deploy/README.md` for the completed local Linux image/HTTP/SSE/regression verification. Public deployment remains outstanding.

Read `backend/INTEGRATION.md` for the verified A1 interface handoff and `deploy/RENDER_STEPS_CN.md` for account setup through preview acceptance.
