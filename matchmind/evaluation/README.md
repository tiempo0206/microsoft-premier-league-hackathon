# Role C evaluation suite

Five harnesses, each answering a different question. Every number below was produced by
running the code in this directory on 2026-10-22/23 against `deepseek-flash` with thinking
disabled, prompt `c3-1.1.0`. Reproduce any of them; none require Azure or Foundry.

| harness | question it answers | cost |
| --- | --- | --- |
| `benchmark.py` | does the pipeline publish correct cards, and how does one agent compare with three? `--auto-cases` derives the sample from any fixture | billable |
| `factcheck_bench.py` | how many known-bad explanations does the code verifier catch, and how many good ones does it wrongly reject? | free |
| `auditor_calibration.py` | both halves of the auditor: does it reject honest cards, and does it catch overreach the code gate cannot see? `--plan` runs the corpus against the gate with no model calls | billable (`--plan` free) |
| `ablation.py` | what breaks when each specialist is switched off? (`--repeats 3` for an interpretable run) | billable |
| `live_smoke.py` | one real end-to-end run with the raw output of every agent | billable |
| `fixture_qualify.py` | is the synthetic data dense and complete enough to carry a demo? (`--recommend` finds a window that can explain an outcome) | free |
| `dense_fixture_proposal.py` | are those thresholds actually reachable? (`--minutes 45` for a half that also supports expected threat) | free |
| `scan_competitors.py` / `fetch_readmes.py` | what is the field shipping? see [`research/README.md`](research/README.md) | free |
| `scan_football_oss.py` | which open football projects and datasets can we legally reuse? | free |
| `real_data_calibration.py` | does the synthetic clip behave like real football? compares it against Role B's five-minute real-match sample | free |

Two documents sit alongside them for the submission:

* [`PLAN_REVIEW.md`](PLAN_REVIEW.md) — the critical assessment, the 13 borrowed ideas, the gaps.
* [`SUBMISSION_POSITIONING.md`](SUBMISSION_POSITIONING.md) — what we may claim per criterion, and
  the sentences the submission must not contain.
