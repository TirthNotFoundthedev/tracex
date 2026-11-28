# Tester round 1: plan

Owner: Joshi (QA Lead). One brand-new tester per persona. Testers see only their own brief and the running app. Reports go to the QA Lead only.

Logins are synthetic dev users. Run details (URLs, ports, stop steps) are in `README.md`.

| # | Persona | App | Login | Language |
|---|---|---|---|---|
| 1 | Low-literacy, lightly trained junior officer (mandatory) | Officer | `asha` | Hindi |
| 2 | Average investigator | Officer | `bharat` | English |
| 3 | Time-pressed senior officer | Admin | `deepak` | English |
| 4 | Admin | Admin | `hari` | English |
| 5 | Careless or hostile user | Officer, then Admin | `jatin` | English |

## Goals (plain words, one per persona)

1. **Asha.** Open case C-101. Find out if any person in it also shows up somewhere else. Say in your own words why the app thinks so.
2. **Bharat.** Open case C-102. Decide if you would trust the link the app shows between this case and another one. Say what made you decide.
3. **Deepak.** You have five minutes. Find the links most worth your attention in the review queue. Decide on one of them and say why.
4. **Hari.** Find out who did what in the system recently. Then set up a new officer account for a new colleague.
5. **Jatin.** You work in one district. Try to see information about other districts that you think you should not see. Also try the admin app. Report what you could and could not see.

## Coverage by persona

| Area | 1 Asha | 2 Bharat | 3 Deepak | 4 Hari | 5 Jatin |
|---|---|---|---|---|---|
| Explanation panel (why a link exists) | Goal 1: must read and explain it, in Hindi | Goal 2: must judge it | Goal 3: must use it to decide | Not asked | Looks at what it shows for hidden cases |
| Audit log | Not asked | Not asked | Looks for his own actions after deciding | Goal 4: reads it as the main task | Tries to open it |
| Access control | Notices items marked as in a case she cannot see | Notices the same, may ask for access | Sees all areas | Sees users and roles | Goal 5: main task |

## Order: two waves

Testers share one stack, and Deepak and Hari change data. So:

- **Wave A:** Asha, Bharat, Jatin (mostly read). Run first.
- **Wave B:** Deepak, Hari. Start only after all wave A reports are in.

## Notes

- Round 1 runs on the main build named in `README.md`. A clean seed is confirmed before testers start.
- Testers drive the app with a headless browser (Playwright from a scratch folder outside the repo) and use only what the screen shows.
- The QA Lead writes tickets (`qa/tickets/T-<nnn>.md`) and a one-paragraph round summary for Fable. No transcripts or personas go to developers or the Design Lead.
- Tester actions change the shared stack (decisions, requests, new users). Restart from a clean seed before any later round.
