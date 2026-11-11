# Design flows

Owner: Sen. Rules and reasons: `DESIGN_RULES.md`. Text in `[ ]` is a button; `[ * ]` is the one primary button. `(icon)` always sits beside its label.
All strings below are the English source. Hindi strings live in the i18n files and are reviewed for length. Data shown is synthetic.

## 1. Explanation panel: wording pattern

Order is fixed. Plain reasons first, strength next to them, numbers last and closed.

```
+--------------------------------------------------------------+
| (check-circle) Strong match                                  |
| Phone number 98xxxx1234 in Case 24/118 and Case 31/207       |
+--------------------------------------------------------------+
| Why we think so                                              |
|  (check) Same phone number in both cases                     |
|  (check) Names sound alike: Mohd. Irfan / Irfan              |
|  (check) Both called the same 2 numbers                      |
+--------------------------------------------------------------+
| Why it may be wrong                                          |
|  (alert) Ages differ: 34 and 29                              |
|   -- or --                                                   |
|  Nothing found against this link.                            |
+--------------------------------------------------------------+
| Where this came from                                         |
|  Case 24/118, call record, page 2, line 14                   |
|  Case 31/207, statement of witness, page 5, line 3           |
+--------------------------------------------------------------+
| (chevron) More detail                       (closed)         |
+--------------------------------------------------------------+
| [ * Confirm they are the same ]   [ Reject this link ]       |
+--------------------------------------------------------------+
```

Pattern rules:
- Reason sentence = what matched + where or how, 12 words or fewer, no verbs of inference ("suggests", "indicates"). Examples: "Same phone number in both cases", "Same bank account number", "Same vehicle number: UP32 AB 1234", "Names sound alike: A / B", "Both called the same 2 numbers", "Both seen in the same place: Lucknow".
- Strength words: "Strong match" (linked automatically), "Possible match. Please check." Low-band pairs are not links and appear nowhere.
- A reason against uses the alert icon and the same sentence style: "Different dates of birth: 1990 and 1994".
- Source line: "Case [number], [document type], page [n], line [n]". If page or line is unknown: "Case [number], [document type]".
- "More detail" opened shows, with a one-sentence explanation for each: "Match score: 0.91 (out of 1)", "Tier: 2 of 3", "Rules that matched: phone number exact, name sound", "Strong match starts at 0.85", raw values as stored. Admin terms are allowed only here.
- Phone numbers in the officer app are shown in full to the officer who owns the case (mono font); masking is a backend rule, not designed here.

## 2. Officer app

### Screen list
O1 Sign in. O2 My cases. O3 Case. O4 Item (person, phone, bank account, vehicle). O5 Also appears in. O6 Why linked (explanation panel). O7 Reject check. O8 Link decided. O9 Other police area (restricted). O10 Ask for access. O11 Request sent. O12 Problem, empty and waiting states.

Header on every screen after O1: `[(arrow-left) Back]  Screen title  [(languages) हिंदी]`. O1 has the language switch only.

### O1 Sign in (first screen)
```
+------------------------------------------+
| TraceX                  [(languages) हिंदी] |
+------------------------------------------+
| Sign in                                  |
| Your user ID                             |
| [______________________]                 |
| Your password                            |
| [______________________]  [(eye) Show]   |
| [ * Sign in ]                            |
| Forgot your password? Ask your admin.    |
+------------------------------------------+
```
Error: "We could not sign you in. Check your user ID and password. [Try again]". After sign-in the language chosen stays.
Flow: choose language (optional) -> enter ID and password -> `Sign in` -> O2.

### O2 My cases
Title: "My cases". Intro line: "Choose a case to open." Search field: "Search by case number" with `[(search) Search]`.
```
| (folder) Case 24/118                  (chevron) |
|   Theft, Hazratganj. Opened 3 Mar 2026         |
|   (link) 2 items appear in other cases         |
| (folder) Case 31/207                  (chevron) |
```
Rows: one target each. `[Show more]` after 50. Empty: "No cases yet. Ask your supervisor to add your cases." Loading: "Loading your cases...".

