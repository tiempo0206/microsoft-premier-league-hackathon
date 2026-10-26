# MatchMind recording package — 110 seconds

Role A, issue #21, 2026-10-26. Based on main `1113388` and C's canonical [demo script](../../../evaluation/DEMO_SCRIPT.md). This package is narration, captions, an edited shot list and inspectable preflight evidence. **No finished video or voice recording is included.** A6 capture, export and representative review remain unfinished.

Use [narration.md](narration.md) for the English voice track and import [captions.en.srt](captions.en.srt) into the editor. [cues.json](cues.json) is the text/timing source. Captions end at 01:50, leaving ten seconds below the two-minute limit for export variation; include any credits inside that timeline. Do not add a ten-second outro afterward. Reading speed is measured in `validation.json`, not a recorded voice duration.

## Capture these eight segments, then edit to the timeline

| Edited time | Record on screen | Keep visible / action |
| --- | --- | --- |
| 00:00–00:08 | Public match centre, purple/lime title and synthetic badge | The actual public URL and synthetic label. No concept image presented as UI. |
| 00:08–00:20 | Match overview, Play, statistics and progress | Select 5x, Play, then show changing clock/counts. Record longer source footage as needed. |
| 00:20–00:34 | The insight returned for 25:00–27:30 | Wait for the real result, then Pause. Capture the actual generation/verification labels. A fallback stays a fallback; do not re-label it or overlay a fictitious live result. |
| 00:34–00:48 | Explore evidence; select a received evidence ID | Show its point and, if recorded, pass endpoint in Where it happened. Keep the paused clock for comparison; no seek or player-tracking claim. |
| 00:48–01:00 | Casual → Analyst | Record both narratives from the same card, with unchanged facts/evidence. |
| 01:00–01:14 | Verification text and actual Analysis activity | Show actual traces. An earlier recorded rejection must carry its original date/run and a “Recorded example” label; it is not this take's rejection. |
| 01:14–01:28 | Separately captured local rule fallback | Persistent label: **OFFLINE DEMONSTRATION · RULE FALLBACK**. Explicit mock provider; record the actual fallback card and continuing clock/statistics. This is an intentional no-model process, not footage of a natural provider outage. |
| 01:28–01:50 | Controlled-test terminal results, then closing product/URL | Label **CONTROLLED OFFLINE TEST · 21 CORRUPTIONS / 4 VALID CONTROLS**. Show the recap consistency for exactly three prefixes. Close with framework, Render and the single-window/prototype limits. |

This is an **edited shot list**, not a 110-second uncut latency claim. Reaching 27:30 from 25:00 takes **30 wall seconds at 5x** (15 seconds at 10x), before model latency. The older canonical script's early insight slot cannot follow an 8-second Play in a literal uncut 5x take. Capture the full wait; if shortening it in the edit, display **WAIT SHORTENED** on the transition. Never accelerate narration/clock footage and quote it as model response time.

## Offline rehearsal and the fallback segment

The rehearsal uses the default synthetic derivative, matching the deployed match identity and 3/2 window. From `matchmind` on macOS/Linux, with the existing project environment:

```sh
MATCHMIND_MODEL_PROVIDER=mock MATCHMIND_SERVE_FRONTEND=1 \
  MATCHMIND_DATA_DIR=data/extra/validated-demo \
  .venv/bin/python -m uvicorn ai.app:app \
  --host 127.0.0.1 --port 18430 --workers 1
```

Open `http://127.0.0.1:18430/`. Use the mock provider explicitly: a missing shell key alone does not establish that the loaded configuration has no key. This process calls no paid model. On Windows, set these three environment variables in the recording terminal and use `.venv\Scripts\python.exe` with the same module/host/port/worker arguments.

Build assets locally before recording (`pnpm run build` in `frontend`). For the public segment, warm the actual service and inspect its visible mode. Playing through the analysis window on the configured public service can invoke its live model; this package does not automate or repeat that workflow. A health response alone is not proof of a new live result. Previous live evidence remains in its original dated record under `evaluation/evidence/`; do not claim that local framework evidence is a cloud test.

Keep model/admin credentials out of terminal footage and captions. Show only the prepared result text and ordinary local commands, with a single browser window. Record at 1280×720 or higher and keep subtitles clear of generation/verification labels and selected-event details. The concept image and PR #20-only navigation are not substitutes for deployed footage; PR #20 remains pending at this package's preflight.

## Prepared evidence and readiness

[evidence/](evidence/) contains fresh offline verifier/recap output (terminal trailing spaces trimmed) and [preflight.json](preflight.json) records public HTTP checks and byte-identical deployed/main asset hashes. No deployment revision is inferred solely from those hashes, and no new paid model workflow was run. Browser UI inspection timed out, so this package establishes HTTP/build availability, not a new public keyboard/evidence walkthrough or a completed screen recording.

Read the actual `Rule fallback`, `Precomputed` or `Live model` label in each take. The `Evidence checked` line states code-only versus agent-and-code checks; neither establishes tactical causality. The historical Wyscout sample is used offline for comparison, not played back as the synthetic match. One five-minute reference does not validate a league distribution or the unsupported recovery trigger.

For C's editorial review: `evaluation/SUBMISSION_POSITIONING.md` still contains an old sentence saying A2/A3 are unbuilt, despite merged PR #14 and C's later role audit. `evaluation/evidence/README.md` describes its saved development-machine evidence, not every later cloud run. A has left those C-owned files untouched; reconcile them before the final recording/submission. C's canonical demo schedule also needs the edited-wait clarification above.
