"""The new service's HTTP boundary; no classroom/auth or Cloudflare imports."""
import asyncio
import json

from fastapi import Request
from fastapi.responses import JSONResponse
from contracts.validation import check_shape


class ApiError(Exception):
    def __init__(self, status, code, message, retryable=False):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable


def error_response(error: ApiError):
    headers = {"Retry-After": "60"} if error.status == 429 else None
    return JSONResponse({"error": {"code": error.code, "message": error.message,
                                   "retryable": error.retryable}}, error.status, headers=headers)


async def read_body(request: Request, shape: str, limit=16384, timeout=10):
    is_json = request.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/json"
    body = bytearray()
    try:
        async with asyncio.timeout(timeout):
            async for chunk in request.stream():
                if len(body) + len(chunk) > limit:
                    raise ApiError(413, "INVALID_REQUEST", "Request exceeds the byte limit.")
                body.extend(chunk)
        # Finish a bounded small upload before replying. Closing with unread bytes
        # can reset the TCP connection instead of delivering the intended 415.
        if not is_json:
            raise ApiError(415, "INVALID_REQUEST", "Content-Type must be application/json.")
        def invalid_constant(value):
            raise ValueError(value)
        value = json.loads(body, parse_constant=invalid_constant)
        check_shape(shape, value)
    except TimeoutError:
        raise ApiError(408, "TIMEOUT", "Reading the request body timed out.", True) from None
    except ApiError:
        raise
    except Exception:
        raise ApiError(400, "INVALID_REQUEST", "JSON does not match the request contract.") from None
    return value


def parse_second(value, default, fixture):
    if value is None:
        return default
    try:
        # No floats, exponent syntax, bools, or implicit clamping.
        if not value.isascii() or not value.isdigit():
            raise ValueError
        parsed = int(value)
        if not fixture.match["clip_start_sec"] <= parsed <= fixture.match["clip_end_sec"]:
            raise ValueError
        return parsed
    except ValueError:
        raise ApiError(400, "INVALID_REQUEST", "Time must be an integer second inside this clip.") from None
