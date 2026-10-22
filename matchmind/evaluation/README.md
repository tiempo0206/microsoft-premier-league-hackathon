# Role C evaluation

Twelve windows over the shipped synthetic fixture, run twice: once through the
three-agent product pipeline, once through a deliberately weaker single agent. Both
modes share the same input, the same model (`deepseek-flash`, thinking disabled) and the
same deterministic verifier, so the only variable is orchestration.

Reproduce (billable, opt in explicitly):

```
python -m evaluation.benchmark                  # all 12 windows, both modes
python -m evaluation.benchmark --cases positive
python -m evaluation.benchmark --mode single
```

Machine-readable reports land in `.artifacts/evaluation/` (git-ignored). This file records
the sanitised result of the run described below.

## Case design

The fixture contains **exactly one window that fires the frozen high-press detector**
(1500-1650, `high_recoveries >= 3` and `linked_shots >= 2`). "Four positive cases" is
therefore not physically available, and labelling three non-triggering windows as
positives would have inflated the pass rate. The groups state what each case can actually
prove:

| group | n | what it tests |
| --- | --- | --- |
| `positive` | 2 | the triggering window, English and Chinese |
| `non_trigger` | 4 | valid windows the detector does not fire on; the card must stay honest |
| `negative` | 2 | the team asked about never recovered high at all |
| `tampered` | 4 | metrics inflated, or an event moved outside the window |

## Result — 2026-10-22, `deepseek-flash`, prompt `c3-1.1.0`

| group | cases | passed | fallback | rejected | model calls |
| --- | --- | --- | --- | --- | --- |
| positive | 2 | 2 | 0 | 0 | 11 |
| non_trigger | 4 | 3 | 1 | 0 | 19 |
| negative | 2 | 2 | 0 | 0 | 10 |
| tampered | 4 | 0 | 0 | 4 | **0** |

Overall: **7 published cards, 1 honest fallback, 4 correct refusals**. The arithmetic gate
refused every tampered window with **zero** model calls, i.e. the cheapest and most
certain check in the system runs first.

## Three agents vs one agent

| | three agents | single agent |
| --- | --- | --- |
| model calls, 12 windows | 40 | 12 |
| median latency | 10 484 ms | 3 781 ms |
| claims the verifier refused | 5 | 8 |
| windows whose prose failed verification | 4 | 7 |
| can be published as `passed` | yes | **no** |

Read this honestly:

* Three agents cost roughly **3.3x the calls and 2.8x the latency**. They are not faster
  and not cheaper.
* They produced **fewer unverifiable claims (5 vs 8)** and **fewer prose failures (4 vs
  7)** on identical input. That is the actual argument for the extra cost, and it is a
  modest one on 12 windows.
* The single agent **cannot ever** be published as `passed`: frozen contract 2.0.0
  requires `verification.method == "agent_and_code"` whenever `generation.mode ==
  "live_model"`, and an agent reviewing its own output is not an independent check. This
  is a structural argument, not a statistical one, and it does not depend on the sample.

Do not claim multi-agent superiority on 12 windows. Quote the sample size.

## What the run found, in order of severity

1. **Chinese narratives could never pass.** The numeric check used a `\w` lookbehind and
   Python's `\w` matches CJK, so `115` inside `时间为115秒` was invisible. Fixed.
2. **Single-character Chinese numerals were read as digits.** `一` in `一次都没射门` and
   `三` in `进攻三区` became 1 and 3, so every Chinese sentence failed the stray-number
   check. Bare Chinese numerals are now accepted when stating a metric value and no longer
   scanned as strays.
3. **Event coordinates were treated as invented numbers.** A good claim says `the recovery
   came at x=78`; 78 is a supplied fact. Event coordinates are now in the allowed set.
   Documented consequence: the stray-number check is looser, which is one reason the
   auditor agent still exists.
4. **A metric of zero was written without a digit.** `took no shots` and `没有完成任何射门`
   are correct English and Chinese and were rejected for not containing `0`. Zero now has
   its own vocabulary.
5. **The auditor rejected nearly every interpretation claim.** Root cause was a real
   overreach: `each of those recoveries produced a shot` against 3 recoveries and 2 shots.
   Fixed by giving the analyst quantifier rules and telling the auditor to judge overreach
   rather than style.

Items 1-4 are the same class of bug: a verifier that is *too strict* silently disables a
whole language or a whole claim type, and it looks exactly like the model failing.

## Known limits of the measurement

* 12 windows over one fixture is a smoke sample, not evidence of generalisation.
* One model, one provider, one day. Prices and latency move.
* `negative` and `positive` groups have only two members each.
* The single-agent baseline is one prompt written for this comparison; a better single
  prompt would narrow the gap.
* Latency measured on a warm connection during off-peak hours. Peak hours are documented
  as roughly double the price and may be slower.
