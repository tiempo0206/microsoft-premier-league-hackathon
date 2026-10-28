# Frontend handoff — purple/lime theme, provenance and playback

- Owner: Role A / Tianbo Cao (`tiempo0206`), assisted by Codex.
- Date: 2026-10-28 (Asia/Shanghai); earlier observations retain their recorded dates.
- Current branch: `codex/readme-platform-screenshots`, task #25. The submission/preflight update
  PR **#24** (`050ee8a`), navigation PR **#20** (`1360326`) and recording kit PR **#22** (`2636e09`)
  are merged. The theme/source work is in PR #14 (`d4488d1`).
- Current starting main SHA: `050ee8a`; C's integration and the refreshed submission material are
  included. Shared baseline recorded by C:
  `03910f8889e846bc70215c3c0faf4bb63cd84977`.
- Contract: `2.0.0`. This documentation slice also edits the repository-root README, explicitly
  requested by the representative; no other role's module or handoff is changed.

## Current follow-up: real platform screenshots in the repository README

The representative requested platform screenshots and an introduction in the root README. Its new
walkthrough presents the desktop match centre, selected-evidence inspection and two mobile views,
reusing four already committed actual application captures. English text explains playback, the
shared Casual/Analyst fact set, recorded event locations and keyboard return navigation. Image alt
text describes the visible UI; the mobile views appear together at 300px width.

The capture context identifies the 2026-10-25–26 local integrated rehearsals, dense synthetic QA
sample, mock provider and Rule fallback / Code only labels. These screenshots are neither concept
art nor a new public/live-model acceptance. Existing capture records remain linked. The README's
data wording now distinguishes synthetic runtime data from the bundled, separately attributed
CC BY 4.0 Wyscout offline reference; the earlier blanket "no licensed dataset" claim was incorrect.

Validation for this documentation-only slice checks repository-relative links, all four tracked image
targets and their alt text, the rendered Markdown/mobile table, frozen files and whitespace. Original
README CRLF line endings and screenshot bytes are preserved. No application source, dist, dependency,
model request, fixture, contract or deployment configuration changes. C still reviews/merges the PR
under the existing main protection. The Role A module guard covers paths inside matchmind; the
representative's explicit README request authorizes the additional root documentation edit.

## Earlier follow-up: refreshed recording baseline and submission copy

At the representative's request, A refreshed the recording entry point after C's merges. The old `frontend/demo/recording-kit/preflight.json` remains byte-for-byte unchanged. New `preflight-2026-10-26-post-integration.json` records **14:49 UTC / 22:49 Asia/Shanghai**, against main `cd050e4`: root/health/catalogue HTTP 200, production contract 2.0.0, model_ready true, synthetic Harbor FC / Mountain United. Public HTML and local dist list the same two assets, both byte-identical:

- `index-DnW473jk.js`: `20ff045be18cfdc3d2f58d7aa3c6b6f20188ab5ce7234507f07c059627e00fdb`
- `index-Bkk-p2ET.css`: `8ab4470be0931fca3125deb5aa85a958a15c1b865a6d8e15216d3a25bd6c33b7`

The README now selects that snapshot and marks the old evidence as historical. `capture_preflight.py` reproduces GET-only snapshots using the existing pinned httpx dependency, refuses to overwrite a file, retains full SHA-256s and does not infer the entire deployment revision. It starts no replay or model workflow. No new public interaction, new live result or completed film is claimed. The original narration, SRT and offline evidence are preserved.

`frontend/submission/` adds a detailed English Description, other field values and a sourced submission guide. The copy describes the actual Microsoft Agent Framework / DeepSeek / Render implementation, three model roles, two audience modes, merged keyboard navigation and scoped offline evaluation. It distinguishes fictional synthetic runtime data from the attributed historical comparison. Azure/Foundry deployment, player tracking and a historical replay are not claimed. Native Edge could read the portal/editor but AX setValue and paste left the old text unchanged; Save remained disabled. The representative then chose manual editing and requested the complete copy in chat. **No portal save or final contest submission is claimed.** Video recording/export is still unfinished.

The representative also requested repository administration. The authenticated owner had admin permission: visibility is now **public**, verified with an anonymous GitHub API GET. Main requires the existing three GitHub Actions checks, an up-to-date branch, one approving review and resolved conversations; administrators are included, force pushes and main deletion disabled. The closed PR #5 branch was archived at `archive/closed-pr-5-development-pack` (`6976bd77c962dabd22a8eb6c21714b6fd8843083`) before its branch reference was removed. No commit history was rewritten. A pattern scan of 414 fetched historical text blobs found no credential-pattern matches; this is not a completeness guarantee. These owner-requested settings do not change code ownership or C's integration role.

