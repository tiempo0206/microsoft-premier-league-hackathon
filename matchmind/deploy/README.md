# Deployment utilities

Current service, Render settings and takeover steps live in the [single B handoff](../docs/handoff/backend.md).

| File | Purpose |
| --- | --- |
| Dockerfile / Dockerfile.dockerignore | B-only image; build context matchmind/ |
| backend.env.example / start-backend.ps1 | Local B configuration and startup |
| preflight.py / smoke_backend.py | Offline readiness / supplied public-origin probe |
| verify_backend.py | Complete B acceptance, with owned temporary HTTP/SSE servers |
| adapter_check.py | Offline C output compatibility; network connections blocked |
| Dockerfile.release / matching ignore | Combination template requiring A's built dist and C source |
| release_check.py / release_run.py | Assembly readiness and C composition startup |
| release.env.example / requirements-release.lock | Runtime placeholders / tested Linux dependency snapshot |
| render-backend.yaml | Optional new B preview on main; do not duplicate the existing service |

From matchmind/, build B with `docker build -f deploy/Dockerfile -t matchmind-backend .`.
Final combined build must include frontend/dist in the actual cloud build context; a Git-ignored local artifact does not travel with a Render Git clone. Detailed steps and the existing service are in the handoff.

Images run one non-root worker. B's image has no frontend/model SDK/key; the release template explicitly includes A/C artifacts. Configuration examples contain no credentials. No database or object storage is required.
