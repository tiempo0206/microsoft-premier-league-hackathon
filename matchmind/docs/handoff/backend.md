# Backend handoff — B1

- Role / developer: B / `wunianze666-netizen`, assisted by Codex.
- Task: [Issue #6](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/6).
- Local branch: `codex/backend-ab-mvp`.
- A1 dependency/base: `f88d286092e602d73804e1afeb114ec0f126b2ff` (PR #3, not merged at start).
- Contract: frozen `2.0.0`. Frontend, AI module, shared contracts and fixtures are unchanged.

## Scope and plan

1. B1: independent local fixture loader, deterministic statistics and read APIs.
2. B2/B3: isolated replay/control and bounded snapshot SSE, keeping A1's snapshot consumer working.
3. B4: only the existing asynchronous AI boundary; no prompts, model accounts or model client implementation.

C is unclaimed. The human owns backend/data/deployment; this does not transfer C's model responsibilities to B. No database, user login or object storage is needed for this slice.

## Known data and contract limits

The frozen fixture has shot(goal) E022 by H01 followed by goal E023 by H02. The loader reports this as a known shared-data warning without modifying frozen data. Structural/order/team conflicts fail loading. Before a public competition demo, the scorer relation needs a separately reviewed fixture correction; this branch does not claim complete football-semantic validation.

The shared error enum lacks a generic INTERNAL_ERROR. Known client errors use the frozen error shape. Unexpected 500 errors remain framework-sanitized until a shared contract patch is reviewed; do not mislabel them as model failures.

## Runtime and verification

B1 implements fixture loading, pure statistics, health, match catalogue/detail, bounded event windows and stats. Nine new tests pass on Python 3.12.14 (six data/domain, three real loopback HTTP); all 19 common tests pass. Dependencies were installed from TUNA at the existing pinned versions. Shared hashes and role-B scope pass. No paid model calls, cloud resources, public deployment or repository visibility changes were performed.

Kimi status: unavailable (no CLI or desktop process discovered), planning pass not run. Codex implements and reviews. DSPy skipped: deterministic backend work, no LM optimization.

## Reuse record

Design reference only: `farlyfeifei/xingma-qihang` at `4f5d0c93d7a87849e50cf55f6ce10122f2df0a82`, `lib/platform/http.ts`, `lib/platform/client.ts`, `lib/platform/budget.ts`, `lib/classroom/drafts.ts`. Generic ideas retained: bounded body reading, unified known errors, cancellation/deadlines, atomic admission and idempotent retry. No old source file, D1/R2 migration, classroom auth, secrets or cloud resource configuration is copied. The reviewed source has no explicit repository license; this is not a claim of a license to copy it.