Validation: TypeScript/Vite build and 29 frontend tests passed with unchanged tracked dist; full offline Python suite **457 passed / 69 subtests**. Frozen-file, Role A scope, whitespace, preflight help/overwrite refusal and anonymous repository/archive readback are checked before PR handoff. No frozen contract, fixture, runtime source, model/deployment configuration, dependency or B/C-owned file changed. C should review/merge the Role A PR; the new protection also requires a teammate approval.

The sections below are dated earlier observations, preserved as historical records.

## Integrator note (Role C), on merging #20 before #21

Both branches rewrote this header, so they conflicted; this is the merged version and it keeps both
records in the order they landed. Because #20 merged first, the tracked bundle is now
`/assets/index-DnW473jk.js` + `index-Bkk-p2ET.css` and the next deployment serves those. A's dated
observation below -- that `index-DiFIbE5M.js` was byte-identical to main `1113388` -- was true when it
was recorded and is superseded by that merge, not falsified by it. The recording kit ships no build
assets, so it needed no rebuild.

- Branch: `codex/frontend-demo-kit`; task #21, A6 recording package. Previous theme/source/focus work was merged in PR #14 (`d4488d1`); evidence navigation landed as PR #20 (`1360326`) immediately before this one, merged by C.
- Starting main SHA: `1113388b29b15be573af4ee04ec2cd613bec7c3b`; C's offline comparison/tuned proposal and source-copy correction are included. Shared baseline recorded by C: `03910f8889e846bc70215c3c0faf4bb63cd84977`.
- Contract: `2.0.0`. This slice changes frontend recording docs/assets/evidence and this handoff only. No runtime source, build asset, dependency, B/C implementation, fixture, contract or deployment change.

## Latest follow-up: recording package and public-build preflight

`frontend/demo/recording-kit/` contains the 110-second edited shot list, English narration, 18-cue importable SRT, timing source/validation and fresh inspectable offline/public-HTTP evidence. The captions have no gaps/overlaps, end at 01:50, use at most two lines/44 characters per line and peak at 15.6 characters per second. The 190-word script plans approximately 104 words per minute; this is not a recorded voice duration. The kit keeps actual generation/verification labels, a persistent offline-fallback segment label, controlled-test sample sizes and the single historical-window limit.

The shot schedule explicitly fixes a timing ambiguity: from 25:00 to the 27:30 trigger takes 30 wall seconds at 5x before model latency. Source footage must include the actual wait; an edit shortening it must say WAIT SHORTENED. The kit is an edited timeline, not an uncut response-time claim. It does not assume PR #20-only controls have deployed or claim that a fresh take had a natural model rejection. C's canonical demo and submission/evidence descriptions need editorial reconciliation where they still say A2/A3 are unbuilt or describe only the earlier local evidence; A left those C-owned files untouched.

On 2026-10-26, direct HTTPS root/health/matches returned 200. The public catalogue is synthetic MM-DEMO-01, Harbor FC / Mountain United. Deployed assets `index-DiFIbE5M.js` and `index-Bfv8OZrL.css` are byte-identical to main `1113388`; production health reports contract 2.0.0 / model_ready true. This establishes the published main theme/source build, not the exact deployment commit or a new live-model result. The earlier proxy-route failures did not establish service failure. Browser UI reads timed out, so no new public screenshot/keyboard/evidence acceptance is claimed; the temporary tab is left to automatic turn-end cleanup. No replay Play/control or new model workflow was requested.

A reran `evaluation.factcheck_bench` offline: 21 targeted corruptions caught, four valid controls accepted, zero false alarms. `ai.recap --series 1550 1650 1800` returned consistent true for exactly those three prefixes. The kit retains the fresh outputs, not an invented terminal screenshot. Neither controlled-test score is a live reliability rate. No model calls or deployment/configuration changes were made.

Validation: TypeScript/Vite build and 29 frontend tests passed; 19 common contract/mock tests and frozen-file/A-scope/whitespace checks passed. The build regenerated the existing hashes without tracked dist changes. SRT/timing, offline-result and public/local-hash validation passed. A6 **video capture/export, synchronized voice track, final duration/frame review and representative review remain unfinished**; the package is prepared material, not a completed film. Public advanced interaction/native retry acceptance remains separate. C reviews/merges this package and PR #20 independently.

