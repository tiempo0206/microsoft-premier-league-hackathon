# Demo script — 110 seconds, filmed against the deployed service

Written by Role C, rewritten after the UI landed and the service went public. The earlier version of
this file forbade showing the interface because A2/A3 did not exist; they exist now, and the product
is live at **https://matchmind-backend-preview.onrender.com**. A judge who clicks that URL sees
exactly what the video shows.

**The rule that has not changed: if it is not in the repository or on the public URL, it is not in the
film.** A judge who cannot reproduce a shot has been misled, and that is worse than a shorter demo.

See `docs/05_acceptance.md` for the official expectations (under two minutes, English or English
translation, synthetic data disclosed early).

---

## Pre-flight — do this before recording, not during

1. **Warm the service.** It runs on a free instance and sleeps when idle; the first request after a
   quiet spell waits tens of seconds. Open the URL in the recording browser and wait for the match
   centre to render *before* you start the take.
2. Open the second terminal you will need for the honesty shot (`Rule fallback`, below).
3. Set the browser to 1280×720, one window, no bookmarks bar, no other tabs.
4. Do not record the clock in the corner if it shows a date before the submission.

## Shot list

| time | on screen | what it proves | how |
| --- | --- | --- | --- |
| 0–8 s | The live page, synthetic badge visible. One sentence over it: *"A viewer cannot check why a moment mattered. We make the check possible."* | The product is deployed and the data is declared synthetic | the public URL |
| 8–20 s | `MATCH OVERVIEW`, then press **Play** at 5×. The clock runs, statistics update, events appear. | A real replay with a server-side clock, not a video | Play, then "Playback speed" → 5× |
| 20–35 s | At ~1650 the insight card appears on its own. Hold on it: the mode label reads **Live model**, and **Evidence checked** is present. | Analysis fires from the data; the card states whether a model wrote it and who checked it | wait, do not click |
| 35–50 s | Expand **Explore evidence**. Events highlight; **Where it happened** shows the points on the pitch; the **Event timeline** marks the cited events. | Every claim is traceable to specific events — the claim is checkable, not just readable | click the evidence control |
| 50–62 s | Toggle the audience control **Casual → Analyst**. The prose changes; the claims and evidence below it do not. | Two audiences from one verified fact set, no second model call | click the toggle |
| 62–75 s | Scroll the card to the verification line. If this run rejected anything it is listed here as `draft 1 C4: …` — say what it means. If nothing was rejected, say that instead: *"this run needed no correction; here is a recorded run that did"* and show `evaluation/evidence/`. | The correction is real and attributable, not decoration | read it off the card |
| 75–90 s | **Honesty shot.** A second terminal: stop the local server, start it with `MATCHMIND_MODEL_PROVIDER=mock`, play to the same window. The card appears labelled **Rule fallback** and the match keeps playing. | The system degrades instead of failing, and labels itself | local run, provider set to `mock` |
| 90–100 s | `python -m evaluation.factcheck_bench` → `catch 21/21, false alarms 0/4`; then `python -m ai.recap --series 1550 1650 1800` → `consistent: true` | The verifier and the cross-recap check are measured, not asserted | both commands |
| 100–110 s | Closing text card: what we did **not** build, and the sample sizes behind the numbers that were quoted. | Honesty as the closing argument | — |

Total 110 s. The hard limit is 120 s.

## Do not film

* **A pitch full of player dots.** The shipped 30-event clip has 8–9 players a side; `fixture_qualify`
  fails it on density and says so in public. Use the event timeline and evidence points, which are
  real.
* **A before/after accuracy comparison.** The ablation separates exactly one variant from noise and
  the README states that.
* **An uptime claim.** The instance sleeps. Never say "always on", "instant", or anything the free
  plan cannot honour.
* **A four-language claim.** The contract has `en` and `zh`.
* **Foundry or Azure.** Neither was used. The deployment is Render.
* **A fallback presented as a live model, or a live model presented as a fallback.** The label on the
  card is the product's whole argument; get it right on screen.

## The honesty shot in detail

The degradation must be a **real** run with no model available, not an injected error dressed up as
natural. Say so out loud: *"No model in this process — so the card is a rule fallback, and it says
so."* One variable is enough, because a missing key on its own would still be read from the local
`.env`:

```sh
# Windows PowerShell
$env:MATCHMIND_SERVE_FRONTEND="1"; $env:MATCHMIND_MODEL_PROVIDER="mock"; $env:PORT="8000"
.venv\Scripts\python -m deploy.release_run
```

Verified before this script was written: `generation.mode` comes back `rule_fallback`,
`verification.method` comes back `code_only`, the health endpoint reports `degraded` with
`model_ready: false`, and the replay keeps advancing. Two things make it honest and cheap to
reproduce:

* the card's own `generation.mode` field says `rule_fallback`, and the UI renders that label;
* the statistics keep updating and the replay never blocks, which is the actual claim.

If you would rather show a model failure instead, a timeout is the realistic one: set
`MATCHMIND_MODEL_TIMEOUT_SEC=1` on a local run. Then **label it on screen as an induced timeout**.
`docs/05_acceptance.md` requires fault injections to be marked as demonstrations.

## Narration notes

* Say the sample size whenever a number appears: "21 controlled corruptions", "five independent
  windows", "one recorded run".
* Say "synthetic" once, early, and let the badge carry it from then on.
* Never say "the AI decided". Say "the auditor rejected a claim and the card was republished without
  it" — more impressive, and true.
* If the model is slow on the day, pause the replay and wait; the explanation stays aligned with the
  evidence, which is the point.
