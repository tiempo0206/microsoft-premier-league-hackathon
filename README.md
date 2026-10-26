# MatchMind — verified explanations for live football

**Microsoft × Premier League "Inside the Game" hackathon.**
Category entered: **Best Multi-Agent System**. Contract 2.0.0. All match data is synthetic.

**[Live demo →](https://matchmind-backend-preview.onrender.com)** — one process serving the app, the
API and the AI pipeline. It runs on a free instance, so the first request after an idle spell takes
tens of seconds while the container wakes.

MatchMind turns a stream of synthetic match events into the kind of explanation a broadcaster puts on
screen: *"HOME won the ball high up the pitch three times, and two of those became shots within 15
seconds."* The interesting part is not that a language model can write that sentence. It is that
**every number in it is computed by code, every claim cites the events behind it, and a separate
adversarial agent may delete claims but never write them.**

## Why this is not another LLM commentary wrapper

Three gates stand between the model and a viewer:

| Gate | What it does | Where |
| --- | --- | --- |
| **Arithmetic** | refuses a window whose own metrics contradict its own events | `matchmind/ai/verify.py` |
| **Semantic auditor** | a second agent whose only job is to reject claims the data does not support; its decision is derived from its rejection lists, never taken from a flag it asserts | `matchmind/ai/service.py` |
| **Contract coupling** | a card may only be labelled `passed` when *both* an agent and code reviewed it — the frozen schema enforces this, so a self-reviewing agent can never claim verification | `matchmind/contracts/contract.schema.json` |

The product's selling point is what it **refuses** to say. In the deployed run the auditor removed
one claim and the card still published, carrying `verification.rejected_claims: ["C5"]`.

## What was measured, with the caveats attached

| Harness | Result |
| --- | --- |
| `evaluation/factcheck_bench.py` — controlled corruptions | **21/21 caught, 0/4 false alarms** |
| `evaluation/auditor_calibration.py` — both directions | **0/15** honest cards wrongly rejected; **50/50** rigged cards caught and correctly attributed |
| Dense fixture, 5 independent windows | **11/11 published** in the best run, 8/11 in a second run — quote the range |
| `evaluation/ablation.py`, 18 runs per variant | exactly one effect separates from noise: the repair round |
| Single agent vs three | three agents cost 2.8× the calls and 1.7× the latency; the single agent can never carry `passed`. That is the claim, not "more accurate" |
| Role B acceptance | 512 normal + 72 invalid synthetic backtests, **0 failures, 0 false or missed triggers** |

Every one of those numbers has limits — one fixture, one model, a handful of windows — and
[`matchmind/evaluation/README.md`](matchmind/evaluation/README.md) states them next to the number
rather than in a footnote.

## Run it

Requires Python 3.12 and Node ≥ 22.13 (pnpm 11.25.0). No Azure, Foundry or cloud account is needed.

```sh
cd matchmind
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt      # Windows
# .venv/bin/python -m pip install -r requirements-dev.txt        # macOS / Linux

cd frontend && pnpm install --frozen-lockfile && pnpm run build && cd ..
```

Start it (the same entry point the container uses; `PORT` defaults to 8000 locally and to 10000
inside the image):

```sh
# Windows PowerShell
$env:MATCHMIND_SERVE_FRONTEND="1"; $env:PORT="8000"; .venv\Scripts\python -m deploy.release_run
# macOS / Linux
MATCHMIND_SERVE_FRONTEND=1 PORT=8000 .venv/bin/python -m deploy.release_run
```

Open <http://127.0.0.1:8000>. **With no model key the app still runs** and every card is labelled
`rule_fallback`. To use a real model, set `MATCHMIND_MODEL_PROVIDER`, `MATCHMIND_MODEL_BASE_URL`,
`MATCHMIND_MODEL_NAME` and `MATCHMIND_MODEL_API_KEY` in the environment — never in the repository.

Check your own copy against the same gates CI runs:

```sh
python -m pytest tests -q        # 434 tests, offline, no network calls
python tools/check_frozen.py     # contract and fixtures untouched
python -m deploy.verify_backend  # Role B's full acceptance; spawns a loopback server
```

## Verify the claims yourself

Every headline claim in this file maps to one command and an expected result. Run them in `matchmind/`
with the `.venv` from above; the billed ones are marked and cost fractions of a cent.

| Claim | Command | You should see |
| --- | --- | --- |
| The arithmetic verifier catches controlled corruption | `python -m evaluation.factcheck_bench` | `catch 21/21`, `false alarms 0/4` |
| The semantic auditor is calibrated in both directions, and the corpus is invisible to the code gate | `python -m evaluation.auditor_calibration --plan` | `13/13` cases usable as auditor tests, `code_gate_blocked_whole_card: false` for every rigged one |
| Role B's data and replay layer is correct under load | `python -m deploy.verify_backend` | `status: passed`, 512 normal + 72 invalid cases, `false_triggers 0`, `missed_triggers 0` |
| The frontend really talks to the backend | `cd frontend && pnpm run test:backend` | `status: passed`, `model_calls: 0`, 8 named checks |
| A real model produced a verified card | see `evaluation/evidence/` | `live_model`, `agent_and_code`, `passed` |
| The whole thing degrades when the model is gone | `MATCHMIND_MODEL_PROVIDER=mock MATCHMIND_SERVE_FRONTEND=1 python -m deploy.release_run` | cards labelled `Rule fallback`; the clock keeps running |
| The cross-recap check rejects a series that contradicts itself | `python -m ai.recap --series 1550 1650 1800` | `consistent: true` |

Two of these are deliberately **not** in the test suite because they are slow or billable; that is why
they are one-liners you can run yourself.

## Deployment

The deployed service builds `matchmind/deploy/Dockerfile.release` from `main`, serves the API and the
frontend from one origin on port 10000, and runs `deploy.release_check --profile integrated` at image
build time so a misassembled image cannot start. Environment variables it needs:
`MATCHMIND_SERVE_FRONTEND=1`, `MATCHMIND_MODEL_*` (provider, base URL, model name, key),
`MATCHMIND_MODEL_TIMEOUT_SEC=20`, `MATCHMIND_ORCHESTRATOR=framework`, `MATCHMIND_THINKING=disabled`.

## What is built, and what is not

**Built and running:** event-driven replay with a server-side clock and SSE; the three-agent analysis
pipeline (analyst → narrator → auditor) on Microsoft Agent Framework; the deterministic verifier; a
rule-based fallback that stays useful when the model dies; a broadcast overlay payload with a spoken
script; a match recap that can report the goal no single moment card can see; expected-threat ranking
that refuses when the sample is too thin; an MCP server with eight tools; an A2A agent card and a
declared `message/send` subset.

**The frontend is a working product, not a mock-up:** playback with play/pause/reset and 1×/2×/5×/10×,
all six stream kinds handled, an insight card with the Casual/Analyst switch, expandable claims, the
cited events highlighted on the pitch and on the timeline, the generation-mode and evidence-checked
labels on screen, keyboard focus that returns to the button you came from, and a data-sources panel
that separates the synthetic replay from the historical reference.

**Not built, and not claimed:** Azure or Foundry integration; full A2A compatibility; a paid always-on
deployment (the free instance sleeps); validation against real Premier League data — what exists is one
five-minute real sample used to calibrate the synthetic clip, described in
[`matchmind/evaluation/README.md`](matchmind/evaluation/README.md) §1c; and the 110-second video
itself, for which the shot list and captions are prepared in `matchmind/frontend/demo/recording-kit/`.

## Repository layout

| Path | Owner | Contents |
| --- | --- | --- |
| `matchmind/frontend/` | A | match centre, snapshot and SSE consumer |
| `matchmind/backend/`, `matchmind/data/` | B | fixtures, statistics, replay sessions, deployment entry |
| `matchmind/ai/`, `matchmind/evaluation/` | C | pipeline, verifier, harnesses, submission documents |
| `matchmind/contracts/` | shared, frozen | schema 2.0.0, generated types, examples |

## Honest paperwork

The documents below are why the claims above can be trusted; each one lists what it does **not**
establish.

- [`matchmind/evaluation/SUBMISSION_POSITIONING.md`](matchmind/evaluation/SUBMISSION_POSITIONING.md) — what we may claim per criterion, and the sentences the submission must not contain
- [`matchmind/evaluation/PLAN_REVIEW.md`](matchmind/evaluation/PLAN_REVIEW.md) — 13 places rival projects are ahead of us, plus 8 self-criticisms
- [`matchmind/evaluation/README.md`](matchmind/evaluation/README.md) — every measurement with its sample size
- [`matchmind/evaluation/evidence/`](matchmind/evaluation/evidence/README.md) — a committed, credential-free record of one real model run
- [`matchmind/docs/handoff/ai.md`](matchmind/docs/handoff/ai.md) — the AI pipeline's handoff, including every defect found and how it was found
- [`matchmind/docs/handoff/backend.md`](matchmind/docs/handoff/backend.md) · [`frontend.md`](matchmind/docs/handoff/frontend.md) — the same record for the data/backend and frontend sides
- [`matchmind/frontend/demo/recording-kit/`](matchmind/frontend/demo/recording-kit/README.md) — the 110-second shot list, timed narration and importable captions, ready for capture
- [`docs/development-plan.md`](docs/development-plan.md) · [`docs/contracts.md`](docs/contracts.md) — the original written plan and interface proposal from 2026-10-21, kept as history and marked as such at the top of each file
- [`docs/hackathon.md`](docs/hackathon.md) — official rules links and submission reminders

## Rules compliance

- **All match data is original and synthetic** (CC0). No real Premier League footage, tracking data or
  licensed dataset is used or redistributed.
- Model keys live only in server-side environment variables — not in the repository, the image, the
  build arguments or the logs. `tests/ai/test_invariants.py` enforces this.
- Contract 2.0.0 is frozen. `tools/check_frozen.py` fails any change to the schema or the fixtures,
  and CI runs it on every push.
- The repository must be **public** before submission (Official Rules §4.4); that is an owner action.

## Contributing

Branch, open a pull request, keep it small. `CONTRIBUTING.md` has the workflow,
`matchmind/AGENTS.md` and `matchmind/AI_RULES.md` have the module ownership and the rules every
AI-assisted change follows, and `.github/CODEOWNERS` says who reviews what.