### O3 Case
Title: "Case 24/118". Breadcrumb: "My cases > Case 24/118". Subtitle: "People, phone numbers, bank accounts and vehicles in this case". Four groups, each a heading with count, rows below:
```
| (user) People (3)                               |
|   Mohd. Irfan                (link) Also in 2 cases (chevron) |
| (phone) Phone numbers (4)                       |
| (landmark) Bank accounts (1)                    |
| (car) Vehicles (2)                              |
```
Rows with no other cases show "Only in this case". Row with a possible match waiting for the officer shows "(alert) Please check". Primary action: none on this screen (rows are the actions). Rule 5 exception recorded: navigation screens have no button.

### O4 Item
Title: the value, e.g. "Mohd. Irfan" or "98xxxx1234". Under it, the type: "Person in Case 24/118". Facts as plain label-value lines ("Age: 34", "Address: ..."). Primary button:
```
[ * (link) Show other cases ]
```
If nothing else: message "This appears only in this case." and no button.

### O5 Also appears in
Title: "Also appears in". Intro: "[Value] also appears in these cases."
```
| (check-circle) Strong match                      |
|   Case 31/207, Aminabad                          |
|   Same phone number in both cases                |
|   [ * Why was this linked? ]                     |
+--------------------------------------------------+
| (alert-triangle) Possible match. Please check.   |   (dashed border)
|   Case 40/009, Hazratganj                        |
|   Names sound alike: Mohd. Irfan / Irfan         |
|   [ * Check this ]                               |
+--------------------------------------------------+
| (lock) Another police area                       |   (restricted card, section O9)
```
Each card has one button; with several cards, the button on cards waiting for a decision is primary, others are outlined. Order: possible matches first, then strong, then restricted. Rows are cases the officer can open. Strong-linked cases are links (no decision needed) and offer "Why was this linked?".

### O6 Why linked
The explanation panel (section 1) as the whole screen. Title: "Why these are linked" (strong) or "Please check this link" (possible). Buttons depend on role:
- Possible match, Investigating officer or above with access to both cases (and, for a link across two areas, a Senior officer covering both): `[ * Confirm they are the same ]` `[ Reject this link ]`.
- Strong (automatic) match: no Reject for anyone. Supervisor and above: `[ Undo this link ]` with the line "This was linked automatically. You can undo it if it is wrong." Others: no button.
- Officer: no buttons; line "You can look at this link but not decide it. Ask your investigating officer or supervisor."
- Investigating officer without access to both cases: no buttons; line "You do not have access to both cases."
- Link joins two police areas and the officer is not a Senior officer: no buttons; line "This link joins two police areas. Only a senior officer can decide it." Senior officer not covering both: "You do not cover both police areas."
Both buttons equal size. Confirm acts at once. Reject opens O7.

### O7 Reject check
Replaces the content (no modal):
```
| Reject this link?                                |
| The two records will no longer be shown          |
| as the same.                  |
| [ * No, go back ]      [ (x) Yes, reject ]       |
```
"Yes, reject" uses the danger style; "No, go back" is primary here because the safe choice should be the easiest. Flow: Reject -> O7 -> Yes -> O8.

### O8 Link decided
Message, stays on the page: "(check) You confirmed this link. The two records are now shown as the same." or "(x) You rejected this link. If this was a mistake, ask your supervisor." Buttons: `[ * Back to this case ]`, and after a Confirm only, `[ Undo ]` for Supervisor and above. After Undo: "Your decision was undone. [Check this link again]". There is no Undo after a Reject: reopening a rejected link happens only in the admin panel review queue (A3, Rejected filter; D34), never in the officer app. Every decision is written to the audit log by the backend; the officer is not told about the log.

### O9 Other police area (restricted card)
```
+--------------------------------------------------+
| (lock) Another police area                       |   restricted bg, dashed border
| Phone number 98xxxx1234                          |
| also appears in a case in another police area.   |
| You cannot see that case.                        |
| [ * Ask for access ]                             |
+--------------------------------------------------+
```
The value shown is the officer's own item, not theirs. No case number, area name, strength or count. States: no pending request -> button; request pending -> "Request sent on 12 Mar. We will tell you when it is decided." (no button); granted -> becomes a normal card (O5); refused -> "Access was not given. [Ask again]" with the refusal reason only if the approver wrote one.

