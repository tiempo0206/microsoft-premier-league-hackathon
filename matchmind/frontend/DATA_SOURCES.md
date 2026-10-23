# Match data accuracy and adoption status

Checked on 2026-10-23. The representative's policy is to prefer real data when it can support the platform, otherwise use a clearly identified synthetic fallback. The current public application still uses that fallback. A real model generating text does not make its input match a real match.

## Current public match

`data/extra/validated-demo` is the B-owned `fixture-2.0.1` derivative of the original synthetic fixture. Its provenance explicitly identifies fictional teams **Harbor FC** and **Mountain United**, a first-half 25:00–30:00 excerpt, event positions, and no continuous player tracking. They must not be presented as Premier League clubs or an actual fixture. There is no real match date or current-season live feed behind this dataset.

The read-only B dataset audit passed: 30 events, matching source/output hashes, roster/scoring-shot relationships and expected states. The fixture reference independently recomputed the declared 1500–1650 metrics: 3 high recoveries, 2 linked shots, possession 35/115 seconds and shots 2/0 (HOME/AWAY). These are consistent **synthetic** statistics, not independently observed Premier League facts. Goal events determine score; shots are counted separately. Evidence positions do not establish off-ball movement or tactical causality.

Provenance: `data/extra/validated-demo/PROVENANCE.json`, match metadata, events and `expected.json`; original source `data/fixtures/PROVENANCE.json`. Contract 2.0.0 fixes `synthetic` to true and the frontend requires it.

## Real-data candidates reviewed

| Candidate | Evidence actually checked | Adoption status |
| --- | --- | --- |
| [StatsBomb/Hudl open-data](https://github.com/hudl/open-data/tree/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb) | Actual source bytes at the pinned commit: match 3749493, Arsenal–Everton on 2003-08-16, Premier League 2003/2004, final score 2–1; 3057 event records, no duplicated event IDs. The first-half 25:00–30:00 window has 79 events: 28 passes, 2 Ball Recoveries and 1 shot among other types. All 31 candidate pass/shot/recovery records have inspected IDs, times, team/player/possession and location fields. | Historical source technically worth evaluating, **not integrated**. Its [license](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf) restricts third-party provision, commercial exploitation and modification/redistribution (1.2.1, 1.2.2, 7), and requires attribution (1.4). Permission covering the public event API and external model processing has not been established. |
| [Pappalardo/Massucco Wyscout collection](https://doi.org/10.6084/m9.figshare.c.4415000.v5) | The [authors' paper](https://doi.org/10.1038/s41597-019-0247-7) documents historical 2017/2018 English event records under CC BY 4.0. | Candidate only. Original Figshare page and public metadata API returned HTTP 403 in this environment. Original event-file bytes, checksum and field coverage were not verified. No unverified mirror was substituted. |

The StatsBomb profile is a single inspected match; it does not establish current-season coverage, a live service, or a successful platform integration. Its real events must not be augmented to force the synthetic demo's 3/2 trigger. The source audit used no model calls and sent no provider event records to a model. Local ignored evidence and a companion notebook are under `.artifacts/frontend-data-audit/`; third-party event files are not committed or served by this change.

## Requirements before switching the public dataset

Track the cross-role work in [issue #15](https://github.com/tiempo0206/microsoft-premier-league-hackathon/issues/15). B verifies source rights/access, original identities, date/season, starting score and an accurate provider mapping. C versions the frozen contract with A/B review; A then renders the agreed provenance and historical/synthetic labels. No real input may be labelled synthetic to pass the existing validator.

The mapping must preserve the original period clocks, outcomes, own-goal handling, coordinates/attack direction and possession semantics. Missing facts remain unavailable. Derived possession estimates and heuristic detections must be labelled as derived; no generated recoveries, player motion or event positions may be inserted into a real match. Verify events against published metadata and reconcile full-match and clip statistics before public acceptance.

The [hackathon rules §4.7](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md#47-use-of-footage) require synthetic football-realistic data. A real historical mode therefore also needs an explicit submission-scope decision from the integrator/representative. The current fallback remains plainly synthetic while source access/rights, mapping, contract and submission requirements are unresolved. This is not a conclusion that real football data does not exist.
