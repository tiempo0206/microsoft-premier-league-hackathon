# Competitor scan — Microsoft × Premier League "Inside the Game"

Collected by Role C on 2026-10-22/23. **Read-only OSINT**: every project below was read
through its public README. Nothing was cloned, installed, vendored or executed, and no
third-party code entered this repository. The analysis lives in
[`../PLAN_REVIEW.md`](../PLAN_REVIEW.md); this file only records what was scanned.

## How the scan was run

```
python -m evaluation.scan_competitors     # 9 queries -> competitors.json
python -m evaluation.fetch_readmes        # 18 chosen repos -> readmes/*.md (git-ignored)
```

Both scripts are re-runnable. `competitors.json` records the query, creation date, size,
language and topics for every hit so the team can re-check a claim.

**Third-party READMEs are read but not committed.** `fetch_readmes.py` writes them to
`readmes/`, which is git-ignored: the analysis belongs here, other people's prose does not.
Re-run the script to fetch them again.

## Coverage

| step | count |
| --- | --- |
| GitHub search queries | 9 |
| candidate repositories returned | 125 |
| relevant after keyword filter | 113 |
| with a substantial README | 45 |
| read in detail and stored in `readmes/` | 17 |
| forks of `microsoft/insidethegamehackathon` at scan time | 14 |

Date filter: repositories created on or after 2026-09-20.

## The 17 repositories read, and why each was chosen

| repository | what it represented | why it mattered to us |
| --- | --- | --- |
| `Wael-Akhdar/InsideTheGame` | GamePulse | Ships MCP, an overlay JSON export, a fact-checker with a measured 40/40, and a simulator validated against 1,446 real matches |
| `likalight/touchline` | Touchline | Closest structural rival: five-role pipeline plus a published per-role **ablation** |
| `pshah208/matchlens` | MatchLens | Same product name and thesis; ships A2A, MCP, an explicit director with legal-transition policy and a handoff log |
| `Zhiyilang/matchlens` | MatchLens | Cited insights, xG-centric |
| `Adamzuckk/Rematch` | ReMatch | Event-level **counterfactual** ("what else was available"), deterministic geometry, no xG |
| `dhruvkulkarni02/second-act` | Second Act | **Falsifiable prediction**: half-time adjustments stated as measurable tests, then confirmed or rejected |
| `diego-sicignano/soundpitch` | SoundPitch | **Accessibility** as the differentiator, plus a whole README section of honest limits |
| `iSharaf6/regista` | Regista | Match-director framing, overlay output |
| `abhiiiesh/MatchMind` | MatchMind | Identical product name |
| `TheNeuralWars/matchmind` | MatchMind | Identical product name, momentum focus |
| `sagitta414/before-the-roar` | Before the Roar | Personalisation depth, correction and recovery section |
| `lauramiro/the-dugout` | The Dugout | Explains a manager's decisions live |
| `TomThomasPrintac/live-sub-intel` | Live Sub Intel | Substitution intelligence as a niche |
| `bradhack/lasso` | Lasso | Exposes its tools **through GitHub Copilot** via MCP; held-out-season model report |
| `enniob/pitchlens` | PitchLens | Same hackathon, TypeScript, evaluation-first README |
| `GOkwori/matchdesk` | MatchDesk | Broadcast production-studio framing |
| `SairajBandre16/tacticlens` | TacticLens | Azure deployment angle |

## Pattern frequency across the 17 READMEs

Simple keyword counts, useful only as a smell test for what the field considers table
stakes. Not a quality ranking.

| capability | repositories mentioning it |
| --- | --- |
| MCP | 5 of the top 5 by README depth |
| broadcast overlay output | 4 |
| A2A | 3 |
| xG or expected goals | 5 |
| counterfactual / what-if | 3 |
| explicit cache of verified output | 4 |
| Foundry deployment | 5 |
| Agent Framework | 5 |

**Conclusion we acted on:** MCP, an overlay contract and A2A are table stakes among the
strongest entries, and we had none of the three. MCP was implemented the same night
(`ai/mcp_server.py`); the other two are ranked in `../PLAN_REVIEW.md` §5.

## What we deliberately did not copy

Fine-tuned Foundry deployments, tactical simulators with realism calibration, and xG
models. Each raises the cost for a judge to reproduce the demo, and we would rather ship a
smaller claim that anyone can verify in five minutes. The reasoning is in
`../PLAN_REVIEW.md` §6.
