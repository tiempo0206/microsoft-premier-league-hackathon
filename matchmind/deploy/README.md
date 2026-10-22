# Role B — backend-only deployment

This package runs the data/API service, with no frontend build, page assets, model implementation, cloud provisioning, database or object storage. Default configuration is in `backend.env.example`; export its values in the process/platform environment. Arbitrary .env files are not auto-loaded.

## Local readiness and startup

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

The local Docker Linux engine cannot start because Windows denies access to a stale IPC socket directory, including after the human-authorized elevated repair attempt. The image has **not** been built or started. No factory reset, persistent-data deletion or ACL takeover was performed. Python 3.12 Linux x86-64 wheels for all 20 locked dependencies were resolved/downloaded successfully through TUNA; this is dependency availability evidence, not a substitute for an image test. No public service or paid resource has been created. Render's cloud builder does not require a working local Docker Desktop installation.

## Render account through preview acceptance

Follow `RENDER_STEPS_CN.md`. The prepared `render-backend.yaml` uses repo-root-relative paths, a free single-instance Singapore backend, no model/database secrets and disabled service auto-deploy. Also disable Blueprint Auto Sync in the dashboard. The branch must be pushed and the private repository authorized before creating the service. The file passed the official JSON Schema locally; authenticated platform validation and the first Linux build remain outstanding.

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
