# STATE

Last updated: 2026-11-12, mid session S2. P2 slice in flight: four PRs open (#15, #16, #17, #18), none merged.

## Done
- PLAN.md approved by the owner (2026-11-11). Governance files in place.
- Private repo github.com/TirthNotFoundthedev/tracex. `main` protected (PR + CI checks backend, frontend).
- P0 foundation merged (PR #4), tag `m0-foundation`. PR #7 merged: self-hosted Noto fonts, Lucide, shared i18n with Hindi parity check, compose smoke job.
- P1 specs merged, tag `m1-specs`: `docs/specs/engine-matching.md` (Iyer), `api-access-control.md` + `api-audit-log.md` (Khan, gated by Dutta), `DESIGN_RULES.md`, `design-flows.md`, tokens, specimen (Sen).
- S1 merged with the owner's OK (PRs #12, #10, #11, #9, #13), `main` green, tag `m1-contracts` pushed: matching-spec errata (Iyer), `docs/specs/data-kit.md` (Bose, hired), `contracts/` + `docs/architecture.md` + access/audit spec amendments (Khan; Iyer approved, Dutta's security gate passed on the third round), review-queue filter Waiting / Rejected / Undone with Reopen, Approvals page and real-font specimen (Sen). Decisions D43-D49.

## In progress
- PR #15 (Naidu, 2.2 parsers + extraction + normalization): three fix rounds done, CI green, 472 tests. Ownership (OWNS) is read only from a closed set of patterns (D51). Iyer's "Re-review 2" was requested and is the last gate; if it did not get posted, re-request it.
- PR #16 (Bose, 2.1 data kit generator, small + demo tiers): APPROVED by Iyer, 7 minors fixed (f4e82cf), new golden hashes. Must not merge until #17 is on main, main is merged into the branch, and the `data-kit` CI job passes on Linux against the golden hash (D52).
- PR #17 (Rao: `data-kit` CI job, `.env.example` seed placeholders, Prettier exact pin): approved by Fable. Merge first.
- PR #18 (Iyer: spec errata from the #15 and #16 reviews, docs only): approved by Fable. Merge with or after #16.

## Next
1. Owner OK by number, then merge in this order: #17, then #16 (after its Linux data-kit job is green), #18, #15 (after Iyer approves).
2. Bose (Sonnet): 2.3 per-case graphs, within-case dedupe, provenance, from `main` after #15 and #16 land. Also due before the 2.4 end-to-end gate: G-16 reference scorer and G-09 per-AC isolation.
3. Iyer (Opus): 2.4 Tier 1 + scoring skeleton + SAME_AS, after 2.3; reviewed by Khan. First end-to-end test runs the extractor over the generated kit against ground truth.
4. Tag `m2-slice`, then P3 onward as in PLAN.md §5.

## Carried forward (not blocking)
- Dutta, for P3 implementation: a rejected transition record's Neo4j edge must be reverted, not only alerted; reword the Reconciliation text in `docs/architecture.md`; U47-U54 and A49-A53 must become tests against the running API.
- Sen: Hindi strings need a native-speaker review; checklist item 16 must be repeated on the real app screens; queue and approval i18n keys are listed in design-flows for the screen builders to add in both languages. A string for "a matching run is in progress, try again shortly" (409 RUN_IN_PROGRESS, D49) is needed in both apps.
- Rao: `smoke` and `data-kit` as required checks (ask the owner first); remaining range-pinned root devDependencies (eslint, typescript, typescript-eslint, globals, @eslint/js, eslint-plugin-react-hooks).
- Naidu follow-ups (safe-side misses): shared-note owners in parentheses ("Number X is the family number (used by A and B)"), landlines in CDR rows. Devanagari noise names that transliterate to a different Roman spelling than ground truth ("saksena" vs "saxena") wait for Iyer's ruling in Re-review 2.
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
- Usage in S2: two Sonnet authors with three fix rounds, a Rao task and five Opus review passes took the 5-hour window from 7% to 91%; weekly 49%. Start 2.3/2.4 at the top of a fresh window.
- Review pattern that worked: when adversarial review keeps finding holes in a deny-list, switch the author to an allow-list (closed patterns) instead of another patch round.
- Authors built against specs without seeing each other's output; have the reviewer run one against the other before approving.

## Open questions for the owner
- OK to merge #17 now, and #16, #18, #15 once the conditions in "Next" hold?
- OK to make `smoke` and `data-kit` required checks on `main`?

## Resume prompt (paste into a new session in this folder)
> You are Fable, CEO / Project Lead / CTO of TraceX. Read STATE.md, then PLAN.md §4–5, ROSTER.md and PROTOCOLS.md. Do not re-read the source document or PPT unless a task needs a section. Check usage, then continue from "Next" in STATE.md, delegating to the roles in ROSTER.md. Keep updates to me brief; checkpoint STATE.md, commit and push before limits run out.
