# Backend handoff — AB integration

- Role / developer: B / `wunianze666-netizen`, assisted by Codex.
- Task: [Issue #6](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/6).
- Local branch: `codex/backend-ab-mvp`.
- A1 dependency/base: `f88d286092e602d73804e1afeb114ec0f126b2ff` (PR #3, not merged at start).
- Contract: frozen `2.0.0`. Frontend, AI module, shared contracts and fixtures are unchanged.

## Scope and plan

1. B1: independent local fixture loader, deterministic statistics and read APIs.
2. B2/B3: isolated replay/control and bounded snapshot SSE, keeping A1's snapshot consumer working.
3. AI handoff hooks only: create a validated observed request and publish a checked result. No automatic analysis scheduler, deadline/admission controller for models, prompts, model accounts or model-client implementation is included.

C is unclaimed. The human owns backend/data/deployment; this does not transfer C's model responsibilities to B. No database, user login or object storage is needed for this slice.

## Known data and contract limits

The frozen fixture has shot(goal) E022 by H01 followed by goal E023 by H02. The loader reports this as a known shared-data warning without modifying frozen data. Structural/order/team conflicts fail loading. Before a public competition demo, the scorer relation needs a separately reviewed fixture correction; this branch does not claim complete football-semantic validation.

The shared error enum lacks a generic INTERNAL_ERROR. Known client errors use the frozen error shape. Unexpected 500 errors remain framework-sanitized until a shared contract patch is reviewed; do not mislabel them as model failures.

## Runtime and verification

B1 was committed locally as `71a709f`. B2/B3 add isolated create/get/control, monotonic playback, end/reset handling, bounded TTL sessions, UUID idempotency keys, expected-run guards, independent SSE queues and snapshot recovery. Periodic full snapshots keep the unchanged A1 client compatible; incremental match_event/match_state are also emitted. AI hooks can emit actual returned insight/agent_status after cross-field checks; no background analysis or live model calls run by default.

Checks on Python 3.12.14 / Node 24.19.0:

- 21 new backend tests (real HTTP/SSE plus clock-controlled domain tests); 19 inherited common tests; 11 inherited frontend role tests.
- Actual A1 `getMatches`, `createReplay` and `subscribeToSnapshots` run against a real B process through `tests/backend/a1-consumer-check.mjs`: connected, clock reached 1505, pause held, reset run became 2. Page/JS assets use the same origin; unknown API returned JSON 404.
- The existing frontend compiled with direct `node .../typescript/bin/tsc --noEmit` and `node .../vite/bin/vite.js build`. No A source or lockfile changed. Existing matching dependencies on E: were reused through an ignored node_modules junction, not a fresh frontend install.
- Backend packages installed from TUNA at the prescribed pins; `backend/requirements.lock` records the resolved transitive versions. No AI-provider SDK was installed.
- Frozen contracts/fixtures and role-B scope are checked. No browser visual test is claimed; this is an unchanged-client HTTP/SSE integration check.
- Dockerfile/runbook provided; Docker's Linux engine is unavailable, so the container image is **not built/tested**. No account creation, model call, cloud resource, public deployment, access change or new backend push occurred.

Commands from `matchmind/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/backend -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe tools/check_frozen.py
.\.venv\Scripts\python.exe tools/check_scope.py --role B --base f88d286092e602d73804e1afeb114ec0f126b2ff
node --experimental-strip-types --test tests/frontend/replay.test.mjs
# With a local B service and frontend/dist present:
node --experimental-strip-types tests/backend/a1-consumer-check.mjs http://127.0.0.1:8877
```

## Remaining integration work

A2 owns visible play/pause/reset controls; A1 currently displays server snapshots but has no buttons. A should also use a stable creation key across StrictMode/retries: abandoned anonymous creates otherwise consume capacity until TTL. C remains unclaimed. A future B/C integration slice needs bounded analysis dispatch, model timeouts/admission and honest precomputed/live/fallback labels before real AI exposure. The offline stub is only called in tests and its known saved-result label is not silently fixed in C's module. Public release also needs the reviewed shared fixture/error-contract corrections and a tested image/host. A1 refresh starts a new replay; durable or sessionStorage refresh recovery is not claimed.

Kimi status: unavailable (no CLI or desktop process discovered), planning pass not run. Codex implements and reviews. DSPy skipped: deterministic backend work, no LM optimization.

## Reuse record

Design reference only: `farlyfeifei/xingma-qihang` at `4f5d0c93d7a87849e50cf55f6ce10122f2df0a82`, `lib/platform/http.ts`, `lib/platform/client.ts`, `lib/platform/budget.ts`, `lib/classroom/drafts.ts`. Generic ideas retained: bounded body reading, unified known errors, cancellation/deadlines, atomic admission and idempotent retry. No old source file, D1/R2 migration, classroom auth, secrets or cloud resource configuration is copied. The reviewed source has no explicit repository license; this is not a claim of a license to copy it.
