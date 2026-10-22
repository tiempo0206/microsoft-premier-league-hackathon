# AB preview deployment

One FastAPI process serves A1's built frontend and same-origin `/api/v1`. There are no runtime model calls, authentication, database or object storage. Review the frozen scorer mismatch and shared error-contract gap in `docs/handoff/backend.md` before the final competition demo.

## Container target

From `matchmind/`:

```sh
docker build -f deploy/Dockerfile -t matchmind-ab .
docker run --rm -p 8000:8000 -e PORT=8000 matchmind-ab
```

The Dockerfile builds A's pinned frontend, installs B's resolved Python dependencies and runs as a non-root user. Only allowlisted files enter the image. Model-provider SDKs are absent. The Docker executable exists locally, but its Linux engine is not running: **the image has not been built or tested**. Local frontend compilation and the Python runtime are checked separately.

## Initial host: Render

Register at [Render](https://dashboard.render.com/). Local development needs no cloud account. Once publication/deployment is authorized and the branch is remote:

- Create one **Web Service** from the team repo. Its owner may need to authorize private-repo access.
- Root directory: `matchmind`; runtime: Docker; Dockerfile: `deploy/Dockerfile`; build context: this root directory. Prefer Singapore if available.
- Free is for previews and sleeps after 15 idle minutes. Consider the currently advertised US$7/month Starter compute instance for judging, after checking memory use and checkout price. Do not confuse it with a workspace-plan upgrade.
- Keep one instance. `backend.run` reads `PORT` and starts one worker. Health path: `/api/v1/health`.
- No database, disk or model key is needed for AB. No analysis jobs or model requests run by default.
- Check page/assets, APIs, playback, SSE reconnect and restart behavior. A1 displays snapshots; A's UI controls remain A2 work.

Checked 2026-10-22: [first deploy](https://render.com/docs/your-first-deploy), [free limits](https://render.com/docs/free), [advertised compute price](https://render.com/articles/render-vs-railway). No resources were created by this runbook.

## Student option, without blocking AB

The human may apply with their academic identity for [Azure for Students](https://azure.microsoft.com/en-us/free/students/). Official terms require age 18+, full-time attendance at an accredited degree-granting institution and academic verification. The offer currently advertises US$100 for 12 months without a credit card. Actual account/region eligibility and activation remain unverified; a hackathon login is not an Azure subscription. [Offer terms](https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0170p/)

Keep Render as the immediate preview route. If student activation succeeds and the team chooses Azure, reuse the same image in one Container App, one active revision, min/max replicas 1 and a fixed resource budget. Add no Azure-specific API layer. The backend role does not need Foundry model resources.

## AI stays separate

B creates observed inputs via `Replays.analysis_request(...)` and accepts checked outputs via `publish_analysis(request,result)`. A future integrator may call `await ai.service.analyze(request)` with explicit deadlines, admission limits and truthful generation labels. This branch has **no automatic analysis scheduler or runtime model call**. The unchanged fixture stub is only exercised by offline tests. Prompts, providers, orchestration and semantic auditing remain C work.
