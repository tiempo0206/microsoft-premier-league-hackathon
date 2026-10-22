# Football data sources and open-source libraries — what we can actually reuse

Compiled by Role C on 2026-10-23. Every row was checked against the GitHub API
(`evaluation/scan_football_oss.py`, raw output in `football_oss.json`), so the star counts,
licence identifiers and last-push dates are records rather than recollection.

The question this file answers is narrow: **of the open football ecosystem, what can this
project reuse without breaking the competition rules or its own honesty claims?**

---

## 1. The licensing problem comes first

Official rules §4.4 forbid third-party trademarks and copyrighted material without permission,
and §4.7 specifically addresses the use of footage. Several of the best-known football datasets
are *not* freely redistributable, which matters more for us than for a research notebook
because **our repository must become public before submission**.

| source | what it is | the licence reality | usable by us? |
| --- | --- | --- | --- |
| `statsbomb/open-data` (3.7k★) | Real event data for selected competitions | GitHub licence field is `NOASSERTION`; the data itself ships under StatsBomb's own public-data agreement — attribution plus non-commercial restrictions, and it is *their* data, not ours | **No.** Do not copy events into our repo. Reading it locally to sanity-check a generator is a different act from redistributing it, and even that should be agreed with the team |
| `statsbomb/statsbombpy` (747★) | Client for the above | **No licence file at all** | No. An unlicensed dependency in a public repo is a liability |
| `probberechts/soccerdata` (2.1k★) | Scrapers for Club Elo, FBref, ESPN, Football-Data.co.uk and others | `NOASSERTION`; also, scraping terms of the upstream sites are not ours to grant | No for shipped data; useful as a reference for what fields exist |
| `openfootball/football.json` (1k★) | Plain-JSON fixtures and results | **CC0-1.0** | Yes, trivially — but it is results only, with no events, so it cannot drive our pipeline |
| `ML-KULeuven/socceraction` (821★) | Event data → SPADL, expected threat, VAEP | **MIT** | Yes for code. Not a data source |
| `PySport/kloppy` (565★) | One interface over many event/tracking providers | **BSD-3-Clause** | Yes |
| `andrewRowlinson/mplsoccer` (550★) | Pitch plotting for matplotlib | **MIT** | Yes |
| `Alek050/databallpy` (106★) | Tracking/event synchronisation | **MIT** | Yes, if we ever do tracking |
| `eddwebster/football_analytics` (2.8k★) | A curated link collection | `NO LICENCE`, but it is a list of links, which we would read rather than copy | Reference only |

**Conclusion on data.** This hackathon's premise is synthetic events, and the rules ask us to
create or extend synthetic football-realistic data. Shipping StatsBomb or Wyscout events would
be both a licensing problem and a category problem. The right use of those datasets is
**calibration during development, described in prose, with no rows committed** — exactly what
GamePulse does when it says its simulator totals were checked against 1,446 real matches while
only aggregated statistics were published.

---

## 2. What we could genuinely reuse, in order of value

### 2.1 `socceraction` (MIT) — the highest-value borrow, and we should borrow the *idea*

Its contribution is a canonical action representation (SPADL) plus two valuation models:

* **expected threat (xT)** — a 16×12 grid, value iteration over move/shot transitions, giving
  the threat a pass or carry adds;
* **VAEP** — values each action by the change in probability of scoring and conceding.

**Why this matters for us.** Our `Metrics` are seven counts. A viewer asking "why did *that*
pass matter" gets no answer, because a count cannot rank an action. xT is the cheapest honest
way to rank a pass: it is a published, inspectable model with a fixed grid, and a rival already
ships an xT grid as its momentum input.

**What we would take.** The grid dimensions and the value-iteration structure, reimplemented in
plain Python over our own event schema, and labelled as a heuristic with the formula shown. The
library itself expects real provider data and a pandas pipeline; adding it as a dependency for
one grid would be heavier than the code it replaces.

**What we must not do.** Claim our number is "xT" if we change the grid or the training data.
Call it "threat added (heuristic, socceraction-style grid)" and cite the paper.

### 2.2 `kloppy` (BSD-3) — an adapter pattern, not a dependency

kloppy's real lesson is structural: **one internal event model, many provider adapters**, so the
engine never learns a provider's quirks. We already do this in miniature — `AnalysisRequest`
carries a neutral event list — and GamePulse goes further by running public Wyscout and Sportec
data through the identical contract.

**Concrete borrow.** If we ever want a second data source, add an adapter that emits our
`Event` shape and nothing else. Do not let a second schema into the engine.

### 2.3 `mplsoccer` (MIT) — a real dependency, worth it only if the frontend slips

It removes a day of pitch-plotting work, and its shot maps and radars are what a broadcast
viewer recognises. But it is a *matplotlib* library producing static images, while our viewer
needs an interactive SVG pitch. Reuse is worth it only for the pre-rendered images in the video
or for a "match report" page. **Not before A2/A3 exist.**

### 2.4 `databallpy` (MIT) — not now

It solves tracking-to-event synchronisation, which we do not have because we have no tracking.
Listed for completeness, not recommended.

---

## 3. What we should copy conceptually without adding a dependency

| idea | where it comes from | how it lands here |
| --- | --- | --- |
| Canonical action model, provider-agnostic | kloppy, socceraction/SPADL | keep `AnalysisRequest` as the only internal shape; adapters emit it |
| Value an action by the change it causes | VAEP, xT | rank passes by threat added rather than counting them |
| Validate synthetic data against real totals | GamePulse's realism tab | `evaluation/fixture_qualify.py` already encodes thresholds; the missing step is *comparing* those totals to published league averages. That comparison is a table in a doc, not committed data |
| Pitch control / space valuation | several community notebooks | out of scope; needs player positions we deliberately do not model |
| Plain CC0 fixtures for smoke tests | `openfootball/football.json` | could give us realistic fixture names and dates for the catalogue, no events needed |

---

## 4. Things I looked for and did not find

Recorded so nobody repeats the search:

* `koenvoetbal/floodlight` — 404. If a project by that name exists it is under a different
  owner; do not cite it from memory.
* `deepsport-analytics/deepsport`, `UnravelSports/SoccerMap`, `karangandhi1/football-analytics`,
  `mfyz/expected-goals`, `soccer-analytics/soccer-analytics` — all 404 at the names I tried.
* A maintained, licence-clean, event-level open dataset that we could ship. There is not one.
  This is the honest reason our data story rests on a generator plus published calibration.

---

## 5. The recommendation in one paragraph

Do not add a football dependency. Take the **xT grid idea** from `socceraction` and implement it
in plain Python over our own events, labelled as a heuristic. Take the **adapter discipline** from
`kloppy` and keep `AnalysisRequest` the only internal shape. Keep `mplsoccer` in reserve for
pre-rendered assets. Use real datasets only for **calibration described in prose with no rows
committed**, because the repository must become public and StatsBomb's data is not ours to
redistribute. If the team wants a real-data path for the credibility argument, the safe route is
an adapter plus a documented "we validated our generator totals against published league
averages", not a checked-in dataset.
