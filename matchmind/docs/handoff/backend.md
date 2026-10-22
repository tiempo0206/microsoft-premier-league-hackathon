# Role B handoff — data processing and backend deployment

- Developer: B / `wunianze666-netizen`, assisted by Codex.
- Task: [Issue #6](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/6).
- Local branch: `codex/backend-ab-mvp`.
- Shared application base: A1 `f88d286092e602d73804e1afeb114ec0f126b2ff`.
- Previous backend base: `16454f9`; data preparation slice: `3ee04dc`.
- Contract remains `2.0.0`. This slice is limited to B-owned backend/data/deployment/tests and this handoff. Frontend/AI source and frozen contracts/fixtures are unchanged.

## Human scope and delivered behavior

The human explicitly narrowed work to their own data-processing and deployment responsibilities. No frontend build, browser operation, UI development, model implementation, cloud account creation or cross-task coordination is part of this slice.

1. Prepared a B-owned corrected synthetic dataset at `data/extra/validated-demo`, revision `fixture-2.0.1`. The original shared source stays frozen. Only Match generator_version and E023's scorer differ; the first 20 event objects and all previously audited totals are unchanged.
2. Added explicit fictional rosters, independently specified expected states/metrics, CC0 provenance and source/output SHA-256 records.
3. Added deterministic preparation/check commands. They verify frozen source digests and write only five managed files under the B-owned output directory; they are not a new football simulator or model job.
4. Added fail-closed dataset audit and deployment preflight for shape/order, roster membership, one-to-one shot/goal relations, baseline totals, integrity and reproducibility. Missing/null/invalid metadata fails. Checks remain active under Python optimization.
5. Switched default runtime to API-only. `MATCHMIND_SERVE_FRONTEND=0`; `/` is JSON 404 and no page files are needed. The backend's existing optional static hosting is reserved for a later, separately coordinated integration.
6. Replaced the Node/frontend container stage with a Python-only backend image, non-root user, one worker, explicit source/context allowlists and offline data checks at build/startup. It contains no AI module or model SDK.
7. Added backend-only environment examples and startup preflight. No key, token or database credential is required.

## Data provenance and compatibility

The frozen original records scoring shot E022 as H01 and goal E023 as H02. The B-owned derivative records the confirmation as H01. Time and ID semantics remain unchanged; score is still counted only on goal. `prepare_demo.py --check` verifies exact bytes without editing the source. `PROVENANCE.json` records the explicit change and inherited CC0 license. This validates the sparse synthetic excerpt's declared event relationships, not continuous tracking or real-world causal claims.

## Commands

From `matchmind/`, using its existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe data/generator/prepare_demo.py --check
.\.venv\Scripts\python.exe -m deploy.preflight --output .artifacts/backend-preflight.json
.\.venv\Scripts\python.exe -m unittest discover -s tests/backend -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe tools/check_frozen.py
.\.venv\Scripts\python.exe tools/check_scope.py --role B --base 16454f9
```

`deploy/start-backend.ps1` runs preflight before the loopback server and restores the caller's PORT on exit. The container entry `python -m backend.run` checks readiness before starting one worker on the platform PORT. Read `backend/README.md` and `deploy/README.md` for the exact backend-only commands.

## Verification

- 36 backend tests passed, including data-corruption/metadata/roster/scorer cases, optimized-Python preflight, API-only startup, config validation and report credential redaction.
- 19 inherited common tests passed. Shared frozen hashes and role-B scope passed; frontend/AI/contract/frozen-source paths have no changes.
- Default offline readiness report passed with corrected dataset, one worker, frontend disabled and required_credentials empty.
- All 20 locked dependency wheels resolved/downloaded for Python 3.12 Linux x86-64 through TUNA, stored on E:. This validates availability, not actual Linux execution.
- PowerShell startup syntax checked. New source and complete diff reviewed by Codex. No frontend or Node checks were run in this slice.
- The local Docker Linux engine is unavailable; no successful image build/run is claimed. No cloud resources, paid requests, new backend push, PR merge or public deployment were performed.

## Remaining boundary

The unexpected-500 shared error-enum gap remains unchanged; it requires a separate shared-contract decision. Replay state remains bounded single-process memory and is lost on restart. This data/deployment slice does not implement runtime analysis dispatch, prompts or model readiness; existing internal handoff hooks are preserved.

Kimi: no CLI or desktop process discovered, so the planning pass did not run; Codex performed the implementation and review. DSPy skipped for deterministic data/deployment work.

## Reuse

Earlier backend work referenced generic HTTP limits, cancellation, atomic budgets and idempotency designs in the user-specified `xingma-classroom-upgrade` baseline `4f5d0c93d7a87849e50cf55f6ce10122f2df0a82`. No old source file, D1/R2 migration, auth/course data, secret or cloud configuration was copied. The current dataset derives only from this hackathon starter's recorded CC0 synthetic events.
