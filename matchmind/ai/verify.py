"""Deterministic claim and narrative verification.

This module is the 'code' half of `agent_and_code`. It never calls a model. It is the
only thing allowed to decide that a number in an explanation is the number the backend
computed, and that a sentence did not smuggle in a cause the window cannot support.

A schema validator cannot do this job, which is why it lives here as an explicit,
testable gate instead of a prompt instruction.
"""
import re

METRIC_KEYS = ("high_recoveries", "linked_shots", "window_seconds",
               "home_possession_seconds", "away_possession_seconds",
               "home_shots", "away_shots")

# The frozen heuristic in docs/02_contract.md: a linked shot arrives within 15s.
LINKED_SHOT_HORIZON_SEC = 15

# Phrases that assert a cause the event window does not contain. Case-insensitive.
UNSUPPORTED_INFERENCE = (
    "fatigue", "fatigued", "tired", "exhausted", "tiring",
    "intentionally", "deliberately", "on purpose",
    "coaching decision", "coach decided", "manager decided", "instructed",
    "tactical instruction", "changed formation because",
    "motivated by", "lost confidence", "nervous", "gave up",
)

_NUMBER = re.compile(r"(?<![0-9A-Za-z_.-])(\d+(?:\.\d+)?)(?![0-9A-Za-z_-])")
# NOTE the character classes are explicit ASCII rather than \w / \b. Python's \w matches
# CJK ideographs, so a \w-based lookbehind refuses to see the 115 in "时间为115秒" and
# every Chinese narrative fails numeric verification for no real reason. Explicitly ASCII
# keeps Asian-language prose readable while still ignoring ids such as MM-DEMO-01-E007,
# which are stripped by _ID_TOKEN first anyway.
# Event ids and ids such as MM-DEMO-01-E007 must not be read as numbers.
_ID_TOKEN = re.compile(r"\b[A-Za-z]+[A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b")
_WORD_NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty".split())}
_WORD_NUMBERS["thirty"] = 30
_WORD_NUMBERS["forty"] = 40
_WORD_NUMBERS["fifty"] = 50
_ZH_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_ZH_COMPOUND = re.compile(r"([一二两三四五六七八九])?十([一二三四五六七八九])?")
_ZH_SINGLE = re.compile(r"[零一二三四五六七八九两]")


def allowed_numbers(request):
    """Every number an explanation in this window is allowed to state."""
    values = {float(v) for v in request["metrics"].values()}
    values.add(float(LINKED_SHOT_HORIZON_SEC))
    values.add(float(request["window"]["start_sec"]))
    values.add(float(request["window"]["end_sec"]))
    return values


def numbers_in(text):
    """Digits, English number words and 1-99 Chinese numerals found in the text.

    Documented limitation: only Chinese compounds of the form 十, X十, 十Y and X十Y
    are recognised. A sentence that spells a number in some other scheme is not caught
    by this check, which is one reason the auditor agent still exists.
    """
    found = set()
    for token in _NUMBER.findall(_ID_TOKEN.sub(" ", text)):
        try:
            found.add(float(token))
        except ValueError:
            pass
    lowered = _ID_TOKEN.sub(" ", text).lower()
    for word, value in _WORD_NUMBERS.items():
        if re.search(r"\b" + word + r"\b", lowered):
            found.add(float(value))
    for match in _ZH_COMPOUND.finditer(text):
        tens, ones = match.group(1), match.group(2)
        found.add(float((_ZH_DIGITS.get(tens, 1) * 10) + _ZH_DIGITS.get(ones, 0)))
    for char in _ZH_SINGLE.findall(_ZH_COMPOUND.sub(" ", text)):
        found.add(float(_ZH_DIGITS[char]))
    return found


_ZERO_EXPRESSIONS = ("zero", "none", "no shots", "no shot", "not a single", "without a shot",
                     "without any", "never", "未", "没", "无", "零")