- Branch: `codex/frontend-evidence-navigation`; task #19. Previous #13/#16/#18 and source-presentation work was merged by C in PR #14 (`d4488d1`, 2026-10-25).
- Current starting main SHA: `1113388b29b15be573af4ee04ec2cd613bec7c3b`. C's offline calibration/comparison and source-copy correction (`6f5d14d`) are retained. Shared baseline recorded by C: `03910f8889e846bc70215c3c0faf4bb63cd84977`.
- Contract: `2.0.0`. A changes only frontend source/build/docs/QA and this handoff. This slice adds local selected-event reading navigation; no shared contract, fixture, B/C implementation, dependency or deployment change.

## Latest follow-up: selected-evidence navigation and current calibration docs

Main advanced from `0df6144` through C's PR #14 merge and offline comparison/tuned proposal. A started this new branch at `1113388`, preserving the purple/lime UI and C's `Not played back` provenance copy. C chose offline calibration/comparison for this submission, with no default-runtime replacement or independent historical mode. A reran `evaluation.real_data_calibration --json`: the report generated successfully, zero model calls, six of twelve comparisons outside tolerance. `frontend/DATA_SOURCES.md` and README now distinguish completed comparisons/tuned proposal from the unchanged default replay, and remove stale claims that calibration is still wholly undecided. A did not change the report, generator or runtime dataset.

`MatchIntelligence.tsx` remembers the originating evidence/timeline button. After a cited event is selected, `View selected event on pitch` focuses the recorded-position panel; its return action focuses the exact originating button, reopening a collapsed evidence disclosure first. A timeline selection offers `Back to timeline`. These handlers only select, scroll and focus; they make no replay/model request. Timeline auto-positioning no longer requests smooth animation. Buttons have a 44px minimum height and a visible theme-coordinated focus ring; the evidence panel is programmatically focusable without adding a routine Tab stop.

The real local B/C app served the built UI with explicit mock provider and the synthetic dense press QA dataset. Keyboard round trips at 390×844 and 1280×720 passed. The first iteration preserved paused 29:13, all statistics and 108 observed events. It returned focus to E011 (`aria-pressed=true`), restored a closed disclosure, and returned timeline selection to its exact row. After JSX formatting cleanup, the final bundle was reloaded and both viewport round trips plus timeline return passed again at clip complete 30:00. The mobile selected panel fit x20–370/y186.71–681.19; both document scroll widths matched viewport width. C's full-time/date/credit and offline-comparison source copy remained present. Final Reset produced idle run 2, 25:00, zero insights/events/navigation buttons and a connected feed. No captured browser warning/error; temporary viewport, tab and server were cleaned up. No paid model call or public deployment.

Final assets: `index-DnW473jk.js` / `index-Bkk-p2ET.css`. TypeScript/Vite build, 29 frontend tests, real B/C consumer probe (five normal SSE kinds, zero model calls), 457 Python tests / 69 subtests, frozen-file/scope/whitespace checks passed. Screenshots, structured observations and reproduction are in `frontend/qa/evidence-navigation-2026-10-26.md` and `frontend/qa/2026-10-26/evidence-navigation/`. No new implementation-mirroring unit tests were needed for this reversible reading interaction.

A read-only public root/health attempt on 2026-10-26 failed with a local URL/network error through the previously configured proxy. This did not establish public service failure or deployment state. The last verified public build observations below retain their dates. This new A slice awaits C review/merge and an explicit chosen-build deployment; public advanced acceptance and the final English video remain pending.


## Earlier follow-up: apply the project concept to the working UI

On 2026-10-25 the representative requested a working UI consistent with the generated project concept. Issue #18 records this A slice. `App.tsx`, `DataSources.tsx`, `styles.css`, `index.html` and the local favicon now coordinate deep purple, layered purple surfaces, lime actions/evidence and lilac secondary information. The introduction reads “Football, explained.” with an original M mark and decorative geometric crown. Header anchors reach the actual match, insights and source disclosure. Playback/statistics, insights, agent traces, evidence, timeline, notices and sources use the same theme tokens. Semantic labels, keyboard focus, selected evidence and reduced-motion support remain present. No dependency or remote asset was added.

`frontend/project-media/` preserves the concept PNG and prompt receipt as a design reference. It is not imported into the runtime bundle. The app still displays actual server results; concept scores/metrics, fake completed agent steps, real-club logos and player tracking were not introduced. The synthetic runtime/historical-reference distinction and source attribution remain intact. No consumer, API, backend, AI or fixture logic changed.

