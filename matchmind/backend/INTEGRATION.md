# Backend status and frontend handoff

Checked 2026-10-22 by fetching Git refs and reading PR metadata. This document is maintained by B; it does not implement A's page or C's model logic.

## Verified team state

`origin/main` is still `760dbd5` and contains collaboration documentation. The frontend's latest pushed branch is `origin/feat/a1-frontend`, SHA `f88d286092e602d73804e1afeb114ec0f126b2ff`; [PR #3](https://github.com/tiempo0206/microsoft-premier-league-hackathon/pull/3) remains open. Local unpushed frontend work is unknown, so this is not a statement that its owner has done no further work.

A1 already selects a synthetic clip, creates a replay, consumes named snapshots and shows clock/score/statistics with loading, retry and reconnection states. Its handoff leaves playback controls/six incremental message kinds for A2, and insight cards/evidence/audience modes for A3. These are not present in the pushed A1 page. The illustrated pitch is not yet an evidence visualizer.

B's branch `codex/backend-ab-mvp` includes A1 as a dependency plus backend/data/deployment work. The B code is local until its branch is pushed/reviewed; a teammate cannot fetch local-only commits. No main merge or visibility change has been performed.

## What can connect now

Start B from `matchmind/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

A's existing Vite configuration already accepts `MATCHMIND_BACKEND_URL=http://127.0.0.1:8000` in its process environment. Restarting that dev server routes its unchanged relative `/api/v1` calls to B. No contract or field rename is needed.

| A behavior | B endpoint/payload | Current state |
| --- | --- | --- |
| Clip selection | `GET /api/v1/matches` | Ready; generator_version is fixture-2.0.1 |
| Create replay | `POST /api/v1/replays`, `{match_id,speed:5}` | Ready; returns idle snapshot, not auto-play |
| Clock, score, stats | named `snapshot` stream | Ready; full snapshots retained for A1 |
| Controls | `POST /api/v1/replays/{id}/control` | Backend ready; A2 buttons still needed |
| Evidence geometry | `GET /api/v1/matches/{id}/events?from_sec=1500&to_sec=1650` | Backend ready; A3 selection/highlighting still needed |
| Insight cards | `snapshot.insights` and `insight` event | Delivery path ready; needs an injected AI adapter and A3 rendering |
| Audience mode | `insight.narratives.casual` / `.analyst` | Payload supported; A switches locally without another model request |

Because new sessions start idle, seeing 25:00 until a play command is expected. B does not auto-start to disguise missing playback buttons.

For A2 integration, use one stable UUID `Idempotency-Key` per logical create/control operation, including StrictMode/retry replays. Send `X-MatchMind-Expected-Run` for controls and replace state atomically on new-run snapshots. Defaults remain backward compatible with A1. Listen to `snapshot`, `match_event`, `match_state`, `insight`, `agent_status`, and `error`; statistics must come from snapshots/state, not be re-counted from events.

Reconnections recover snapshots, not a complete transport log. Evidence queries can recover point details. Model timeouts/invalid output must not reset the clock or hide valid statistics. Show generation modes as precomputed / rule fallback / live model using the real payload; a synthetic-data label is always also present.

## B4 handoff: dispatch versus model implementation

B now implements a bounded dispatch controller. With a trusted async adapter injected, crossing 1650 enqueues exactly one fixed 1500–1650 window per replay generation. Queue wait plus adapter time share the default 12-second deadline. Initial limits are 1 active adapter, 8 queued jobs and 30 admitted tasks per monotonic hour bucket (not a rolling-hour quota). Rejected admission does not reset prior usage. Reset/expiry invalidates queued jobs and cancels active requests; late results remain subject to epoch and deadline checks.

The trusted async adapter must propagate cancellation, avoid blocking the event loop and apply its own SDK/network timeouts. Python cannot forcibly interrupt arbitrary blocking code or an adapter that indefinitely suppresses cancellation; this controller is not a process sandbox. Such an adapter would occupy its worker, although any result returned after the deadline is rejected.

Integration factory interface (the integration owner supplies the adapter):

```python
app = create_app(analyzer=trusted_async_analyze, analysis_source="external")
```

For the unchanged offline fixture stub, use `analysis_source="precomputed"`. B changes only the copied transport metadata to reflect that this configured adapter replays a saved result; it does not change C's module, prompts, text or frozen examples. A live-model result cannot be relabelled precomputed. Only C's actual returned traces are forwarded; no fake progress agents are synthesized.

The default `backend.app:app` and backend-only image inject no adapter and make no model calls. A real model client, prompts, semantic auditing, real-model readiness and actual Microsoft Agent Framework use are still unimplemented C/integration work. Passing ID/numeric checks does not prove tactical causality.

## Recommended integration sequence

1. Review the existing A1 baseline and B branch as small PRs; do not replace main with a separately initialized repository.
2. A points its current dev proxy at B. Verify catalogue/create/snapshot first.
3. A2 attaches controls; test pause/reset, two replay sessions, disconnect recovery and stable retry keys.
4. In a joint integration environment, inject the existing offline adapter. The fixture window should yield an honestly labelled precomputed card; A3 binds its evidence IDs to returned events.
5. C replaces the adapter with an authorized real model workflow while preserving the request/result shape. Retest errors/timeouts and source labels.
6. Publish a backend preview, then the combined release after the frontend build and real AI are ready. The backend URL alone is not the finished competition website.

## Deployment progression

`deploy/render-backend.yaml` is a prepared free-tier, single-instance backend preview Blueprint. It uses JSON syntax, which is valid YAML, and repo-relative Dockerfile/context paths. Auto-deploy is off. The selected branch must be pushed before use; its private repo must be authorized in the Render account. This file has not created a resource or been validated by the authenticated Render API.

Current backend image is API-only. For the final single-origin website, A supplies a reviewed `dist` build; the release integrator packages that artifact and the agreed C runtime with B, then explicitly enables existing static hosting. This avoids rewriting A's API client or buying a second always-on server. No frontend source or build task is performed by this handoff.

Before public release: validate the actual image on Linux, test a fresh-browser flow, keep the service reachable for judging, test the model endpoint from the real host, record image/source versions and retain a low call budget. Free hosting is suitable for preview; assess idle sleep and paid compute before final judging. Do not label an offline card or a backend-only preview a completed AI submission.
