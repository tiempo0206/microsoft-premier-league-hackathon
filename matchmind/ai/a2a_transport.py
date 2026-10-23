"""A2A JSON-RPC transport — a narrow, declared subset.

Until now this project published an A2A *agent card* and had no endpoint behind it, which is a
description without a service. This module adds the endpoint and states precisely what it accepts,
because a partial protocol implementation that pretends to be complete is worse than none.

Supported, and nothing else:

* `POST /a2a`, JSON-RPC 2.0, one request per HTTP call.
* Method `message/send`. The message must carry exactly one `data` part shaped
  `{"skill": "<mcp tool name>", "arguments": {...}}`.
* The reply is a `message` with one `data` part holding the tool result, plus a `text` part with
  the same result rendered for a human reader.
* Every other method returns JSON-RPC error `-32601 Method not found`, and every transport or
  shape problem returns a specific error code rather than an empty success.

Deliberately NOT implemented, and advertised as such in the agent card: streaming, task lifecycle
(`tasks/get`, `tasks/cancel`), push notifications, file parts, and free-text intent parsing. The
last one matters: we do not guess which tool a sentence wanted. A caller names the skill.

Why structured parts rather than natural language: the whole product argument is that a claim must
be traceable. Letting an LLM-shaped endpoint guess which tool was meant would put an untraceable
step in front of every answer.

    python -m ai.a2a_transport            # print the supported method list and a demo round trip
"""
import asyncio
import inspect
import json

from . import mcp_server

JSONRPC_VERSION = "2.0"
SUPPORTED_METHODS = ("message/send",)
INPUT_PART_KINDS = ("data",)
OUTPUT_PART_KINDS = ("data", "text")

ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32603

# Only these may be reached over the wire. Listed explicitly so adding an MCP tool does not
# silently widen the public surface.
EXPOSED_SKILLS = (
    "list_matches", "get_metrics", "get_event_window", "get_candidate_moments",
    "explain_window", "build_overlay", "build_recap", "get_threat_ranking",
)


def _error(request_id, code, message, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}


def _ok(request_id, result):
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def capabilities():
    """The honest capability statement, mirrored into the agent card."""
    return {"supportedMethods": list(SUPPORTED_METHODS),
            "inputPartKinds": list(INPUT_PART_KINDS),
            "outputPartKinds": list(OUTPUT_PART_KINDS),
            "exposedSkills": list(EXPOSED_SKILLS),
            "streaming": False,
            "taskLifecycle": False,
            "freeTextIntentParsing": False}


def _find_data_part(message):
    for part in (message or {}).get("parts") or []:
        if part.get("kind") == "data" and isinstance(part.get("data"), dict):
            return part["data"]
    return None


def _render(result):
    try:
        text = json.dumps(result, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(result)
    return text if len(text) <= 900 else text[:900] + "..."


def dispatch(payload):
    """Pure JSON-RPC handling. Returns the response dict; never raises for bad input."""
    if not isinstance(payload, dict):
        return _error(None, ERROR_INVALID_REQUEST, "request must be a JSON object")
    request_id = payload.get("id")
    if payload.get("jsonrpc") != JSONRPC_VERSION:
        return _error(request_id, ERROR_INVALID_REQUEST,
                      "jsonrpc must be \"2.0\"")
    method = payload.get("method")
    if method not in SUPPORTED_METHODS:
        return _error(request_id, ERROR_METHOD_NOT_FOUND,
                      "unsupported method; this agent implements only %s"
                      % (", ".join(SUPPORTED_METHODS),),
                      {"supportedMethods": list(SUPPORTED_METHODS)})

    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return _error(request_id, ERROR_INVALID_PARAMS, "params must be an object")
    message = params.get("message")
    if not isinstance(message, dict):
        return _error(request_id, ERROR_INVALID_PARAMS, "params.message is required")
    if message.get("role") not in (None, "user"):
        return _error(request_id, ERROR_INVALID_PARAMS,
                      "only role=user messages are accepted")

    data = _find_data_part(message)
    if data is None:
        return _error(request_id, ERROR_INVALID_PARAMS,
                      "message must carry one data part of the form "
                      "{\"skill\": ..., \"arguments\": {...}}; free-text intent parsing is not "
                      "implemented on purpose",
                      {"inputPartKinds": list(INPUT_PART_KINDS)})
    skill = data.get("skill")
    arguments = data.get("arguments") or {}
    if skill not in EXPOSED_SKILLS:
        return _error(request_id, ERROR_INVALID_PARAMS,
                      "unknown skill %r" % (skill,),
                      {"exposedSkills": list(EXPOSED_SKILLS)})
    if not isinstance(arguments, dict):
        return _error(request_id, ERROR_INVALID_PARAMS, "arguments must be an object")

    handler = getattr(mcp_server, skill, None)
    if handler is None:
        return _error(request_id, ERROR_INTERNAL, "skill %r is not callable" % (skill,))
    try:
        if inspect.iscoroutinefunction(handler):
            result = asyncio.run(handler(**arguments))
        else:
            result = handler(**arguments)
    except TypeError as error:
        return _error(request_id, ERROR_INVALID_PARAMS,
                      "%s rejected its arguments: %s" % (skill, error))
    except ValueError as error:
        return _error(request_id, ERROR_INVALID_PARAMS, str(error))
    except Exception as error:                       # noqa: BLE001 - JSON-RPC must answer
        return _error(request_id, ERROR_INTERNAL, "%s failed: %s"
                      % (skill, type(error).__name__))

    body = _ok(request_id, {
        "kind": "message",
        "role": "agent",
        "messageId": "a2a-" + str(request_id if request_id is not None else "0"),
        "parts": [
            {"kind": "data", "data": {"skill": skill, "result": result}},
            {"kind": "text", "text": _render(result)},
        ],
    })
    return body


def main(argv=None):
    demo_request = {
        "jsonrpc": JSONRPC_VERSION,
        "id": "demo-1",
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [
            {"kind": "data", "data": {"skill": "get_metrics",
                                      "arguments": {"match_id": "MM-DEMO-01",
                                                    "start_sec": 1500, "end_sec": 1650,
                                                    "team_id": "HOME"}}}]}},
    }
    refused = {"jsonrpc": JSONRPC_VERSION, "id": "demo-2", "method": "tasks/get",
               "params": {"id": "task-1"}}
    print(json.dumps({"capabilities": capabilities(),
                      "demo": dispatch(demo_request),
                      "unsupported_method": dispatch(refused)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