def states_value(text, value):
    """Does `text` actually state this metric value?

    The digit must appear, because that is what catches "made 4 recoveries" against a
    verified value of 3. But a claim about a count of ZERO is naturally written as "took
    no shots" or "没有完成任何射门", and demanding a literal 0 there rejected correct
    sentences in both languages. Zero gets its own vocabulary.
    """
    if value in numbers_in(text):
        return True
    if value == 0:
        lowered = text.lower()
        return any(phrase in lowered for phrase in _ZERO_EXPRESSIONS)
    return False


def unsupported_phrases(text):
    lowered = " " + text.lower() + " "
    return [phrase for phrase in UNSUPPORTED_INFERENCE if phrase in lowered]


def stray_numbers(text, request):
    allowed = allowed_numbers(request)
    return sorted(n for n in numbers_in(text) if n not in allowed)


def _claim_evidence(claim):
    values = claim.get("evidence_event_ids")
    return values if isinstance(values, list) else []


def check_claims(raw_claims, request):
    """Return (approved claims, rejected claim ids, issues).

    A rejected claim is dropped rather than repaired: repairing would mean inventing a
    fact, and the fallback path already exists for the case where nothing survives.
    """
    event_ids = {e["event_id"] for e in request["events"]}
    metrics = request["metrics"]
    approved, rejected, issues = [], [], []
    if not isinstance(raw_claims, list) or not raw_claims:
        return [], [], ["no claims returned"]
    for index, claim in enumerate(raw_claims):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "C%d" % (index + 1))
        kind = claim.get("kind")
        text = claim.get("text")
        evidence = _claim_evidence(claim)
        problems = []
        if kind not in ("metric", "interpretation"):
            problems.append("unknown claim kind")
        if not isinstance(text, str) or not text.strip():
            problems.append("empty claim text")
        if not evidence:
            problems.append("claim cites no evidence")
        elif not set(evidence) <= event_ids:
            problems.append("claim cites an event outside the window")
        if kind == "metric":
            key = claim.get("metric_key")
            if key not in metrics:
                problems.append("unknown metric key")
            elif claim.get("metric_value") != metrics[key]:
                problems.append("metric value does not equal the computed value")
            elif not states_value(text or "", metrics[key]):
                problems.append("metric value is not stated in the claim text")
        elif kind == "interpretation":
            if claim.get("metric_key") is not None or claim.get("metric_value") is not None:
                problems.append("interpretation must not carry a numeric fact")
            if text:
                stray = stray_numbers(text, request)
                if stray:
                    problems.append("interpretation states unsupported numbers: "
                                    + ", ".join("%g" % n for n in stray))
                phrases = unsupported_phrases(text)
                if phrases:
                    problems.append("interpretation asserts an unsupported cause: "
                                    + ", ".join(phrases))
        if problems:
            rejected.append(claim_id)
            issues.extend(claim_id + ": " + problem for problem in problems)
            continue
        approved.append({
            "claim_id": claim_id,
            "kind": kind,
            "text": text.strip(),
            "metric_key": claim.get("metric_key") if kind == "metric" else None,
            "metric_value": claim.get("metric_value") if kind == "metric" else None,
            "evidence_event_ids": list(dict.fromkeys(evidence)),
        })
    if not any(c["kind"] == "metric" for c in approved):
        issues.append("no metric claim survived verification")
    return approved, rejected, issues


