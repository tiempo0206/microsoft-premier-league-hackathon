"""MatchMind as an MCP server, so any MCP client can query the match engine.

    python -m ai.mcp_server              # stdio transport
    python -m ai.mcp_server --http       # streamable HTTP on 127.0.0.1:8000/mcp

Every tool here reads the same deterministic code the product uses. There is no second
implementation of the statistics, the detector or the verifier, so an MCP answer and a
product answer cannot drift apart.

Honesty rules this server keeps:
* `explain_window` reports `generation.mode`, so a client can always tell a live model
  card from a `rule_fallback` one. It never presents a fallback as live inference.
* Without a configured model, `explain_window` still returns a useful, verified
  `rule_fallback` card instead of failing. The read-only tools need no key at all.
* Windows are clipped to the fixture's declared coverage; asking outside it is an error,
  not a silent widening.

The SDK is `mcp>=2`, where `FastMCP` was renamed to `MCPServer`. Copied examples written
for `mcp<2` fail at import.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer           # noqa: E402

from ai.config import from_env                       # noqa: E402
from ai.overlay import overlay_payload, validate_payload   # noqa: E402
from ai.service import analyze                       # noqa: E402
from ai.tools import Toolbox                         # noqa: E402
from ai.verify import consistency_issues, high_press_chains   # noqa: E402
from backend.data import Catalog                     # noqa: E402
from backend.inputs import analysis_input            # noqa: E402
from backend.stats import window_events, window_metrics       # noqa: E402

DATA_DIR = ROOT / "data" / "extra" / "validated-demo"
INSTRUCTIONS = """MatchMind exposes a synthetic football match engine plus a verified
explanation pipeline.

The numbers always come from deterministic code, never from a model. When you call
explain_window, read `generation.mode`: "live_model" means a real model wrote the card and
code verified every number and event id; "rule_fallback" means no model was used or the
model output failed verification. Never describe a rule_fallback card as AI-generated live
analysis.

