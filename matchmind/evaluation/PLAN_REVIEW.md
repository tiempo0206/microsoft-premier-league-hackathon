# Plan review — Role C's critical assessment

Written by Role C (Meng Yuxuan) as integrator, on 2026-10-22/23. This is an assessment,
not an official team document. Everything about other projects comes from their public
READMEs, collected in `evaluation/research/readmes/` with the raw inventory in
`evaluation/research/competitors.json`; nothing was cloned, installed or executed.

Scope of the scan: 9 GitHub searches, 125 candidate repositories, 113 relevant, 45 with a
substantial README, 17 read in detail. The official `microsoft/insidethegamehackathon`
repo has 14 forks and 69 stars at scan time.

---

## 1. Where we are genuinely ahead

These are the only claims worth making in a pitch, because a rival cannot copy them by
reading our README.

**1.1 The verifier is measured, not asserted.**
`evaluation/factcheck_bench.py` reports **17/17 required corruptions caught, 0/4 false
alarms**, and is pinned by `tests/ai/test_factcheck_bench.py` so it cannot silently drift.
Most rivals claim a fact-checker; the strongest one we found (Touchline) reports 99.7%
blocked with zero false alarms, which is why ours has to report a number at all.

**1.2 The contract itself forbids passing a self-reviewed card.**
`check_result` requires `verification.method == "agent_and_code"` whenever
`generation.mode == "live_model"`. A single agent reviewing its own output cannot legally
emit `passed`. That is a structural argument for multi-agent that does not depend on a
sample, and no rival's README makes it.

**1.3 The refusal path is the product, and it runs before the model.**
All 4 tampered windows are refused with **zero** model calls, measured in every run. The
arithmetic gate (`ai/verify.py: consistency_issues`) recomputes the detector from the
events and rejects a window whose own metrics contradict them. This catches the case a
schema validator cannot: a well-formed number that the evidence refutes.

**1.4 Cost per decision is tiny and stated.**
A full three-agent pass costs about 9 s and roughly $0.001 on `deepseek-flash`. A 12-window
evaluation costs cents. Several rivals depend on a fine-tuned Foundry deployment, which
means a judge reproducing their demo needs an Azure subscription. Ours reproduces offline.

---

## 2. Where rivals are clearly ahead — the honest gap list

Ordered by how much score each gap costs us. The "who" column is the project whose README
demonstrates the capability; all are in `evaluation/research/readmes/`.

| # | Gap | Who shows it | Why it costs us score |
| --- | --- | --- | --- |
| 1 | **MCP server** | GamePulse, pshah208/matchlens, Lasso, The Dugout, Regista, TheNeuralWars | Judging text names "MCP integration". Five of the seven strongest projects ship one. We shipped none until tonight. |
| 2 | **A2A endpoint** (`/.well-known/agent-card.json`, `/a2a`) | pshah208/matchlens, Touchline, Lasso | Best Multi-Agent criterion literally names A2A. Still missing for us. |
| 3 | **Per-role ablation** | Touchline publishes a five-way ablation with quantified damage per role | The criterion is "an outcome a single agent could not achieve as effectively". Ablation answers it directly; our single-vs-multi comparison only gestures at it. |
| 4 | **Overlay JSON for a broadcast renderer** | GamePulse (`/api/overlay`), Touchline, Regista, pshah208 | Official 4.1 asks for output "machine-readable enough to be rendered as synchronized graphical overlays". We produce a UI, not a broadcast contract. |
| 5 | **Simulator validated against real football** | GamePulse: 8/8 totals within tolerance of 1,446 real matches, 14/16 spatial checks, 13 m player-position error vs real tracking | Technological Implementation explicitly scores "creativity and optimized synthetic data creation". Our fixture is 30 events; theirs is validated against a corpus. |
| 6 | **Explicit director / handoff log / legal-transition policy** | pshah208/matchlens: a `director` picks the next handoff, a deterministic policy enforces legal transitions, every recovery is "a rejected trace step plus a handoff" | Criterion: "coordinate through shared state and effective handoffs, recover from failures". Our pipeline is a fixed sequence with one repair; our `traces` are not a handoff log. |
| 7 | **Storyline continuity** | Touchline's StorylineKeeper: without it "20 of 28 goals lose their match context" | Our cards are stateless. Card #4 cannot say "second time in five minutes". |
| 8 | **Editorial rate control** | Touchline's MomentScout: 0.7 graphics/minute with it, about 21 without | A viewer drowning in cards is a broken product. We have no rate limit on published insights. |
| 9 | **Accessibility as the differentiator** | soundpitch: audio-first for blind and low-vision users, with a full "Honest limits" section | Impact (20%) rewards a real underserved audience. Our "casual/analyst" split is a reading level, not an audience. |
| 10 | **Falsifiable prediction** | Second Act: predicts each manager's adjustment as a measurable test, then confirms or rejects it in the second half | The most original mechanic we found. Nothing in our plan has a prediction that can be proven wrong on screen. |
| 11 | **Multiple moment types** | GamePulse: four detectors (dominant-but-unrewarded, pressing that fades, the player everything goes through, the turning point) | We have one (`high_press`), and the frozen enum already reserves two more we never implemented. |
| 12 | **Counterfactual at event level** | Rematch: compares the action taken against the options actually present, deterministic geometry | Turns "what happened" into "what else was available", which is a far better answer to "why does this matter". |
| 13 | **Real-data path through the same contract** | GamePulse runs public Wyscout and Sportec data through the identical event contract | We prove nothing about generality; our whole system is one 30-event fixture. |

