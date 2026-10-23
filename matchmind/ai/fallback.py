"""Deterministic rule fallback: an honest, useful card with no model involved.

Two rules govern this module.

1. It reads only the AnalysisRequest. It never reads a fixture file, a session store or
   a clock, so it cannot leak a future event into a recap.
2. It never invents a number. Every metric claim restates `request["metrics"]`, and the
   interpretation claim is written to be true for any window that triggered the
   detector. When the input is inconsistent we reject instead of narrating.
"""
from .verify import (LINKED_SHOT_HORIZON_SEC, METRIC_KEYS, consistency_issues,
                     high_press_chains)

_TITLES = {"en": "Pressure creates chances", "zh": "前场压迫制造机会"}
_FALLBACK_ERRORS = {
    "no_model": ("MODEL_UNAVAILABLE", "No live model is configured; this card is a rule fallback.", False),
    "timeout": ("TIMEOUT", "The analysis deadline expired; this card is a rule fallback.", True),
    "provider": ("MODEL_UNAVAILABLE", "The model call failed; this card is a rule fallback.", True),
    "invalid": ("MODEL_INVALID_OUTPUT", "Model output failed verification; this card is a rule fallback.", True),
    "budget": ("CAPACITY_LIMIT", "Analysis capacity is exhausted; this card is a rule fallback.", True),
}


def _team_label(request):
    team = request["team_id"]
    return ("Home side" if team == "HOME" else "Away side") if request["language"] == "en" \
        else ("主队" if team == "HOME" else "客队")


def recovery_chains(request):
    """Evidence selection only; never overrides a metric."""
    return high_press_chains(request)


def _evidence(request, chains):
    ordered = []
    for chain in chains:
        ordered.extend(chain["evidence_event_ids"])
    if not ordered:
        team = request["team_id"]
        ordered = [e["event_id"] for e in request["events"] if e["team_id"] == team]
    if not ordered:
        ordered = [e["event_id"] for e in request["events"]]
    return list(dict.fromkeys(ordered))[:12]


def rule_claims(request, chains, evidence):
    metrics = request["metrics"]
    own_shots = metrics["home_shots"] if request["team_id"] == "HOME" else metrics["away_shots"]
    lang = request["language"]
    cited = evidence[:6]
    claims = []

    if lang == "zh":
        texts = [
            ("metric", "本窗口内%s前场高位夺回 %d 次。" % (_team_label(request), metrics["high_recoveries"]),
             "high_recoveries", metrics["high_recoveries"], [c["recovery_event_id"] for c in chains][:4] or cited),
            ("metric", "其中 %d 次在 %d 秒内形成射门。" %
             (metrics["linked_shots"], LINKED_SHOT_HORIZON_SEC),
             "linked_shots", metrics["linked_shots"],
             [e for c in chains for e in c["linked_shots"]][:4] or cited),
            ("metric", "%s本窗口内射门 %d 次。" % (_team_label(request), own_shots),
             "home_shots" if request["team_id"] == "HOME" else "away_shots", own_shots, cited),
            ("interpretation",
             "%s在这段时间里持续在对方半场夺回球权并迅速完成射门，这是一个可复核的观察结果，"
             "不构成对对手体能、意图或教练决定的推断。" % _team_label(request),
             None, None, cited),
        ]
    else:
        texts = [
            ("metric", "The %s made %d high recoveries in this window." %
             ("home side" if request["team_id"] == "HOME" else "away side",
              metrics["high_recoveries"]),
             "high_recoveries", metrics["high_recoveries"], [c["recovery_event_id"] for c in chains][:4] or cited),
            ("metric", "%d of those recoveries produced a shot within %d seconds." %
             (metrics["linked_shots"], LINKED_SHOT_HORIZON_SEC),
             "linked_shots", metrics["linked_shots"],
             [e for c in chains for e in c["linked_shots"]][:4] or cited),
            ("metric", "The %s took %d shots in this window." %
             ("home side" if request["team_id"] == "HOME" else "away side", own_shots),
             "home_shots" if request["team_id"] == "HOME" else "away_shots", own_shots, cited),
            ("interpretation",
             "The side kept recovering the ball high and shooting quickly inside this window. "
             "That is an observed pattern, not evidence about the opponent's condition, "
             "intent or any coaching instruction.",
             None, None, cited),
        ]

    for index, (kind, text, key, value, ids) in enumerate(texts, start=1):
        claims.append({"claim_id": "C%d" % index, "kind": kind, "text": text,
                       "metric_key": key, "metric_value": value,
                       "evidence_event_ids": list(dict.fromkeys(ids))})

    # Say what the frozen 15-second metric cannot: a recovery that paid off later in the
    # same move. Without this the card ignores the only goal in the shipped fixture. It is
    # an interpretation claim, not a metric, and it states no invented number.
    later = [c for c in chains if c["sustained_shots"] and not c["linked_shots"]]
    if later:
        chain = later[0]
        text = ("其中一次夺回没有在 %d 秒内直接形成射门，但后续同一波进攻最终完成了射门或进球。"
                % LINKED_SHOT_HORIZON_SEC if request["language"] == "zh" else
                "One of those recoveries did not produce a shot within %d seconds, but the "
                "same move did end in a shot or a goal later on." % LINKED_SHOT_HORIZON_SEC)
        claims.append({"claim_id": "C%d" % (len(claims) + 1), "kind": "interpretation",
                       "text": text, "metric_key": None, "metric_value": None,
                       "evidence_event_ids": list(dict.fromkeys(chain["evidence_event_ids"]))})
    return claims