* [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — a 110-second shot list built only from things that exist.
* [`CONTRACT_2_1_PROPOSAL.md`](CONTRACT_2_1_PROPOSAL.md) — the one reviewable contract bump.
* [`evidence/`](evidence/README.md) — a committed, credential-free record of one real model run, for
  acceptance criterion 5. Evidence that the live path works, not a benchmark: n = 1.

The critical assessment of the whole plan, including the borrowed ideas and the gaps,
is in [`PLAN_REVIEW.md`](PLAN_REVIEW.md).

---

## 1. The verifier: 21/21 caught, 0/4 false alarms

`python -m evaluation.factcheck_bench` exercises `ai/verify.py` directly with 22 controlled
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
| Chinese requested, English prose | yes |
| English requested, Chinese prose | yes |
| a `high_recoveries` claim citing only a shot | yes |
| a `linked_shots` claim citing only passes | yes |
| universal quantifier ("each of the three") when only two did | **no — auditor's job** |

Four of those classes were added after real defects rather than for symmetry: the language pair
after a Chinese request came back in English, and the evidence-type pair after noticing that a claim
could cite a plausible-looking id of the wrong type. A metric of ZERO is exempt from the
evidence-type rule, because "took no shots" has no shot event to cite and its honest evidence is
whatever did happen — that exemption exists because the first version of the check rejected correct
cards.

The last row is the honest gap and it is why the auditor agent exists: a regex cannot tell
"two of three" from "three of three". The bench marks it `must_be_caught: false` rather than
quietly counting it as a pass.

**Caveat that must travel with this number** (the same one a rival project states about its
own equivalent): the corruptions are the kinds the verifier was built to catch, so the
figure shows the checks work, not how accurate a model is.

---

## 1a. The semantic auditor, measured in both directions

The code verifier is measured by §1 at zero cost. The auditor is a model, so it needs real calls.
One number is not enough, because a model that rejects everything scores perfectly on one half:

| corpus (all pass the code gate unchanged) | cases | runs | result |
| --- | --- | --- | --- |
| honest cards — only supplied numbers, no causal claim | 3 | 15 | **15/15 approved → 0.0% false alarms** |
| rigged cards — right arithmetic, wrong claim | 10 | 50 | **50/50 caught → 0.0% misses** |
| — of which the rejection **named the planted claim** | 10 | 50 | **50/50 → 0.0% caught for the wrong reason** |
| combined correct decisions | 13 | 65 | **100.0%** |

The ten rigged cards are the classes the arithmetic layer cannot see at all. Every one of them
passes `check_claims` and `check_narratives` untouched — that is asserted by
`tests/ai/test_auditor_calibration.py`, so if the gate ever starts catching one, the corpus has to
be re-drawn rather than silently counted as an auditor win:

| class | example |
| --- | --- |
| contradicts data | "HOME controlled the ball for most of the window" (35 s to 115 s) |
| correct value, wrong team | `home_shots = 2` stated as "AWAY took 2 shots" |
| universal negative | "AWAY never won the ball back" (they did, twice) |
| quantifier overreach | "each of those recoveries turned into a shot" (two of three) |
| superlative needing the whole match | "the most intense pressing spell of the match" |
| player-level claim, no player data | "the AWAY right-back kept getting caught out of position" |
| mechanism nobody measured | "the press worked because AWAY's midfield stopped tracking runners" |
| prediction | "that pattern will decide the rest of the match" |
| counterfactual | "had AWAY turned that possession into a shot, the game would look different" |
| overreach in the prose, not the claims | narrative says "AWAY's shape collapsed once the press arrived" |

**The caveat that must travel with 100%.** The corpus is mine, written from the classes I could
think of, and each case was written to be decidably wrong. A perfect score here means the auditor
catches the overreach I named, on the window I used, on this model — it does **not** bound the
classes I did not think of, and it is not a general accuracy figure. The value of the measurement is
the comparison, not the number: **the code gate catches 21/21 of the corruptions in §1 and 0/10 of
these.** That is the whole argument for a second agent.

Reproduce the corpus check for free (no key, no calls):

```
python -m evaluation.auditor_calibration --plan
```

and the scored run:

```
python -m evaluation.auditor_calibration --runs 5
```

### History: why the previous number was 33.3%

| prompt version | runs | false alarms |
| --- | --- | --- |
| `c3-1.2.0` | 6 | **33.3%** |
| `c3-1.3.0` | 10 | **0.0%** |

The defect was not judgement, it was contradiction: the auditor answered `approved: false` while
its own `issues` text said *"No factual violations found"* and both rejection lists were empty. A
redundant boolean the model can contradict is not a decision.

The fix removes the flag. The auditor now returns only `rejected_claims`, `narrative_problems` and
`notes`, and **the code derives the decision from the lists**. Notes are recorded and never block.
An explicit `approved: false` with nothing named is treated as approval and recorded as a
contradiction, because the code gate already verified every number on the card.

This matters beyond tidiness: a constant rejection made the visible correction look staged, and it
cost an extra model call on every card. After the fix, 8 of 11 dense-fixture cards resolve in three
calls and the 3 corrections that do occur name a specific claim.

---

## 1b. Recap consistency across a series — the failure mode no single payload can show

A replay does not publish one recap, it publishes one every few minutes, and the viewer sees the
series. Every payload can pass its own validator and the series can still contradict itself:

* a cumulative counter **goes down** as the clip advances, which can only mean a recap read the
  wrong slice of events or a stale fixture;
* the **same goal is credited to a different player** in two recaps;
* the clock goes backwards, or two recaps cover the same window and disagree about it;
* a card-based recap includes a card from another match, or drops one that aired.

`ai.recap.recap_series_issues()` sorts the payloads by cutoff itself, validates each one, then
compares. It is deterministic and free — the same class of check as the code gate, applied to two
payloads at once instead of one. `recap_from_insights_issues()` does the same for the card-based
path, which previously derived its own cutoff from the cards and therefore could not notice that a
card belonged to another match or that two cards overlapped.

```
python -m ai.recap --series 1550 1650 1800
```

Pinned by `tests/ai/test_recap.py::SeriesConsistencyTests` and
`::CardBasedRecapConsistencyTests`, including the negative direction: a counter that only grows
must **not** be flagged, or the check would be useless noise.

---

## 1c. Is the synthetic clip realistic? Measured against one real match

Role B delivered a real match — Arsenal 4–3 Leicester City, 2017-08-11 — as a research package under
`data/extra/real-history-wyscout`: 1,768 events for the full game plus the 96 events of the first-half
window 25:00–30:00, CC BY 4.0, hash-verified. It is **not** a runtime fixture and cannot become one:
the frozen contract requires `synthetic: true`, and the official rules require synthetic data.

So it is used for what it can support: **calibration**. `evaluation/real_data_calibration.py` puts the
real five minutes and our synthetic five minutes side by side on the only metrics that survive the
vocabulary gap, with the tolerances fixed before the numbers were looked at.

| metric, same 300 s window | real sample | synthetic (shipped) | synthetic (dense proposal) |
| --- | --- | --- | --- |
| events | 96 | 30 | 110 |
| **seconds per event** | **3.12** | **10.0** | **2.73** |
| passes | 59 | 18 | 94 |
| pass share | 61.5% | 60.0% | 85.5% |
| shots per 10 min | 8.0 | 10.0 | 20.0 |
| passes starting in the final third | 28.8% | 33.3% | 18.1% |
| median gap between events | 1.9 s | 10.0 s | 2.0 s |

**What this says, in order of importance:**

1. **The shipped clip's composition is realistic; its density is not.** Pass share is within 2.4% of
   real football and the final-third share within 15.6%. It is 3.2× too sparse, which is exactly what
   `fixture_qualify.py` already failed it on — now confirmed against a real match instead of against a
   threshold we invented. That threshold was ≤ 3.0 s per event; the real sample runs at 3.12. It was
   picked from football intuition before this data existed and lands within 4% of it.
2. **The dense proposal fixes density and overshoots composition.** It is within 12.5% on density —
   the problem it was built to solve — but 39% too pass-heavy and **150% too shot-heavy**. A demo
   built on it would look busy in a way real football does not. If it is adopted, the generator needs
   its pass and shot rates pulled down, not just its event count raised.
3. **Four of the eight comparisons are out of range, and they are listed as such.** The harness prints
   the failures before the passes, because a table where everything is green is the one nobody checks.

**What it refuses to compute**, and why: `high_recoveries`, `linked_shots`, `sustained_control`, the
3-recovery/2-shot trigger, and pass completion. Wyscout's sample has no `possession_id` and no
attribution of who won a duel, so every one of those would have to be invented — and inventing them is
precisely what the metric is supposed to detect. The refusals print with the report and are pinned by
`tests/ai/test_real_data_calibration.py`.

**Caveats that travel with the table:** it is one match, one five-minute window; Wyscout's `Shot` class
is wider than ours; the coordinate comparison assumes Wyscout's x runs in the attacking direction (if
that is wrong, the coordinate rows fail and the density rows stand); and the real sample is CC BY 4.0,
not our CC0 synthetic data, so nothing from it is redistributed as ours.

