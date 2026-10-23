"""Role C composition root — the single place where AI is wired into the backend.

Role B deliberately left the analysis adapter un-injected so that no model SDK ships
inside the backend-only image and `backend.app:app` keeps its verified behaviour. The
integration therefore lives here, in C-owned code, and never edits a B-owned file.

    python -m uvicorn ai.app:app --host 127.0.0.1 --port 8000 --workers 1

Single worker and single replica are mandatory: replay sessions live in process memory,
which is why the frozen contract forbids scaling this shape out.

Three C-owned surfaces are added here rather than in `backend/`:

* `GET /api/v1/health` - B's payload is a constant `model_ready: false`; once an analyzer is
  injected that is a lie, so C replaces it with the truth.
* `GET /api/v1/replays/{id}/insights/{insight_id}/overlay` - the timed broadcast payload from
  `ai/overlay.py`, which official rules 4.1 ask for.
* `GET /.well-known/agent-card.json` - the A2A description from `ai/a2a.py`.

All three are interception rather than route registration, because B's JSON-404 catch-all
for `/api/{unmatched:path}` is registered before anything C can add.
"""
import json

from fastapi.responses import JSONResponse

from backend.app import create_app

from .a2a import agent_card
from .a2a_transport import dispatch as a2a_dispatch
from .config import from_env
from .overlay import overlay_payload, validate_payload
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


def build_app(config=None, *, public_url="http://127.0.0.1:8000", clock=None):
    """The same application object B verifies, plus the injected analyzer and C's surfaces.

    `clock` is a test seam: publication checks compare the insight window against the replay
    clock, so an integration test needs to move time without waiting for it.
    """
    config = config or from_env()
    kwargs = {"analyzer": live_analyzer(config), "analysis_source": "external"}
    if clock is not None:
        kwargs["clock"] = clock
    application = create_app(**kwargs)
    state = {"config": config, "public_url": public_url}

    @application.middleware("http")
    async def c_surfaces(request, call_next):
        path = request.url.path

        if path == "/a2a" and request.method == "POST":
            body = None
            try:
                raw = await request.body()
                body = json.loads(raw.decode("utf-8")) if raw else None
            except (ValueError, UnicodeDecodeError):
                body = None
            response = a2a_dispatch(body)
            status = 200 if "result" in response else 400
            return JSONResponse(response, status_code=status)

        if request.method != "GET":
            return await call_next(request)

        if path == "/api/v1/health":
            return JSONResponse(health_payload(state["config"]))

        if path == "/.well-known/agent-card.json":
            card = agent_card(state["public_url"], model_ready=state["config"].configured)
            return JSONResponse(card)

        if path.startswith("/api/v1/replays/") and path.endswith("/overlay"):
            return await _overlay_response(application, path)

        return await call_next(request)

    application.state.model_config = config
    application.state.public_url = public_url
    return application


async def _overlay_response(application, path):
    """Resolve .../replays/{replay_id}/insights/{insight_id}/overlay against live state."""
    parts = [p for p in path.split("/") if p]
    # api, v1, replays, <replay_id>, insights, <insight_id>, overlay
    if len(parts) < 7 or parts[0] != "api" or parts[2] != "replays" or parts[4] != "insights":
        return JSONResponse({"error": {"code": "NOT_FOUND",
                                       "message": "Overlay route not found.",
                                       "retryable": False}}, status_code=404)
    replay_id, insight_id = parts[3], parts[5]
    try:
        snapshot = await application.state.replays.get(replay_id)
    except Exception:                                  # noqa: BLE001 - B raises its own error
        return JSONResponse({"error": {"code": "NOT_FOUND", "message": "Replay not found.",
                                       "retryable": False}}, status_code=404)
    for insight in snapshot.get("insights") or []:
        if insight.get("insight_id") != insight_id:
            continue
        try:
            payload = overlay_payload(insight)
        except ValueError as error:
            return JSONResponse({"error": {"code": "STATE_CONFLICT", "message": str(error),
                                           "retryable": False}}, status_code=409)
        return JSONResponse({"payload": payload, "problems": validate_payload(payload, insight)})
    return JSONResponse({"error": {"code": "NOT_FOUND", "message": "Insight not found.",
                                   "retryable": False}}, status_code=404)


app = build_app()
