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
| We proved the thresholds are reachable | `evaluation/dense_fixture_proposal.py` — 110 events, 1 per 2.7 s, 11 players a side, 0 contract violations, all 7 checks green |
| One deterministic implementation per concept | the recovery chain exists once, in `ai/verify.high_press_chains`, and the tools, the fallback and the recap all call it |
| The verifier is measured | `evaluation/factcheck_bench.py` — 17/17 corruptions caught, 0/4 false alarms, pinned by a regression test |
| 236 tests, offline, across three roles | `python -m pytest tests -q` |
| Frozen interface discipline | contract 2.0.0 untouched; `tools/check_frozen.py` and `tools/check_scope.py` gate every change |

**We cannot claim** a simulator validated against real football (a rival did that against 1,446
real matches; we did not). Do not imply it.

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
| The semantic auditor is calibrated, not trusted | `evaluation/auditor_calibration.py`: false-alarm rate 33.3% → 0.0% after removing a flag the model could contradict |
| The code verifier is measured | `evaluation/factcheck_bench.py`: 21/21 corruptions caught, 0/4 false alarms |

**We cannot claim** a full A2A implementation (the transport is one method), a component-ablation
result that separates most variants (only the repair round is separated from noise), or that
multi-agent is statistically better (the dense sample has 15 windows; quote the number or say
nothing).

### Real-World Impact & Applicability (20%)

| We can claim | Evidence |
| --- | --- |
| It runs for cents, not for an Azure subscription | one full pass ≈ 9 s and ≈ $0.001 on `deepseek-flash`; `evaluation/README.md` |
| It degrades instead of failing | a dead model still produces a verified rule-fallback card; replay never blocks |
| It refuses rather than guesses | 4/4 tampered windows refused with zero model calls |
| A graphics department can consume it | `ai/overlay.py`, source mode on every graphic |
| An outside agent can use it today | MCP tools + A2A card |

**We cannot claim** enterprise readiness at scale: single process, in-memory sessions, 8
sessions, 30 analyses per hour. Say the limits out loud; `docs/handoff/ai.md` lists them.

### User Experience & Presentation (20%)

| We can claim | Evidence |
| --- | --- |
| Honest labels on screen: live / cached / fallback | `generation.mode` in every payload, surfaced in the overlay and the MCP note |
| An explanation you can check, not just read | every claim cites event ids; the overlay pins them to the timeline |
| Two audiences from one verified fact set | `narratives.casual` and `narratives.analyst`, same claims |

**We cannot claim** that the frontend shows any of this yet. A2/A3 are unbuilt, so **the video
must not pretend the UI exists.** See `evaluation/DEMO_SCRIPT.md`.

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

* "Uses Microsoft Foundry" / "deployed on Azure" — we used neither.
* "A2A compatible" — we implement `message/send` with a structured data part and nothing else.
  Say "publishes an A2A agent card and implements a declared subset of the transport".
* "Multi-agent is 3x more accurate" — 12 windows, and the gain was in verifiability, not accuracy.
* "Trained/fine-tuned a model" — no training happened.
* "Validated against real Premier League data" — all data is synthetic; that is the rules' premise.
* "Real-time video tracking" — explicitly out of scope.
* "Production ready" — single process, in-memory sessions.

## The one-paragraph pitch we can defend

> MatchMind turns synthetic match events into explanations a viewer can check. Every number on
> screen is computed by deterministic code, every claim cites the events behind it, and a
> separate adversarial agent is only allowed to approve or reject — never rewrite. When a claim
> cannot be traced, it is removed and the card says which claims were removed. When the model is
> unavailable, the card degrades to a verified rule fallback and says so, and the match keeps
> playing. The same engine is exposed as MCP tools and an A2A agent card, and produces a timed
> overlay payload a broadcast renderer can consume.