### O10 Ask for access
Title: "Ask for access". Text: "Tell the other police area why you need to see this case."
```
| Your reason                                      |
| [ ____________________________ ]  (at least 20 characters) |
| [ * Send request ]   [ Cancel ]                  |
```
Errors: empty -> "Please write your reason. [Fix]"; short -> "Please write a little more: at least 20 characters."

### O11 Request sent
"(check) Request sent. We will tell you when it is decided." `[ * Back to this case ]`. Notification of the decision appears on O2 as a message at the top: "Your request for access was approved. [See the case]".

### O12 States
- Loading: "Loading..." with spinner icon.
- No connection: "No connection. Nothing was changed. [Try again]".
- Not allowed: "You do not have access to this. [Back to my cases]".
- Server problem: "Something went wrong on our side. Nothing was changed. [Try again]. If it keeps happening, tell your admin."
- Session ending: "You will be signed out in 2 minutes. [Stay signed in]".

### Officer flow in one line
Sign in -> My cases -> Case -> Item -> Also appears in -> Why linked -> Confirm or Reject (role permitting) -> Back to this case. Restricted branch: Also appears in -> Another police area -> Ask for access -> Request sent. Maximum 6 clicks from sign-in to a decision.

## 3. Admin panel

Layout: left navigation (icon + label) with Upload, Matching, Review queue, Access requests, Users and roles, Audit log, Thresholds, Network graph. Header: user name, area, `[(languages) हिंदी]`, `[(log-out) Sign out]`. Each page has one title and at most one primary button.

### A1 Upload case material
Title: "Upload case material". Fields: "Case" (select from list or "New case number"), a drop area "Drop files here or [Choose files]", accepted types written in words: "PDF, Word, Excel, text, images". Primary: `[ * Upload files ]`. Result table: File, Case, Status ("Waiting", "Reading", "Done", "Could not read: [reason in words]"), `[Open]`. Failure row action: `[Try again]`.

### A2 Matching
Title: "Find links between cases". Line: "Last run: 12 Mar 2026, 14:05. Found 6 strong, 14 possible." Primary: `[ * Start matching ]`. While running: progress line "Matching 120 of 480 records..." and `[Stop]`. When done: message "Matching finished. 14 possible matches need review. [Go to review queue]".

### A3 Review queue (possible matches)
Title: "Links to check". Table, 44px rows, columns: Strength (badge, words + score), Item, Case A, Case B, Main reason, Waiting since. Sort labels in words. Filters: Type, Area, "Waiting more than 7 days". Row button `[Open]`.
Open -> A3b: the explanation panel with admin detail open by default, buttons `[ * Confirm they are the same ]` `[ Reject this link ]`, then `[Next one]`. Reject needs the same second step (O7). Strong links show `[ Undo this link ]` instead of Reject. Count shown: "Link 3 of 14".

#### A3c Rejected filter and Reopen (D34)
Reopening a rejected link is done here and nowhere else. The officer app never lists a rejected link and has no Reopen button (a rejected link is not a connection, so there is not even a locked card for it).

**Where the filter sits.** Directly under the page title, above the Type / Area filters, as a two-choice status switch with the label "Show":
```
Show:  [ (check) Waiting (14) ]  [ Rejected (3) ]
```
It is a pair of buttons, 44px high, 8px apart. The chosen one has a solid 2px `action` border, bold text and a check icon; the other has a `line` border and no icon, so the choice is readable in grayscale. Default is "Waiting". Both counts are always visible. The choice is kept in the page address so Back returns to it. Type and Area filters apply to both choices; "Waiting more than 7 days" is hidden under Rejected.

**Counts.** Counts include only links the viewer may see (access spec: rows the viewer may not see do not exist for them). A count never reveals a hidden link.

