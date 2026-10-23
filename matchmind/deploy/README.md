# Role B — backend-only deployment

**Current status (2026-10-23):** the shared code is on main and the B preview is
live at https://matchmind-backend-preview.onrender.com . Authenticated API
configuration and post-deploy public HTTP/SSE checks passed. Start with
`RENDER_STEPS_CN.md` and `../backend/INTEGRATOR_HANDOFF_CN.md` to take over; do not
repeat account creation or look for the old role branch.

This package runs the data/API service, with no frontend build, page assets, model implementation, cloud provisioning, database or object storage. Default configuration is in `backend.env.example`; export its values in the process/platform environment. Arbitrary .env files are not auto-loaded.

## Local readiness and startup

For a complete backend/data acceptance, use `python -m deploy.verify_backend` from `matchmind/`. It runs data/readiness, analysis export, backend/common tests and real loopback HTTP/SSE probes, then stops its own servers. No model, Docker or cloud account is required. That local command does not itself attest to Linux/cloud/frontend/live-AI acceptance; the separate Linux and B cloud records are already available.

From `matchmind/`, after installing the pinned `backend/requirements.lock`:

```powershell
.\.venv\Scripts\python.exe data/generator/prepare_demo.py --check
.\.venv\Scripts\python.exe -m deploy.preflight --output .artifacts/backend-preflight.json
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Or use `deploy/start-backend.ps1`; it validates readiness before starting, keeps the local listener on loopback and restores the caller's PORT setting on exit. It does not install or launch any cloud tool.

`deploy.preflight` is read-only unless `--output` is explicitly supplied. Exit 0 means the backend dataset/config checks passed; exit 2 means they failed. It checks source/output hashes, roster membership, shot/goal pairing, audited statistics and deterministic reconstruction. It never prints environment values, model keys or credentials. Python `-O` does not disable its checks.

The default dataset is `data/extra/validated-demo`, revision `fixture-2.0.1`. The original frozen `data/fixtures/` is preserved; selecting that known-invalid original deliberately fails readiness. Both the container entrypoint and application startup reject invalid configured data. No model readiness is required for backend startup.

## Backend container

Build context is `matchmind/`:

```sh
docker build -f deploy/Dockerfile -t matchmind-backend .
docker run --rm -p 8000:8000 --env-file deploy/backend.env.example matchmind-backend
```

The image uses Python 3.12, pinned backend dependencies, one worker and a non-root runtime user. It copies only backend modules, schemas and local data/preparation helpers. It runs offline preflight during the build and again at startup. No Node/npm/pnpm, frontend directory, AI module, model SDK, old classroom resource or API key is included.

`Dockerfile.dockerignore` excludes the build context by default and explicitly permits the small required files. This avoids sending .venv, node_modules, .env and unrelated work to the builder. Docker supports an ignore file named for its Dockerfile in the same directory. [Official build-context documentation](https://docs.docker.com/build/concepts/context/#filename-and-location)

The backend image has now been **built and run on Linux** from source commit `cd484485e5f742d0bb2bae86c0ae8a6becb6c934`, tag `matchmind-backend:b-cd48448`. Build/startup preflight, actual HTTP/control/SSE, container restart behavior and the 512-normal/72-invalid synthetic regression passed. The image runs as UID 10001, uses Python 3.12.15, and contains no AI directory, frontend, .env files or generated backtest artifacts. The Linux dataset hash matches the Windows regression.

On this machine, Docker Desktop 4.96.2 still reproduced its Windows AF_UNIX error after a normal stop/start, even after an IPC cleanup. With the human's explicit uninstall/reinstall authorization, it was replaced by a dedicated WSL2 Docker Engine 29.8.2 and the native Windows CLI/Buildx, using a pinned-key SSH context named `matchmind-wsl`. The failed Desktop application was officially uninstalled. Three complete stops/starts of the dedicated WSL distribution preserved the image, and an additional cold start and HTTP/SSE pass succeeded after Desktop removal. The entire WSL VM was then shut down and the engine was confirmed ready again through the user launcher. This is a verified replacement runtime; it is not a claim that the Desktop vendor bug was fixed.

Machine-specific startup/stop scripts, SSH material and settings backups are outside Git. The local desktop shortcut is `启动 Docker`; the image/runtime data stays on E:. Other teammates may use any working Docker Linux engine. The runtime repair itself did not provision cloud resources; Render's cloud builder does not depend on this local workaround.

## Render account through preview acceptance

Follow `RENDER_STEPS_CN.md` for the existing service, its ID, source version and configuration. The optional `render-backend.yaml` now targets main with repo-root-relative paths and a Free single-instance Singapore backend. It creates only a B preview, with no model/database secrets and auto-deploy off. The existing service was created manually; do not create a duplicate Blueprint. Its cloud build, authenticated configuration read-back and public smoke have passed. A future Blueprint has an independent Auto Sync switch.

Once the service is live, run from `matchmind/`:

```sh
python deploy/smoke_backend.py https://your-service.onrender.com
```

This explicitly creates one short-lived synthetic replay and checks health, data revision, audited statistics, idempotent create/reset, play/pause, old-run rejection, invalid input and named SSE snapshot recovery. It does not cross the analysis trigger window or request a model job. The backend-only `/` returns JSON 404; use `/api/v1/health` and the documented API. A public API preview is not the final frontend/AI website.

## Host configuration for a later authorized deployment

For a Docker web-service host such as the already selected Render route:

| Setting | Value |
| --- | --- |
| Root/build context | `matchmind` |
| Dockerfile | `deploy/Dockerfile` |
| Process | `python -m backend.run` (image default) |
| Port | Platform `PORT`, default 8000 |
| Health path | `/api/v1/health` |
| Instances/workers | Exactly 1 / 1; state is in process memory |
| Frontend serving | `MATCHMIND_SERVE_FRONTEND=0` |
| Data directory | `data/extra/validated-demo` |
| Required model/database secrets | None |

Verify HTTP health, match revision, statistics, playback/control, SSE reconnect and restart behavior after deployment. A container restart intentionally loses replay sessions. Keep the generic unexpected-500 error-contract limitation in the handoff record; shared contract changes require their own review. This runbook prepares deployment only and does not authorize publication, payment or changes to access.
