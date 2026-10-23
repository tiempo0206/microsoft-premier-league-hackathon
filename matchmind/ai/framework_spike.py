"""C4 spike: can Microsoft Agent Framework drive DeepSeek within the analysis deadline?

Run:  .\\.venv\\Scripts\\python.exe -m ai.framework_spike
Billable. Prints a sanitised report. Writes nothing.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from .config import from_env


async def run(thinking_disabled: bool) -> dict:
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatCompletionClient

    config = from_env()
    client = OpenAIChatCompletionClient(
        model=config.model, api_key=config.api_key, base_url=config.base_url)
    options = {"max_tokens": 400, "response_format": {"type": "json_object"}}
    if thinking_disabled:
        # DeepSeek documents the thinking toggle as a top-level request field. The OpenAI
        # SDK exposes it through extra_body.
        options["extra_body"] = {"thinking": {"type": "disabled"}}
    agent = Agent(
        client=client,
        name="spike-analyst",
        instructions=("Return exactly one JSON object and nothing else. "
                      "Shape: {\"ok\": true, \"window\": \"<the window string>\"}."),
        default_options=options,
    )
    started = time.monotonic()
    try:
        response = await agent.run(
            "Window start_sec=1500 end_sec=1650 team=HOME. Reply with the required JSON.")
        elapsed = round((time.monotonic() - started) * 1000)
        text = response.text if hasattr(response, "text") else str(response)
        parsed = None
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        return {"thinking_disabled": thinking_disabled, "success": parsed is not None,
                "elapsed_ms": elapsed, "parsed": parsed,
                "text_head": (text or "")[:180]}
    except Exception as error:                       # noqa: BLE001 - a spike must report
        return {"thinking_disabled": thinking_disabled, "success": False,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "error": type(error).__name__ + ": " + str(error)[:300]}


async def main():
    config = from_env()
    if not config.configured:
        print(json.dumps({"error": "no model configured"}, indent=2))
        return 1
    report = {"config": config.public(), "results": []}
    for flag in (True, False):
        result = await run(flag)
        report["results"].append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
