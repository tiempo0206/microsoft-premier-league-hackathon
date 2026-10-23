# Demo script — 110 seconds, only what exists

Written by Role C. The plan's `docs/05_acceptance.md` describes an aspirational video that
assumes the frontend exists. It does not yet. This version is constrained to artefacts that
exist today and can be reproduced by a judge.

**Rule for this video: if it is not in the repository, it is not in the film.** A judge who
clones the repo and finds nothing behind a shot has been misled, and that is worse than a
shorter demo.

---

## Shot list

| time | what is on screen | what it proves | reproduce |
| --- | --- | --- | --- |
| 0–10 s | One sentence: "A viewer cannot check why a moment mattered. We make the check possible." Then a single verified card with `rejected_claims` visible. | The problem, and that we remove claims rather than defend them | any run of `evaluation.live_smoke` |
| 10–25 s | `python -m ai.recap` running, printing score, shots, possession, `Goals: H01 for HOME`, and "the most recent recovery paid off 40 seconds later" | The recap role, and the thing no moment card can say | `python -m ai.recap` |
| 25–45 s | A live analysis: `python -m evaluation.live_smoke --debug`, showing analyst → narrator → auditor(rejected) → narrator(repair), ending `status=passed`, `rejected_claims=[C4,C5]` | The three roles, the one repair round, and the honest record of what was refused | same command |
| 45–60 s | The overlay payload: `python -m ai.overlay`, scrolling to show `lower_third`, `stat_line`, `evidence_pin`, and `source.mode` on each | A graphics renderer can consume it, and cannot present a fallback as live | `python -m ai.overlay` |
| 60–72 s | `python -m evaluation.factcheck_bench` printing 17 corruptions all caught and 0 false alarms | The verifier is measured, not asserted | same command |
| 72–85 s | A tampered window refused: `python -m evaluation.fixture_qualify` is not this shot — instead show the benchmark line `T1 multi "rejected" calls=0` | The gate runs before the model, so it is free | `python -m evaluation.benchmark --cases tampered` |
| 85–100 s | The MCP server answering: `python -m ai.mcp_server` plus one tool call, and the A2A card at `/.well-known/agent-card.json` | Interoperability that exists today | both commands |
| 100–110 s | Text card: what we did not build (frontend, Foundry, Azure, video tracking) and the measured numbers with their sample size | Honesty as the closing argument | — |

## Do not film

* A pitch view with player dots. The fixture has 30 events and 8–9 players a side; the pitch
  would look empty and the density check says so in public.
* Any UI screenshot. A2/A3 are unbuilt; do not mock one up.
* A "before/after accuracy" comparison. The ablation is underpowered and the README says so.
* An A2A handshake. The card exists, the transport does not.
* A claim that the model writes in four languages. Two (`en`, `zh`) are in the contract.

## If the frontend lands before the deadline

Replace shots 1 and 45–60 with the real page, and keep `source.mode` and `rejected_claims`
visible in frame — they are the product, not decoration. Everything else stays.

## Narration notes

* Say the sample size out loud when quoting a number: "12 windows", "17 corruptions".
* Say "synthetic" once, early, and let the badge on screen carry it.
* Never say "the AI decided". Say "the auditor rejected two claims and the card was republished
  without them", which is both more impressive and true.
