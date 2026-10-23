# Frontend handoff — A2/A3 integration

- Owner: Role A / Tianbo Cao (`tiempo0206`), assisted by Codex.
- Date: 2026-10-23 (Asia/Shanghai).
- Branch: `codex/frontend-integration`; task: #10.
- Starting main SHA: `bcaed0e`; synchronized main through `31b2c56` before rebuilding the release bundle. Shared baseline recorded by C: `03910f8889e846bc70215c3c0faf4bb63cd84977`.
- Contract: `2.0.0`. Only A-owned frontend, frontend tests and this handoff changed. No shared contract, fixture, B/C source or deployment file changed.

## Delivered

A1 is already on main (PR #3). This branch completes the next frontend slices:

- A2: play/pause/reset and 1/2/5/10 speeds; all six named SSE kinds; complete snapshot replacement, authoritative match-state statistics, event timeline, real analysis traces and separate business/transport errors.
- A2 recovery: stable UUIDs for create/command retries, expected-run headers, abort/cleanup, sync after an unconfirmed control, old-run/duplicate/foreign-session guards. Reset clears insights, traces, events and selected evidence atomically. Repeated real narrator steps are preserved.
- A3: insight cards, local Casual/Analyst switching, metrics and claims, generation/verification labels, expandable evidence, selected event details, timeline highlighting and recorded pitch geometry. Selecting evidence does not seek. Future event details are not rendered before the replay clock reaches them.
- A4/A5 local coverage: real combined B/C app with offline C fallback, HTTP/SSE consumer integration, keyboard controls and evidence selection, 1280x720 desktop and 390px mobile checks. No horizontal overflow was observed at those sizes.

## Validation

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

## Startup and production handoff

Use `frontend/README.md` for the exact commands. Development proxy target: `MATCHMIND_BACKEND_URL=http://127.0.0.1:8000`. The integrated process is `ai.app:app`, with provider explicitly `mock` for free offline verification. The dense press dataset was exercised locally; no default dataset was changed.

`pnpm run build` supplies `frontend/dist`, which B's existing `deploy/Dockerfile.release` expects. C's latest main now tracks that directory for Git-based Render builds, so this branch includes the rebuilt A2/A3 bundle and removes the old A1 hashed assets. Current entry assets are `index-BVwS-ZmQ.js` and `index-5U3MrlGQ.css`. The backend-only Render Blueprint remains API-only.

`MATCHMIND_SERVE_FRONTEND=1 MATCHMIND_MODEL_PROVIDER=mock .venv/bin/python -m deploy.release_check --profile integrated` passed all five assembly checks, with 0 model calls. The resulting same-origin production build was also opened through the real backend locally; this is separate from public Render acceptance.

## Remaining joint acceptance

- C/integrator reviews and merges this PR. No automatic main merge, repo visibility change or Render deployment is performed here.
- B/C verify the combined release on the actual public Render host, including SSE timing and cloud-to-model connectivity. Local success does not establish these.
- C/representative supplies the authorized live model configuration and runs the real workflow; Live model/agent review labels are supported by the page but were not produced in this offline frontend QA.
- A6: record and approve the final English video with actual live-model/verified failure-injection footage. This branch supplies working playback, evidence and audience-mode interactions; it does not claim the video exists.
