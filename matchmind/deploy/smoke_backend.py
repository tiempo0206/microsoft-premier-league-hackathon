"""Probe an explicitly supplied backend; creates one short synthetic replay, no AI job."""
import argparse
import json
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def require(condition, message):
    if not condition:
        raise ValueError(message)


def probe(base):
    parsed = urlsplit(base)
    require(parsed.scheme in ("http", "https") and parsed.hostname,
            "Use an HTTP(S) service origin.")
    require(not parsed.username and not parsed.password and not parsed.query
            and not parsed.fragment and parsed.path in ("", "/"),
            "Use an origin without credentials, query or path.")
    base = base.rstrip("/")

    def call(path, body=None, key=None, run=None, status=200):
        headers = {"Content-Type": "application/json"}
        if key: headers["Idempotency-Key"] = key
        if run: headers["X-MatchMind-Expected-Run"] = str(run)
        request = Request(base + path, headers=headers,
                          data=json.dumps(body).encode() if body is not None else None)
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            require(response.status == status, f"Unexpected HTTP status on {path}.")
            return json.load(response)

    health = call("/api/v1/health")
    require(health["contract_version"] == "2.0.0", "Contract version differs.")
    matches = call("/api/v1/matches")
    require(any(m["match_id"] == "MM-DEMO-01" and m["generator_version"] == "fixture-2.0.1"
                for m in matches), "Validated demo revision missing.")
    state = call("/api/v1/matches/MM-DEMO-01/stats?at_sec=1650")
    require(state["score"] == {"HOME": 0, "AWAY": 0}, "Score differs at 1650.")
    require(state["shots"] == {"HOME": 2, "AWAY": 0}, "Shots differ at 1650.")
    key = str(uuid.uuid4())
    body = {"match_id": "MM-DEMO-01", "speed": 1}
    initial = call("/api/v1/replays", body, key, status=201)
    replay = initial["replay"]
    repeated = call("/api/v1/replays", body, key, status=201)
    require(repeated == initial, "Create retry was not idempotent.")
    path = "/api/v1/replays/" + replay["replay_id"]
    call(path + "/control", {"action": "play"}, run=1)
    time.sleep(1.1)
    paused = call(path + "/control", {"action": "pause"}, run=1)
    require(paused["replay"]["clock_sec"] > 1500, "Replay clock did not advance.")
    time.sleep(0.15)
    require(call(path)["replay"]["clock_sec"] == paused["replay"]["clock_sec"],
            "Paused replay advanced.")
    reset_key = str(uuid.uuid4())
    reset = call(path + "/control", {"action": "reset"}, reset_key, 1)
    require(call(path + "/control", {"action": "reset"}, reset_key, 1) == reset,
            "Reset retry was not idempotent.")
    require(reset["replay"]["run_id"] == 2 and reset["replay"]["clock_sec"] == 1500,
            "Reset generation/state differs.")
    error = call(path + "/control", {"action": "play"}, run=1, status=409)
    require(error["error"]["code"] == "STATE_CONFLICT", "Old run was accepted.")
    invalid = call("/api/v1/replays", {"match_id": "MM-DEMO-01", "speed": 999}, status=400)
    require(invalid["error"]["code"] == "INVALID_REQUEST", "Invalid input was accepted.")
    # Reconnect with an old transport ID must receive a fresh named snapshot.
    request = Request(base + path + "/stream", headers={
        "Last-Event-ID": replay["replay_id"] + ":1:1"})
    with urlopen(request, timeout=20) as response:
        require(response.headers.get_content_type() == "text/event-stream", "SSE type differs.")
        name, data = None, []
        for _ in range(100):
            line = response.readline(65536).decode("utf-8").rstrip("\r\n")
            if line.startswith("event: "): name = line[7:]
            if line.startswith("data: "): data.append(line[6:])
            if not line and data: break
        message = json.loads("\n".join(data))
        require(name == "snapshot" and message["kind"] == "snapshot"
                and message["run_id"] == 2, "Fresh snapshot recovery failed.")
    return {"result": "passed", "contract_version": "2.0.0",
            "checks": ["health", "data", "stats", "retry", "play_pause", "reset",
                       "old_run", "invalid_input", "SSE_snapshot_reconnect"],
            "model_ready": health["model_ready"], "model_job_requested": False,
            "temporary_replay": "idle; expires by server TTL"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", help="For example https://your-service.onrender.com")
    args = parser.parse_args()
    try:
        print(json.dumps(probe(args.origin), ensure_ascii=False))
    except Exception as error:
        # Do not echo server bodies, authentication headers or full input URLs.
        print(json.dumps({"result": "failed", "error_type": type(error).__name__,
                          "next": "Check service logs, wake a sleeping free service and retry."}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
