"""Token accounting and cost estimation.

Two honesty rules:

1. This is an **estimate** from a published price table, never a bill. Prices change, peak and
   off-peak differ, and only the provider knows what was actually charged. Every surface that
   shows a number from here says "estimated".
2. A cache hit costs nothing, because no request was made. Reporting a hit as a full-price call
   would make the cache look worthless and the cost claim wrong in the safe direction.

Prices below were read from the provider's public page on 2026-10-22 and must be re-checked
before anyone quotes a total in a submission. They are stored per million tokens.
"""
from dataclasses import dataclass, field

# USD per 1,000,000 tokens: (input, output), off-peak.
PRICES_PER_MILLION = {
    "deepseek-flash": {"input": 0.15, "output": 0.60},
    "deepseek-v4-pro": {"input": 0.66, "output": 1.98},
}
# Peak hours are documented as roughly double. We default to peak so an estimate errs high.
PEAK_MULTIPLIER = 2.0
PRICES_READ_ON_DATE = "2026-10-22"


@dataclass
class UsageLedger:
    """Accumulates usage across the model calls of one analysis."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls_billed: int = 0
    calls_cached: int = 0
    unknown_usage_calls: int = 0
    models: set = field(default_factory=set)

    def add(self, usage, model=None, *, cached=False):
        if cached:
            self.calls_cached += 1
            return
        if not isinstance(usage, dict):
            self.unknown_usage_calls += 1
            return
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if not isinstance(prompt, int) or not isinstance(completion, int):
            self.unknown_usage_calls += 1
            return
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += usage.get("total_tokens") or (prompt + completion)
        self.calls_billed += 1
        if model:
            self.models.add(model)

    def rate(self, model, *, peak=True):
        table = PRICES_PER_MILLION.get(model)
        if not table:
            return None
        factor = PEAK_MULTIPLIER if peak else 1.0
        return {"input": table["input"] * factor, "output": table["output"] * factor}

    def estimate_usd(self, *, peak=True):
        """None when we cannot price every call, because a partial total would mislead."""
        if self.unknown_usage_calls:
            return None
        total = 0.0
        if not self.models:
            return 0.0
        for model in self.models:
            rate = self.rate(model, peak=peak)
            if rate is None:
                return None
            total += self.prompt_tokens / 1e6 * rate["input"]
            total += self.completion_tokens / 1e6 * rate["output"]
        return round(total, 6)

    def as_dict(self, *, peak=True):
        estimate = self.estimate_usd(peak=peak)
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls_billed": self.calls_billed,
            "calls_cached": self.calls_cached,
            "unknown_usage_calls": self.unknown_usage_calls,
            "models": sorted(self.models),
            "estimated_usd_peak": estimate,
            "estimate_basis": ("published price table read %s, peak multiplier x%.1f; an "
                               "estimate, not a bill" % (PRICES_READ_ON_DATE, PEAK_MULTIPLIER)),
        }


def describe(ledger):
    """One line for a trace note. Empty when there is nothing honest to say."""
    data = ledger.as_dict()
    if not data["calls_billed"] and not data["calls_cached"]:
        return ""
    parts = ["%d model call(s), %d prompt + %d completion tokens"
             % (data["calls_billed"], data["prompt_tokens"], data["completion_tokens"])]
    if data["calls_cached"]:
        parts.append("%d served from cache" % data["calls_cached"])
    if data["estimated_usd_peak"] is not None:
        parts.append("estimated $%.6f at peak rates" % data["estimated_usd_peak"])
    else:
        parts.append("cost not estimated (usage unavailable or model unpriced)")
    return "; ".join(parts)
