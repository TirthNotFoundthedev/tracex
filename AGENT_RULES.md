# AGENT_RULES

How every agent on TraceX behaves. Owner: Fable. Breaking a rule is a defect; if a rule blocks you, escalate, do not work around it.

1. **Stay in role.** Your role card in ROSTER.md says what you own. Do only that.
2. **Touch only owned paths.** Need a change elsewhere? Ask the owner through your lead. Never edit governance files (`*_RULES.md`, `PROTOCOLS.md`, `PLAN.md`, `ROSTER.md`, `DECISIONS.md`) unless you own them.
3. **Read before working:** your role card, this file, the sections of PROTOCOLS.md and CODEBASE_RULES.md named in your brief, and the spec for your task. Nothing more; do not go reading the whole repo.
4. **Spec, then tests, then code.** No implementation without a written spec with acceptance criteria and tests that encode it.
5. **Never commit to `main`.** Work on a short-lived branch, open a pull request, and let a different agent review it. Do not merge your own PR.
6. **Escalate instead of guessing.** Unclear spec, a conflict between documents, a missing decision, or a task that looks already done: stop and report to your lead (leads report to Fable). State the question and your recommended answer.
7. **No duplicate work.** Before starting, check STATE.md and open branches/PRs for the same task.
8. **Developers and the Design Lead never contact testers** and never read tester transcripts or personas. You receive tickets from the QA Lead only.
9. **Testers never see** source code, docs, the plan, tickets or earlier results. Testers use only the running app.
10. **Synthetic data only.** No real FIRs, call records, bank statements or personal data, anywhere, ever.
11. **No secrets in the repo.** Config comes from environment variables; `.env` is ignored, `.env.example` is committed.
12. **Stay in scope.** Cross-case entity resolution MVP. No FIR storage, no case management, no machine-learned matching. Do not add features, dependencies or abstractions the spec does not ask for.
13. **Report in the short format**, and report honestly: failing tests and skipped steps are stated, not hidden.

## Report format

```
ROLE / TASK:
CHANGED: (branch, PR, files or areas; one line each)
TESTS: (what ran, pass/fail counts)
UNFINISHED:
NEEDS: (decisions, reviews, or work from another role)
```

Keep it under 20 lines. No pasted code or logs unless a failure needs it.
