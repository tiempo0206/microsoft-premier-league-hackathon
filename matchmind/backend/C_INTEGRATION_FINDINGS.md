# C compatibility finding for the integrator

**Resolved on main (2026-10-23).** C added `card_evidence` to union every retained
claim's citations into the card evidence. The main handoff records 12/12 normal
requests passing and 3/3 corruptions refused, with zero model calls. This file is
the historical report against `02228b8`; it is no longer an open blocker. Rerun
`python -m deploy.adapter_check` on the release commit to retain the guarantee.

Checked 2026-10-23 against C commit `02228b8` in an isolated Linux image. No C
source was modified, no key was supplied and no model call was made.

## Historical defect: fallback evidence truncation on denser inputs

`ai/fallback.py::_evidence` returns at most 12 IDs. `rule_claims` separately
selects recovery/shot IDs from every chain. A claim can therefore reference a
valid input event that is absent from `Insight.evidence_event_ids`.

The shared `check_result(request, result)` correctly raises
`ValueError: claim evidence mismatch`. B correctly refuses to publish it.

Measured using `backend.showcase.build_packet()` and bare
`await ai.service.analyze(request)`:

| Input group | Result |
| --- | --- |
| press, primary 1500–1650, en/zh | Both fail; `MM-SHOW-PRESS-E042` missing from the Insight evidence |
| delayed, primary 1500–1650, en/zh | Both fail; `MM-SHOW-DELAYED-E041` missing |
| Other eight normal inputs | Shared result validation passes |
| Contradictory count / wrong match / future event | All three refused before any model call |

This is **4 invalid fallback outputs out of 12 normal inputs**, not a live-model
quality score. The input requests themselves pass contract validation and all B
data audits. The small original fixture does not expose this density boundary.

## One-command reproduction after C is present

```text
python -m backend.showcase
python -m deploy.adapter_check --output .artifacts/C-offline-compatibility.json
```

The checker imports C read-only, supplies no provider/config, blocks Python socket
connections and validates every output. It is a trusted-adapter regression check,
not a hostile-code sandbox. It never prints C exception messages or model keys.

C's fix makes the final Insight evidence contain the ordered union of all
retained claim evidence, while retaining valid request-event IDs and the frozen
schema. Do not
weaken `check_result`, remove the third recovery, falsify the metrics, or silently
truncate a retained claim's evidence to get a green result.

Acceptance for C: all 12 normal requests produce contract-valid non-rejected
offline results; all three corruptions are refused; model calls remain zero.
Run C's existing tests and semantic checks separately after the fix.

## Safe adoption policy

- B's original `validated-demo` remains the default. Its baseline metrics and all
  frozen files remain unchanged.
- The release image retains `validated-demo` as its conservative default; C's fix is already in main.
- Enhanced datasets can already be used for B-only data/replay demonstrations.
- `deploy.release_run` checks enhanced integrated datasets against the offline
  adapter gate, now recorded as passing on main. It does not silently replace a failed
  model result with a fabricated card.
- C's model/semantic implementation remains C-owned. This document is a handoff,
  not authorization for B to edit or merge C's code.