**Rejected table.** Line above it: "These links were rejected. A supervisor can reopen them." Columns: Item, Case A, Case B, Rejected by (name, then the plain role label from DESIGN_RULES 7a), Rejected on ("12 Mar 2026"), Reason (wraps, never cut with "..."; full text in Open), `[Open]`. Default sort: Rejected on, newest first. No strength badge (the link is no longer a link). "Show more" after 50 rows. If the rejecter wrote no reason the cell says "No reason written."

**Open on a rejected link (A3d).** The explanation panel as it stood when rejected, admin detail open, headed by a message with the history (never hidden in More detail):
```
| (x) Rejected by Meena Rao (Investigating officer) on 12 Mar 2026 |
|     Reason: Different people. Ages differ by 12 years.            |
| Why we think so / Why it may be wrong / Where this came from      |
| [ * (rotate-ccw) Reopen this link ]   [ Back to the list ]        |
```
`Reopen this link` is the one primary button, shown only to a viewer who holds the right (table below). Nothing else on this screen changes the link.

**Reopen confirmation (second step).** Replaces the content, no modal, same pattern as O7:
```
| Reopen this link?                                                 |
| It goes back to "Links to check". A person must then confirm      |
| or reject it. Matching runs will not change it.                   |
| Why are you reopening it? (not required)                          |
| [ ______________________________ ]                                |
| [ * Yes, reopen ]            [ No, go back ]                      |
```
"Yes, reopen" is primary here because reopening loses nothing: the link only returns to the queue and can be rejected again. "No, go back" is outlined. A reason, if written, is kept in the link history, not in the audit log (access spec). If the API makes the reason required, the label drops "(not required)" and an empty field shows "Please write your reason. [Fix]".

**After reopen.** The message stays on the page: "(check) You reopened this link. It is back in 'Links to check'." with `[ * Open it ]` and `[ Back to the list ]`. The link:
- leaves the Rejected filter at once; Rejected count goes down by 1, Waiting count up by 1;
- appears under Waiting as a Possible match (dashed `check` border, alert-triangle, "Possible match. Please check.") with a second tag "(rotate-ccw) Reopened" beside the badge, so it is not mistaken for a new link;
- in A3b shows "Reopened by Charu Singh on 14 Mar 2026. Earlier it was rejected by Meena Rao on 12 Mar 2026." and "Matching runs do not change this link. Only a person can." (D37: a reopened link is never changed by a rerun, so its strength stays as it was);
- takes the normal decisions again: `[ * Confirm they are the same ]` `[ Reject this link ]` (Reject with its second step, O7), for roles that may decide it.
There is no Undo for a reopen; to reverse it a supervisor rejects the link again in the normal way.

**Who can reopen.** Access spec: Reopen a REJECTED / UNDONE link is allowed for SUPERVISOR and above; a link whose ends are in different districts is decided only by a SENIOR covering both ends (D32). Rejected links are not connections, so no stub is shown for them.
| Viewer | Rejected filter | Reopen |
|---|---|---|
| Supervisor, both cases in own area | rows listed, full detail | button shown |
| Supervisor, link joins two areas | row not listed; if opened by address: "This link joins two police areas. Only a senior officer can decide it." | no button |
| Senior officer covering both ends | rows listed, full detail | button shown |
| Senior officer not covering both | row not listed; if opened by address: "You do not cover both police areas." | no button |
| Administrator (D29) | counts only (below) | none |
| Investigating officer, Officer | not part of the admin panel; if reached: "Only a supervisor can reopen a link." | none |
A missing button always comes with its line (DESIGN_RULES 5), never a greyed button.

**Administrator view (D29).** The filter shows both counts. In place of the table: a message "You can see how many links are rejected. Case details are for officers with access." and a counts-only summary: Waiting, Rejected, Reopened this month. No `[Open]`, no case numbers, no names.

**Empty state.** "No rejected links. Links that officers reject will appear here." If filters hide everything: "Nothing found. Check the filters or try fewer words." with `[Clear filters]`.

