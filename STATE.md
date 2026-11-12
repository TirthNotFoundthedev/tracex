# STATE

Last updated: 2026-11-12, later in session S2. P2.1 and P2.2 are merged; 2.3 and the reference scorer are in review; 2.4 has not started.

## Done
- PLAN.md approved by the owner (2026-11-11). Governance files in place.
- Private repo github.com/TirthNotFoundthedev/tracex. `main` protected (PR + CI checks backend, frontend).
- P0 foundation merged (PR #4), tag `m0-foundation`. PR #7 merged: self-hosted Noto fonts, Lucide, shared i18n with Hindi parity check, compose smoke job.
- P1 specs merged, tag `m1-specs`: `docs/specs/engine-matching.md` (Iyer), `api-access-control.md` + `api-audit-log.md` (Khan, gated by Dutta), `DESIGN_RULES.md`, `design-flows.md`, tokens, specimen (Sen).
- S1 merged with the owner's OK (PRs #12, #10, #11, #9, #13), `main` green, tag `m1-contracts` pushed: matching-spec errata (Iyer), `docs/specs/data-kit.md` (Bose, hired), `contracts/` + `docs/architecture.md` + access/audit spec amendments (Khan; Iyer approved, Dutta's security gate passed on the third round), review-queue filter Waiting / Rejected / Undone with Reopen, Approvals page and real-font specimen (Sen). Decisions D43-D49.
- S2 merged (PRs #17, #19, #16, #18, #15), `main` green: `data-kit` CI job + seed placeholders + Prettier pin (Rao), data kit generator small + demo tiers with golden hashes verified on Linux (Bose, 2.1), spec errata from the reviews (Iyer), parsers + extraction + normalization (Naidu, 2.2; ownership from closed patterns, D51). Decisions D50-D54.

## In progress
- PR #20 (Bose, data-kit reference scorer G-16, §8.1 mapping, G-09 isolation): Iyer CHANGES (4 blockers, 5 minors: a wrong engine could pass). Fix round running, plus two additions: ground-truth `raw_text` for PERSON/ORG without role word, leading `M/s` or alias clause (golden hashes will change), and a transliteration split inside one within_case group is allowed.
- PR #21 (Bose, 2.3 per-case graphs, `docs/specs/engine-graph.md`, Neo4j store, `neo4j==5.28.2`): two review rounds; one blocker left (a shared bare alias merges two full names depending on load order). Fix round 2 running: dedupe must be order-independent by construction, with a permutation test.
- PR #22 (Rao: Neo4j service in backend CI, Neo4j pinned to `5.26.12-community` in CI and compose, six root devDependencies exact-pinned): approved by Fable, CI green. Needs the owner's OK by number; the merge was blocked by the permission check.
- PR #23 (Naidu: no junk PERSON from "Complainant: M/s ...", raw_text rule pinned, `file_load_key` exported, placeholder bank holders blank): CI green, Iyer's review running. Iyer must explain the noise-OWNS count ("254 of 273" now, "211 of 215" before).
- Two Bose agents ran in parallel on disjoint paths (`data-kit/` and `backend/tracex_engine/graph/`).

## Next
1. Owner OK by number for #22, then for #20, #21, #23 once Iyer approves each. Merge #22 first, then have #21 merge main so its 9 Neo4j tests run in GitHub CI (so far only proven locally).
2. Iyer: one errata PR after #20 lands. Pending items: matching §5 G5 (entity confidence = highest mention confidence; an attribution below 0.7 is never an anchor); data-kit §4.3 (`tower_place` is the calling number's cell), §8.1 (per-mention `raw_text`; one engine entity sits in one within_case group in one case), §8.2 (`raw_text` convention), §8.3 (S4 integrity clauses, `evidence_kinds` checked in S1, CONFIRMED-by-harness, superseded links skipped, ANY_EDGE fails in every stored state).
3. Iyer (Opus): 2.4 Tier 1 + scoring skeleton + SAME_AS, from `main` after #20, #21, #23 land; reviewed by Khan. Gate: scorer `ok` on b01 and on b01+b02, plus Iyer's own engine tests for the scenario-only ACs (16, 18, 20, 23, 24, 25, 27) and for the extractor follow-ups he listed.
4. Tag `m2-slice`, then P3 onward as in PLAN.md §5.

## Carried forward (not blocking)
- Dutta, for P3 implementation: a rejected transition record's Neo4j edge must be reverted, not only alerted; reword the Reconciliation text in `docs/architecture.md`; U47-U54 and A49-A53 must become tests against the running API.
- Sen: Hindi strings need a native-speaker review; checklist item 16 must be repeated on the real app screens; queue and approval i18n keys are listed in design-flows for the screen builders to add in both languages. A string for "a matching run is in progress, try again shortly" (409 RUN_IN_PROGRESS, D49) is needed in both apps.
- Rao: `smoke` and `data-kit` as required checks (ask the owner first). Workspace packages under `apps/*` and `packages/*` were not audited for range pins.
- Naidu follow-ups (safe-side misses): family-note owners in parentheses, the Devanagari pronoun "उसका नंबर", a Devanagari name swallowing a following verb, a name directly after a locality with no comma, landlines in CDR rows, `OrgMention` has no aliases field. Devanagari-vs-Roman transliteration differences ("saksena" vs "saxena") are a P3 comparator matter (Iyer's ruling).
- Bose follow-up on #21: a witness sharing a name with both a complainant and an accused should start its own entity (in fix round 2). Replacing an uploaded case is a later Backend + Graph slice; files are immutable until then.
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
- Merges: the owner said "make sure it's good and push it" about #17 and #19; the permission check still blocked a later merge (#22) as unreviewed, so keep asking by PR number (D53).
- Leftover Neo4j containers from reviews may be running (`docker ps`); agents were denied permission to remove containers that were not theirs.
- Review pattern that worked: when adversarial review keeps finding holes in a deny-list, switch the author to an allow-list (closed patterns) instead of another patch round.
- Authors built against specs without seeing each other's output; have the reviewer run one against the other before approving.

## Open questions for the owner
- OK to merge #22 now?
- OK to merge #20, #21 and #23 once Iyer approves each and CI is green?
- OK to make `smoke` and `data-kit` required checks on `main`?

## Resume prompt (paste into a new session in this folder)
> You are Fable, CEO / Project Lead / CTO of TraceX. Read STATE.md, then PLAN.md §4–5, ROSTER.md and PROTOCOLS.md. Do not re-read the source document or PPT unless a task needs a section. Check usage, then continue from "Next" in STATE.md, delegating to the roles in ROSTER.md. Keep updates to me brief; checkpoint STATE.md, commit and push before limits run out.
