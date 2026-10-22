# Frontend handoff — A1

- Role / developer: A / Tianbo Cao (`tiempo0206`), assisted by Codex.
- Branch: `feat/a1-frontend`.
- Baseline SHA: `384b58f6195138aadd22f956855acef73fedc0c5`.
- Contract: `2.0.0`; shared contracts, fixtures, mock, and AI stub remain unchanged from the baseline.

## Baseline preparation

The repository had no shared MatchMind baseline. The prerequisite commit above imports the 69 starter files verbatim from the supplied v2.1 archive. A1 is a separate commit on top. The archive itself and the prior review report are not included. C should confirm this baseline before coordinating B/C branches.

## A1 delivered behavior

- Loads `GET /api/v1/matches`, selects the supplied synthetic clip, and creates a replay with `POST /api/v1/replays` at the recommended speed 5.
- Subscribes to the named `snapshot` stream and displays server-provided clock, score, shots, passes, completed-pass accuracy, and estimated possession seconds.
- Shows the synthetic label, fictional team names, and the 25:00–30:00 clip boundaries. Zero pass attempts show an em dash.
- Includes loading, empty catalogue, API failure/retry, stream reconnection, and last-valid-snapshot states.
- Cleans up requests/subscriptions; discards duplicated snapshots, old runs, and mismatched replay identities.
- Adds an English page, local SVG branding, local styles, and keyboard-accessible selection/retry controls. No external fonts, CDNs, model keys, or runtime model calls.

## Changed files

Frontend entry, favicon, page/styles, consumer-side replay client and hook, Vite type declarations, README, local installer-cache ignore, and the test script in `frontend/package.json`; role tests in `tests/frontend/replay.test.mjs`; this handoff. No dependency versions or lockfile changes.

## Verification

From `matchmind/frontend`:

```sh
pnpm run typecheck
pnpm run test
pnpm run build
```

From `matchmind`:

```sh
.venv/bin/python tools/check_frozen.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python tools/check_scope.py --role A --base 384b58f6195138aadd22f956855acef73fedc0c5
```

Results: TypeScript check and production build passed; 11 role tests and all 19 common Python tests passed; frozen files and role scope checks passed. Browser verification confirmed the initial 25:00 / 0:0 screen, connected snapshot feed, and failure/retry recovery against the actual local mock. These checks concern A1, not complete product acceptance.

Local environment: Node 24.11.1, pnpm 11.25.0, TypeScript 7.0.2, Python 3.13.9, jsonschema 4.26.0. Python 3.12 was not installed on this machine; the documented team target remains 3.12 and was not independently tested here.

## Runtime state and next work

- Runtime source: local contract mock. No live model, semantic verification, or real AI analysis is claimed.
- No shared contract change is needed for A1. The review's fixture/statistic issues remain C/B follow-up work and were not silently changed in this role.
- A2: playback controls, all six incremental SSE kinds, and complete control/reconnect scenarios.
- A3: insight cards, evidence highlighting, and audience mode selection.
- A4/A5: real backend integration and full responsive/accessibility acceptance.
- Merging the baseline and assigning B/C remain team coordination tasks. No production backend or public deployment is included.