**Problem states.** Reopen failed: "We could not reopen it. Nothing was changed. [Try again]". Someone already acted (conflict): "Someone already changed this link. [Show the list]". Access removed meanwhile: "You do not have access to reopen this link. [Back to the list]". Loading: "Loading..." with spinner.

**Strings (English / Hindi).** Western digits in both. `{n}`, `{name}`, `{date}`, `{role}` are filled by the app. The keys go into the shared i18n files, both languages together, when the screen is built; this spec does not add them. Hindi needs native-speaker review before release.
| Key | English | Hindi |
|---|---|---|
| queue.show | Show | दिखाएँ |
| queue.filter.waiting | Waiting ({n}) | प्रतीक्षा में ({n}) |
| queue.filter.rejected | Rejected ({n}) | अस्वीकृत ({n}) |
| queue.rejected.intro | These links were rejected. A supervisor can reopen them. | ये लिंक अस्वीकार किए गए थे। सुपरवाइज़र इन्हें फिर से खोल सकते हैं। |
| queue.col.rejectedBy | Rejected by | किसने अस्वीकार किया |
| queue.col.rejectedOn | Rejected on | अस्वीकार करने की तारीख |
| queue.col.reason | Reason | कारण |
| queue.reason.none | No reason written. | कारण नहीं लिखा गया। |
| queue.rejected.history | Rejected by {name} ({role}) on {date} | {name} ({role}) ने {date} को अस्वीकार किया |
| queue.reopen.button | Reopen this link | इस लिंक को फिर से खोलें |
| queue.reopen.title | Reopen this link? | इस लिंक को फिर से खोलें? |
| queue.reopen.body | It goes back to "Links to check". A person must then confirm or reject it. Matching runs will not change it. | यह "जाँचने वाले लिंक" में वापस जाएगा। फिर किसी व्यक्ति को इसे पक्का या अस्वीकार करना होगा। मिलान चलाने से यह नहीं बदलेगा। |
| queue.reopen.reasonLabel | Why are you reopening it? (not required) | इसे फिर से क्यों खोल रहे हैं? (ज़रूरी नहीं) |
| queue.reopen.yes | Yes, reopen | हाँ, फिर से खोलें |
| queue.reopen.no | No, go back | नहीं, वापस जाएँ |
| queue.reopen.done | You reopened this link. It is back in "Links to check". | आपने यह लिंक फिर से खोल दिया। यह अब "जाँचने वाले लिंक" में है। |
| queue.reopen.openIt | Open it | इसे खोलें |
| queue.backToList | Back to the list | सूची पर वापस जाएँ |
| queue.tag.reopened | Reopened | फिर से खोला गया |
| queue.reopened.history | Reopened by {name} on {date}. Earlier it was rejected by {name2} on {date2}. | {name} ने {date} को फिर से खोला। पहले इसे {name2} ने {date2} को अस्वीकार किया था। |
| queue.reopened.rerun | Matching runs do not change this link. Only a person can. | मिलान चलाने से यह लिंक नहीं बदलता। केवल कोई व्यक्ति बदल सकता है। |
| queue.empty.rejected | No rejected links. Links that officers reject will appear here. | कोई अस्वीकृत लिंक नहीं है। अधिकारी जो लिंक अस्वीकार करेंगे, वे यहाँ दिखेंगे। |
| queue.empty.filtered | Nothing found. Check the filters or try fewer words. | कुछ नहीं मिला। फ़िल्टर जाँचें या कम शब्द लिखें। |
| queue.clearFilters | Clear filters | फ़िल्टर हटाएँ |
| queue.noRight.role | Only a supervisor can reopen a link. | केवल सुपरवाइज़र लिंक को फिर से खोल सकते हैं। |
| queue.noRight.twoAreas | This link joins two police areas. Only a senior officer can decide it. | यह लिंक दो थाना क्षेत्रों को जोड़ता है। इसका फ़ैसला केवल वरिष्ठ अधिकारी कर सकते हैं। |
| queue.noRight.notBoth | You do not cover both police areas. | आप दोनों थाना क्षेत्रों को कवर नहीं करते। |
| queue.admin.counts | You can see how many links are rejected. Case details are for officers with access. | आप देख सकते हैं कि कितने लिंक अस्वीकृत हैं। मामले का ब्योरा केवल पहुँच वाले अधिकारियों के लिए है। |
| queue.error.reopen | We could not reopen it. Nothing was changed. | हम इसे फिर से नहीं खोल सके। कुछ भी बदला नहीं गया। |
| queue.error.conflict | Someone already changed this link. | किसी ने यह लिंक पहले ही बदल दिया है। |
| queue.error.denied | You do not have access to reopen this link. | आपको इस लिंक को फिर से खोलने की पहुँच नहीं है। |
| officer.rejected.mistake | You rejected this link. If this was a mistake, ask your supervisor. | आपने यह लिंक अस्वीकार किया। अगर यह ग़लती थी, तो अपने सुपरवाइज़र से कहें। |

