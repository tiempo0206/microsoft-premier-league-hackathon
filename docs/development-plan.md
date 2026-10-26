# Development proposal: MatchLens

> **Historical proposal, 2026-10-21.** This document is the plan that was written before any code
> existed, kept for the record. The product it describes has since been built and deployed; see the
> [repository README](../README.md) for what exists today, and `matchmind/docs/handoff/` for the
> engineering record. Where this file and the frozen contract disagree, the contract (2.0.0) wins.


Research date: **2026-10-21, Asia/Shanghai**. Status: **proposal, not an implemented product**.

## Starting position

The repository currently contains collaboration documents only. The team has three members, has confirmed event registration, and does not yet have an Azure account. Technical specialties and available development hours are not known. Assign the workstreams below by interest and experience rather than assuming responsibilities from GitHub usernames.

This proposal targets a working demo within one week. Time estimates are planning assumptions.

## Verified event facts

The [Official Rules](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md), checked at upstream commit `fec6ae2229917574898dc740fd2002381ac758cd`, describe a synthetic-event-to-personalized-insight challenge. Five judging dimensions carry 20% each: technical implementation, agentic innovation, impact, UX/presentation, and category fit (§6).

Submission needs public code, an English or translated presentation, a demo video under two minutes, and judging access (§4). The submission deadline converts to **2026-10-28 14:59 Asia/Shanghai**; aim to submit by **12:00**. See [the event reference](hackathon.md) for source links and dates.

The following product choices, architecture, metrics, and work estimates are our recommendations, not additional competition requirements.

## Recommended product

**MatchLens helps a viewer understand what changed in a match, why the observable change matters, and which events support the explanation.** A casual fan and an analyst can view the same events through different levels of detail.

The first screen should contain:

1. A replay clock, score, and synthetic-data badge.
2. A simple pitch showing the selected event sequence.
3. A rolling view of shots, pass completion, and completed passes entering the final third.
4. A small set of explanation cards with an expandable evidence list.
5. Casual/analyst and English/Chinese controls.
6. A recap of events observed so far when playback is stopped or completed.

Use fictional clubs and players for the first fixture. A professional-looking pitch and evidence interaction provide a clear demonstration without needing a television broadcast feed.

### Example user experience

Illustrative synthetic scenario, not a claim about an actual match: the current five-minute window contains three Northbridge shots, compared with zero in the preceding five minutes. Completed passes entering the final third increase from two to eight.

- Casual view: a short explanation of the increased attacking activity, with the metric values shown in separate factual chips.
- Analyst view: the exact two windows, metric definitions, and linked event sequence.
- Evidence action: highlight the supporting passes and shots on the pitch and timeline.

Describe the observed pattern. Do not claim the opponent is tired or that a coaching decision caused the change unless the input actually contains evidence for that claim.

### Alternatives considered

These are qualitative judgments for a small team with a short deadline.

| Direction | Strength | Main development burden | Recommendation |
| --- | --- | --- | --- |
| Personalized, evidence-backed match companion | Shows a complete input-to-viewer experience | Requires consistent contracts and useful explanations | Build this MVP |
| General football question-answering chatbot | Quick to prototype | Needs a stronger event-driven experience to stand out | Keep questions contextual to a selected moment |
| Player tracking and event extraction from video | Visually compelling | Footage rights, detection, tracking, calibration, and evaluation | Revisit after the event pipeline works |

The initial category strategy is to make a convincing Foundry-backed application. Consider a multi-agent category only if a measured second agent improves the experience enough to justify its latency and complexity. Category choice remains provisional.

## Proposed architecture

```text
Seeded synthetic fixture
        |
        v
Replay controller -> event validation and deduplication
        |
        v
Deterministic match state and rolling metrics
        |
        v
Candidate moment detector
        |
        v
Evidence agent: inspect candidates, call bounded event/metric tools
        |
        v
Structured explanation -> reference/claim validation -> fallback if needed
        |
        v
Server-sent events -> React viewer -> audience-specific rendering
```

### Components

