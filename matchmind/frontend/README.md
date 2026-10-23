# MatchMind frontend

React/Vite match centre for the frozen 2.0.0 contract. The page connects to the real B/C application or the supplied local mock. It includes playback, server statistics, insight narratives, evidence inspection and actual analysis traces. All assets are local; model credentials stay on the server.

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

Common Python checks run from `matchmind`:

```sh
.venv/bin/python -m pytest tests -q
.venv/bin/python tools/check_frozen.py
```

## Interaction and recovery

- Play, pause, reset and speeds 1/2/5/10 use the frozen control endpoint. A replay starts idle. Reset preserves speed and advances the run.
- Catalogue/create/control failures show recovery actions. Create and command retries retain one UUID per logical operation. An unconfirmed command can be retried with the same key or resolved by syncing the current replay.
- All six named SSE kinds are handled. Snapshots replace state; `match_state` supplies statistics. Events only populate the timeline, never increment totals. Old runs, duplicated sequence numbers and other replay identities are discarded.
- Snapshot recovery does not promise lossless transport-log replay. Match event queries restore evidence details, filtered to the current replay clock so future events remain hidden.
- Casual/Analyst switch locally between the same insight's two narratives. Evidence selection highlights the event row and recorded pitch point without seeking or changing the clock. Only recorded positions and pass endpoints are drawn.
- Rule fallback, Precomputed and Live model follow the actual generation field. Evidence checked distinguishes code-only checks from agent-and-code review; it does not claim proven tactical causality. Analysis activity lists only server traces, including repeated correction steps.

## Production handoff

Run `pnpm run build` before packaging B's integrated release image: `deploy/Dockerfile.release` copies the resulting `frontend/dist`. Production uses one origin and one worker/instance; the backend serves these assets and `/api`. The backend-only Render preview is API-only. Public release, live-model verification and the final video remain joint B/C/representative work; this frontend change creates no cloud resources.