def check_narratives(raw, request, claims):
    """Return (narratives or None, issues). Narratives may not add facts."""
    if not isinstance(raw, dict):
        return None, ["narrator returned a non-object"]
    claim_text = " ".join(c["text"] for c in claims)
    issues = []
    for key in ("casual", "analyst"):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append("missing narrative: " + key)
            continue
        stray = stray_numbers(value, request)
        if stray:
            issues.append("%s states unsupported numbers: %s"
                          % (key, ", ".join("%g" % n for n in stray)))
        phrases = unsupported_phrases(value)
        if phrases:
            issues.append("%s asserts an unsupported cause: %s" % (key, ", ".join(phrases)))
        if any(event_id in value for event_id in (e["event_id"] for e in request["events"])):
            issues.append(key + " leaks raw event ids instead of readable text")
    if claim_text and not any(word in claim_text.lower() for word in (" ", )):
        issues.append("claims are empty")
    if issues:
        return None, issues
    return {"casual": raw["casual"].strip(), "analyst": raw["analyst"].strip()}, []


def insight_evidence(claims):
    """Union of approved claim evidence, order preserving, at least one id."""
    seen = list(dict.fromkeys(eid for claim in claims for eid in claim["evidence_event_ids"]))
    return seen


def high_press_chains(request):
    """The frozen high-press heuristic, recomputed from the handed-over events.

    The single implementation used both to pick evidence and to cross-check the metrics
    the backend supplied. Two implementations would eventually disagree, and the one
    that disagreed silently would be the one writing the explanation.
    """
    team = request["team_id"]
    attacks_right = team == "HOME"          # frozen convention: HOME attacks right
    events = request["events"]
    chains = []
    for recovery in events:
        if recovery["type"] != "recovery" or recovery["team_id"] != team:
            continue
        x = recovery["position"]["x"] if attacks_right else 100 - recovery["position"]["x"]
        if x < 66.67:
            continue
        following = [e for e in events
                     if e["team_id"] == team
                     and e.get("possession_id") == recovery.get("possession_id")
                     and 0 < e["timestamp_sec"] - recovery["timestamp_sec"] <= LINKED_SHOT_HORIZON_SEC]
        chains.append({
            "recovery_event_id": recovery["event_id"],
            "timestamp_sec": recovery["timestamp_sec"],
            "possession_id": recovery.get("possession_id"),
            "linked_shots": [e["event_id"] for e in following if e["type"] == "shot"],
            "evidence_event_ids": [recovery["event_id"], *[e["event_id"] for e in following]],
        })
    return chains


def consistency_issues(request):
    """Refuse to explain a window whose own metrics contradict its own events.

    A schema validator only proves shape. This proves the arithmetic: if the supplied
    `high_recoveries` does not equal the recoveries actually present, every sentence
    built on it would state a number the evidence contradicts. Role C's rule is to
    reject such a window rather than narrate it.

    Documented limits, deliberately not guessed at here:
    * possession_seconds needs Match.initial_possession_team, which AnalysisRequest does
      not carry, so it is not cross-checked.
    * the strict chain check applies to type "high_press"; other detector types in the
      frozen enum are not implemented for P0 and are only checked for shot counts.
    """
    metrics = request["metrics"]
    events = request["events"]
    issues = []
    home_shots = sum(1 for e in events if e["type"] == "shot" and e["team_id"] == "HOME")
    away_shots = sum(1 for e in events if e["type"] == "shot" and e["team_id"] == "AWAY")
    if metrics["home_shots"] != home_shots:
        issues.append("home_shots=%d but the window contains %d"
                      % (metrics["home_shots"], home_shots))
    if metrics["away_shots"] != away_shots:
        issues.append("away_shots=%d but the window contains %d"
                      % (metrics["away_shots"], away_shots))
    window = request["window"]
    if metrics["window_seconds"] != window["end_sec"] - window["start_sec"]:
        issues.append("window_seconds does not match the window")
    if request["type"] == "high_press":
        chains = high_press_chains(request)
        if metrics["high_recoveries"] != len(chains):
            issues.append("high_recoveries=%d but the window contains %d"
                          % (metrics["high_recoveries"], len(chains)))
        linked = sum(1 for chain in chains if chain["linked_shots"])
        if metrics["linked_shots"] != linked:
            issues.append("linked_shots=%d but the window contains %d"
                          % (metrics["linked_shots"], linked))
    return issues
