# STATE

Last updated: 2026-11-13, end of session S2. P2 is complete and tagged `m2-slice`; P3 has not started and starts in a new session.

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
- Nothing running. P3 starts in a new session (the owner asked for that).

## Where the engine stands after P2 (read before briefing P3)
- With Tier 1 only, the worked scenario (C-101 / C-201) gives three AUTO phone links at 100; the Irfan person link is SUGGESTED at 45.0 (expected AUTO 85.5 once Tier 2 name similarity and Tier 3 shared network exist). With the AC-01 Tier 2/3 values injected in tests it reaches AUTO 85.5.
- Pass now: AC-02, 04, 06, 07, 09, 19, 26, and AC-15 after b02. Wait for Tier 2: AC-03, 05, 10, 17, 21, SF-07. Wait for Tier 3: AC-01 (person link), 08, 11, 12, 13, 14, 22, SF-06. Scenario-only (AC-16, 18, 20, 23, 24, 25, 27): engine tests with injected values.
- Zero-tolerance checks hold over the whole kit: S3 non-links 0 fail, S4 closed world and integrity 0 fail, no trap hit.
- The gate is `backend/tests/engine/e2e/test_kit_gate.py` with `waiting.py`: per batch it pins exactly which expected links fail and why (b01: 17 failing, 10 skipped; b01+b02: 20 failing, 2 skipped). When a tier makes a link reachable the test fails until the entry is removed: that is how P3 progress is tracked. The scorer's overall `ok` stays false until the list is empty or the scorer can defer links.
- Tier 2 and 3 plug in through `EvidenceProvider` / `pending_seams` in `tracex_engine.matching`; blocking keys B2 and B4-B7, PER_AGE_CONFLICT and PER_RELATIVE_CONFLICT are named seams.
- Engine API for the Backend: `Matcher.run_matching(...) -> RunResult(run, transitions, updated_link_ids)`, `apply_decision(...)` (codes STATE_MISMATCH, ILLEGAL_TRANSITION, NOT_FOUND, REPLAY_CONFLICT), `explanation(link_id)`, `cluster_of(entity_id)`, `Thresholds`, `ThresholdsError`, `DEFAULT_THRESHOLDS`.

## Next
1. P3, each task in its own worktree from `main`, each ending in a PR, in parallel where marked:
   - 3.1 Tier 2 fuzzy / probabilistic: Naidu (Sonnet), reviewed by Iyer. Includes the comparators, phonetic or pool-aware handling of Devanagari-vs-Roman spellings ("saksena" vs "saxena"), and the Naidu follow-ups below that create missed links.
   - 3.2 Tier 3 contextual (shared contacts, shared counterparties, co-location): Bose (Sonnet), reviewed by Iyer. Bose also takes over the SHARED / HUB / MULTI_USER flags from `matching/flags.py` (spec §1 assigns them to Graph) and adds a way for the scorer to defer not-yet-reachable links (`--defer` or a waits-for-tier field) so `ok` can be true mid-build.
   - 3.3 Composite score, bands, review queue, undo, identity clusters: Iyer (Opus), after 3.1 and 3.2.
   - 3.4 API, auth, access control, access requests, audit log: Khan (Sonnet), in parallel with 3.1/3.2. Starts by amending `docs/architecture.md` with the eight items from the PR #28 re-review comment (documents.file_name and the document_id mapping; read-time overlay of state and history; persist from transitions plus updated_link_ids; ADMIN run totals from created_by_state only; reconcile sweep for withdrawn edges and stub match_runs rows; the four engine answer codes as divergence; thresholds validated before RUNNING; per-link serialisation of decisions). Dutta's carried items below apply.
   - 3.5 Security review of 3.4: Dutta (Opus).
2. Tag `m3-engine`, then P4 apps as in PLAN.md §5 (P4 may start against a mocked contract in parallel with P3 if usage allows).

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
- Usage in S2: the 5-hour limit was hit four times mid-task (agents fail with a rate-limit error and keep their work; resume them with SendMessage after the reset). Roughly one window buys two Sonnet authors with fix rounds plus four or five Opus review passes. Checkpoint STATE.md before a window reaches about 80%.
- Opus agents with a very large context stalled repeatedly ("no progress for 600s"). What worked: tell the agent to push the branch at once, write one small file at a time, commit and push after each, put timeouts on commands, and open a draft PR rather than hold work back. Prefer a fresh hire per task over resuming an agent past about 400k tokens.
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
