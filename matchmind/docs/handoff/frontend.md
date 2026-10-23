# Frontend handoff — A4 public integration acceptance

- Owner: Role A / Tianbo Cao (`tiempo0206`), assisted by Codex.
- Date: 2026-10-23 (Asia/Shanghai).
- Branch: `codex/frontend-public-acceptance`; task: #13.
- Starting main SHA: `601256039a5485120d42376c329e347144893441`. Shared baseline recorded by C: `03910f8889e846bc70215c3c0faf4bb63cd84977`.
- Contract: `2.0.0`. This slice changes only `frontend/{README,DATA_SOURCES}.md`, `tests/frontend/{public-probe,public-stream-probe,http-event-source,backend-probe}.mjs` and this handoff. No shared contract, fixture, frontend runtime, built asset, B/C source or deployment file changed. These acceptance/documentation changes need no contract change; real-data ingestion would require a separately reviewed contract update.

## Current public release

The [public match centre](https://matchmind-backend-preview.onrender.com) serves the integrated application, despite retaining its earlier backend-preview service name. The backend handoff's API-only description is historical.

- Existing Render service: `srv-dbdegcnavr4c739pockg`, free plan, Singapore, one instance; repository main, Docker root `matchmind`, release Dockerfile `deploy/Dockerfile.release`.
- Management API inspection found live deployment `dep-dbdhuvd9fdbs73b6pqv0`, source `36790b58ac0eee1884c59456397d593a8965f793`, finished at 2026-10-23 08:49:41 UTC.
- Current main `6012560` differs only in C's `evaluation/DEMO_SCRIPT.md`; it adds no runtime changes. No redundant deployment, resource creation, secret/config change or plan upgrade was performed during this acceptance.
- Public health returned HTTP 200, contract `2.0.0`, mode `production`, `model_ready: true`. The root returned HTTP 200 and the A2/A3 bundle. Health alone is not live-model proof; the actual workflow below supplies that evidence.
- The temporary management-credential process was closed after inspection. No credential is included in source, reports or this handoff.

## Public acceptance observed

On 2026-10-23, B's existing `deploy.smoke_backend.probe` passed against the public host: health, data, stats, retry, play/pause, reset, old-run protection, invalid input and SSE snapshot reconnect. It requested no model job and left its own temporary replay idle for TTL cleanup. HTTPS verification remained enabled, using the project's certifi CA bundle.

The new manual `tests/frontend/public-probe.mjs` then passed one explicitly opted-in live analysis window (report start: 12:50:54 UTC). It uses the actual frontend HTTP consumer and reducers, rather than a second implementation of the API. The observed result was:

- Public JS and CSS were byte-identical to this checkout's reviewed assets: `index-BVwS-ZmQ.js` (SHA-256 `e256d4e8340f48066d167d4fdb510d0d8d8165037b9ced3abe4831cb45fdee13`) and `index-5U3MrlGQ.css` (`66417b321c10d9b4da63ca5490c49e3305705a452e7074cbbb43bb6ab694bef3`).
- Baseline match `MM-DEMO-01`, analysis window 1500–1650. Playback paused at 1710 while the workflow finished; the paused clock held. Snapshot statistics matched the public stats endpoint.
- Generation was `live_model`, provider `deepseek`, model `deepseek-flash`; verification was `passed` with method `agent_and_code`. This establishes actual cloud-to-model connectivity for this run, not a long-term reliability rate.
- The published metrics were 3 high recoveries, 2 linked shots, a 150-second window, possession 35/115 seconds and shots 2/0 (HOME/AWAY). Both distinct audience narratives belonged to the same insight; all 14 evidence references resolved to recorded events within that window.
- Nine actual trace records included validator, analyst, narrator and auditor activity, with two analyst attempts. The rejection text identified `draft 1 C5` and its unsupported numeric interpretation; it did not ambiguously reject a final published claim number. These traces do not prove every sentence or tactical causal claim correct.
- Retrying reset with the same key advanced the run exactly once to run 2, returned to 1500, and cleared insights/traces. A subsequent snapshot stayed empty. The frontend reducer rejected an injected late insight from the prior run.

The ignored report is `.artifacts/frontend-public-acceptance/result.json`, status `passed_live`. It records the actual generation, verification, narratives, metrics, trace durations and checks. No API key is required by the script or stored in the report. One window can entail several model calls; this is not a claim of one provider request. No second live window was run to improve the result.

Run the explicit command in `frontend/README.md` only for authorized manual acceptance. The script is excluded from ordinary tests and CI, exits before network access without `--origin ... --live-once`, bounds result observation, and does not retry a failed AI workflow. It does not simulate a real provider outage. Offline fallback, named model errors and malformed-message recovery remain covered by the existing checks below.

### Follow-up: actual public frontend SSE consumer

The next synchronization fetched origin with no newer main commit (`6012560`); PR #14 remained open with both CI jobs passed and the review requested from C. On 2026-10-23 at 13:08:35 UTC, `public-stream-probe.mjs --origin https://matchmind-backend-preview.onrender.com` passed using the actual frontend subscription and reducers:

- Selected 1x on a separate replay. The first incremental progress message arrived 2284 ms after the play request began. The accepted frames included 1 `match_state`, 1 `match_event` and 6 snapshots across connection, controls, explicit reconnection and reset. This is one observed delivery time, not a latency guarantee or load test.
- Paused at 1501 (25:01); the clock held. Explicitly closing and reopening the subscription produced a fresh snapshot with matching statistics and no duplicated recovered timeline events.
- The active stream supplied a new-run snapshot after reset, without substituting the HTTP control response for that test. Run 2 was idle at 1500, with empty insights, traces and timeline.
- No analysis window was reached and no insight or agent-status frame appeared; `model_job_requested` was false. The earlier live report was preserved and no additional live workflow was invoked.

The ignored transport report is `.artifacts/frontend-public-transport/result.json`. The Node-only `http-event-source.mjs` adapter was extracted from the existing offline backend probe and is shared by the two stream probes. It parses the HTTP wire stream; browser production code still uses native EventSource. The check explicitly opens a new connection and does not claim browser automatic retry or a real provider outage.

## Browser boundary and remaining work

The public page loaded and a screenshot showed the integrated page. Browser automation's DOM, accessibility and native scroll operations repeatedly timed out, including a fresh retry during the follow-up. A native-app alternative was denied by the tool's safety restriction for the Codex app. Consequently this run does **not** establish public browser play/pause clicks, keyboard audience/evidence selection, mobile layout or browser-native EventSource retry timing. The live-model consumer probe uses HTTP snapshots; the separate stream probe above establishes public wire-level incremental delivery and explicit reconnect recovery. Neither replaces a full browser walkthrough.

The earlier local A5 browser checks below remain valid local evidence. A/C still need the public keyboard/evidence/mode walkthrough and the final English video using C's revised `evaluation/DEMO_SCRIPT.md` from `6012560`. No final video has been recorded. C/integrator reviews and merges this acceptance PR; no automatic main merge is performed.

## Data accuracy follow-up

The representative asked for accurate data, team names and match information, then clarified the decision: prefer real data if it can support the platform; otherwise use synthetic data. The currently deployed fixture is still synthetic, with fictional Harbor FC / Mountain United. All public 3/2 analysis results above describe that fixture; `live_model` identifies AI execution, not a real football match.

A completed a read-only source and consistency audit. The 30-event validated synthetic dataset passed B's audit and the fixture reference recomputed its declared metrics. An actual StatsBomb historical match/event file was inspected, but public-API/external-model rights have not been established under its license. A second CC BY 4.0 Wyscout candidate's original download/metadata access returned HTTP 403, so its actual files were not validated. Neither was adopted or combined with generated events. `frontend/DATA_SOURCES.md` records exact source scope, dates, evidence and remaining requirements.

[Issue #15](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/15) assigns B/C the source/mapping/contract review needed for real ingestion. Current `Match.synthetic: true`, provenance checks and initial-state assumptions prevent an honest data-only swap. The official synthetic-data requirement also needs a submission-scope decision. A can render new source/date/club metadata after the contract is agreed. Until then the working public dataset remains explicitly synthetic under the representative's fallback condition, with no claim that real integration is complete.

## Latest verification

The integrated executable baseline passed `pnpm run typecheck`, all 27 frontend unit tests, frozen-file checks, and 434 Python tests plus 62 subtests. The first Python run could not bind loopback sockets inside the sandbox; rerunning the same suite with the required socket permission passed. That was an environment restriction, not a product failure. Main's subsequent demo-document-only commit did not change this executable baseline.

For this slice, `pnpm run test` again passed all 27 tests and `pnpm run build` passed TypeScript and Vite with unchanged asset hashes. `node --check tests/frontend/public-probe.mjs`, `.venv/bin/python tools/check_frozen.py` and `.venv/bin/python tools/check_scope.py --role A --base 601256039a5485120d42376c329e347144893441` passed (run the latter three from `matchmind`). Running the public probe without arguments returned the expected exit code 2 and preserved the existing report. Routine tests remain offline. No public browser or video completion is inferred from these checks.

After extracting the shared SSE adapter, `pnpm run test` still passed 27/27 and `pnpm run test:backend` passed against its real B/C child server, including all five normal message kinds, with zero model calls. The child server was stopped. The public stream script's syntax and no-argument guard also passed; without an explicit origin it returns exit 2 before network access.

## Previous A2/A3 delivery (merged PR #12)

The preceding frontend branch was `codex/frontend-integration`, task #10, starting at `bcaed0e` and synchronized through `31b2c56`. C merged it as `fb2c4b61fb325406c46f1d8630dfd6f1cd90ba32` on 2026-10-23. The following local validation describes that earlier delivery.

### Delivered

A1 is already on main (PR #3). PR #12 completed:

- A2: play/pause/reset and 1/2/5/10 speeds; all six named SSE kinds; complete snapshot replacement, authoritative match-state statistics, event timeline, real analysis traces and separate business/transport errors.
- A2 recovery: stable UUIDs for create/command retries, expected-run headers, abort/cleanup, sync after an unconfirmed control, old-run/duplicate/foreign-session guards. Reset clears insights, traces, events and selected evidence atomically. Repeated real narrator steps are preserved.
- A3: insight cards, local Casual/Analyst switching, metrics and claims, generation/verification labels, expandable evidence, selected event details, timeline highlighting and recorded pitch geometry. Selecting evidence does not seek. Future event details are not rendered before the replay clock reaches them.
- A4/A5 local coverage: real combined B/C app with offline C fallback, HTTP/SSE consumer integration, keyboard controls and evidence selection, 1280x720 desktop and 390px mobile checks. No horizontal overflow was observed at those sizes.

### Local validation of PR #12

From `frontend`:

```sh
pnpm run typecheck
pnpm run test
pnpm run build
pnpm run test:backend
```

From `matchmind`:

```sh
MATCHMIND_MODEL_PROVIDER=mock .venv/bin/python -m pytest tests -q
.venv/bin/python tools/check_frozen.py
.venv/bin/python tools/check_scope.py --role A --base 31b2c56
```

Results: TypeScript/build passed; 27 frontend unit tests passed; 433 Python tests and 62 subtests passed; frozen-file and role-scope checks passed. The additional frontend backend probe passed with 0 model calls. It launches a real B/C app with a 5x accelerated test clock, checks actual consumer requests/messages, and stops its own child.

The probe covers catalogue/event recovery, play/pause/speed, a frozen pause clock, the real rule fallback (3 high recoveries / 2 linked shots), both narrative fields and evidence IDs, comparison with server statistics, second-session isolation, fresh snapshot after reconnect, reset retry with the same operation key, and stale-run rejection. Named model/business errors and malformed stream recovery are covered by frontend unit tests; the probe does not claim a real provider outage or network-location test.

Browser checks against `ai.app:app`, dataset `data/extra/showcase/press`, provider explicitly `mock`:

- Initial 25:00 / 0:0 and connected feed; API failure/retry restored the page.
- Keyboard play/pause and 10x selection; pause held at 26:56 across subsequent checks.
- Actual fallback card appeared for 25:00–27:30 with 3 recoveries, 2 linked recoveries and code-only verification. Validator trace explicitly said no model was called.
- Keyboard audience switch changed the same card's narrative. Keyboard evidence selection highlighted the matching event row and pitch point; the clock stayed at 30:00.
- Keyboard reset returned to 25:00 / run 2 with zero insights and zero observed events.
- Desktop 1280x720 and mobile 390px layouts were inspected; 13 expanded evidence buttons fit without horizontal overflow.

Screenshots are local ignored artifacts under `.artifacts/frontend-integration/` (desktop, mobile and evidence view), not source assets or live-model evidence.

Environment: Node 24.11.1, pnpm 11.25.0, TypeScript 7.0.2; local Python 3.13.9. Backend/AI pinned requirements were installed into the existing project `.venv`. Python 3.12 remains the team's target and was not tested on this machine.

### Startup and production handoff

Use `frontend/README.md` for the exact commands. Development proxy target: `MATCHMIND_BACKEND_URL=http://127.0.0.1:8000`. The integrated process is `ai.app:app`, with provider explicitly `mock` for free offline verification. The dense press dataset was exercised locally; no default dataset was changed.

`pnpm run build` supplies `frontend/dist`, which B's existing `deploy/Dockerfile.release` expects. C's main tracks that directory for Git-based Render builds, so PR #12 included the rebuilt A2/A3 bundle and removed the old A1 hashed assets. Current entry assets are `index-BVwS-ZmQ.js` and `index-5U3MrlGQ.css`. The backend-only Blueprint template remains separate from the integrated release now running on the public service.

`MATCHMIND_SERVE_FRONTEND=1 MATCHMIND_MODEL_PROVIDER=mock .venv/bin/python -m deploy.release_check --profile integrated` passed all five assembly checks, with 0 model calls. The resulting same-origin production build was also opened through the real backend locally; this is separate from public Render acceptance.

The earlier offline frontend QA produced only rule-fallback labels. The separate public live workflow above supersedes that limitation for cloud/model connectivity, while retaining the outstanding public browser and video checks.
