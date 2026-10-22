# Role C evaluation suite

Five harnesses, each answering a different question. Every number below was produced by
running the code in this directory on 2026-10-22/23 against `deepseek-flash` with thinking
disabled, prompt `c3-1.1.0`. Reproduce any of them; none require Azure or Foundry.

| harness | question it answers | cost |
| --- | --- | --- |
| `benchmark.py` | does the pipeline publish correct cards on 12 windows, and how does one agent compare with three? | billable |
| `factcheck_bench.py` | how many known-bad explanations does the verifier catch, and how many good ones does it wrongly reject? | free |
| `ablation.py` | what breaks when each specialist is switched off? (`--repeats 3` for an interpretable run) | billable |
| `live_smoke.py` | one real end-to-end run with the raw output of every agent | billable |
| `fixture_qualify.py` | is the synthetic data dense and complete enough to carry a demo? (`--recommend` finds a window that can explain an outcome) | free |
| `dense_fixture_proposal.py` | are those thresholds actually reachable? (generates a qualifying fixture into `.artifacts/`) | free |
| `scan_competitors.py` / `fetch_readmes.py` | what is the field shipping? see [`research/README.md`](research/README.md) | free |

Two documents sit alongside them for the submission:

* [`PLAN_REVIEW.md`](PLAN_REVIEW.md) — the critical assessment, the 13 borrowed ideas, the gaps.
* [`SUBMISSION_POSITIONING.md`](SUBMISSION_POSITIONING.md) — what we may claim per criterion, and
  the sentences the submission must not contain.
