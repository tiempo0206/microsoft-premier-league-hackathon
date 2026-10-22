# Role B handoff — data processing and backend deployment

**Latest (2026-10-23):** use `backend/INTEGRATOR_HANDOFF_CN.md` for the current
assembly instructions and `backend/C_INTEGRATION_FINDINGS.md` for the measured C
blocker. The 2026-10-23 addendum at the end supersedes earlier status statements.

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
8. Added optional B4 dispatch through an injected async adapter: fixed observed window, one task per replay generation, bounded queue/concurrency/hour bucket, cancellation, late-result protection and sanitized error messages. No adapter is injected by the default entrypoint; no model client or prompt is implemented.
9. Added `backend/INTEGRATION.md`, a free Render backend Blueprint, Chinese account-to-deployment instructions and a public-origin smoke command. Read-only inspection of PR #3 confirms A1; its unchanged API/snapshot consumer was exercised against B without building or editing the frontend.

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

- 46 backend tests passed, including the previous data/API suite plus adapter dispatch, queue/call deadline, budget/concurrency, cancellation/old-run and invalid-output cases.
- 19 inherited common tests passed. Shared frozen hashes and role-B scope passed; frontend/AI/contract/frozen-source paths have no changes.
- Default offline readiness report passed with corrected dataset, one worker, frontend disabled and required_credentials empty.
- All 20 locked dependency wheels resolved/downloaded for Python 3.12 Linux x86-64 through TUNA, stored on E:. This validates availability, not actual Linux execution.
- PowerShell startup syntax checked. New source and complete diff reviewed by Codex. The API-only Node check imported A1's unchanged consumer and passed catalogue/create/play/pause/reset through actual HTTP and named SSE. No frontend build, UI implementation or browser visual check was performed.
- The backend smoke command passed on a real loopback server: health/data/stats/create retry/play/pause/reset retry/old-run rejection/invalid input/SSE reconnect.
- The Render file passed its official JSON Schema locally, not the authenticated Render API. The local Docker engine remains unavailable after a human-authorized elevated transient-directory repair was denied by Windows; no image build/run is claimed. No cloud resources, paid requests, PR merge or public deployment were performed.

## Publication

The implementation through `e848395bc3723ba1ea2922af099437e20422dbbf` was pushed to `origin/codex/backend-ab-mvp` and the remote SHA was verified. This is the existing private team repository, not a new/public repository. A1 is still a branch dependency pending PR #3; no teammate branch or main was modified. No backend PR or cloud service has been created. The subsequent documentation commit records publication; use the current remote branch tip when deploying.

## Remaining boundary

The unexpected-500 shared error-enum gap remains unchanged; it requires a separate shared-contract decision. Replay state remains bounded single-process memory and is lost on restart. Dispatch is now implemented but disabled until a trusted async adapter is injected. That adapter must honor cancellation and network timeouts; arbitrary blocking Python code is not isolated. Prompts, real model readiness, semantic auditing and Microsoft Agent Framework implementation remain C/integration work. Public deployment needs a Render account and private repository authorization. Final frontend artifacts and real AI must be integrated separately; A1 does not yet contain A2 controls or A3 insight/evidence views in its pushed branch.

Kimi: no CLI or desktop process discovered, so the planning pass did not run; Codex performed the implementation and review. DSPy skipped for deterministic data/deployment work.

## Data and analysis closure — 2026-10-22

The human explicitly extended B's focus to complete data preparation and deterministic analysis while A continues the frontend and C/real AI remains separately arranged. Development stays on `codex/backend-ab-mvp`; PR and merge remain deferred.

- Added one shared event-window, possession-interval and recovery-chain implementation. Runtime metrics and offline evidence use it; public HTTP/SSE payloads stay frozen at 2.0.0.
- Runtime now checks the actual 3-high-recovery / 2-linked-recovery predicate before optional adapter admission. Negative windows consume no AI budget.
- Added `backend.inputs.analysis_input` as the common runtime/offline request builder, retaining the existing C signature and copied source events.
- Added versioned, deterministic analysis export: whole-clip totals and contribution IDs, half-open ownership segments, event-time checkpoints, three negative controls, input hashes, 301 logical-second invariant checks and a contract-valid offline request. These are engineering files, not AI Insights or new frontend endpoints.
- Added `python -m deploy.verify_backend`: readiness → analysis export → backend/common tests → owned loopback API → actual HTTP/control/SSE smoke → process-tree/port cleanup. Default output is ignored `.artifacts/backend-delivery/`, with source hashes and explicit unverified cloud/container/frontend/AI fields.
- Fixed a Windows venv redirector cleanup issue found during acceptance: terminate only the tree rooted at the exact owned child, wait, and verify that its listener closed. Tests cover error-path cleanup; no global Python/process-name kill is used.
- **63 backend tests and 19 common tests passed** in the final one-command run. Data/frozen/scope and Python compilation checks passed; no frontend, AI, contract or frozen-fixture file was edited. No extra dependency, new dataset account or model request is needed.

Read `backend/DATA_PIPELINE.md` for the Chinese execution/hand-off instructions. The report and offline request are generated artifacts and can be recreated by teammates from the branch. No private logs or local settings are committed.

Linux image execution and Render public acceptance remain outstanding. Docker Desktop was separately upgraded in place to 4.96.2 with official hash/signature verification; the existing Windows socket still prevents startup and the human chose a manual reboot before further validation. This local B pass does not claim a completed A/C integration or full competition submission.

## Reuse

