"""Single-process MatchMind API. No model account is required for local work."""
import copy
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from .data import Catalog
from .http import ApiError, error_response, parse_second
from .stats import state_at

ROOT = Path(__file__).resolve().parents[1]


def create_app(data_dir=None):
    catalog = Catalog(Path(data_dir) if data_dir else ROOT / "data/fixtures")
    app = FastAPI(title="MatchMind", version="2.0.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.catalog = catalog
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
        return error_response(ApiError(error.status_code, "NOT_FOUND" if error.status_code == 404 else "INVALID_REQUEST",
                                       "Resource not found." if error.status_code == 404 else "HTTP method is not supported."))

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

    return app


app = create_app()