`frontend/qa/theme-2026-10-25.md` and `frontend/qa/2026-10-25/theme/` record actual local browser screenshots and structured observations. The real B/C app served the built UI on loopback with explicit `MATCHMIND_MODEL_PROVIDER=mock`, `MATCHMIND_SERVE_FRONTEND=1` and the synthetic dense press QA dataset. Keyboard Play, 10x selection, Pause, audience modes, evidence expansion/selection and Reset worked. A paused check held 29:51 while event E011 highlighted its recorded position and timeline row. The final build also reached clip complete at 30:00 and displayed actual Rule fallback / Code only results, 3 high recoveries / 2 linked recoveries / 150s window. Both audience narratives were read from that same insight. Reset returned to 25:00, idle run 2, zero insights/events and a connected feed.

At 1280×720 and 390×844, document scroll width equalled viewport width. Mobile event-list scroll/client width both measured 348px with observed events. All four principal mobile panels measured 350px inside 20px margins. Source disclosure expanded with Space; keyboard focus reached the collection link and the full stacked source panel fit within the viewport. Eight solid foreground/background token pairs exceeded 4.5:1 in the recorded calculation; this is not a full accessibility audit. No browser warning/error was captured. The temporary viewport was reset and the QA tab/server stopped. No paid model call or public deployment was made.

Final assets: `index-9Jdbo-up.js` / `index-Bfv8OZrL.css`, superseding the source-disclosure-only hashes below. TypeScript/Vite build, 29 frontend tests, real B/C consumer probe (five normal SSE kinds, zero model calls), 440 Python tests / 69 subtests and frozen-file checks passed. A-scope and whitespace checks apply to the final staged changes. C still reviews/merges PR #14 and coordinates explicit Render deployment; public acceptance and final video remain pending. #15 calibration/versioned-data adoption is separate.

## Earlier follow-up: local native browser SSE retry

On 2026-10-25 main remained `0df6144` and C had not reviewed #14. A added only a manual loopback fault proxy under `tests/frontend/`, browser evidence under `frontend/qa/`, README guidance and this handoff. The real local B/C app used an explicitly mock provider. A separate browser tab played at 1x and paused at 25:10 after two events. One `SIGUSR2` to the owned proxy cut its downstream SSE stream while the backend stayed alive. Without a reload or explicit subscription restart, the browser requested the same stream again with `Last-Event-ID` ending `:1:26`, 3004 ms after the injected stream closure. The first subsequent UI read was already connected; the transient reconnecting banner and total recovery duration were not measured.

Before/after UI records matched: same replay/run 1, paused clock 25:10, unchanged statistics and two distinct timeline IDs without duplication. Reset then returned the same replay to idle run 2 at 25:00 with zero statistics/empty timeline and a connected feed. The browser tab, proxy and upstream server were closed; no AI window or model call was requested. The application/build from `86564f8` is unchanged. This establishes a local paused-case native retry, not lossless playing-event recovery or public Render retry timing.

`frontend/qa/browser-reconnect-2026-10-25.md` links the structured UI result, raw proxy log and two screenshots in `frontend/qa/2026-10-25/reconnect/`, with reproduction steps. Helper syntax/help, external-URL refusal and a local production/model-ready stub refusal passed; frozen-file, A-scope, result/log and whitespace checks apply. The helper has no HTTP injection endpoint, binds only loopback, is excluded from automated tests/CI/production, and requires operators to configure mock explicitly. C review/merge/deployment, public advanced browser acceptance, data adoption/calibration and the final video remain open.

## Earlier follow-up: local source-disclosure acceptance

On 2026-10-25 main still had no commit after `0df6144`; PR #14 remained open without C review. A completed the previously missing local source-disclosure checks on the unchanged `409d25c` application/build using a separate in-app browser tab and an explicitly mock local integrated server. Space expanded, Return collapsed, and Tab/Shift+Tab reached the collection/license links with visible focus. At 1280×720 the source sections occupied two 559px columns; at 390×844 they stacked into 308px sections. Document scroll width equalled viewport width in both cases, and screenshots showed the complete source copy without clipping. This establishes local browser acceptance, not physical-device or public-release acceptance.

Reviewable screenshots, DOM measurements, keyboard steps and reproduction instructions are committed under `frontend/qa/2026-10-25/` and `frontend/qa/source-reference-2026-10-25.md`. The viewport override was reset, temporary browser tab closed and owned server stopped. Playback remained idle, zero model calls were made, and no runtime source/build/contract/data/deployment change was needed. Public advanced interaction/retry acceptance, final video and C's actual calibration/adoption decision remain open. Frozen-file, A-scope, image/report consistency and whitespace checks apply to this evidence-only slice; earlier passing code tests and source verification are retained with their original scope.

