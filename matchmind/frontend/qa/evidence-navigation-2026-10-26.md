# Selected evidence navigation — 2026-10-26

Role A, issue #19; branch `codex/frontend-evidence-navigation`, base main `1113388`, frozen contract 2.0.0.

Expanded insight evidence and the recorded-position panel can be far apart on mobile. After selecting a cited event, `View selected event on pitch` now moves focus to the evidence panel. Its return button restores focus to the exact originating evidence or timeline button. A collapsed evidence disclosure is reopened before restoring focus. No selection/navigation action controls the replay or requests a model. Internal timeline positioning uses immediate scrolling rather than an explicit smooth animation.

## Reproduce

Build with `pnpm run build` in `frontend`. From `matchmind`:

```sh
MATCHMIND_MODEL_PROVIDER=mock MATCHMIND_SERVE_FRONTEND=1 \
  MATCHMIND_DATA_DIR=data/extra/showcase/press \
  .venv/bin/python -m uvicorn ai.app:app \
  --host 127.0.0.1 --port 18420 --workers 1
```

Open the same-origin built UI in an isolated browser. Play at 5x or 10x, pause after the actual fallback insight appears, then use keyboard Space to expand evidence, select E011 and activate the new jump. Return and verify focus, clock, statistics and observed-event count. Repeat from a timeline row and after manually collapsing the evidence disclosure. Reset must remove the old selected event and navigation state.

## Recorded scope

Evidence is under [2026-10-26/evidence-navigation](2026-10-26/evidence-navigation/). The first iteration paused at 29:13. At 390×844 the selected panel fit within x20–370/y186.71–681.19, with its recorded point, pass endpoint and return action visible. Evidence navigation and return preserved that paused clock, all statistics and 108 observed events. Return focused E011 with `aria-pressed=true`; closing its disclosure before returning reopened it. Timeline return focused the selected timeline row instead. At 1280×720 the panel and focus ring also fit; document scroll widths equalled the respective viewport widths.

The source disclosure preserves C's merged `Not played back` copy and offline-comparison explanation. The current runtime remains synthetic; the tuned calibration proposal has not been adopted into the default replay. A reran C's calibration report on main `1113388`: six of twelve comparisons were out of tolerance, with zero model calls. A report exit code is not a claim of universal realism.

Validation uses the real integrated B/C app with an explicitly mock provider and a synthetic QA dataset. It is local emulation, not a physical-device, screen-reader or public Render acceptance. No paid model request, default dataset, shared contract, cloud configuration or deployment change is included.

The final rebuilt bundle (`index-DnW473jk.js` / `index-Bkk-p2ET.css`, after JSX formatting/spacing cleanup) was reloaded and exercised again at clip complete, 30:00: evidence-to-pitch and exact-button return at both widths, plus timeline return. The committed screenshots show that final build. The structured result distinguishes its completed-clip checks from the earlier paused-clock checks. Reset returned the same final-build replay to idle run 2 at 25:00, zero insights/events/navigation buttons and a connected feed. No warning/error was captured; temporary viewport/tab and local server were cleaned up.

Checks passed: 29 frontend tests, TypeScript/Vite build, real B/C consumer probe (five normal SSE kinds, zero model calls), 457 Python tests / 69 subtests, frozen-file and A-scope checks. C's offline report ran successfully while explicitly reporting six out-of-range comparisons. No implementation-mirroring style/focus unit tests were added; actual browser keyboard checks cover the reading interaction.