* [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — a 110-second shot list built only from things that exist.
* [`CONTRACT_2_1_PROPOSAL.md`](CONTRACT_2_1_PROPOSAL.md) — the one reviewable contract bump.

The critical assessment of the whole plan, including the borrowed ideas and the gaps,
is in [`PLAN_REVIEW.md`](PLAN_REVIEW.md).

---

## 1. The verifier: 17/17 caught, 0/4 false alarms

`python -m evaluation.factcheck_bench` exercises `ai/verify.py` directly with 18 controlled
corruptions and 4 correct explanations, and is pinned by
`tests/ai/test_factcheck_bench.py` so it cannot drift silently.

| corruption | caught |
| --- | --- |
| wrong metric value (says 9, computed 3) | yes |
| metric value never stated in the claim text | yes |
| invented event id | yes |
| real event cited from outside the window | yes |
| claim with no evidence | yes |
| invented metric key | yes |
| empty claim text | yes |
| claim kind outside the enum | yes |
| stray number inside an interpretation | yes |
| unsupported causation (fatigue) | yes |
| interpretation carrying a numeric fact | yes |
| no metric claim survived, only interpretations | yes |
| narrative invents a number | yes |
| narrative leaks a raw event id | yes |
| narrative claims fatigue | yes |
| narrative missing one audience | yes |
| empty prose | yes |
| universal quantifier ("each of the three") when only two did | **no — auditor's job** |

The last row is the honest gap and it is why the auditor agent exists: a regex cannot tell
"two of three" from "three of three". The bench marks it `must_be_caught: false` rather than
quietly counting it as a pass.

**Caveat that must travel with this number** (the same one a rival project states about its
own equivalent): the corruptions are the kinds the verifier was built to catch, so the
figure shows the checks work, not how accurate a model is.

---

## 2. Product evaluation over 12 windows

Case design is constrained by the data: the fixture contains **exactly one window that fires
the frozen high-press detector**, so "four positive cases" is not physically available and
labelling non-triggering windows as positives would inflate the pass rate.

| group | n | what it tests |
| --- | --- | --- |
| `positive` | 2 | the triggering window, English and Chinese |
| `non_trigger` | 4 | valid windows the detector does not fire on |
| `negative` | 2 | the team asked about never recovered high at all |
| `tampered` | 4 | metrics inflated, or an event moved outside the window |

Result, identical for both orchestrators:

| group | passed | fallback | rejected | model calls |
| --- | --- | --- | --- | --- |
| positive | 1 | 1 | 0 | 8 |
| non_trigger | 3 | 1 | 0 | 19 |
| negative | 2 | 0 | 0 | 10 |
| tampered | 0 | 0 | 4 | **0** |

**6 published cards, 2 honest fallbacks, 4 correct refusals, 0 contract violations.** Every
tampered window is refused with **zero** model calls: the arithmetic gate runs before the
model, so the cheapest and most certain check costs nothing.

## 3. Three agents vs one agent

| | three agents | single agent |
| --- | --- | --- |
| agent invocations, 12 windows | 28–40 | 12 |
| median latency | 7.0–11.4 s | 3.8 s |
| claims the verifier refused | 5–9 | 8 |
| windows whose prose failed verification | 4 | 7 |
| publishable as `passed` | yes | **no** |

The single agent is 2–3x cheaper and faster. It produced **more** unverifiable claims and
**more** prose failures on identical input, which is the modest statistical case for the
extra cost. The strong case is structural: frozen contract 2.0.0 requires
`verification.method == "agent_and_code"` whenever `generation.mode == "live_model"`, so an
agent reviewing its own output can never legally emit `passed`. Quote the sample size (12)
whenever you quote this table.

## 4. Orchestrator: Agent Framework vs direct HTTP

`MATCHMIND_ORCHESTRATOR=framework` is the default; the direct path remains a supported
fallback and is used automatically when a caller injects an httpx transport (which is how
tests keep their traffic off the network).

| | Agent Framework (default) | direct Chat Completions |
| --- | --- | --- |
| 12 windows published | 6 | 6 |
| median latency | **7 008 ms** | 9 446 ms |
| agent invocations | 32 | 28 |
| contract violations | 0 | 0 |

Equal quality, about 20–25% faster, slightly more calls. Consistent direction across two
independent full runs and the positive-only run.

## 5. Ablation: one variant is separated, the rest are not

`python -m evaluation.ablation --repeats 3` disables one role at a time over 6 windows × 3
repeats = 18 runs per variant, and scores every published card with the real, unpatched verifier.

| variant | fallback count | per repeat | within-variant spread | cards with a universal claim | median |
| --- | --- | --- | --- | --- | --- |
| `full` | 5 / 18 | 1, 2, 2 | 1 | 10 | 8 109 ms |
| `no_code_gate` | 4 / 18 | 1, 1, 2 | 1 | 6 | 8 046 ms |
| `no_auditor` | 6 / 18 | 2, 2, 2 | 0 | 9 | 8 141 ms |
| **`no_repair`** | **17 / 18** | 6, 6, 5 | 1 | 6 | 5 750 ms |
| `no_tools` | 6 / 18 | 2, 2, 2 | 0 | 6 | 8 094 ms |

Between-variant range of the means is **4.33**, within-variant spread is at most **1**. So exactly
one claim survives the noise test:

> **The repair round is worth about twelve extra published cards out of eighteen.** Without it,
> 17 of 18 windows degrade to a rule fallback instead of 5.

Everything else is inside the noise: removing the code gate, the auditor or the tools changes the
fallback count by at most 2, which is the same size as the run-to-run spread. **Do not claim those
have a measured effect.**

`published_with_bad_claims` is 0 for every variant, including `no_code_gate`. On clean input the
model rarely fabricates a number, so a live run cannot show what the code gate is for — that is
what §1 measures instead, with controlled corruption (17/17 caught, 0/4 false alarms). The code
gate's value is a property of adversarial input, not of average input.

An honest oddity worth keeping: `no_code_gate` produced *fewer* universal-quantifier cards (6) than
the full pipeline (10). The plausible cause is that the repair round, which only runs when
something is rejected, re-narrates and reintroduces generalising wording. Two runs of a small
sample cannot settle that, and the numbers are recorded rather than explained away.

To go further: more windows, not more repeats. Six windows with one positive window each is the
binding constraint.

## 6. Known limits of every number here

* One fixture, one model, one day, one machine. Prices and latency move.
* 12 windows with two positives is a smoke sample, not evidence of generalisation.
* The fixture's own window boundary hides the only goal: the 1640 recovery and the 1680 goal
  fall in different windows, so no card can connect them. Widening the linked-shot horizon
  does not help because the goal is not in the request. Diagnostic and recommendation are in
  `PLAN_REVIEW.md` §3.2.
* Latency measured on a warm connection during off-peak hours; peak is documented at about
  double the price.
* `agent_calls` counts agent invocations from the trace, not HTTP requests. The framework
  path never touches `ChatCompletionsProvider`, so `model_calls` reads 0 there and must not
  be used to compare orchestrators.
