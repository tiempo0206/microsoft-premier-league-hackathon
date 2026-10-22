"""Single-process MatchMind API. No model account is required for local work."""
import copy
import asyncio
import contextlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
import anyio
from sse_starlette.sse import EventSourceResponse

from .data import Catalog
from .audit import audit_dataset
from .http import ApiError, error_response, parse_second, read_body
from .replays import Replays
from .settings import Settings
from .stats import state_at

ROOT = Path(__file__).resolve().parents[1]


def create_app(data_dir=None, settings=None, clock=time.monotonic, frontend_dist=None):
    settings = settings or Settings.from_env()
    directory = Path(data_dir) if data_dir is not None else Path(settings.data_directory)
    if not directory.is_absolute():
        directory = ROOT / directory
    catalog = Catalog(directory)
    data_report = audit_dataset(directory, catalog)
    if data_report["status"] != "passed":
        codes = ", ".join(sorted({issue["code"] for issue in data_report["issues"]}))
        raise ValueError(f"Dataset readiness failed: {codes}. Run python -m deploy.preflight for details.")
    replays = Replays(catalog, settings, clock)

    @asynccontextmanager
    async def lifespan(app):
        ticker = asyncio.create_task(replays.run())
        try:
            yield
        finally:
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker
            await replays.close()

    app = FastAPI(title="MatchMind", version="2.0.0", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.catalog = catalog
    app.state.data_report = data_report
    app.state.replays = replays
    for fixture in catalog.fixtures.values():
        for warning in fixture.warnings:
            logging.getLogger(__name__).warning("Frozen synthetic fixture: %s", warning)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ApiError)
    async def api_error(request, error):
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response(ApiError(400, "INVALID_REQUEST", "Request parameters are invalid."))

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        response = error_response(ApiError(error.status_code, "NOT_FOUND" if error.status_code == 404 else "INVALID_REQUEST",
                                          "Resource not found." if error.status_code == 404 else "HTTP method is not supported."))
        response.headers.update(error.headers or {})
        return response

    def fixture_for(match_id):
        fixture = catalog.fixtures.get(match_id)
        if fixture is None:
            raise ApiError(404, "NOT_FOUND", "Match not found.")
        return fixture

    @app.get("/api/v1/health")
    async def health():
        return {"status": "degraded", "contract_version": "2.0.0", "mode": "development", "model_ready": False}

    @app.get("/api/v1/matches")
    async def matches():
        return [copy.deepcopy(f.match) for f in catalog.fixtures.values()]

    @app.get("/api/v1/matches/{match_id}")
    async def match(match_id: str):
        return copy.deepcopy(fixture_for(match_id).match)

    @app.get("/api/v1/matches/{match_id}/events")
    async def events(match_id: str, from_sec: str | None = None, to_sec: str | None = None):
        fixture = fixture_for(match_id)
        start = parse_second(from_sec, fixture.match["clip_start_sec"], fixture)
        end = parse_second(to_sec, fixture.match["clip_end_sec"], fixture)
        if start > end:
            raise ApiError(400, "INVALID_REQUEST", "The event window is reversed.")
        return [copy.deepcopy(e) for e in fixture.events if start <= e["timestamp_sec"] <= end]

    @app.get("/api/v1/matches/{match_id}/stats")
    async def stats(match_id: str, at_sec: str | None = None):
        fixture = fixture_for(match_id)
        return state_at(fixture, parse_second(at_sec, fixture.match["clip_start_sec"], fixture))

    def request_headers(request):
        key = request.headers.get("Idempotency-Key")
        if key is not None:
            try:
                key = str(uuid.UUID(key))
            except ValueError:
                raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be a UUID.") from None
        raw = request.headers.get("X-MatchMind-Expected-Run")
        expected = None
        if raw is not None:
            try:
                if not raw.isascii() or not raw.isdigit() or len(raw) > 10:
                    raise ValueError
                expected = int(raw)
                if expected < 1:
                    raise ValueError
            except ValueError:
                raise ApiError(400, "INVALID_REQUEST", "Expected run must be a positive integer.") from None
        return key, expected

    @app.post("/api/v1/replays")
    async def create_replay(request: Request):
        body = await read_body(request, "CreateReplay", settings.max_request_bytes, settings.body_timeout)
        key, _ = request_headers(request)
        return JSONResponse(await replays.create(body, key), status_code=201)

    @app.get("/api/v1/replays/{replay_id}")
    async def get_replay(replay_id: str):
        return await replays.get(replay_id)

    @app.post("/api/v1/replays/{replay_id}/control")
    async def control_replay(replay_id: str, request: Request):
        body = await read_body(request, "ControlReplay", settings.max_request_bytes, settings.body_timeout)
        key, expected = request_headers(request)
        return await replays.control(replay_id, body, key, expected)

    @app.get("/api/v1/replays/{replay_id}/stream")
    async def stream(replay_id: str):
        subscriber_id, queue = await replays.subscribe(replay_id)

        async def messages():
            try:
                while (message := await queue.get()) is not None:
                    yield {"event": message["kind"],
                           "id": f"{message['replay_id']}:{message['run_id']}:{message['seq']}",
                           "data": json.dumps(message, ensure_ascii=False, separators=(",", ":"))}
            finally:
                with anyio.CancelScope(shield=True):
                    await replays.unsubscribe(replay_id, subscriber_id)

        # Last-Event-ID intentionally restores a new snapshot, not a replayed transport log.
        return EventSourceResponse(messages(), ping=15, send_timeout=5,
                                   headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/v1/replays/{replay_id}/insights/{insight_id}")
    async def insight(replay_id: str, insight_id: str):
        snapshot = await replays.get(replay_id)
        for item in snapshot["insights"]:
            if item["insight_id"] == insight_id:
                return item
        raise ApiError(404, "NOT_FOUND", "Insight not found.")

    @app.api_route("/api/{unmatched:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def missing_api(unmatched: str):
        raise ApiError(404, "NOT_FOUND", "API route not found.")

    # A1 is a single-page entry; unknown /api routes must remain JSON 404s.
    assets = Path(frontend_dist) if frontend_dist else ROOT / "frontend/dist"
    if settings.serve_frontend and (assets / "index.html").is_file():
        app.mount("/", StaticFiles(directory=assets, html=True), name="frontend")

    return app


app = create_app()
