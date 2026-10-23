# Live-model evidence

One file: `live-run-2026-10-23-framework.json`. It exists because `docs/05_acceptance.md` P0
criterion 5 asks for it — *"真实模型至少完成一次实际解释与审核流程，保留经过脱敏的模型和耗时证据"* — and
because "we called a real model" is the kind of claim that a judge should be able to check without
trusting anybody.

## What it shows

| field | value | why it matters |
| --- | --- | --- |
| `result.generation.mode` | `live_model` | not a fallback, not precomputed. The three-valued label is the whole honesty scheme |
| `result.generation.model` | `deepseek-flash` | the model that actually answered |
| `result.verification.method` | `agent_and_code` | the frozen contract only permits `passed` for `live_model` when an agent **and** code both reviewed the card |
| `result.verification.status` | `passed` | so this card is a genuinely verified one, not a decorated fallback |
| `result.agent_invocations` | `3` | analyst → narrator → auditor, one call each, from the trace |
| `result.traces[0].note` | `orchestrator=agent_framework` | Microsoft Agent Framework was the path that ran; this is the record the acceptance criterion asks for |
| `elapsed_ms` | `6860` | wall clock for the whole pipeline, measured on this machine |
| `contract` / `publishable` | `contract_valid` / `true` | the shared `check_result` and `can_publish` both accept it |
| `provenance` | git head, prompt version `c3-1.3.0`, contract `2.0.0` | enough to tell whether a later reader is looking at a stale record |

## What it does not show

* **It is not a benchmark.** n = 1. It says a live path works and produces a publishable card; it
  says nothing about accuracy, reliability or how often it works. Those live in
  `evaluation/README.md` §1–§5, with their own sample sizes and caveats.
* **It is not a cloud test.** Everything here ran on a development machine against
  `api.deepseek.com`. `AI_RULES.md` and `docs/05_acceptance.md` both say a mainland model endpoint
  must be re-tested from the actual host, and no document in this repository claims that happened.
* **`model_calls_direct_provider` reads 0, and that is correct.** The Agent Framework orchestrator
  calls the model through its own client, so `ChatCompletionsProvider.calls` is never incremented.
  The field is named for the counter it is, the note next to it says so, and
  `result.agent_invocations` is the number that actually counts. An earlier draft printed a bare
  `model_calls: 0` beside a `live_model` card, which would have read like "no model was called" —
  that is the kind of honest field that is worse than no field, so it was fixed rather than kept.
* **`usage_line` is empty on this path** for the same reason. Token counts and cost for a framework
  run are not measured here; do not quote a cost for this file.

## How it was produced

```
$env:MATCHMIND_ORCHESTRATOR="framework"
.\.venv\Scripts\python.exe -m evaluation.live_smoke --record live-run-2026-10-23-framework.json
```

`evaluation/live_smoke.py` **refuses to write** the file if a key-shaped string or the configured key
appears anywhere in the payload. It does not scrub and save: a scrubbed file is one whose provenance
nobody can vouch for. `tests/ai/test_live_evidence.py` re-checks every committed file in this
directory for the same thing, so a hand-edited record cannot slip a credential in.

Cost of the run: well under one cent on `deepseek-flash`. It is billable, so it is never part of the
test suite — the tests only read the file.
