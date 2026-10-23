# B synthetic showcase candidates

Generate/verify from `matchmind/`: `python -m data.generator.showcase --check`.
Rebuild only these managed B files with `--write`. Original frozen data is untouched.

Each child is a standalone audited dataset; do not combine their JSON metadata.

| Folder | Events | High recoveries / linked in 1500–1650 | HOME goals at1650 |
| --- | ---: | --- | ---: |
| press | 128 | 3 / 2 | 1 |
| delayed | 127 | 3 / 0 | 0 |
| quiet | 137 | 0 / 0 | 0 |

Set `MATCHMIND_DATA_DIR=data/extra/showcase/press` for B-only replay. The default
remains `data/extra/validated-demo`. The integrated C path must pass
`python -m deploy.adapter_check` before enhanced data is adopted.
The defect measured at C commit 02228b8 is fixed on main; the recorded gate is
12/12 normal requests plus 3/3 corruptions refused. The findings file is historical.

These are original CC0-1.0 scripted excerpts with seeded coordinate variation,
connected pass points, consistent scoring and independent expected states. They
are not a model, tracking dataset, real match sample, xG estimate or calibrated
football simulator. All 22 roster members appear in events; no continuous
off-ball locations are invented. See each PROVENANCE.json for exact hashes and limits.
