# STATE

Last updated: 2026-11-12, late in session S2. P2.1, 2.2 and 2.3 are merged with the reference scorer; 2.4 (Tier 1 matcher) is being built; no PR is open except this checkpoint.

## Done
- PLAN.md approved by the owner (2026-11-11). Governance files in place.
- Private repo github.com/TirthNotFoundthedev/tracex. `main` protected (PR + CI checks backend, frontend).
- P0 foundation merged (PR #4), tag `m0-foundation`. PR #7 merged: self-hosted Noto fonts, Lucide, shared i18n with Hindi parity check, compose smoke job.
- P1 specs merged, tag `m1-specs`: `docs/specs/engine-matching.md` (Iyer), `api-access-control.md` + `api-audit-log.md` (Khan, gated by Dutta), `DESIGN_RULES.md`, `design-flows.md`, tokens, specimen (Sen).
- S1 merged with the owner's OK (PRs #12, #10, #11, #9, #13), `main` green, tag `m1-contracts` pushed: matching-spec errata (Iyer), `docs/specs/data-kit.md` (Bose, hired), `contracts/` + `docs/architecture.md` + access/audit spec amendments (Khan; Iyer approved, Dutta's security gate passed on the third round), review-queue filter Waiting / Rejected / Undone with Reopen, Approvals page and real-font specimen (Sen). Decisions D43-D49.
- S2 merged (PRs #17, #19, #16, #18, #15), `main` green: `data-kit` CI job + seed placeholders + Prettier pin (Rao), data kit generator small + demo tiers with golden hashes verified on Linux (Bose, 2.1), spec errata from the reviews (Iyer), parsers + extraction + normalization (Naidu, 2.2; ownership from closed patterns, D51). Decisions D50-D54.
- Later in S2, merged with the owner's OK by number (PRs #22, #24, #23, #20, #26, #25, #21), `main` green: Neo4j service in backend CI with Neo4j pinned to `5.26.12-community` and root devDependencies exact-pinned (Rao); extractor fix for role word + `M/s` and the raw_text rule (Naidu); reference scorer `python -m datakit score`, `engine-result/1` schema, G-09 isolation, ground-truth bare-name `raw_text` (Bose); noise persons in one case have distinct names, G-17 (Bose); spec errata 2/3 (Iyer); per-case graphs, order-independent within-case dedupe, Neo4j store and `docs/specs/engine-graph.md` (Bose, 2.3). The 9 Neo4j tests run in GitHub CI (822 backend tests, none skipped). Decisions D55-D56.

## In progress
- Iyer (Opus, fresh hire this session): 2.4 Tier 1 + scoring skeleton + SAME_AS on branch `feat/engine-tier1-matching` (own worktree). Cut off once by the 5-hour limit and resumed; told to commit and push early. No PR yet when this was written. If the agent cannot be resumed, hire a fresh Iyer and point it at that branch.

## Next
1. When Iyer's PR is up: Khan (Sonnet, hire fresh with the ROSTER card) reviews it as integration reviewer: engine API the Backend will import, transition and run records against `docs/architecture.md`, explanation payload against `contracts/explanation.schema.json`, no Postgres or access knowledge in the engine. Fable reads the gate: Tier-1-reachable acceptance cases pass S1; zero-tolerance checks (S3, S4, traps) hold over the whole kit; worked scenario AC-01 links end to end; every other AC is listed with the tier it waits for.
2. Owner OK by PR number, merge, tag `m2-slice`, update this file.
3. P3 as in PLAN.md §5: 3.1 Tier 2 (Naidu, Iyer reviews), 3.2 Tier 3 (Bose, Iyer reviews), 3.3 composite + review queue + undo + clusters (Iyer), 3.4 API/auth/access/audit (Khan) in parallel, 3.5 security gate (Dutta).

## Carried forward (not blocking)
- Dutta, for P3 implementation: a rejected transition record's Neo4j edge must be reverted, not only alerted; reword the Reconciliation text in `docs/architecture.md`; U47-U54 and A49-A53 must become tests against the running API.
- Sen: Hindi strings need a native-speaker review; checklist item 16 must be repeated on the real app screens; queue and approval i18n keys are listed in design-flows for the screen builders to add in both languages. A string for "a matching run is in progress, try again shortly" (409 RUN_IN_PROGRESS, D49) is needed in both apps.
- Rao: `smoke` and `data-kit` as required checks (ask the owner first). Workspace packages under `apps/*` and `packages/*` were not audited for range pins.
- Naidu follow-ups (safe-side misses): family-note owners in parentheses, the Devanagari pronoun "उसका नंबर", a Devanagari name swallowing a following verb, a name directly after a locality with no comma, `M/s.` at a sentence end turning the next sentence's name into an ORG, landlines in CDR rows, `OrgMention` has no aliases field, Devanagari legal suffixes are not stripped by `normalized`, a bare two-word suffix name without `M/s` ("Om Traders") reads as a PERSON. Devanagari-vs-Roman transliteration differences ("saksena" vs "saxena") are a P3 comparator matter. PR #23's final suffix-rule tightening was merged without a second look by Iyer (output on the small tier was identical).
- Bose: the noise-name pass in `data-kit/datakit/noise.py` ends silently after 100 passes if it never converges (G-17 would catch it; an explicit error would be clearer); G-10 public-figure name check before demo readiness; replacing an uploaded case is a later Backend + Graph slice (files are immutable until then). `KIT_VERSION` was not bumped for the G-17 change.
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
- Usage in S2: the 5-hour limit was hit twice mid-task (agents fail with a rate-limit error and keep their work; resume them with SendMessage after the reset). Roughly one window buys two Sonnet authors with fix rounds plus four or five Opus review passes. Weekly was 69% late in S2. Checkpoint STATE.md before a window reaches about 80%.
- A subagent whose branch was merged and deleted cannot be resumed (its worktree is gone): hire a fresh one with the role card.
- Merges: keep asking the owner by PR number in one batch (D53); the owner answers quickly with "yes, merge them". Use `gh pr update-branch <n>` to bring a PR up to date with main before its final CI check. `gh pr merge` can fail with a transient GraphQL error: check the PR state and retry.
- Always re-run a PR's CI on top of current main before merging when other PRs landed since its review: #21 passed alone and failed in combination (D56).
- Leftover Neo4j containers from reviews may be running (`docker ps`); agents were denied permission to remove containers that were not theirs.
- Review pattern that worked: when adversarial review keeps finding holes in a deny-list, switch the author to an allow-list (closed patterns) instead of another patch round.
- Authors built against specs without seeing each other's output; have the reviewer run one against the other before approving.

## Open questions for the owner
- OK to make `smoke` and `data-kit` required checks on `main`?

## Resume prompt (paste into a new session in this folder)
> You are Fable, CEO / Project Lead / CTO of TraceX. Read STATE.md, then PLAN.md §4–5, ROSTER.md and PROTOCOLS.md. Do not re-read the source document or PPT unless a task needs a section. Check usage, then continue from "Next" in STATE.md, delegating to the roles in ROSTER.md. Keep updates to me brief; checkpoint STATE.md, commit and push before limits run out.
