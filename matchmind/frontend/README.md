# MatchMind frontend — A1

A React/Vite match centre using the frozen 2.0.0 contract. The initial screen loads the match catalogue, creates a replay at speed 5, and displays complete server snapshots. All assets are local; no model account or key is needed.

## Run locally

In the `matchmind` directory, prepare the Python environment as described in `docs/01_cn_setup.md`, then start the supplied mock:

```sh
.venv/bin/python -m tools.mock_api
```

In a second terminal, from `matchmind/frontend`:

```sh
pnpm install --frozen-lockfile
pnpm run dev
```

Open the Local URL printed by Vite, normally `http://127.0.0.1:5173`. The existing Vite proxy sends `/api` to `http://127.0.0.1:8765`.

On Windows, use `.venv\Scripts\python.exe` from the project root for the mock. To connect to B's backend later, set `MATCHMIND_BACKEND_URL` in the Vite process environment; the API paths and UI fields stay unchanged.

## Checks

```sh
pnpm run typecheck
pnpm run test
pnpm run build
```

The role tests use the existing Node runtime and its TypeScript stripping support, without adding test dependencies. Common Python checks run from `matchmind`.

## A1 scope

- Match selection, synthetic label, 25:00 initial clock, score, shots, passes, pass accuracy, and estimated possession time.
- Loading, empty catalogue, API error/retry, stream reconnect, and last-valid-snapshot states.
- A named `snapshot` listener and connection cleanup; totals are read from the server, never accumulated from events.

Playback controls and incremental SSE kinds belong to A2. Insight cards, evidence interaction, and audience modes belong to A3. A1 contains no model calls and does not claim live AI analysis.
