# MatchMind frontend

React/Vite match centre for the frozen 2.0.0 contract. The page connects to the real B/C application or the supplied local mock. It includes playback, server statistics, insight narratives, evidence inspection and actual analysis traces. All assets are local; model credentials stay on the server.

## Visual theme

The working interface follows the representative's [project concept](project-media/matchmind-project-concept-v1.png): deep purple (`#10091c`), layered purple panels, lime (`#b7f34b`) actions and highlights, and lilac secondary information. `src/styles.css` owns the shared color tokens, including readable fallback/error states, keyboard focus and selected evidence. The M mark and restrained crown/pitch decoration are local SVG/CSS. Header links navigate to the actual match, insights and source disclosure.

The [generation receipt](project-media/matchmind-project-concept-v1-prompt.md) describes the concept artwork. That PNG is a design reference, not a runtime screenshot or a new data source; it is not imported into the production bundle. Actual results, clocks, statistics, generation labels and verification states still come from the existing 2.0.0 consumer. No decorative completed-agent steps or example 3/2 metrics are substituted into the app.

The [110-second English recording package](demo/recording-kit/README.md) provides a timed narration, importable SRT, edited shot list and fresh offline/public-HTTP preflight evidence. It is separate from the generated concept and does not contain a completed video. Capture/export and representative review remain pending.

The current public match is a synthetic fallback with fictional teams, not an actual Premier League fixture. The representative prefers real data when a usable, permitted source can support the platform. See [data-source accuracy and adoption status](DATA_SOURCES.md) for the inspected real-data candidates, verified synthetic calculations and requirements before switching. Live-model labels describe AI generation, separately from match-data authenticity.

`About the data` is a keyboard-accessible disclosure of replay provenance and the separately labelled Wyscout historical research reference. The latter shows the source date, full-time result, excerpt, authors, DOI and CC BY 4.0 attribution. It is not played back or passed to the model. C uses it for offline comparisons and a tuned synthetic proposal; the deployed/default replay has not been replaced or tuned. B's samples from PR #17 pass offline verification; frontend tests compare the displayed reference facts with those original records. See [the measured calibration and its limits](../evaluation/README.md) and #15.

## Run with the integrated backend

Prepare the project's Python environment using `docs/01_cn_setup.md`. The integrated app requires B's backend dependencies and C's AI dependencies, including MCP; install their pinned requirements in `.venv`. From `matchmind/` on macOS/Linux:

```sh
.venv/bin/python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.lock -r ai/requirements.txt
MATCHMIND_MODEL_PROVIDER=mock MATCHMIND_DATA_DIR=data/extra/showcase/press \
  .venv/bin/python -m uvicorn ai.app:app --host 127.0.0.1 --port 8000 --workers 1
```

This explicit offline configuration uses C's rule fallback and B's validated dense press scenario. No model account is needed. The default dataset remains unchanged elsewhere in the project.

In a second terminal, from `matchmind/frontend`:

```sh
pnpm install --frozen-lockfile
MATCHMIND_BACKEND_URL=http://127.0.0.1:8000 pnpm run dev
```

Open Vite's printed Local URL, normally `http://127.0.0.1:5173`. The proxy target is a Vite process variable; restart Vite after changing it. All browser requests remain relative `/api/v1` paths.

On Windows PowerShell, use `.venv\Scripts\python.exe` and set the process variables with `$env:MATCHMIND_MODEL_PROVIDER = 'mock'`, `$env:MATCHMIND_DATA_DIR = 'data/extra/showcase/press'`, and `$env:MATCHMIND_BACKEND_URL = 'http://127.0.0.1:8000'` in the respective terminals before running the same module/scripts.

## Run with the contract mock

Start `.venv/bin/python -m tools.mock_api` from `matchmind`, then run `pnpm run dev` from `frontend` without a proxy override. The default target is `127.0.0.1:8765`. The mock supplies complete snapshots; the real backend also emits incremental messages.

The bundled mock's saved analysis uses the supplied frozen sample and its original labels. Use the integrated offline app above to demonstrate the actual `rule_fallback` workflow. The frontend displays the received generation field and does not relabel server output.

## Checks

From `matchmind/frontend`:

```sh
pnpm run typecheck
pnpm run test
pnpm run build
pnpm run test:backend
```

`test:backend` requires the integrated Python dependencies. It launches its own real B/C server on a random loopback port, uses an explicitly offline model and an accelerated 5x server test clock, exercises the actual frontend HTTP/SSE consumer, and stops its child server. It tests controls, pause, insight/evidence payloads, statistics, isolation, snapshot reconnect, idempotent reset and stale-run rejection. `MATCHMIND_PYTHON` can select a different project interpreter. It does not test the browser layout or Render.

### Manual public stream acceptance

From `frontend`, run:

```sh
node --experimental-strip-types ../tests/frontend/public-stream-probe.mjs \
  --origin https://matchmind-backend-preview.onrender.com
```

This manual check creates its own replay, selects 1x, observes early `match_state` and `match_event` frames, pauses, explicitly reconnects, and observes the reset generation over SSE. It stops before the first AI window at 1650 and verifies that no insights or analysis traces appeared. It saves message counts, the first progress arrival time and reset state in `matchmind/.artifacts/frontend-public-transport/result.json`. Each wait is bounded, and the script attempts to pause its own replay on failure.

