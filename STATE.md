# STATE

Last updated: 2026-11-11, end of session S1. P1 is complete and tagged `m1-contracts`; P2 has not started.

## Done
- PLAN.md approved by the owner (2026-11-11). Governance files in place.
- Private repo github.com/TirthNotFoundthedev/tracex. `main` protected (PR + CI checks backend, frontend).
- P0 foundation merged (PR #4), tag `m0-foundation`. PR #7 merged: self-hosted Noto fonts, Lucide, shared i18n with Hindi parity check, compose smoke job.
- P1 specs merged, tag `m1-specs`: `docs/specs/engine-matching.md` (Iyer), `api-access-control.md` + `api-audit-log.md` (Khan, gated by Dutta), `DESIGN_RULES.md`, `design-flows.md`, tokens, specimen (Sen).
- S1 merged with the owner's OK (PRs #12, #10, #11, #9, #13), `main` green, tag `m1-contracts` pushed: matching-spec errata (Iyer), `docs/specs/data-kit.md` (Bose, hired), `contracts/` + `docs/architecture.md` + access/audit spec amendments (Khan; Iyer approved, Dutta's security gate passed on the third round), review-queue filter Waiting / Rejected / Undone with Reopen, Approvals page and real-font specimen (Sen). Decisions D43-D49.

## In progress
- Nothing running. P2 was not started in S1 because the 5-hour usage window was 94% used.

## Next
1. P2 engine vertical slice, each in its own worktree from `main`, each ending in a PR:
   - Bose (Sonnet): 2.1 data kit generator per `docs/specs/data-kit.md` (small tier first, golden hash, ground truth). Give Rao the `.env.example` seed-password placeholders.
   - Naidu (Sonnet, hire): 2.2 parsers (CDR, bank) + extraction + normalization, tests first. First explicit test: the extractor reads ownership from the officer's note ("is used by"), otherwise the worked scenario drops to review. Also define the hedge wording for AC-19 (data-kit Q7).
   - Bose: 2.3 per-case graphs, within-case dedupe, provenance (after 2.1).
   - Iyer (Opus): 2.4 Tier 1 + scoring skeleton + SAME_AS, after 2.2 and 2.3. Reviewed by Khan (integration).
2. Tag `m2-slice`, then P3 onward as in PLAN.md §5.

## Carried forward (not blocking)
- Dutta, for P3 implementation: a rejected transition record's Neo4j edge must be reverted, not only alerted; reword the Reconciliation text in `docs/architecture.md`; U47-U54 and A49-A53 must become tests against the running API.
- Sen: Hindi strings need a native-speaker review; checklist item 16 must be repeated on the real app screens; queue and approval i18n keys are listed in design-flows for the screen builders to add in both languages. A string for "a matching run is in progress, try again shortly" (409 RUN_IN_PROGRESS, D49) is needed in both apps.
- Rao: `smoke` as a required check (ask the owner first); exact-pin Prettier; `.env.example` seed placeholders.

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
- Usage at end of S1: 5-hour window 94% used, weekly 33%. One round of three Sonnet authors plus Opus review and gate rounds cost about 90% of a 5-hour window; start P2 at the top of a fresh window.

## Open questions for the owner
- OK to merge the S1 closing state PR (STATE.md only)?

## Resume prompt (paste into a new session in this folder)
> You are Fable, CEO / Project Lead / CTO of TraceX. Read STATE.md, then PLAN.md §4–5, ROSTER.md and PROTOCOLS.md. Do not re-read the source document or PPT unless a task needs a section. Check usage, then continue from "Next" in STATE.md, delegating to the roles in ROSTER.md. Keep updates to me brief; checkpoint STATE.md, commit and push before limits run out.