## Earlier follow-up: received historical reference

The representative supplied B's #15 handoff and requested a fresh sync. Main `0df6144` includes the Wyscout original-field research kit. After code inspection, A ran `.venv/bin/python -m data.generator.real_history --verify` offline: passed, match 2499719, 1,768 full-match records, 96 first-half 1500–1800 records, `synthetic=false`, `runtime_compatible=false`, zero model calls. This independently checks the delivered sample/manifest; the complete-season archive result remains B's recorded verification, not an A re-download. Source acquisition is no longer waiting on B.

`DataSources.tsx` adds a native `details` disclosure, `About the data`, below the existing replay notes. It labels the current synthetic replay separately from `Historical reference · Not connected`: Arsenal–Leicester City, source UTC date 2017-08-11, **source full-time** result 4–3 and the 96-record first-half 25:00–30:00 research excerpt. It credits Pappalardo/Massucco and Wyscout, links the versioned collection and CC BY 4.0, and describes selection/reserialization. It explicitly says the research source has not calibrated the current replay. The footer is scoped to the synthetic replay. No original real event records are included in the browser bundle or submitted to replay/model endpoints.

`historicalReference.ts` contains presentation metadata only. Two new source-reference tests compare the displayed identity/date/score/credits with the original match/manifest and recompute the displayed excerpt count from the full original-field sample. `DATA_SOURCES.md` now records the resolved Wyscout access gap and the remaining adoption/initial-state/provider-mapping questions for C. A did not add a second schema or a playable historical option. The absent explicit recovery/possession records remain unavailable; the synthetic 3/2 trigger is not asserted for Arsenal–Leicester City.

Current rebuilt entry assets: `index-C8F7BEC-.js` / `index-GQj0pIxq.css`. TypeScript/Vite build and 29 frontend tests passed; common Python suite passed **440 tests / 69 subtests**; the real B/C frontend consumer probe passed with an explicit mock provider and zero model calls. The initial native Edge inspection observed expanded source content, then hit `noWindowsAvailable`; keyboard/mobile acceptance was not established at that attempt. The later isolated-browser record above resolves those local source-disclosure gaps. See `frontend/qa/browser-2026-10-24.md` for the historical observations. These runtime changes still need C review/merge and deployment; no cloud change was made.

**Next for C / #15:** choose calibration or independent historical replay; retain the synthetic submission pipeline. Calibration needs documented comparable event/window/unit definitions and actual results before the UI can claim it happened. A historical runtime needs reviewed source/date/season/competition/identity/initial-score/credit semantics and a versioned contract. A is ready to consume those agreed fields. B's delivered sample is usable research input; no additional B download/account setup is needed.

## Latest follow-up: browser review and focus repair

On 2026-10-24 a separate Edge browser provided usable native accessibility and screenshots. Public initial layouts were inspected at emulated 1280×720 and 390×844 with no observed horizontal clipping. Public keyboard Play, advancing statistics/events, pause at 25:34 and an idle reset run 2 were observed. No new public live-model window was requested. This closes part of the earlier browser tooling gap; it does not complete expanded public insight/evidence/audience-mode or final-video acceptance.