Coverage is the declared clip of the fixture only. Ask list_matches first.
"""

server = MCPServer(name="matchmind", version="2.0.0", instructions=INSTRUCTIONS)


def _catalog():
    return Catalog(DATA_DIR)


def _fixture(match_id):
    fixtures = _catalog().fixtures
    if match_id not in fixtures:
        raise ValueError("unknown match_id %r; call list_matches" % (match_id,))
    return fixtures[match_id]


def _check_window(fixture, start_sec, end_sec):
    match = fixture.match
    if not isinstance(start_sec, int) or not isinstance(end_sec, int):
        raise ValueError("start_sec and end_sec must be integers")
    if start_sec > end_sec:
        raise ValueError("start_sec must not be after end_sec")
    if not match["clip_start_sec"] <= start_sec <= end_sec <= match["clip_end_sec"]:
        raise ValueError("window must sit inside %d..%d; the fixture declares no data outside it"
                         % (match["clip_start_sec"], match["clip_end_sec"]))
    return match


def _build_request(match_id, start_sec, end_sec, team_id, language, task_id):
    fixture = _fixture(match_id)
    _check_window(fixture, start_sec, end_sec)
    return analysis_input(fixture, replay_id="MCP", run_id=1, task_id=task_id,
                          start_sec=start_sec, end_sec=end_sec,
                          team_id=team_id, language=language)


def list_matches() -> list:
    """List the synthetic matches this server can answer about, with their declared clip."""
    catalog = _catalog()
    return [{
        "match_id": fixture.match["match_id"],
        "home": fixture.match["home"],
        "away": fixture.match["away"],
        "period": fixture.match["period"],
        "clip_start_sec": fixture.match["clip_start_sec"],
        "clip_end_sec": fixture.match["clip_end_sec"],
        "synthetic": fixture.match["synthetic"],
        "event_count": len(fixture.events),
        "generator_version": fixture.match.get("generator_version"),
    } for fixture in catalog.fixtures.values()]


def get_metrics(match_id: str, start_sec: int, end_sec: int, team_id: str = "HOME") -> dict:
    """Deterministic metrics for one window. These are the only numbers an explanation may cite."""
    if team_id not in ("HOME", "AWAY"):
        raise ValueError("team_id must be HOME or AWAY")
    fixture = _fixture(match_id)
    _check_window(fixture, start_sec, end_sec)
    metrics = window_metrics(fixture, start_sec, end_sec, team_id)
    return {"match_id": match_id, "window": {"start_sec": start_sec, "end_sec": end_sec},
            "team_id": team_id, "metrics": metrics,
            "definitions": {
                "high_recoveries": "recoveries by this team with attack-normalised x >= 66.67",
                "linked_shots": "high recoveries followed by a shot from the same possession within 15s",
                "possession_seconds": "recorded ownership intervals, not tracking ground truth",
            },
            "consistency_issues": consistency_issues(
                {"match_id": match_id, "team_id": team_id, "type": "high_press",
                 "events": window_events(fixture, start_sec, end_sec), "metrics": metrics,
                 "window": {"start_sec": start_sec, "end_sec": end_sec}})}


def get_event_window(match_id: str, start_sec: int, end_sec: int) -> list:
    """The raw synthetic events in a window, in match-clock order."""
    fixture = _fixture(match_id)
    _check_window(fixture, start_sec, end_sec)
    return window_events(fixture, start_sec, end_sec)


def get_candidate_moments(match_id: str, start_sec: int, end_sec: int,
                          team_id: str = "HOME") -> list:
    """High-recovery chains the detector would consider explaining, ranked by cause-effect links."""
    if team_id not in ("HOME", "AWAY"):
        raise ValueError("team_id must be HOME or AWAY")
    fixture = _fixture(match_id)
    _check_window(fixture, start_sec, end_sec)
    request = {"team_id": team_id, "window": {"start_sec": start_sec, "end_sec": end_sec},
               "events": window_events(fixture, start_sec, end_sec)}
    return Toolbox(request).get_candidate_moments()


async def explain_window(match_id: str, start_sec: int, end_sec: int,
                         team_id: str = "HOME", language: str = "en",
                         task_id: str = "MCP-TASK") -> dict:
    """Run the full verified pipeline on one window and return the AnalysisResult.

    Check `generation.mode` before quoting anything as live model output.
    """
    if language not in ("en", "zh"):
        raise ValueError("language must be en or zh")
    request = _build_request(match_id, start_sec, end_sec, team_id, language, task_id)
    config = from_env()
    result = await analyze(request, config=config if config.configured else None)
    return {"contract_version": request["contract_version"], "result": result,
            "model_ready": config.configured,
            "note": ("live model card" if (result.get("insight") or {})
                     .get("generation", {}).get("mode") == "live_model"
                     else "deterministic rule fallback; no model was used or its output failed verification")}


async def build_overlay(match_id: str, start_sec: int, end_sec: int,
                        team_id: str = "HOME", language: str = "en") -> dict:
    """Explain one window and return a timed broadcast overlay payload.

    Official rules 4.1 ask for output a graphics renderer can consume. The payload carries
    the source mode on every graphic, so a renderer cannot accidentally present a rule
    fallback as live model output.
    """
    explained = await explain_window(match_id, start_sec, end_sec, team_id, language,
                                     "MCP-OVERLAY")
    insight = (explained.get("result") or {}).get("insight")
    if not insight:
        raise ValueError("no publishable insight for this window: "
                         + str((explained.get("result") or {}).get("error")))
    payload = overlay_payload(insight)
    return {"overlay": payload, "problems": validate_payload(payload, insight),
            "source_mode": insight["generation"]["mode"]}


for _fn in (list_matches, get_metrics, get_event_window, get_candidate_moments,
            explain_window, build_overlay):
    server.add_tool(_fn)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MatchMind MCP server")
    parser.add_argument("--http", action="store_true",
                        help="serve streamable HTTP on 127.0.0.1:8000/mcp instead of stdio")
    args = parser.parse_args(argv)
    server.run(transport="streamable-http" if args.http else "stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
