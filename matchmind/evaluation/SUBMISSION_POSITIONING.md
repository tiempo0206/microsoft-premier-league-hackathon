# Submission positioning — what we can claim, and what we must not

Written by Role C for the submission representative. Every claim below points at a file or a
command in this repository that a judge could run. Anything not on the list is not claimed.

**Category to enter: Best Multi-Agent System.** Not Foundry, not Azure Cloud Native — we used
neither, and both categories require evidence we do not have.

---

## The five criteria, honestly scored by us

### Technological Implementation (20%)

Judges look for: *creativity and optimized synthetic data creation*, software quality, hero
technologies, code structure.

| We can claim | Evidence |
| --- | --- |
| The synthetic dataset is *qualified*, not merely generated | `evaluation/fixture_qualify.py` — 7 checks with thresholds and reasons; the shipped fixture fails 3 and we publish that |
| The synthetic data is **calibrated against real football**, and where it is off is published too | `evaluation/real_data_calibration.py` compares our 300-second clip with a real five-minute match sample (CC BY 4.0, Role B's delivery): composition is inside tolerance, density is 3.2× too sparse, and the dense proposal fixes density but overshoots shots by 150%. All three statements are in `evaluation/README.md` §1c |
| We refuse to compute what the real record cannot support | the calibration harness refuses recovery, possession and the 3-recovery trigger, because that sample has no `possession_id` and no won-ball attribution |
| We proved the thresholds are reachable | `evaluation/dense_fixture_proposal.py` — 110 events, 1 per 2.7 s, 11 players a side, 0 contract violations, all 7 checks green |
| One deterministic implementation per concept | the recovery chain exists once, in `ai/verify.high_press_chains`, and the tools, the fallback and the recap all call it |
| The verifier is measured | `evaluation/factcheck_bench.py` — 21/21 corruptions caught, 0/4 false alarms, pinned by a regression test |
| The *semantic* layer is measured in both directions | `evaluation/auditor_calibration.py` — 0/15 honest cards wrongly rejected, 50/50 rigged cards caught and correctly attributed; and the corpus is asserted to be invisible to the code gate, so the 100% is not counting the gate's work |
| Consistency is checked across payloads, not just inside them | `ai.recap.recap_series_issues()` — cumulative counters may not go down, one goal may not be credited twice to different players; `tests/ai/test_recap.py` |
| 453 tests, offline, across three roles | `python -m pytest tests -q` |
| Frozen interface discipline | contract 2.0.0 untouched; `tools/check_frozen.py` and `tools/check_scope.py` gate every change |

**We cannot claim** a simulator validated against real football. What we have is **one real match, one
five-minute window**, used to check our clip's density and composition — not 1,446 matches (a rival did
that), not a Premier League distribution, and not a calibration of the trigger itself, because that
sample cannot support it. Say "calibrated against one real five-minute sample and we publish where it
misses", never "validated against real football".

### Agentic Design & Innovation (20%)

Judges look for: agentic patterns, orchestration, MCP integration, multi-agent collaboration,
novelty.

| We can claim | Evidence |
| --- | --- |
| Three roles with disjoint inputs, not three renamed prompts | `ai/service.py: _run_round`; `tests/ai/test_service.py::test_roles_get_different_system_prompts_and_inputs` |
| A fourth role with a different input granularity | `ai/recap.py` reads the whole prefix while a moment card reads one window |
| MCP server, 8 tools, same deterministic code | `ai/mcp_server.py`; `python -m ai.mcp_server` |
| A2A agent card with skills mapped 1:1 to the MCP tools | `ai/a2a.py`; `/.well-known/agent-card.json`; a test keeps the sets equal |
| An A2A JSON-RPC endpoint, honestly scoped | `ai/a2a_transport.py`; `POST /a2a` implements `message/send` with a structured data part only, and refuses free text rather than guessing a tool. The card advertises exactly that subset |
| Microsoft Agent Framework is the default orchestrator | `MATCHMIND_ORCHESTRATOR=framework`; trace records which orchestrator actually ran |
| The contract itself forbids a self-reviewed pass | `check_result` requires `agent_and_code` for any `live_model` card — a structural argument, not a sample |
| Failures are visible, not hidden | every degradation is labelled `rule_fallback` with an `error.code`; the auditor's refusals land in `verification.rejected_claims` |
| The semantic auditor is calibrated, not trusted | `evaluation/auditor_calibration.py`: false-alarm rate 33.3% → 0.0% after removing a flag the model could contradict; then measured in both directions — 0% false alarms on honest cards and 0% misses on 10 classes of overreach the code gate cannot see |
| The code verifier is measured | `evaluation/factcheck_bench.py`: 21/21 corruptions caught, 0/4 false alarms. The two layers are measured on disjoint corpora, which is why both exist |

**We cannot claim** a full A2A implementation (the transport is one method), a component-ablation
result that separates most variants (only the repair round is separated from noise), or that
multi-agent is statistically better (the dense sample has 15 windows; quote the number or say
nothing).

### Real-World Impact & Applicability (20%)