def rule_narratives(request, metrics):
    if request["language"] == "zh":
        return {
            "casual": "这段时间主队在对方半场反复抢下球，很快就形成了射门。",
            "analyst": "本窗口记录到 %d 次前场高位夺回，其中 %d 次在 %d 秒内形成射门；"
                       "持球时间为 %d 秒对 %d 秒。以上都是可复核的计数，不含因果判断。"
                       % (metrics["high_recoveries"], metrics["linked_shots"],
                          LINKED_SHOT_HORIZON_SEC, metrics["home_possession_seconds"],
                          metrics["away_possession_seconds"]),
        }
    side = "home side" if request["team_id"] == "HOME" else "away side"
    return {
        "casual": "The %s kept winning the ball high up the pitch and turning it into shots."
                  % side,
        "analyst": "This window records %d high recoveries, %d of which produced a shot within "
                   "%d seconds, with possession %d seconds to %d seconds. These are auditable "
                   "counts and not a causal explanation."
                   % (metrics["high_recoveries"], metrics["linked_shots"], LINKED_SHOT_HORIZON_SEC,
                      metrics["home_possession_seconds"], metrics["away_possession_seconds"]),
    }


def _rejected(request, code, message, retryable, traces):
    return {"task_id": request["task_id"], "replay_id": request["replay_id"],
            "run_id": request["run_id"], "status": "rejected", "insight": None,
            "traces": traces,
            "error": {"code": code, "message": message, "retryable": retryable}}


def rule_result(request, *, reason="no_model", traces=None, rejected_claims=None):
    """Build a contract-valid rule_fallback AnalysisResult. Never raises for valid input."""
    traces = list(traces or [])
    metrics = request["metrics"]
    if any(key not in metrics for key in METRIC_KEYS):
        return _rejected(request, "INVALID_REQUEST",
                         "Request metrics are incomplete; refusing to narrate a partial window.",
                         False, traces)

    # Refuse to narrate numbers the window's own events contradict, even though the
    # schema accepts them. This is the difference between an honest fallback and a
    # convincing lie.
    inconsistent = consistency_issues(request)
    if inconsistent:
        return _rejected(request, "INVALID_REQUEST",
                         "Request metrics contradict the supplied events: "
                         + "; ".join(inconsistent) + ". Refusing to explain.",
                         False, traces)

    chains = recovery_chains(request)
    evidence = _evidence(request, chains)
    if not evidence:
        return _rejected(request, "INVALID_REQUEST",
                         "No usable evidence inside the window; refusing to explain.",
                         False, traces)

    claims = rule_claims(request, chains, evidence)
    narratives = rule_narratives(request, metrics)
    code, message, retryable = _FALLBACK_ERRORS.get(reason, _FALLBACK_ERRORS["no_model"])
    traces.append({"task_id": request["task_id"], "agent": "validator",
                   "status": "fallback", "duration_ms": 0,
                   "note": "Deterministic rule fallback (" + reason + "). No model was called."})
    insight = {
        "insight_id": "INS-" + request["task_id"],
        "match_id": request["match_id"],
        "window": dict(request["window"]),
        "type": request["type"],
        "team_id": request["team_id"],
        "metrics": dict(metrics),
        "evidence_event_ids": evidence,
        "claims": claims,
        "narratives": narratives,
        "verification": {"status": "fallback", "method": "code_only",
                         "rejected_claims": list(rejected_claims or [])},
        "generation": {"mode": "rule_fallback", "provider": "none", "model": None},
        "display": {"title": _TITLES.get(request["language"], _TITLES["en"]), "priority": 1},
    }
    return {"task_id": request["task_id"], "replay_id": request["replay_id"],
            "run_id": request["run_id"], "status": "fallback", "insight": insight,
            "traces": traces,
            "error": {"code": code, "message": message, "retryable": retryable}}
