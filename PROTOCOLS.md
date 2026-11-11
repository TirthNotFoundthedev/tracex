# PROTOCOLS

How work gets done on TraceX. Owner: Fable. Changes are logged in DECISIONS.md.

## 1. Task intake and briefing
Fable (or a lead, for its workers) issues a brief:

```
ROLE CARD: (pasted from ROSTER.md)
RULES TO READ: (named sections)
GOAL: (one or two sentences)
INPUTS: (file paths and spec sections; pointers, not pasted text)
DONE WHEN: (acceptance criteria)
TOUCH: (paths)
DO NOT TOUCH: (paths)
```

Before issuing: check STATE.md and open PRs so the task is not already done or in flight. The source document and PPT are never passed whole; only the needed section is quoted.

## 2. Spec → tests → build
1. Spec in `docs/specs/<area>-<feature>.md`: purpose, behaviour, acceptance criteria, out of scope. Short.
2. Tests that encode the acceptance criteria, committed first and failing.
3. Implementation until tests pass, lint and type-check clean.
4. Docs touched by the change are updated in the same PR (contract, architecture overview, runbook).

## 3. Review and merge
- One PR per task, small. Title in conventional-commit form.
- Reviewer is a different agent from the author, per the review matrix in PLAN.md §4.
- UI changes also need Design Lead approval, given from rendered screenshots.
- Anything touching auth, access control, audit logging or data handling also needs Security Reviewer approval.
- CI must be green. The Release Manager merges (squash), deletes the branch, and updates STATE.md.
- Reviewer verdicts: APPROVE, or CHANGES with a numbered list. No rewriting the author's code in review.

## 4. Bug ticket lifecycle
Tickets live in `qa/tickets/T-<nnn>.md`, written only by the QA Lead.
`OPEN → ASSIGNED → FIXED (PR linked) → VERIFIED (by a new tester round or QA Lead) → CLOSED`.
Each ticket: what the user tried, expected, saw; severity (blocker / major / minor); owning role. No persona details, no transcript.

## 5. Escalation
Worker → its lead → Fable → the human owner. Escalate when: the spec is unclear or wrong, two documents conflict, a fix fails twice, a rule blocks the task, or cost is running well past the brief. Fable batches questions to the owner into one message.
Model escalation: a task Sonnet has failed twice goes to Opus with the failure notes.

## 6. Session handoff
Before a session or usage window ends: park or finish in-flight work, update STATE.md (done / in progress / next / blockers), commit and push, tell the owner what to start next. A new session starts from the handoff prompt in STATE.md plus STATE.md itself, nothing else.

## 7. Hiring and retiring
Hire only when no existing role covers the work: add a card to ROSTER.md and a line in DECISIONS.md saying why. Retire a role when its work is finished: mark the card RETIRED with the date. Testers are the one exception: a new one every run, never reused, no card.

## 8. Independent testing round
1. QA Lead confirms the build is running from a clean seed.
2. One brand-new tester per persona. Tester brief contains only: persona, app URL and login, goal in plain words, and the report format (tried / expected / happened / stuck). Nothing about the code, design or earlier rounds.
3. Testers report to the QA Lead only. QA Lead writes tickets and a one-paragraph round summary for Fable.

## 9. Release and demo-readiness checklist
- [ ] `main` green; milestone tagged
- [ ] One-command setup and seed works from a fresh clone
- [ ] End-to-end scenario passes (Playwright) and by hand from the runbook
- [ ] Explanation panel, audit log and access control demonstrated in the runbook
- [ ] No open blocker or major tickets
- [ ] Security review signed off
- [ ] Architecture overview, API contract and runbook match the build
- [ ] No secrets, no real data, dependencies pinned