| We can claim | Evidence |
| --- | --- |
| **It is live on the public internet, not just locally** | `https://matchmind-backend-preview.onrender.com` — one process serving the API, the frontend and Role C's composition root. Verified on the host, not on a laptop: `GET /api/v1/health` → `mode: production, model_ready: true`; a replay played to 1755 s and published a `live_model` card with `verification: passed`, `rejected_claims: ["C5"]` |
| **The mainland model endpoint was exercised from the cloud** | that card was generated by Render calling `api.deepseek.com`; `AI_RULES.md` requires this and forbade inferring it from a development machine |
| It runs for cents, not for an Azure subscription | one full pass ≈ 7–9 s and ≈ $0.001 on `deepseek-flash`; `evaluation/README.md`, `evaluation/evidence/` |
| It degrades instead of failing | a dead model still produces a verified rule-fallback card; replay never blocks |
| It refuses rather than guesses | 4/4 tampered windows refused with zero model calls |
| A graphics department can consume it | `ai/overlay.py`, source mode on every graphic; the overlay route answers on the public host |
| An outside agent can use it today | MCP tools + A2A card, both reachable at the public `/.well-known/agent-card.json` |

**We cannot claim** enterprise readiness at scale: single process, in-memory sessions, 8
sessions, 30 analyses per hour. Say the limits out loud; `docs/handoff/ai.md` lists them.

**Nor may we imply the public service is always instantly available.** It runs on Render's free
plan, so it sleeps when idle and the first request after a quiet spell waits tens of seconds. Warm
it before recording the video; do not write "always on", "instant", or anything that promises uptime
we are not paying for.

### User Experience & Presentation (20%)

| We can claim | Evidence |
| --- | --- |
| A real page, served from the same origin as the API | `GET /` returns the built bundle; `frontend/dist` is committed so the image can ship it |
| The full workflow is usable in the browser, not just the API | play/pause/reset, 1×/2×/5×/10×, all six stream kinds; the insight card with the Casual/Analyst switch, expandable claims, and the cited events highlighted on the pitch and on the timeline (`frontend/src/MatchIntelligence.tsx`, `frontend/demo/recording-kit/`) |
| Keyboard users can follow the evidence and come back | selecting a cited event focuses the pitch panel; the panel's return action restores focus to the exact originating button and reopens its disclosure; 44px targets, visible focus ring (`PR #20`, `frontend/qa/evidence-navigation-2026-10-26.md`) |
| Honest labels on screen: live / cached / fallback | `generation.mode` in every payload, rendered as **Live model / Rule fallback / Precomputed**, with the evidence method distinguished as agent-and-code or code-only |
| An explanation you can check, not just read | every claim cites event ids; the overlay pins them to the timeline; the removed claims are shown on the card |
| Two audiences from one verified fact set | `narratives.casual` and `narratives.analyst`, same claims |
| The correction is real, and the public run shows it | the cloud card's trace is `narrator rejected → code-check retry → completed`, and its `rejected_claims` lists C5 |
| Provenance is disclosed, including what we did not use | the About-the-data panel separates the synthetic replay from the historical reference and says the reference is not played back |

**We still cannot claim a finished film.** The interface is real and deployed; what remains is capture —
the 110-second shot list, timed narration and an importable 18-cue SRT are prepared in
`frontend/demo/recording-kit/`, and recording, export and duration review are open. A trimmed wait must
be labelled `WAIT SHORTENED`, and an induced failure must be labelled as a test.
See `evaluation/DEMO_SCRIPT.md`.

### Adherence to Category (20%)

For Best Multi-Agent System the criterion is *"specialized agents have distinct roles,
coordinate through shared state and effective handoffs, recover from failures, and deliver an
end-to-end outcome a single agent could not achieve as effectively."* The honest mapping:

* distinct roles → analyst / narrator / auditor / recap / validator, each with different inputs
* shared state → the `AnalysisRequest` and the verified claim set; the trace IS the handoff log
* recover from failures → one bounded repair round, then a labelled fallback
* outcome a single agent cannot achieve → the contract's own `agent_and_code` requirement, plus
  one agent vs three measured on identical input (fewer unverifiable claims, fewer prose failures)

---

## Sentences the submission must not contain

* "Uses Microsoft Foundry" / "deployed on Azure" — we used neither. The live service is on Render.
* "Always available" / "instant" / uptime promises — free-plan Render sleeps when idle.
* "A2A compatible" — we implement `message/send` with a structured data part and nothing else.
  Say "publishes an A2A agent card and implements a declared subset of the transport".
* "Multi-agent is 3x more accurate" — 12 windows, and the gain was in verifiability, not accuracy.
* "Trained/fine-tuned a model" — no training happened.
* "Validated against real Premier League data" — all data is synthetic; that is the rules' premise.
* "Real-time video tracking" — explicitly out of scope.
* "Production ready" — single process, in-memory sessions.

## The sentences we *can* now add

* "**It is deployed and was verified on the host**: a live model call from the deployed service
  produced a published card with `verification.status: passed`, `method: agent_and_code`, and one
  claim rejected by the auditor (`rejected_claims: ["C5"]`)."
* "**A claim was really removed in that run.** The trace reads `narrator rejected → code-check
  retry → completed`; the correction is not a rehearsal."
* "**The same process serves the page and the API**, so a viewer cannot get a stale frontend
  pointing at a different backend."

## The one-paragraph pitch we can defend

> MatchMind turns synthetic match events into explanations a viewer can check. Every number on
> screen is computed by deterministic code, every claim cites the events behind it, and a
> separate adversarial agent is only allowed to approve or reject — never rewrite. When a claim
> cannot be traced, it is removed and the card says which claims were removed. When the model is
> unavailable, the card degrades to a verified rule fallback and says so, and the match keeps
> playing. The same engine is exposed as MCP tools and an A2A agent card, and produces a timed
> overlay payload a broadcast renderer can consume. It is deployed at
> https://matchmind-backend-preview.onrender.com, where a real model call produced a verified card
> and the auditor removed one claim from it before publication.
