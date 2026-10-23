# B delivery evidence — 2026-10-23

Branch: `codex/backend-ab-mvp`. Contract: 2.0.0. Default data and frozen baseline unchanged.

| Acceptance item | Observed result |
| --- | --- |
| B tests | 85 passed |
| Shared tests | 19 passed |
| Existing synthetic backtest | 512 normal + 72 invalid, zero failed; 154,112 logical seconds |
| Dataset hash for existing backtest | `bb1c39bfd07980695f6d214c0029970d69a7da688cf137c224bf6c3747603473` |
| New showcase | 128 / 127 / 137 events, deterministic, independent expectations and 22-player rosters |
| Actual HTTP/SSE | Baseline and all three showcase datasets pass data/stats/retry/play-pause/reset/old-run/invalid-input/snapshot-reconnect checks |
| Input handoff | 12 valid bilingual requests; 3 separate corruptions; hashed exports |
| Python optimization | Showcase preflight passes with `python -O`; checks are not assertions |
| Frozen/scope checks | Frozen contracts/fixtures unchanged; only B-owned paths |
| B-only Linux image | Built successfully as local `matchmind-backend:b-showcase-20261023` |
| Release dependency snapshot | All 42 pinned Linux Python 3.12 packages installed successfully |
| Isolated assembly | Existing A1 build + C `02228b8` + current B; real image build/start and homepage HTTP200 + API/SSE pass |
| Release image local manifest | `sha256:ecede0668edc9595033269e025c31436ed262dfec2c4d67b5d9c87992daee8b2` |
| Denser C compatibility | 8/12 normal result contracts pass; 4 fail evidence inclusion; all 3 corruptions refused |
| Enhanced release gate | Refuses to start with known-invalid C dense fallback; original baseline remains usable |
| Credentials and model calls | No real key provided, no paid calls; offline adapter checker blocks Python socket connections |
| Public cloud / final browser / live model | Not performed; owned by the team's final integrator |

Reproduce B acceptance from `matchmind/`:

```text
python -m deploy.verify_backend
python tools/check_frozen.py
python tools/check_scope.py --role B --base f88d286092e602d73804e1afeb114ec0f126b2ff
```

Use the project's Python 3.12 virtual environment. Acceptance JSON, source hashes,
input packs, backtests and logs are generated in `.artifacts/backend-delivery/`.
This workstation's final run is in `.artifacts/backend-final-handoff-20261023/`;
isolated assembly records are in `.artifacts/assembly-proof-20261023/`.
These directories are intentionally ignored; teammates regenerate them.

The release image is a **local packaging proof**, not an uploaded registry image,
merged release, completed frontend flow or real-model demonstration. Verification
containers are stopped after probing and retained; no public service was created.

The Docker build additionally exposed a missing Windows wincred helper after the
Desktop uninstall. Official docker-credential-helpers v0.9.12 was restored with
release SHA-256 verified; existing credential settings were preserved. Image
builds then succeeded. No new Docker/Render/model account is required for these
local checks.

Codex reviewed source, scope, contracts, data expectations and staged changes.
Kimi runtime unavailable; Kimi did not run. DSPy skipped for this deterministic
B slice. See `INTEGRATOR_HANDOFF_CN.md` and `C_INTEGRATION_FINDINGS.md` for the
integration owner checklist and the remaining C blocker.