---

## 3. Where our own plan is weak, independent of rivals

**3.1 The data is too thin to carry the demo.** 30 events over 300 seconds. Three of the
fourteen positive-looking windows do not even fire the detector, so the evaluation cannot
honestly report "4 positives" — see `evaluation/README.md`. A judge watching the pitch will
see three dots. This is the single largest risk and it is cheap to fix.

**3.2 No card can see both the recovery and the goal — a window-boundary defect.**
The third high recovery is at 1640 and the goal at 1680. In the shipped configuration the
detector reads 1500–1650, which contains the recovery but not the goal; the next window,
1650–1800, contains the goal but not the recovery, so its `high_recoveries` is 0. **No
single card can connect them.** My first diagnosis blamed the 15-second linked-shot
horizon; that was wrong, and a wider horizon fixes nothing because the goal is not even in
the request. `ai/tools.py` now reports a 45-second context tier, which is useful when a
window does contain both (proved by a test on 1500–1700), but the actual fix is B's: choose
a window that contains the outcome it intends to explain, or give the detector a bounded
look-back. Both are recorded in the handoff as recommendations, not made unilaterally.

**3.3 One moment type out of three reserved.** `Insight.type` allows `high_press`,
`fast_break`, `sustained_control`. We implement one. That is a visible gap against our own
frozen contract.

**3.4 No recap.** Official 4.1(iii) asks for "automated match recaps". Contract v0.1 had
`POST /replays/{id}/recap`; 2.0.0 dropped it and we never noticed.

**3.5 The frontend cannot show what C produces.** A2/A3 are unbuilt. The best artefact in
this repository is currently invisible in the product. Nothing in C's work can fix that,
but it should be said plainly rather than buried.

**3.6 Personalisation is a reading level, not a person.** "Casual / analyst" is not
personalisation in the sense official 4.1(i)(e) describes (favourite club, favourite
player, player-focused mode). `roster.json` has been in the repository since day one and is
used by nothing.

**3.7 The evaluation is a smoke sample.** 12 windows, one fixture, one model, one day, two
of them positive. Every number in `evaluation/README.md` carries that caveat; any pitch
number that drops it becomes a lie.

**3.8 A verifier that is too strict fails the same way as a model that is wrong.** Found
five times tonight (see handoff 2b and the evaluation README's findings list). Two of them
silently disabled the entire Chinese path. The lesson is general: every new check needs a
false-alarm test, not just a catch test.

---

## 4. What was implemented tonight from this review

| Borrowed idea | From | Landed as |
| --- | --- | --- |
| MCP server surface | GamePulse, pshah208, Lasso | `ai/mcp_server.py`, 5 tools, 12 tests, reuses the same deterministic code |
| Catch-rate / false-alarm measurement | Touchline's 99.7% claim, soundpitch's honesty note | `evaluation/factcheck_bench.py` + pinned regression test |
| Per-role ablation | Touchline's five-way ablation | `evaluation/ablation.py` |
| "Never silently swap mock for real" | Rematch | already held by the labelled `rule_fallback`, now asserted in the MCP and app tests |
| Documented honest limits | soundpitch's whole-section approach | this file plus §3 of it |

## 5. What is still worth doing, in order

1. **Densify the fixture** (≥400 events, 3 fixtures: high press / fast break / quiet). Cheap,
   and it fixes §3.1, §3.2 and §3.3 at once.
2. **A2A agent card + endpoint.** Judges name it; it is a few hundred lines.
3. **Overlay JSON export.** Official 4.1 names it; it is a serialiser over an existing
   `Insight`.
4. **Storyline memory + editorial rate cap.** Fixes gaps 7 and 8 for one combined cost.
5. **`sustained` tier at 45 s** so the card stops ignoring the goal.
6. **Recap endpoint** and a fourth role whose input granularity is different (whole prefix,
   not one window), which also strengthens the multi-agent argument.
7. **Player-focused mode** driven by the already-present `roster.json`.

## 6. What not to copy

* **A fine-tuned Foundry model.** GamePulse and Second Act both depend on one. It raises
  reproduction cost for judges and buys wording we do not need.
* **A tactical simulator with a realism tab.** Impressive, and out of reach in the remaining
  time; a half-built one is worse than none.
* **Betting odds or win predictions.** Not our honest claim, and it invites the wrong
  scrutiny.
* **xG.** We deliberately avoid an uncalibrated score dressed up as a metric. If we ever add
  a shot-quality number it must be labelled a heuristic with the formula shown.
