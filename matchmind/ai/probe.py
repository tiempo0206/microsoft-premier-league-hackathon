"""Role C model probe. Config check by default; one billable request only with --live.

Prints a sanitised JSON report. The API key is never printed, echoed in an error, or
written to disk. Run it with the project interpreter:

    .\\.venv\\Scripts\\python.exe -m ai.probe
    .\\.venv\\Scripts\\python.exe -m ai.probe --live
"""
import argparse
import json
import time
import urllib.error
import urllib.request

from .config import from_env


def _request(config, body, timeout):
    url = config.base_url + "/chat/completions"
    headers = {"Authorization": "Bearer " + config.api_key,
               "Content-Type": "application/json"}
    payload = json.dumps(body).encode("utf-8")
    started = time.monotonic()
    request = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response), round((time.monotonic() - started) * 1000)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MatchMind Role C model probe")
    parser.add_argument("--live", action="store_true",
                        help="send exactly one possibly billable JSON request")
    args = parser.parse_args(argv)
    config = from_env()
    report = {"config": config.public(), "prompt_version": None, "live_requested": args.live}

    if not config.configured:
        report["ready"] = False
        report["reason"] = "provider/base_url/model/key incomplete; no request sent"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    if not args.live:
        report["ready"] = True
        report["note"] = "configuration complete; rerun with --live to send one request"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    from .prompts import PROMPT_VERSION
    report["prompt_version"] = PROMPT_VERSION
    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "Return only one JSON object. No markdown."},
            {"role": "user", "content": 'Return exactly {"ok":true,"probe":"matchmind"}.'},
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": 64,
        # Documented OpenAI-format thinking toggle. Verifying it here is the point:
        # thinking defaults to enabled at effort "high" on DeepSeek.
        "thinking": {"type": "disabled"},
    }
    try:
        payload, elapsed = _request(config, body, config.timeout)
        content = json.loads(payload["choices"][0]["message"]["content"])
        report.update({
            "ready": True,
            "success": content == {"ok": True, "probe": "matchmind"},
            "served_model": payload.get("model"),
            "elapsed_ms": elapsed,
            "usage": payload.get("usage"),
            "thinking_parameter_accepted": True,
        })
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["success"] else 2
    except urllib.error.HTTPError as error:
        hint = {400: "parameters, possibly the thinking toggle",
                401: "key or region", 403: "model permission",
                404: "base URL or model name", 429: "quota or rate limit"}.get(
                    error.code, "upstream")
        report.update({"ready": False, "http_status": error.code, "hint": hint})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3
    except (urllib.error.URLError, TimeoutError) as error:
        report.update({"ready": False, "network_error": type(error).__name__})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 4
    except (ValueError, KeyError, IndexError) as error:
        report.update({"ready": False, "bad_envelope": type(error).__name__})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