| Component | Proposal | Reason for this team |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite; SVG pitch | One screen, straightforward event rendering |
| Backend | Python, FastAPI, Pydantic | Keep statistics, validation, and model integration together |
| Source data | Versioned JSONL fixtures and seed metadata | Reproducible replays with no live provider dependency |
| Replay transport | SSE; REST commands for start/pause/reset | The viewer mainly receives updates |
| Initial state | One backend process with run-scoped memory; fixture/run logs on disk | Enough for development without a database service |
| AI | A Foundry provider behind an explicit interface | Local development can use a clearly labelled template provider |
| Agent orchestration | Microsoft Agent Framework after a small compatibility spike | Tool use and traces without building orchestration infrastructure |
| Deployment candidate | One Container App serving the API and built frontend | One origin and one deployment to debug |

For this prototype, treat live replay state as ephemeral. A restart requires a new replay. Use one process/replica until state is externalized; do not imply in-memory state is a production distributed service. Keep the fixture in the image and let a new browser session start its own run.

Microsoft documents explicit workflows and tool-using agents in [Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/). Use functions for fixed calculations and an agent for selecting evidence and composing an explanation. Confirm and pin compatible package versions during implementation.

Foundry supports [schema-constrained outputs](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs). Schema compliance does **not** establish factual correctness; validation must also check event IDs, time windows, and numeric claims. [FastAPI streaming responses](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse) support the transport proposal; SSE framing and reconnection still need application code. [Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview) is a hosting option, not a requirement for local work.

### Evidence and runtime behavior

- All totals and percentages come from deterministic code. Never ask the model to maintain the score or count passes.
- Agents receive only the replay prefix available at the current clock. Recaps must not leak later fixture events.
- The first agent may call `get_metrics`, `get_event_window`, and `get_candidate_moments`, each scoped to the current run and time cutoff.
- Bound tool calls, model calls, timeouts, and retries. Cache by state version, audience, language, and prompt version.
- Start with one agent and at most one regeneration after validation failure. Add an editorial agent only after comparing against this baseline.
- Validate references and typed metric claims in code. Review language separately: a valid reference does not prove a causal explanation.
- Display model-generated, cached, and template/fallback modes honestly. A timeout must not stop replay or silently disguise a template as live inference.
- Record model/deployment, prompt version, evidence IDs, latency, token usage when available, and fallback reason. Measure before making performance claims.

## No Azure account: work can begin today

Develop the fixture, replay engine, metrics, and interface locally while one team member sets up model access. The model adapter should have two named modes, `template` and `foundry`; the template mode is a development aid rather than evidence that cloud AI integration is complete.

### Account and model-access spike

