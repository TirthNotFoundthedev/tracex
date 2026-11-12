# data-kit

Synthetic data generator and ground truth for TraceX. Spec: [docs/specs/data-kit.md](../docs/specs/data-kit.md). Kit version `data-kit/1.0`. Everything is synthetic; generated output is never committed (`data-kit/out/` is git-ignored).

## Generate

Python 3.12, standard library only. From the repository root:

```
cd data-kit
python -m datakit generate --tier small
```

Output goes to `data-kit/out/small/` (about 4 MB, a few seconds). Options:

| Flag     | Default      | Meaning                                                                                     |
| -------- | ------------ | ------------------------------------------------------------------------------------------- |
| `--tier` | `small`      | `small` (CI, 62 planted + 60 noise cases) or `demo` (62 + 600, about 70 MB, about a minute) |
| `--seed` | `20260401`   | Kit seed. The golden hashes are for the default.                                            |
| `--out`  | `out/<tier>` | Output directory                                                                            |

Same kit version and seed give byte-identical output. `out/<tier>/manifest.json` lists every file with its sha256; its own sha256 is the golden hash committed in `golden/<tier>.sha256`.

`python -m datakit seed` rewrites `seed/case_assignments.csv` from `seed/users.json`.

## Score an engine result

`python -m datakit score` is the stdlib reference scorer of spec section 8.3 (task G-16). It reads `ground_truth.json` and an engine result and reports per acceptance case pass or fail, missed links, wrong links and forbidden-trap hits:

```
python -m datakit score --ground-truth out/small/ground_truth.json --result engine_result.json [--json]
```

Exit code 0: every gating check passes. 1: a gating check failed. 2: a file is unreadable or not valid input. `--json` prints the report (`score-report/1`) instead of the text summary.

**Input format.** The engine result is a JSON document described by [schema/engine_result.schema.json](schema/engine_result.schema.json) (`engine-result/1`). It is independent of the engine's internal types and of the API contract; the engine side writes an adapter that produces it.

| Field                           | Meaning                                                                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `batches_loaded`                | `["b01"]` or `["b01","b02"]`: batches matched before this result was taken. Links with a later `batch_min` are skipped.             |
| `harness_applied`               | Ids of ground-truth `scenarios[]` whose human steps were applied (for example `HS-AC13`). Links naming another harness are skipped.  |
| `entities[]`                    | `id` (opaque), `type`, `raw_text`, `normalized`, `mentions[]` of `{case_id, file, line}`                                             |
| `edges[]`                       | Every stored SAME_AS edge in any state: `a`, `b` (entity ids), `state`, `band`, `score`, `gates_failed[]`, `evidence_kinds[]`, `sources[]` |
| `stats.oversized_block_count`   | Optional, reported only                                                                                                              |

`state` is AUTO, SUGGESTED, CONFIRMED, REJECTED, UNDONE or WITHDRAWN; `band` is HIGH, MEDIUM or LOW; `score` is a number or a decimal string; `gates_failed` items are gate ids (`"G1"`) or `{gate, template_key}` for G6, and compare as a set; `sources` are every `(case_id, file, line)` the edge's explanation cites. A pair the engine scored Low and did not store has no edge.

**Mapping** (spec 8.1). Engine entities are matched to ground truth by mention lines, never by id: PERSON and ORG on a shared `(case_id, file, line, type)` plus equal `raw_text`; PHONE, ACCOUNT and VEHICLE on a shared mention plus equal `normalized`. An engine entity that matches any member of a `within_case` group counts for the whole group.

**Checks.**

| Check | Rule in the scorer                                                                                                                                                                      |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1    | Each applicable expected link has an edge on its pair with the stated `state`, `band` and gate set. A state of CONFIRMED is accepted in place of AUTO or SUGGESTED for a link with an applied harness. With several edges on a pair, the best one is judged. Missing: `missed_links`; mismatch: `wrong_links` (kind `state`, `band`, `gates`). |
| S2    | `exact` scores equal by decimal equality (kind `score`); `band` scores are recorded under `reported.band_mode_scores`.                                                                  |
| S3    | `ANY_EDGE` non-links have no edge in any state; `AUTO` non-links have no AUTO edge (also for a SUGGESTED link that carries a `trap`). Hits are `forbidden_hits`.                         |
| S4    | Every AUTO edge lies inside one `cross_case` group (or inside one within-case group); otherwise `wrong_links` kind `closed_world`. An engine entity with no ground-truth match counts as outside. |
| S5    | Every `cited_lines` entry is among the edge's `sources`, and no source is outside the two end cases (kind `provenance`).                                                                |
| S6    | Reported, never gating: noise recall, SUGGESTED edges on non-link pairs (total and per 100 persons), `oversized_block_count`.                                                          |

An acceptance case is `pass` when something about it was checked and nothing failed, `fail` when any of its links or non-links failed, and `not_evaluated` when only behavioural scenarios cover it. Expected links that apply to a later batch, to a harness that was not applied, or that a later batch supersedes (SF-07) are listed under `skipped`.

## Layout

| Path                              | What                                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| `datakit/`                        | Generator (rng, planted fixtures, noise, rendering, ground truth)                                   |
| `pools/`                          | Name, place and phrase pools; `excluded_tokens.txt` lists planted name tokens that noise never uses |
| `schema/ground_truth.schema.json` | JSON Schema of `ground_truth.json`                                                                  |
| `schema/engine_result.schema.json` | JSON Schema of the engine result the scorer reads                                                  |
| `seed/`                           | Jurisdictions, seeded users (no passwords), case assignments                                        |
| `golden/`                         | Committed manifest hashes, one per tier                                                             |
| `tests/`                          | Acceptance tests G-01..G-16 of the spec                                                             |
| `out/<tier>/` (git-ignored)       | `batches/b01`, `batches/b02`, `cases.csv`, `ground_truth.json`, `manifest.json`, `SYNTHETIC.txt`    |

## Checks

CI does not run these yet (see the PR description). Locally, from `data-kit/` with the backend environment (`cd ../backend && uv sync --frozen`):

```
uv run --project ../backend ruff check .
uv run --project ../backend ruff format --check .
uv run --project ../backend mypy
uv run --project ../backend pytest
```

Changing a pool file or a planted value bumps `KIT_VERSION` in `datakit/generate.py` and regenerates `golden/*.sha256` in the same PR:

```
python -m datakit generate --tier small --out /tmp/small   # then sha256 of /tmp/small/manifest.json
```

## Seeded users

`seed/users.json` carries no password. Each user's password comes from the environment variable named in its `password_env`: `TRACEX_SEED_PASSWORD_<USERNAME>` (ASHA, ISHA, JATIN, KIRAN, OMKAR, BHARAT, ESHA, GITA, CHARU, FARID, LATA, DEEPAK, MEENA, HARI).