---

## 2. Product evaluation — and why the sample size was the problem

The old case set was hand-written against one 300-second fixture, which caps the whole evaluation at
the one non-overlapping window that fixture can fire. `--auto-cases` removes the cap: cases are
derived by scanning every window of any fixture, and positives must not overlap so three overlapping
windows cannot masquerade as three samples.

| fixture | span | cases | positives | non-trigger | negatives | tampered |
| --- | --- | --- | --- | --- | --- | --- |
| `data/extra/validated-demo` | 300 s | 7 | **1** | 1 | 1 | 4 |
| `dense-half` (generated into `.artifacts/`) | 2 700 s | 15 | **5** | 4 | 2 | 4 |

Result on the dense half:

| group | passed | fallback | rejected | agent calls |
| --- | --- | --- | --- | --- |
| positive | **5 / 5** | 0 | 0 | 15 |
| non_trigger | **4 / 4** | 0 | 0 | 16 |
| negative | **2 / 2** | 0 | 0 | 8 |
| tampered | 0 | 0 | **4 / 4** | **0** |

**All 11 valid windows published, zero fallbacks, zero contract violations**, median 7.7 s, 39 agent
calls. Eight of the eleven resolved in three calls, so the auditor approved the first draft; the
other three were genuinely corrected. On the shipped fixture the single positive window passes in
some runs and falls back in others — that variance *is* the narrow-sample problem, and it is why the
dense fixture exists rather than evidence that the pipeline is broken.

Reproduce:

```
python -m evaluation.dense_fixture_proposal --minutes 45 --out .artifacts/dense-half
python -m evaluation.benchmark --auto-cases --data-dir .artifacts/dense-half
```