The review found a pending-command focus defect (#16): native disabling removed focus from the Play/Pause button. `App.tsx` now keeps Play/Pause and Reset focusable during confirmation, marks them `aria-disabled`, marks the group `aria-busy`, and guards activation. Existing in-flight/idempotency logic remains unchanged; unavailable/error/ended-play states still use native blocking. Styling indicates busy buttons. The intermediate focus-only assets were `index-C39S-ICU.js` / `index-C-LzJ9lp.css`; the source-disclosure bundle above supersedes them.

On the local integrated app with provider explicitly `mock`, keyboard Space played and paused while focus stayed on the active button. Tab + Space reset to idle run 2 at 25:00 with an empty timeline and focus still on Reset. Build and 27 unit tests passed, as did the real B/C frontend consumer probe with zero model calls. The full record and reproduction commands are in `frontend/qa/browser-2026-10-24.md`; local ignored screenshots/accessibility evidence are under `.artifacts/frontend-browser-20261024/`.

The public service still serves the earlier bundle. The focus repair needs C review/merge and an explicit deployment of the selected main commit. No Render deployment or configuration change was performed for this follow-up. Previous public live results below belong to their recorded older build; they are not acceptance of this unpublished fix.

## Current public release

The [public match centre](https://matchmind-backend-preview.onrender.com) serves the integrated application, despite retaining its earlier backend-preview service name. The backend handoff's API-only description is historical.

- Existing Render service: `srv-dbdegcnavr4c739pockg`, free plan, Singapore, one instance; repository main, Docker root `matchmind`, release Dockerfile `deploy/Dockerfile.release`.
- Management API inspection found live deployment `dep-dbdhuvd9fdbs73b6pqv0`, source `36790b58ac0eee1884c59456397d593a8965f793`, finished at 2026-10-23 08:49:41 UTC.
- Main through `0df6144` adds documentation/CI and B's isolated research package/tests to the previously inspected executable. Its application behavior and default synthetic dataset are unchanged. A's pending focus/source-disclosure bundle is not yet deployed. No resource creation, secret/config change or plan upgrade was performed.
- Public health returned HTTP 200, contract `2.0.0`, mode `production`, `model_ready: true`. The root returned HTTP 200 and the A2/A3 bundle. Health alone is not live-model proof; the actual workflow below supplies that evidence.
- The temporary management-credential process was closed after inspection. No credential is included in source, reports or this handoff.

## Public acceptance observed

On 2026-10-23, B's existing `deploy.smoke_backend.probe` passed against the public host: health, data, stats, retry, play/pause, reset, old-run protection, invalid input and SSE snapshot reconnect. It requested no model job and left its own temporary replay idle for TTL cleanup. HTTPS verification remained enabled, using the project's certifi CA bundle.

The new manual `tests/frontend/public-probe.mjs` then passed one explicitly opted-in live analysis window (report start: 12:50:54 UTC). It uses the actual frontend HTTP consumer and reducers, rather than a second implementation of the API. The observed result was:

- Public JS and CSS were byte-identical to this checkout's reviewed assets: `index-BVwS-ZmQ.js` (SHA-256 `e256d4e8340f48066d167d4fdb510d0d8d8165037b9ced3abe4831cb45fdee13`) and `index-5U3MrlGQ.css` (`66417b321c10d9b4da63ca5490c49e3305705a452e7074cbbb43bb6ab694bef3`).
- Baseline match `MM-DEMO-01`, analysis window 1500–1650. Playback paused at 1710 while the workflow finished; the paused clock held. Snapshot statistics matched the public stats endpoint.
- Generation was `live_model`, provider `deepseek`, model `deepseek-flash`; verification was `passed` with method `agent_and_code`. This establishes actual cloud-to-model connectivity for this run, not a long-term reliability rate.
- The published metrics were 3 high recoveries, 2 linked shots, a 150-second window, possession 35/115 seconds and shots 2/0 (HOME/AWAY). Both distinct audience narratives belonged to the same insight; all 14 evidence references resolved to recorded events within that window.
- Nine actual trace records included validator, analyst, narrator and auditor activity, with two analyst attempts. The rejection text identified `draft 1 C5` and its unsupported numeric interpretation; it did not ambiguously reject a final published claim number. These traces do not prove every sentence or tactical causal claim correct.
- Retrying reset with the same key advanced the run exactly once to run 2, returned to 1500, and cleared insights/traces. A subsequent snapshot stayed empty. The frontend reducer rejected an injected late insight from the prior run.

The ignored report is `.artifacts/frontend-public-acceptance/result.json`, status `passed_live`. It records the actual generation, verification, narratives, metrics, trace durations and checks. No API key is required by the script or stored in the report. One window can entail several model calls; this is not a claim of one provider request. No second live window was run to improve the result.

Run the explicit command in `frontend/README.md` only for authorized manual acceptance. The script is excluded from ordinary tests and CI, exits before network access without `--origin ... --live-once`, bounds result observation, and does not retry a failed AI workflow. It does not simulate a real provider outage. Offline fallback, named model errors and malformed-message recovery remain covered by the existing checks below.

### Follow-up: actual public frontend SSE consumer

The next synchronization fetched origin with no newer main commit (`6012560`); PR #14 remained open with both CI jobs passed and the review requested from C. On 2026-10-23 at 13:08:35 UTC, `public-stream-probe.mjs --origin https://matchmind-backend-preview.onrender.com` passed using the actual frontend subscription and reducers:

- Selected 1x on a separate replay. The first incremental progress message arrived 2284 ms after the play request began. The accepted frames included 1 `match_state`, 1 `match_event` and 6 snapshots across connection, controls, explicit reconnection and reset. This is one observed delivery time, not a latency guarantee or load test.
- Paused at 1501 (25:01); the clock held. Explicitly closing and reopening the subscription produced a fresh snapshot with matching statistics and no duplicated recovered timeline events.
- The active stream supplied a new-run snapshot after reset, without substituting the HTTP control response for that test. Run 2 was idle at 1500, with empty insights, traces and timeline.
- No analysis window was reached and no insight or agent-status frame appeared; `model_job_requested` was false. The earlier live report was preserved and no additional live workflow was invoked.

The ignored transport report is `.artifacts/frontend-public-transport/result.json`. The Node-only `http-event-source.mjs` adapter was extracted from the existing offline backend probe and is shared by the two stream probes. It parses the HTTP wire stream; browser production code still uses native EventSource. The check explicitly opens a new connection and does not claim browser automatic retry or a real provider outage.

## Browser boundary and remaining work

The earlier in-app browser DOM/accessibility/native scroll attempts timed out; direct native control of the Codex app was denied by the tool's safety restriction. The separate Edge review on 2026-10-24 established initial public layouts and basic playback controls, as recorded above. Expanded public evidence/mode interaction and browser-native EventSource retry timing remain unverified. The live-model consumer probe uses HTTP snapshots; the separate stream probe establishes public wire-level incremental delivery and explicit reconnect recovery. These scopes remain distinct.

The earlier local A5 browser checks below remain valid local evidence. A/C still need the public keyboard/evidence/mode walkthrough and the final English video using C's revised `evaluation/DEMO_SCRIPT.md` from `6012560`. No final video has been recorded. C/integrator reviews and merges this acceptance PR; no automatic main merge is performed.

## Data accuracy follow-up

The representative asked for accurate data, team names and match information, then clarified the decision: prefer real data if it can support the platform; otherwise use synthetic data. The currently deployed fixture is still synthetic, with fictional Harbor FC / Mountain United. All public 3/2 analysis results above describe that fixture; `live_model` identifies AI execution, not a real football match.

A completed a read-only source and consistency audit. The 30-event validated synthetic dataset passed B's audit and the fixture reference recomputed its declared metrics. An actual StatsBomb historical match/event file was inspected, but public-API/external-model rights have not been established under its license. A second CC BY 4.0 Wyscout candidate's original download/metadata access returned HTTP 403, so its actual files were not validated. Neither was adopted or combined with generated events. `frontend/DATA_SOURCES.md` records exact source scope, dates, evidence and remaining requirements.

[Issue #15](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/15) assigns B/C the source/mapping/contract review needed for real ingestion. Current `Match.synthetic: true`, provenance checks and initial-state assumptions prevent an honest data-only swap. The official synthetic-data requirement also needs a submission-scope decision. A can render new source/date/club metadata after the contract is agreed. Until then the working public dataset remains explicitly synthetic under the representative's fallback condition, with no claim that real integration is complete.

## Latest verification

The integrated executable baseline passed `pnpm run typecheck`, all 27 frontend unit tests, frozen-file checks, and 434 Python tests plus 62 subtests. The first Python run could not bind loopback sockets inside the sandbox; rerunning the same suite with the required socket permission passed. That was an environment restriction, not a product failure. Main's subsequent demo-document-only commit did not change this executable baseline.

For this slice, `pnpm run test` again passed all 27 tests and `pnpm run build` passed TypeScript and Vite with unchanged asset hashes. `node --check tests/frontend/public-probe.mjs`, `.venv/bin/python tools/check_frozen.py` and `.venv/bin/python tools/check_scope.py --role A --base 601256039a5485120d42376c329e347144893441` passed (run the latter three from `matchmind`). Running the public probe without arguments returned the expected exit code 2 and preserved the existing report. Routine tests remain offline. No public browser or video completion is inferred from these checks.

After extracting the shared SSE adapter, `pnpm run test` still passed 27/27 and `pnpm run test:backend` passed against its real B/C child server, including all five normal message kinds, with zero model calls. The child server was stopped. The public stream script's syntax and no-argument guard also passed; without an explicit origin it returns exit 2 before network access.

## Previous A2/A3 delivery (merged PR #12)

The preceding frontend branch was `codex/frontend-integration`, task #10, starting at `bcaed0e` and synchronized through `31b2c56`. C merged it as `fb2c4b61fb325406c46f1d8630dfd6f1cd90ba32` on 2026-10-23. The following local validation describes that earlier delivery.

### Delivered

A1 is already on main (PR #3). PR #12 completed:

- A2: play/pause/reset and 1/2/5/10 speeds; all six named SSE kinds; complete snapshot replacement, authoritative match-state statistics, event timeline, real analysis traces and separate business/transport errors.
- A2 recovery: stable UUIDs for create/command retries, expected-run headers, abort/cleanup, sync after an unconfirmed control, old-run/duplicate/foreign-session guards. Reset clears insights, traces, events and selected evidence atomically. Repeated real narrator steps are preserved.
- A3: insight cards, local Casual/Analyst switching, metrics and claims, generation/verification labels, expandable evidence, selected event details, timeline highlighting and recorded pitch geometry. Selecting evidence does not seek. Future event details are not rendered before the replay clock reaches them.
- A4/A5 local coverage: real combined B/C app with offline C fallback, HTTP/SSE consumer integration, keyboard controls and evidence selection, 1280x720 desktop and 390px mobile checks. No horizontal overflow was observed at those sizes.

### Local validation of PR #12

From `frontend`:

```sh
pnpm run typecheck
pnpm run test
pnpm run build
pnpm run test:backend
```

From `matchmind`:

```sh
MATCHMIND_MODEL_PROVIDER=mock .venv/bin/python -m pytest tests -q
.venv/bin/python tools/check_frozen.py
.venv/bin/python tools/check_scope.py --role A --base 31b2c56
```

Results: TypeScript/build passed; 27 frontend unit tests passed; 433 Python tests and 62 subtests passed; frozen-file and role-scope checks passed. The additional frontend backend probe passed with 0 model calls. It launches a real B/C app with a 5x accelerated test clock, checks actual consumer requests/messages, and stops its own child.

The probe covers catalogue/event recovery, play/pause/speed, a frozen pause clock, the real rule fallback (3 high recoveries / 2 linked shots), both narrative fields and evidence IDs, comparison with server statistics, second-session isolation, fresh snapshot after reconnect, reset retry with the same operation key, and stale-run rejection. Named model/business errors and malformed stream recovery are covered by frontend unit tests; the probe does not claim a real provider outage or network-location test.

Browser checks against `ai.app:app`, dataset `data/extra/showcase/press`, provider explicitly `mock`:

- Initial 25:00 / 0:0 and connected feed; API failure/retry restored the page.
- Keyboard play/pause and 10x selection; pause held at 26:56 across subsequent checks.
- Actual fallback card appeared for 25:00–27:30 with 3 recoveries, 2 linked recoveries and code-only verification. Validator trace explicitly said no model was called.
- Keyboard audience switch changed the same card's narrative. Keyboard evidence selection highlighted the matching event row and pitch point; the clock stayed at 30:00.
- Keyboard reset returned to 25:00 / run 2 with zero insights and zero observed events.
- Desktop 1280x720 and mobile 390px layouts were inspected; 13 expanded evidence buttons fit without horizontal overflow.

Screenshots are local ignored artifacts under `.artifacts/frontend-integration/` (desktop, mobile and evidence view), not source assets or live-model evidence.

Environment: Node 24.11.1, pnpm 11.25.0, TypeScript 7.0.2; local Python 3.13.9. Backend/AI pinned requirements were installed into the existing project `.venv`. Python 3.12 remains the team's target and was not tested on this machine.

### Startup and production handoff

Use `frontend/README.md` for the exact commands. Development proxy target: `MATCHMIND_BACKEND_URL=http://127.0.0.1:8000`. The integrated process is `ai.app:app`, with provider explicitly `mock` for free offline verification. The dense press dataset was exercised locally; no default dataset was changed.

`pnpm run build` supplies `frontend/dist`, which B's existing `deploy/Dockerfile.release` expects. C's main tracks that directory for Git-based Render builds, so PR #12 included the rebuilt A2/A3 bundle and removed the old A1 hashed assets. Current entry assets are `index-BVwS-ZmQ.js` and `index-5U3MrlGQ.css`. The backend-only Blueprint template remains separate from the integrated release now running on the public service.

`MATCHMIND_SERVE_FRONTEND=1 MATCHMIND_MODEL_PROVIDER=mock .venv/bin/python -m deploy.release_check --profile integrated` passed all five assembly checks, with 0 model calls. The resulting same-origin production build was also opened through the real backend locally; this is separate from public Render acceptance.

The earlier offline frontend QA produced only rule-fallback labels. The separate public live workflow above supersedes that limitation for cloud/model connectivity, while retaining the outstanding public browser and video checks.
