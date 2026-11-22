# STATE

Last updated: 2026-11-22, end of session S3. P3 is complete, merged into `main` (PR #38, owner's OK) and tagged `m3-engine`. P4 starts in a new session.

## Done
- PLAN.md approved by the owner (2026-11-11). Governance files in place.
- Private repo github.com/TirthNotFoundthedev/tracex. `main` protected (PR + CI checks backend, frontend).
- P0 foundation merged (PR #4), tag `m0-foundation`. PR #7 merged: self-hosted Noto fonts, Lucide, shared i18n with Hindi parity check, compose smoke job.
- P1 specs merged, tag `m1-specs`: `docs/specs/engine-matching.md` (Iyer), `api-access-control.md` + `api-audit-log.md` (Khan, gated by Dutta), `DESIGN_RULES.md`, `design-flows.md`, tokens, specimen (Sen).
- S1 merged with the owner's OK (PRs #12, #10, #11, #9, #13), `main` green, tag `m1-contracts` pushed: matching-spec errata (Iyer), `docs/specs/data-kit.md` (Bose, hired), `contracts/` + `docs/architecture.md` + access/audit spec amendments (Khan; Iyer approved, Dutta's security gate passed on the third round), review-queue filter Waiting / Rejected / Undone with Reopen, Approvals page and real-font specimen (Sen). Decisions D43-D49.
- S2 merged (PRs #17, #19, #16, #18, #15), `main` green: `data-kit` CI job + seed placeholders + Prettier pin (Rao), data kit generator small + demo tiers with golden hashes verified on Linux (Bose, 2.1), spec errata from the reviews (Iyer), parsers + extraction + normalization (Naidu, 2.2; ownership from closed patterns, D51). Decisions D50-D54.
- Later in S2, merged with the owner's OK by number (PRs #22, #24, #23, #20, #26, #25, #21), `main` green: Neo4j service in backend CI with Neo4j pinned to `5.26.12-community` and root devDependencies exact-pinned (Rao); extractor fix for role word + `M/s` and the raw_text rule (Naidu); reference scorer `python -m datakit score`, `engine-result/1` schema, G-09 isolation, ground-truth bare-name `raw_text` (Bose); noise persons in one case have distinct names, G-17 (Bose); spec errata 2/3 (Iyer); per-case graphs, order-independent within-case dedupe, Neo4j store and `docs/specs/engine-graph.md` (Bose, 2.3). The 9 Neo4j tests run in GitHub CI (822 backend tests, none skipped). Decisions D55-D56.
- PR #28 merged with the owner's OK, tag `m2-slice`: Tier 1 matching, scoring skeleton (composite score, bands, gates), SAME_AS link stores (in-memory and Neo4j), runs with the D37 rerun rules, human decisions as engine calls, explanation payload builder, `engine-result/1` adapter and the end-to-end kit gate (Iyer, 2.4; Khan approved after one fix round). 1006 backend tests in CI, Neo4j path included. Decisions D57.

## In progress
- Nothing running. P3 merged into `main` by PR #38 with the owner's OK ("Yes, merge to main"); tag `m3-engine` on the merge commit. Branch `opus-5.5-phase-2-attempt-1` is kept as history.

## Session S3 (2026-11-21), on branch `opus-5.5-phase-2-attempt-1`
- Merged into the branch after review and green CI (D58): #31 Tier 2 (Naidu; Iyer review, phonetic floor rejected, D59), #32 Tier 3 + scorer `--defer` + kit 1.1 (Bose; Iyer approved, kit fixes K1-K3, D60), #33 case district from the FIR header (Bose, D61), #35 rarity needs a spelling match (Naidu, into #34), #34 P3.3 run context for providers, PER_NEAR_PHONE, MULTI_USER by `name_sim`, every AC with engine tests (Iyer; Fable reviewed), #36 scorer ignores refused steps + Neo4j district test (Bose), #30 FastAPI backend: Postgres model + migrations, DB roles, scrypt + JWT with refresh rotation, policy on all 57 routes, hash-chained append-only audit log, engine bridge with outbox and reconcile, compose with `migrate` service (Khan; Dutta APPROVE after one fix round, D62).
- Last CI on the full branch (PR #30 head after update): backend, data-kit, frontend, smoke all green.

## Where the engine stands after P3
- AC-01 worked scenario: three AUTO phone links at 100 and the Irfan person link AUTO 85.5 with real Tiers 1-3.
- `waiting.py` FAILING is empty for b01 and b02; the reference scorer is `ok: true` with nothing deferred; S3 non-links, S4 closed world and integrity, and trap checks hold. With HS-AC13 applied, EL-FX13-Q1Q2 is judged and passes.
- `default_providers()` = Tier2Provider, Tier3Provider; no catalogue item is pending.
- Known limits (safe side): ages compared as written (no case dates); oversized Tier 2 blocks skipped but not counted in the run record.

## Next
1. Before the demo (P6) at the latest, Khan: Dutta N3 (an empty engine store on restart must not mark every link WITHDRAWN), item 12 (missing audit anchor counts as BROKEN once the log has more than one row; verify cached, re-run at most once a minute; every route except `/health`, `/ready`, `POST /audit/verify` answers 503 while broken), N2 (refuse to start on `dev-only` secrets unless `TRACEX_ALLOW_DEV_SECRETS=1`), N1 (document the single-DB-login four-eyes limit; nightly verify matches each APPROVED change to its CHANGE_APPROVED audit row), nightly audit verify, runtime explanation-schema validation (minor).
2. P4 apps as in PLAN.md §5, in a new session. Contract consumers note: `CaseRef`, `EntitySummary`, `LinkSummary` now have open `*Base` schemas.

## Carried forward (not blocking)
- Sen: Hindi strings need a native-speaker review; checklist item 16 must be repeated on the real app screens; queue and approval i18n keys are listed in design-flows for the screen builders to add in both languages. A string for "a matching run is in progress, try again shortly" (409 RUN_IN_PROGRESS, D49) is needed in both apps.
- Rao: `smoke` and `data-kit` as required checks (ask the owner first). Workspace packages under `apps/*` and `packages/*` were not audited for range pins.
- Naidu follow-ups (safe-side misses): family-note owners in parentheses, the Devanagari pronoun "उसका नंबर", a Devanagari name swallowing a following verb, a name directly after a locality with no comma, `M/s.` at a sentence end turning the next sentence's name into an ORG, landlines in CDR rows, `OrgMention` has no aliases field, a bare two-word suffix name without `M/s` ("Om Traders") reads as a PERSON. PR #23's final suffix-rule tightening was merged without a second look by Iyer (output on the small tier was identical).
- Bose: G-10 public-figure name check before demo readiness; replacing an uploaded case is a later Backend + Graph slice (files are immutable until then).
- Bose: G-10 public-figure name check before the demo-readiness checklist.

## Blockers
- None.

## Working notes for Fable
- Merging: sub-agents cannot run `gh pr merge` (permission check). Fable may merge only PRs the owner has explicitly OK'd by number; ask in one batch at each milestone. Force-push is blocked too: after a squash merge, rebase a stacked branch and push it as a new branch + new PR.
- Branch every PR from `main`, never from another open PR.
- Agents share one GitHub account, so GitHub approvals are not used; reviews are PR comments.
- Agents do not persist across sessions: re-hire each role with its ROSTER card and pointers to its merged spec.
- Local port 8000 is in use on this machine; use `API_PORT=18000` for local compose runs.
- A stray `python -m http.server` on 127.0.0.1:8765 may still be running from the design specimen check.
- `smoke` is not yet a required check on `main`; ask the owner before changing branch protection, then have Rao add it.
- Prettier is declared as `^3.3.3` in package.json (the lockfile pins it); CODEBASE_RULES wants exact pins. Give to Rao with his next task.
- Reviews: resume the same agent with SendMessage for re-reviews and fix rounds; it keeps its context and is much cheaper than a new hire.
- Do not `cd` into an agent worktree from the main session; use `git show origin/<branch>:<path>`.
- Usage in S2: the 5-hour limit was hit four times mid-task (agents fail with a rate-limit error and keep their work; resume them with SendMessage after the reset). Roughly one window buys two Sonnet authors with fix rounds plus four or five Opus review passes. Checkpoint STATE.md before a window reaches about 80%.
- Opus agents with a very large context stalled repeatedly ("no progress for 600s"). What worked: tell the agent to push the branch at once, write one small file at a time, commit and push after each, put timeouts on commands, and open a draft PR rather than hold work back. Prefer a fresh hire per task over resuming an agent past about 400k tokens.
- A subagent whose branch was merged and deleted cannot be resumed (its worktree is gone): hire a fresh one with the role card.
- Merges: keep asking the owner by PR number in one batch (D53); the owner answers quickly with "yes, merge them". Use `gh pr update-branch <n>` to bring a PR up to date with main before its final CI check. `gh pr merge` can fail with a transient GraphQL error: check the PR state and retry.
- Always re-run a PR's CI on top of current main before merging when other PRs landed since its review: #21 passed alone and failed in combination (D56).
- Leftover Neo4j containers from reviews may be running (`docker ps`); agents were denied permission to remove containers that were not theirs.
- Review pattern that worked: when adversarial review keeps finding holes in a deny-list, switch the author to an allow-list (closed patterns) instead of another patch round.
- Authors built against specs without seeing each other's output; have the reviewer run one against the other before approving.

- S3: a `gh pr checks --watch | tail` chain does not stop on a network drop; #36 merged while data-kit was still pending (it then passed). Read the check result itself before every merge.
- S3: the network to GitHub dropped twice and both running agents stalled ("no progress for 600s"); resume them with SendMessage, their pushed work survives.
- S3: an agent that keeps re-sending the same hand-back while "waiting on its own background work" can be stopped with TaskStop once its work is pushed.

## Open questions for the owner
- OK to make `smoke` and `data-kit` required checks on `main`?

## Resume prompt (paste into a new session in this folder)
> You are Fable, CEO / Project Lead / CTO of TraceX. Read STATE.md, then PLAN.md §4–5, ROSTER.md and PROTOCOLS.md. Do not re-read the source document or PPT unless a task needs a section. Check usage, then continue from "Next" in STATE.md, delegating to the roles in ROSTER.md. Keep updates to me brief; checkpoint STATE.md, commit and push before limits run out.