### A4 Access requests
Title: "Access requests". Table: Requested by, For case (admin sees it), From area, Reason, Date, Status. Row: `[Open]`. Detail: reason text in full, and `[ * Approve ]` `[ Refuse ]`; Refuse has an optional "Reason for refusing". Approve needs second step: "Give [name] access to Case 31/207 for 30 days? [ * Yes, approve ] [No, go back]". Access end date field "Access ends": default 30 days.

### A5 Users and roles
Title: "Users and roles". Table: Name, User ID, Role, Area, Status. `[ * Add user ]` primary. Form: Name, User ID, Area, Role ("Officer: can look", "Investigating officer: can look", "Supervisor: can decide in own area", "Senior officer: can decide across areas", "Administrator: manages the system, no case access"), `[ * Save user ]`. Row `[Open]` -> same form plus `[Turn off this user]` (danger, second confirm: "Turn off [name]? They will not be able to sign in. [ * Yes, turn off ] [No, go back]"). Roles are explained in one sentence beside each choice; codes (JUNIOR etc.) are never shown. Administrators see no case content on any screen: A3, A4 and A8 show case details only to roles with case rights; an Administrator sees counts and status.

### A6 Audit log
Title: "Activity log". Read-only table: Time, Person, What they did, Case, Item. Filters: date range, person, action type (words: "Looked at", "Confirmed", "Rejected", "Asked for access", "Approved access", "Uploaded"). Button `[Download as file]`. No edit or delete controls exist; line at top: "This log cannot be changed."

### A7 Thresholds
Title: "Match settings". Line: "These numbers decide which links are made automatically." Fields with one-sentence help each: "Strong match starts at" (0.85) "Links at or above this are made automatically."; "Possible match starts at" (0.60) "Links between this and the strong level wait in 'Links to check'. Below it, nothing is linked." Visual: horizontal bar split into three labelled zones (words + pattern fill, not colour only): "No link made | Please check | Linked automatically" (the first zone is a score range only; nothing is stored or listed for it). Primary `[ * Save settings ]`; after save: "Saved. New matching runs use these numbers. Past results do not change." Change needs second step stating how many links would move on a test run: "On the last run, 5 possible matches would become strong. [ * Save anyway ] [No, go back]".

### A8 Network graph
Title: "Network of links". Search "Find a person, phone number, account or vehicle", then `[ * Show network ]`. Canvas rules in DESIGN_RULES section 12. Left of canvas: legend (icon + word per node and edge kind). Right panel: selected node's explanation panel. Toggle `[(list) Show as list]` / `[(share-2) Show as picture]`. Message at limit: "Showing the 150 closest. Narrow the search to see others."

### Admin flow in one line
Upload -> Matching -> Links to check -> Confirm or Reject -> (Network graph to inspect) ; side flows: Access requests, Users and roles, Match settings, Activity log.

## 4. Shared states

| State | Text |
|---|---|
| Saved | "Saved." |
| Nothing found (search) | "Nothing found. Check the spelling or try fewer words." |
| Needs more input | "Please fill in: [field name]." beside the field, and a message at top counting them |
| Unsaved changes | "You have not saved your changes. [ * Save ] [Leave without saving]" |
| Language changed | Page redraws in place; no confirmation |