Four defects surfaced the moment this larger sample ran, all now fixed:

1. Metric definitions were absent from the facts block, so the auditor correctly rejected "followed
   by a shot within 15 seconds" as unsupported. The definitions now travel with the facts.
2. Adding them introduced numbers (66.67, 15) that were not in the allowed set, so the narrator was
   rejected for repeating a fact it had just been given. Allowed numbers are now derived from the
   definitions, and an invariant test asserts the property.
3. A narrator formatting failure consumed the auditor correction budget, so a later semantic
   objection had none left. The two budgets are now separate.
4. The auditor asserted `approved: false` while its own reasoning said "no factual violations
   found" and its rejection lists were empty — about a third of runs, on cards the code gate had
   already accepted. See §1a.

## 3. Three agents vs one agent

Both modes get the same input, the same model and the same deterministic verifier. The baseline's
prompt was rewritten to carry the **same rules** the analyst and narrator receive — the metric
definitions, the quantifier rules, the worked example of an overreach, and the two-audience
requirement — so the comparison is about orchestration and not about which prompt was written better.
An earlier baseline used a shorter prompt, which flattered the pipeline.

| | three agents | single agent |
| --- | --- | --- |
| agent invocations, 15 windows | 42–45 | 15 |
| median latency | 7.7–8.4 s | 4.8 s |
| windows whose raw output failed the verifier | **0 published unverified** | **5 of 15 (33%)** |
| publishable as `passed` | yes | **no** |

**Read this carefully, because two of the obvious metrics are traps.**

`claims_rejected` is **not** comparable across modes: it counts every rejection during a run,
including the ones the pipeline then corrects. A higher number for the pipeline means more
correction activity, not worse output — the pipeline rejects more because it has a second pair of
eyes and a repair step. The fair question is whether the *final* card is verified, and for the
pipeline the answer is yes by construction: nothing publishes without passing the code gate.

What the numbers do support:

* One agent fails the verifier on a third of the windows it is asked about. The pipeline publishes
  those same windows because a rejection inside it is worked on rather than shipped.
* One agent can never carry `passed`. Frozen contract 2.0.0 requires `agent_and_code` for a
  `live_model` card, and an agent reviewing its own output is not an independent check.

What they do **not** support: that three agents are cheaper (they cost 2.8x the calls), faster
(1.7x the latency), or that they fabricate less per attempt. Do not say those things.

The dense-fixture result also moves between runs: two runs published 11 of 11 and 8 of 11 valid
windows. Quote the range and the sample size.

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
These are the numbers after the prompt fixes above, which is why they differ from the earlier run.

| variant | fallback count | per repeat | within-variant spread | cards with a universal claim | median |
| --- | --- | --- | --- | --- | --- |
| `full` | 2 / 18 | 1, 0, 1 | 1 | 11 | 8 203 ms |
| `no_code_gate` | 0 / 18 | 0, 0, 0 | 0 | 12 | 7 922 ms |
| `no_auditor` | 0 / 18 | 0, 0, 0 | 0 | 9 | 7 125 ms |
| **`no_repair`** | **11 / 18** | 3, 3, 5 | 2 | 8 | 5 719 ms |
| `no_tools` | 3 / 18 | 1, 1, 1 | 0 | 9 | 8 469 ms |

Between-variant range of the means is **3.67**, within-variant spread is at most **2**. Exactly one
claim survives the noise test:

> **The repair round is worth about nine extra published cards out of eighteen.** Without it, 11 of
> 18 windows degrade to a rule fallback; with it, 2.

Everything else is inside or barely above the noise. Removing the code gate, the auditor or the tools
changes the fallback count by at most 3, and two of those variants produced *fewer* fallbacks than
the full pipeline, which is the opposite of the expected direction and is most likely variance. **Do
not claim those have a measured effect.**

`published_with_bad_claims` is 0 for every variant, including `no_code_gate`. On clean input the
model rarely fabricates a number, so a live run cannot show what the code gate is for — that is what
§1 measures instead, with controlled corruption. The code gate's value is a property of adversarial
input, not of average input. The auditor's value is measured separately by §1a, because a live run
where the auditor rarely objects cannot show it either.

To go further: more windows, not more repeats. Six windows with one positive window each is the
binding constraint; the dense fixture in §2 is the fix.

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