1. Check account eligibility. [Azure for Students](https://azure.microsoft.com/en-us/free/students/) currently offers eligible full-time university students $100 credit for 12 months without a credit card. The [general free account](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/avoid-charges-free-account) has a different offer: eligible new users receive $200 for 30 days. Eligibility, regional availability, and model quota must be checked for the actual account.
2. Follow the [Foundry resource quickstart](https://learn.microsoft.com/en-us/azure/foundry/tutorials/quickstart-create-foundry-resources?tabs=portal). Obtain an active subscription, create a project, and verify one available model deployment.
3. Test one server-side structured-output request from the development machine. Record the endpoint family, deployment name, authentication method, region, and package versions. Do not mix the project endpoint with a resource inference endpoint.
4. Keep credentials out of Git and browser bundles. Use individual identities and appropriate access grants when sharing the project.
5. Record actual request usage and agree on application-level call limits before unattended tests. Initial cloud provisioning and spending are outside this documentation change.

Account creation alone does not prove a model is accessible. Make a successful request the day-one gate. If access is still blocked on October 22, resolve that blocker immediately while the local work continues; a template-only application should not be presented as having completed Microsoft AI integration.

Do not build against old GitHub Models inference examples: the [official service notice](https://docs.github.com/en/github-models) says that service retired on July 30, 2026. GitHub Copilot access is a separate product and should not be assumed to provide this application's runtime model endpoint.

## First development session: one complete slice

The first acceptance milestone is deliberately small: **20 audited events produce the expected statistics and one evidence-backed card on a local page.** A visible template label is acceptable for this milestone.

| Order | Deliverable | Done when |
| --- | --- | --- |
| 1 | Agree on the proposed contracts in [contracts.md](contracts.md) | All three workstreams use the same event and insight examples |
| 2 | Write a 20-event fixture and expected results | A human can verify the score, pass counts, and supporting event IDs |
| 3 | Implement replay and aggregation | Replaying/resetting produces identical results; duplicates are harmless |
| 4 | Render the viewer using the fixture | Play/pause/reset and a selected event sequence work locally |
| 5 | Connect the template provider, then Foundry | The card retains its evidence and explicitly identifies its source mode |
| 6 | Integrate on one branch early | A clean checkout can reproduce the same demonstration |

Create setup commands only when they actually work in the chosen scaffold. Do not assume the directories or endpoints below already exist.

### Proposed repository layout

```text
apps/web/                  React viewer
apps/api/                  FastAPI, replay, metrics, model adapter
packages/contracts/        Versioned schemas generated/checked against API models
data/synthetic/            Fixtures, seed metadata, expected results
tests/                     Domain, contract, and end-to-end checks
docs/                      Research, demo script, judging instructions
```

## Workstreams and calendar

Keep responsibilities provisional until teammates choose them. Integrate daily rather than keeping three independent prototypes.

| Workstream | Initial ownership scope | Integration contract |
| --- | --- | --- |
| Experience | Viewer, pitch, timeline, evidence interaction, audience/language controls | Typed events and insight cards |
| Match engine | Fixtures, validation, replay, metrics, candidate detection | Replay state and tool payloads |
| AI and delivery | Foundry access, evidence agent, evaluation, hosting and demo | Validated insight schema and source labels |

| Shanghai date | Main outcome |
| --- | --- |
| Oct 21 | Choose the MVP, freeze contract v0.1, audit 20 events, attempt a real model request |
| Oct 22 | Connect replay API and viewer; resolve model-access blockers |
| Oct 23 | Run the full event-to-insight-to-evidence interaction with Foundry |
| Oct 24 | Add casual/analyst views, English/Chinese output, and a recap |
| Oct 25 | Exercise failure modes, compare outputs with a simple baseline, and record latency/call counts |
| Oct 26 | Deploy one working URL; verify a fresh browser and document judge access |
| Oct 27 | Freeze features, record an English demo, rehearse submission, and prepare code for publication |
| Oct 28, before 12:00 | Submit and verify receipt, leaving a buffer before the official deadline |

Repository publication is a separate owner action. Keep this development repository private until publication is explicitly arranged.

## Backlog in dependency order

| ID | Task | Acceptance evidence |
| --- | --- | --- |
| M1 | Contract plus audited fixture | Valid event examples and checked expected totals |
| M2 | Replay and rolling metrics | Tests for duplicate events, time cutoffs, window boundaries, reset, and empty input |
| M3 | Single-screen viewer | A replay shows event, metric, and evidence selection updates |
| M4 | Foundry evidence agent | A real request uses bounded tools and produces a validated card; failure returns a labelled fallback |
| M5 | Personalization and recap | Same facts remain consistent across profiles/languages; recap uses the observed prefix |
| M6 | Integration, evaluation, and deployment | Reproducible setup, real URL, recorded results, and an under-two-minute demo |

### Evaluation and scope control

Use meaningful domain checks, not only tests that mirror implementation. Start with the audited fixture, then add small seeded scenarios: sustained attacking activity, a counterattack, a quiet interval, and a model/network failure.

Check exact metric values, valid references, no future-event leakage, stable reset, and profile factual consistency. Manually assess whether explanations add useful context and distinguish observations from speculation. Compare the agent against a fixed template using the same evidence. Only claim improvements supported by recorded results.

Initial performance targets, not measured results: local event-to-metric display below 500 ms and a warm model-backed card within five seconds. Record the machine, network, sample count, median/p95, and fallback rate. Reduce workload if the model cannot meet the target; do not block the replay while waiting.

Keep the first release to one screen, a small fixture set, two audience profiles, and two languages. Full video tracking, calibrated xG, win predictions, speech, a general football knowledge base, Kubernetes, and a large service graph should wait until the core demonstration is reliable.

## Learning resources

Use the [official playlist index](https://github.com/microsoft/insidethegamehackathon/blob/main/RESOURCE%20PLAYLISTS.md) by role: Foundry and agents for model access, workflows for orchestration, and the data playlist for event design. Prefer current Microsoft documentation over copied SDK snippets from older tutorials.
