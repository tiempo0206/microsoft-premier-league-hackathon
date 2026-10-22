"""Role C composition root — the single place where AI is wired into the backend.

Role B deliberately left the analysis adapter un-injected so that no model SDK ships
inside the backend-only image and `backend.app:app` keeps its verified behaviour. The
integration therefore lives here, in C-owned code, and never edits a B-owned file.

    # live if a key is configured, honest rule_fallback otherwise
    python -m uvicorn ai.app:app --host 127.0.0.1 --port 8000 --workers 1

Single worker and single replica are mandatory: replay sessions live in process memory,
which is why the frozen contract forbids scaling this shape out.
"""
from fastapi.responses import JSONResponse

from backend.app import create_app

from .config import from_env
from .service import analyze


def live_analyzer(config=None):
    """Wrap `ai.service.analyze` with an explicit configuration.

    This wrapper is the ONLY place that opts into network access. `ai.service.analyze`
    called bare stays offline, so Role B's dispatch tests never touch a paid endpoint
    even when the developer's environment holds a valid key.
    """
    config = config or from_env()

    async def analyzer(request):
        return await analyze(request, config=config)

    analyzer.model_config = config   # read-only, key-free introspection for tests
    return analyzer


def health_payload(config) -> dict:
    """Honest readiness. `model_ready` reflects the injected adapter, not a constant."""
    ready = config.configured
    return {"status": "ok" if ready else "degraded", "contract_version": "2.0.0",
            "mode": "production" if ready else "development", "model_ready": ready}


def build_app(config=None):
    """The same application object B verifies, plus the injected analyzer."""
    config = config or from_env()
    application = create_app(analyzer=live_analyzer(config), analysis_source="external")

    # B's /api/v1/health is the constant {"status": "degraded", "model_ready": False}
    # because B owns no model. Once an analyzer is injected that payload is a lie, so C
    # replaces it at the composition root. Interception happens before routing, which
    # leaves the JSON-404 catch-all and every other route untouched.
    @application.middleware("http")
    async def honest_health(request, call_next):
        if request.url.path == "/api/v1/health" and request.method == "GET":
            return JSONResponse(health_payload(config))
        return await call_next(request)

    application.state.model_config = config
    return application


app = build_app()