The Node-only `http-event-source.mjs` adapter reads the wire stream and feeds the actual `subscribeToReplay` consumer. It is also used by the offline backend probe. It does not implement browser automatic reconnect: this check explicitly closes and opens a subscription, verifies snapshot recovery without duplicate timeline entries, and leaves the replay reset to idle. Browser clicks, native EventSource retry behavior and a sustained latency/load benchmark remain separate checks. Neither public probe runs in ordinary tests or CI.

### Manual local browser retry (offline)

For a separate **local native-browser retry** check, see [the offline fault-injection record](qa/browser-reconnect-2026-10-25.md). `tests/frontend/browser-reconnect-proxy.mjs` forwards an explicitly mock loopback app and cuts its active SSE response on `SIGUSR2`. The browser performs the automatic retry. This manual helper refuses production/model-ready health, belongs outside CI/production, and does not replace public acceptance or attest a provider configuration by health alone.

### Manual public live acceptance (explicit live opt-in)

The integrated application is currently available at [the Render match centre](https://matchmind-backend-preview.onrender.com). For an authorized manual live check, run this from `frontend`:

```sh
node --experimental-strip-types ../tests/frontend/public-probe.mjs \
  --origin https://matchmind-backend-preview.onrender.com --live-once
```

This command can incur model usage on the configured server. It is excluded from `pnpm run test`, `test:backend` and CI; without both arguments it exits before any network request. It creates its own baseline replay, plays through the first analysis window, pauses, observes the result for a bounded period, and resets that replay. It never retries a failed AI workflow. One analysis window can involve several provider calls, including correction and review; this command does not impose a provider-call quota.

The probe uses the actual frontend HTTP consumer and reducers, verifies the public JS/CSS against this checkout's built files, checks statistics and evidence references, and exercises reset retry and old-run rejection. It writes a report to `matchmind/.artifacts/frontend-public-acceptance/result.json`. `passed_live` requires `live_model`, `agent_and_code` and verification status `passed`; fallback is recorded separately and returns a nonzero exit status. This checks API integration, not browser clicks, SSE delivery timing, layout or prose correctness. Public stream acceptance is a separate command above. See `docs/handoff/frontend.md` for the observed runs and remaining browser/video work.

Common Python checks run from `matchmind`:

```sh
.venv/bin/python -m pytest tests -q
.venv/bin/python tools/check_frozen.py
```

## Interaction and recovery

- Play, pause, reset and speeds 1/2/5/10 use the frozen control endpoint. A replay starts idle. Reset preserves speed and advances the run.
- Play/Pause and Reset keep keyboard focus while confirming a command. Busy buttons expose `aria-disabled`, and repeated activation is suppressed until the current command is resolved.
- Catalogue/create/control failures show recovery actions. Create and command retries retain one UUID per logical operation. An unconfirmed command can be retried with the same key or resolved by syncing the current replay.
- All six named SSE kinds are handled. Snapshots replace state; `match_state` supplies statistics. Events only populate the timeline, never increment totals. Old runs, duplicated sequence numbers and other replay identities are discarded.
- Snapshot recovery does not promise lossless transport-log replay. Match event queries restore evidence details, filtered to the current replay clock so future events remain hidden.
- Casual/Analyst switch locally between the same insight's two narratives. Evidence selection highlights the event row and recorded pitch point without seeking or changing the clock. Only recorded positions and pass endpoints are drawn.
- After selecting cited evidence, `View selected event on pitch` moves keyboard focus to the recorded-position panel. `Back to evidence` returns to the exact originating button and reopens its disclosure if needed. Timeline selections offer `Back to timeline` instead. These are local reading/navigation actions, not replay controls or model requests; timeline positioning uses immediate scrolling.
- Rule fallback, Precomputed and Live model follow the actual generation field. Evidence checked distinguishes code-only checks from agent-and-code review; it does not claim proven tactical causality. Analysis activity lists only server traces, including repeated correction steps.

## Production handoff

The team now commits `frontend/dist` for Git-based Render builds. Rebuild and commit its updated hashed assets alongside frontend source changes. Run `pnpm run build` before packaging B's integrated release image: `deploy/Dockerfile.release` copies the resulting `frontend/dist`. Production uses one origin and one worker/instance; the backend serves these assets and `/api`.

The Render service retains its original `backend-preview` name but now runs the integrated release, including the frontend and live model. Historical backend-only handoff notes describe an earlier deployment. Its previously inspected executable commit is `36790b5`; main through `0df6144` adds documentation/CI and the isolated historical research package/tests, with no runtime adoption. Public API/live acceptance has passed on the earlier bundle.

PR #14's purple/lime theme, playback focus and source disclosure are merged on main (`d4488d1`). C subsequently updated the source copy for offline calibration in `6f5d14d`; this branch starts at main `1113388` and retains that copy. It adds selected-evidence navigation and rebuilds `index-DnW473jk.js` / `index-Bkk-p2ET.css`. This new slice needs C's review/merge and explicit deployment before reaching the public URL. Main's integration history alone does not establish public deployment. The live probe checks bundle equality before requesting a model workflow, so use it only after the selected build is deployed. See [evidence navigation acceptance](qa/evidence-navigation-2026-10-26.md), [theme acceptance](qa/theme-2026-10-25.md) and the dated earlier records for their local/public scope.