Earlier backend work referenced generic HTTP limits, cancellation, atomic budgets and idempotency designs in the user-specified `xingma-classroom-upgrade` baseline `4f5d0c93d7a87849e50cf55f6ce10122f2df0a82`. No old source file, D1/R2 migration, auth/course data, secret or cloud configuration was copied. The current dataset derives only from this hackathon starter's recorded CC0 synthetic events.

## Unified B plan and multi-case regression — 2026-10-22

`backend/B_DELIVERY_PLAN.md` is now the single B execution/acceptance entry point. All work remains on `codex/backend-ab-mvp`; there is no new backend branch, PR or merge. B1–B6 are reported separately: local implementation and checks are not a substitute for container/public/A-C integration acceptance.

- Added `data/generator/scenarios.py`, a finite original synthetic template suite with an independent per-second state oracle. It imports no backend implementation. Runtime data and frozen contracts/fixtures are unchanged.
- The fixed full suite has **512 normal cases and 72 invalid cases**, using development seeds 1–8 and regression-holdout seeds 1001–1008, both teams/directions, eight normal templates and nine fault types. These are B numerical/data regressions, not C model training/evaluation.
- Normal and invalid data are exported separately, with input hashes, per-split results and failing-case export. Data is generated locally (about 3.7 MB) and remains ignored under `.artifacts/`; it is not served as production data or copied into the image.
- Final full backtest passed: **1,536 snapshot comparisons, 154,112 logical-second checks, 256 direction mirrors, 256 team swaps, zero synthetic false/missed triggers**. Holdout shares templates with development; no real-match generalization/AI-accuracy claim is made.
- Tests injected missing linked-shot counts and double goal counts without changing the expected labels; the backtest correctly failed both faulty implementations.
- The regression stage is now part of `python -m deploy.verify_backend`. **68 backend tests, 19 common tests, actual HTTP/SSE, frozen and B-scope checks passed.** Codex reviewed the complete diff; Kimi unavailable and DSPy skipped; no provider calls or new dependencies.
- Verified remote main is still `760dbd5`, while B depends on A1 `f88d286`. B-only scope is currently checked against A1. Before a final main-targeted PR, the integrator must establish the approved shared/A baseline and B must synchronize it on the same branch, then verify a B-only final diff. Do not open a main PR claiming the unmerged starter/A files are B work.

Current hardware/software is sufficient for offline B development and regression. Only the public preview requires a Render account and private-repository authorization; no token, model account, GPU, database or object storage is required now. Linux image/public acceptance and A/C integration remain pending.

## Linux container and stable local runtime verification

- Docker Desktop's Windows socket failure recurred after its normal restart. The human explicitly authorized repair/removal/reinstallation. A WSL IPC cleanup restored one startup but did not pass the restart gate, so it was not accepted as a durable fix.
- The failed Desktop application was officially uninstalled after a replacement was validated. The selected local runtime is dedicated WSL2 Docker Engine 29.8.2 with native Windows CLI/Buildx, context `matchmind-wsl`, and a restricted-key/pinned-host SSH transport to the private WSL address. Host-specific scripts/keys/backups stay outside Git; the user has a `启动 Docker` shortcut.
- Three full WSL shutdown/startup cycles passed, each with an idle delay and image-persistence check. After Desktop removal, the actual user shortcut cold-started the runtime and another container HTTP/SSE pass succeeded. No global WSL configuration or unrelated SSH host settings were changed.
- Built source commit `cd484485e5f742d0bb2bae86c0ae8a6becb6c934` as `matchmind-backend:b-cd48448`. The selected image manifest is `sha256:2245328dd82f9e19787ceaa459107556de4da790558a82c733312fd77988e03f`.
- Actual Linux container startup/preflight, HTTP data/stats, idempotent replay/control, pause/reset, invalid-input/old-run handling, named SSE reconnect, non-root UID 10001 and memory-backed restart behavior passed. Python is 3.12.15. No AI directory, frontend, .env or generated QA dataset is packaged.
- The Linux container's 512-normal/72-invalid backtest passed with exactly the same dataset hash as Windows: `bb1c39bfd07980695f6d214c0029970d69a7da688cf137c224bf6c3747603473`. Detailed local evidence is ignored under `.artifacts/docker-validation/`; the verification container is stopped and retained.
- B has not deployed a public service or integrated A/C deliverables. Render registration/private-repo authorization, cloud build/SSE and final joint acceptance remain outstanding. Existing `384b58f` is the common starter; main adoption/TEAM_ROLES recording is a shared integration responsibility, not missing code to recreate.
# 2026-10-23 final B preparation handoff

Latest executable instructions: `backend/INTEGRATOR_HANDOFF_CN.md`.
Same branch `codex/backend-ab-mvp`; contract 2.0.0; no A/C/frozen-source edits.

- Fixed foul ingestion and actor-versus-possession attribution without changing existing statistics.
- Added three optional original synthetic datasets (128/127/137 events), independent expectations, roster and SHA manifests; baseline defaults stay unchanged.
- Added 12 valid bilingual AnalysisRequest examples plus three separate corruptions, generated with zero model calls.
- Added release preflight/entry, Docker context allowlist, runtime example and a Linux dependency snapshot; final integration stays with the team's integrator.
- Isolated packaging check with A1 build and C `02228b8` proved Linux dependency resolution, startup, homepage serving and HTTP/SSE wiring. It did not merge A/C, test the browser or call a real model.
- The denser cases exposed C fallback evidence truncation: 4/12 normal outputs invalid; all three corruptions refused. Reproduction and acceptance are in `backend/C_INTEGRATION_FINDINGS.md`. Enhanced integrated startup is gated; original data remains the default.
- Render repository authorization remains an owner action. Model account/secret delivery stays with C; B requires no new token, GPU or data account.

Earlier sections above are retained for historical detail.
