# Backend API and release handoff

Checked 2026-10-23. Read [INTEGRATOR_HANDOFF_CN.md](INTEGRATOR_HANDOFF_CN.md) first for the full executable handoff.

## Current baseline and deployed preview

A/B/C are integrated into main (PR #9, recorded baseline 03910f8). B's delivered backend/data/deployment/test content from 0425283 is present there. Do not require teammates to find a deleted role branch. The present documentation update reuses the original B branch only for review.

The API-only preview is live at https://matchmind-backend-preview.onrender.com . Post-configuration public acceptance passed for data/statistics, replay create/control, retry/reset, invalid input, old-run protection and SSE snapshot reconnection.

Render service srv-dbdegcnavr4c739pockg uses main, pinned deployed commit bcaed0e, Free/Singapore/one instance, root matchmind/, Dockerfile deploy/Dockerfile, context '.', health /api/v1/health. Auto-deploy is off. A push to main is not a release.

The preview starts backend.app:app with no AI injected and no frontend. A root JSON404 and model_ready=false are expected. This is not the completed competition website.

## Connect A without a new API client

In A's frontend dev-server environment set MATCHMIND_BACKEND_URL=https://matchmind-backend-preview.onrender.com and restart the existing Vite server. Browser requests remain relative /api/v1 routes; use the existing proxy during development and one origin for the final release.

| A behavior | B endpoint/payload | Contract behavior |
| --- | --- | --- |
| Clip selection | GET /api/v1/matches | Use returned match_id; do not hardcode a single clip |
| Create replay | POST /api/v1/replays, {match_id,speed:5} | Idle snapshot; send play to advance |
| Clock, score, stats | named snapshot / match_state | Full server state is authoritative |
| Controls | POST /api/v1/replays/{id}/control | play/pause/reset/set_speed |
| Evidence | GET /api/v1/matches/{id}/events?from_sec=1500&to_sec=1650 | Closed logical-time interval; no seek implied |
| Insight cards | snapshot.insights / insight | A renders the actual generation/verification mode |
| Audience modes | insight.narratives.casual / .analyst | Local switch; no extra model request |

Use one stable UUID Idempotency-Key per logical create/control operation, including retries. Send X-MatchMind-Expected-Run for controls. Replace state atomically on a new-run snapshot and discard old-run messages. Listen to snapshot, match_event, match_state, insight, agent_status and error. Do not count score/statistics again from events.

Reconnection returns a fresh snapshot, not a complete transport log. Evidence queries recover point details. Models failing or timing out must not stop statistics or reset the clock. Always label synthetic data and the actual live_model / rule_fallback / precomputed source.

## C composition is already provided

C owns ai.service.analyze and ai.app:app. The combination uses B's create_app(analyzer=trusted_async_analyze, analysis_source="external"). C's bare analyze(request) stays offline; its rule result is rule_fallback, not a saved precomputed card.

Use analysis_source="precomputed" only for an adapter that actually replays a saved result. Never relabel a real model or a computed rule result merely to pass a test. Traces describe real execution.

B schedules the observed 1500-1650 window once per replay generation at 1650 when at least 3 high recoveries and 2 linked recoveries are present. Current preview limits: one active adapter, eight queued jobs, 30 admissions per monotonic hour bucket, 12-second total queue/input/call deadline. Reset/expiry invalidates work; late or old-run output cannot publish. A trusted adapter must propagate cancellation, avoid blocking and apply SDK/network deadlines. This controller is not a hostile-code sandbox.

The C composition can use a 20-second candidate shared deadline; configure B/C consistently and remeasure on the real host. The current API-only preview remains at 12 seconds.

C's former fallback evidence-union defect is fixed on main. The recorded offline gate passes 12/12 normal requests and refuses 3/3 corruptions with zero calls. [C_INTEGRATION_FINDINGS.md](C_INTEGRATION_FINDINGS.md) is historical. Rerun python -m deploy.adapter_check on the final selected commit, especially when adopting the three showcase datasets.

## What the final integrator must finish

1. Review current main and use the existing A/B/C interfaces; no shared-contract change is required for the current MVP.
2. A finishes the intended controls/cards/evidence/modes and supplies a reproducible build.
3. Put frontend/dist into the actual cloud build workflow. The release Dockerfile is an assembly template with COPY frontend/dist; Git-ignored local dist will not appear in a fresh Render clone. Use a frontend build stage or CI artifact packaging.
4. C supplies model configuration/Secret and performs its explicit provider probe from the real host. A configured health flag alone does not establish provider availability.
5. Use deploy.release_check --profile integrated and deploy.release_run (C composition root); single worker/instance and same-origin frontend/API.
6. The authorized release Agent operates Render with its private RENDER_API_KEY, restricted by task instruction to this service. This key is for platform management, not model inference. Public API consumers do not need it.
7. Deploy a reviewed commit, wait for live, run the public smoke and then the actual browser/model flow. Retain a known-good version and keep source/mode labels honest.

No credential is present in these docs. Final resource ownership, model quota, publication and maintenance must be accepted by the final integrator. B's technical handoff does not itself transfer account ownership or attest to the unfinished browser/model flow.
