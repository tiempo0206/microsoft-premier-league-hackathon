# MatchMind AI

## Explainable Football Intelligence for Every Fan

MatchMind AI is a working football-intelligence prototype that turns synthetic match events into explanations viewers can inspect. It combines a replay engine, deterministic football statistics, specialized AI agents and an interactive match centre. A viewer can read an insight, inspect its supporting events, see their recorded locations and switch between Casual and Analyst explanations without generating a second answer.

Our central question is simple: **when an AI says a football moment matters, can the viewer check the evidence?** MatchMind makes that connection visible, from the original event sequence to the published explanation.

Live application: https://matchmind-backend-preview.onrender.com/

Source repository: https://github.com/tiempo0206/microsoft-premier-league-hackathon

## The Problem

Football data can describe what happened without making its significance accessible. A table of passes and shots leaves casual viewers to reconstruct the story themselves. Fluent AI commentary has the opposite problem: an explanation may sound convincing while introducing a number, event or causal interpretation that the available data cannot support.

For studio, broadcast and streaming workflows, useful intelligence therefore needs more than polished prose. It needs consistent statistics, identifiable evidence, appropriate language for its audience and an honest account of how each explanation was produced.

## What We Built

**An event-driven match replay.** The application replays a focused five-minute synthetic segment with fictional teams, Harbor FC and Mountain United. Play, Pause, Reset and adjustable playback speed control a server-side clock. Scores, passes, shots and estimated possession time follow authoritative server snapshots, while Server-Sent Events update the interface. Independent sessions and replay-generation checks prevent an old analysis result from appearing after a reset.

**A checkable moment explanation.** The demonstrator identifies a defined pattern in the 25:00–27:30 window: three high recoveries, with two recoveries followed by a shot within the specified 15-second possession chain. Code computes the counts; the model does not invent them. Each insight includes its analysis window, metrics, supporting event IDs and verification information. This is a reproducible heuristic for the demonstration, not a claim that a few events establish tactical causality.

**Evidence inspection in the match centre.** Viewers can expand an insight's evidence and select a cited event. The corresponding timeline entry and recorded pitch location are highlighted, with a pass endpoint shown when the data provides one. Keyboard users can move to the pitch details and return to the same evidence button. Inspecting evidence does not seek or alter the replay clock. The pitch displays recorded events rather than inferred positions for 22 players.

**Two audience experiences from one fact set.** Casual mode gives a concise, accessible explanation. Analyst mode provides more detail and quantitative context. Both narratives belong to the same insight and share its underlying claims and evidence. Switching audiences happens locally and makes no additional model request.

## Purposeful Multi-Agent Collaboration

Microsoft Agent Framework orchestrates three specialized model roles with different responsibilities and inputs:

1. **Analyst:** examines the bounded event window and supplied metrics, producing structured, evidence-linked claims.
2. **Narrator:** turns the accepted fact set into Casual and Analyst explanations while preserving its numbers and scope.
3. **Auditor:** reviews the explanation for unsupported interpretations and identifies claims or narrative passages that should be rejected or corrected.

Deterministic verification checks numerical consistency, event references, time windows and output structure around this workflow. An explanation labelled as a verified live-model result requires both agent review and code checks under the shared contract. The workflow permits bounded correction rather than unlimited retries. If a live result cannot be published, a clearly labelled rule-based fallback preserves the core replay experience.

The architecture separates calculation, explanation and review. It is designed to make responsibility and failure visible; we do not claim that additional agents automatically improve accuracy or that verification proves every football interpretation true.

## Transparent Outputs and Integration

Every card distinguishes **Live model**, **Rule fallback** and **Precomputed** output. Its verification line distinguishes agent-and-code review from code-only checking. Analysis activity displays actual server-reported steps rather than an illustrative animation. A model failure does not stop the server's match clock or statistical updates.

The repository also includes structured broadcast-overlay payloads, prefix-based match recaps and cross-recap consistency checks. Developer integration surfaces include an MCP server with eight tools and an A2A agent card with a deliberately limited structured `message/send` implementation. These are companion capabilities, not additional controls claimed to exist in the current match-centre screen.

## Technology and Deployment

- **AI orchestration:** Microsoft Agent Framework, with specialized analyst, narrator and auditor roles.
- **Model integration:** a server-side, OpenAI-compatible provider interface; the deployed configuration has been exercised with DeepSeek.
- **Backend:** Python, FastAPI, asynchronous analysis, deterministic statistics and Server-Sent Events.
- **Frontend:** React, TypeScript and Vite, with a responsive purple-and-lime interface, keyboard controls and visible evidence selection.
- **Deployment and collaboration:** Render serves the application and API from one origin; GitHub provides source control, pull requests and automated checks.

Model credentials stay on the server. The current prototype runs as a single service with bounded sessions and analysis work. The free deployment can take time to wake after inactivity; this is a demonstrator rather than an always-on broadcast service.

## Evaluation and Data Responsibility

We publish reproducible checks alongside the implementation. In the deterministic verifier's controlled offline test, all **21 targeted corruptions** were caught and all **four valid controls** were accepted. A separate consistency check passed across three specified recap prefixes. Automated tests cover contracts, replay controls, statistics, reset isolation, streaming recovery and frontend/backend integration. These are scoped test results, not a general accuracy or reliability percentage.

The playable match data is synthetic and its teams are fictional. A separately attributed **CC BY 4.0 Wyscout historical excerpt** is used offline to compare event density and composition with a real five-minute sample. It is not played back as the synthetic match or sent to the model as runtime input. The comparison publishes mismatches as well as improvements; one historical window does not validate a league-wide distribution or the high-recovery trigger. We do not manufacture missing recovery or possession records to make a real match fit the demonstration.

## Value and Next Steps

For viewers, MatchMind makes an explanation easier to understand and inspect. For analysts and content producers, its structured outputs offer a starting point for integrating traceable narratives into studio or streaming experiences.

Our next steps are broader evaluation, richer event coverage and production-oriented persistence and scaling. Club/player preferences, continuous player tracking and a playable historical-match mode are outside the current prototype. The delivered experience demonstrates the core loop: **replay the events, explain a moment, inspect the evidence and adapt the explanation to the audience.**
