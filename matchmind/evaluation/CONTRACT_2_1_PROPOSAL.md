# Proposed contract 2.1.0 — one reviewable bump

Status: **proposal, not applied.** Contract stays `2.0.0` and `python tools/check_frozen.py`
still reports `Frozen contracts and fixtures unchanged`. Written by Role C as integrator.

## Why one bump instead of several

Every item below touches `contract.schema.json`, `contracts/VERSION`, the generated
`types.ts`, the generated `openapi.json` and `frozen.sha256.json`, and every item needs Role A
to render something new. Doing them one at a time would mean five frozen-hash churns and five
rounds of A chasing the backend. `01_three-person-AI-instructions` is explicit: *"不允许在冻结
日前一天加第二套 API"* — so the honest reading is one deliberate batch, reviewed once.

Who must review each item: **A** for anything the viewer renders, **B** for anything the
metrics or endpoints change, **C** to author and merge.

## The items

### 1. `Metrics`: the sustained tier (needs B)

```
+ "sustained_recoveries": {"type": "integer", "minimum": 0}
+ "sustained_shots":      {"type": "integer", "minimum": 0}
```
add both to `Metrics.required` and to the `Claim.metric_key` enum.

**Why.** The frozen `linked_shots` uses a 15-second horizon. In the shipped fixture the third
high recovery is at 1640 and the goal at 1680 — 40 seconds later — so `linked_shots` = 2 and
the goal is invisible to every card. C already computes the 45-second tier in
`ai/verify.high_press_chains` and reports it in the tool layer, but a *metric* the card can
claim needs the schema.

**Cost.** B adds two pure functions next to `window_metrics`. A renders two more chips. C
switches its prose from "context" to a real claim.

**Caveat that must survive review.** Widening this does **not** fix the case that matters most:
the 1640 recovery and the 1680 goal never share a window (see `evaluation/PLAN_REVIEW.md`
§3.2). The real fix is B-side window selection or a bounded look-back. The sustained tier is
only useful once a window contains both.

### 2. `Insight`: storyline continuity (needs A)

```
+ "sequence":       {"type": "integer", "minimum": 1}
+ "continues_from": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]}
```
add both to `Insight.required`.

**Why.** `ai/storyline.py` already implements dedupe, minimum spacing, a hard rate cap and
continuity ("second time in five minutes", "which metrics changed since the last card"), and
it is tested. It cannot be switched on: `Insight` is `additionalProperties: false`, so there is
nowhere legal to put the sequence number, and a frontend that wants to show continuity would
have to invent it. A rival attributes "20 of 28 goals lose their match context" to exactly
this omission.

**Cost.** A renders a "second time" badge and greys out a superseded card. C sets the fields
from the storyline decision.

### 3. `Insight.narratives`: a third audience (needs A)

`narratives` is currently a closed object with `casual` and `analyst` required and
`additionalProperties: false`.

```
+ "broadcast": {"type": "string", "minLength": 1}
```
add to the nested `required` list.

**Why.** Official 4.1(i)(e) asks for personalisation beyond one axis, and 4.1(iii) asks for
recaps suitable for broadcast. C already produces both audiences in a single model call, so a
third costs one short paragraph in the same request; the limitation is purely the schema.

**Risk.** Requiring it makes every existing fixture invalid. Either mark it optional (preferred
for a first bump) or regenerate the examples. C recommends optional-with-fallback-to-casual.

### 4. `Recap` type and endpoint (needs A and B)

```
+ Recap definition: {schema-free payload with facts, narrative{casual,analyst},
                     generation, evidence_event_ids, cutoff_sec}
+ POST /api/v1/replays/{replay_id}/recap -> Recap
```
contract v0.1 had this endpoint; 2.0.0 dropped it and nobody noticed.

**Why.** Official 4.1(iii) asks for "automated match recaps". `ai/recap.py` already produces
the payload, validates it and passes 18 tests, including the property that a 1650 cutoff must
report zero goals. It is the only role that can report the goal at all.

**Cost.** B adds one endpoint that calls a C function with the replay's observed prefix. A adds
a recap block. C supplies the payload and validator.

### 5. `AnalysisRequest.language`: widen the enum (needs C only)

```
- "enum": ["en", "zh"]
+ "enum": ["en", "zh", "es", "fr", "ar"]
```
or drop the enum and validate length only.

**Why.** Official 4.1(vi) asks for multi-language storytelling; a rival ships four languages
including right-to-left Arabic. C's prompts and fallback templates are already
language-parameterised; the enum is the only blocker. Arabic additionally needs RTL layout from
A, so C recommends adding `es` and `fr` now and `ar` with a layout change.

## Suggested order

1. **Item 4** — recap. Highest criterion value, no change to existing metrics, nothing existing
   breaks.
2. **Item 5** — language enum. Trivial, unblocks a scored criterion.
3. **Item 2** — storyline fields. Turns a tested policy into a product feature.
4. **Item 3** — third audience. Cheap once A is already touching the card.
5. **Item 1** — sustained metrics. Do it together with the B-side window change, not before it,
   or it buys nothing.

## What this bump deliberately does not include

* **`Event.type` new values** (`pressure`, `possession_change`). The generator does not produce
  them; adding enum values without data would be a lie-by-schema.
* **A prediction or counterfactual type.** Both are good ideas from rival projects and both need
  a real design before they touch a frozen contract.
* **Anything that changes `ReplaySnapshot` or `StreamMessage`.** Role B's transport is stable
  and has 68 tests; leave it alone this close to submission.

## How to apply it, precisely

```
1. edit contracts/contract.schema.json           (C, with A and B review)
2. edit contracts/VERSION -> 2.1.0               (C)
3. python tools/generate_types.py                (C, regenerates contracts/types.ts)
4. python tools/generate_openapi.py              (C, regenerates contracts/openapi.json)
5. update contracts/frozen.sha256.json           (C, after 3 and 4)
6. update contracts/examples/*.json              (C, keep them contract-valid)
7. python tools/check_frozen.py                  (must pass)
8. python -m pytest tests -q                     (all three roles green)
9. A updates the viewer; B updates metrics/endpoints if items 1 or 4 landed
```

Step 5 is the one people get wrong: updating only the hash to make the check pass hides a real
divergence. The hash must be regenerated **from** regenerated artefacts, never edited by hand.
