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

## Layout

| Path                              | What                                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| `datakit/`                        | Generator (rng, planted fixtures, noise, rendering, ground truth)                                   |
| `pools/`                          | Name, place and phrase pools; `excluded_tokens.txt` lists planted name tokens that noise never uses |
| `schema/ground_truth.schema.json` | JSON Schema of `ground_truth.json`                                                                  |
| `seed/`                           | Jurisdictions, seeded users (no passwords), case assignments                                        |
| `golden/`                         | Committed manifest hashes, one per tier                                                             |
| `tests/`                          | Acceptance tests G-01..G-15 of the spec                                                             |
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
