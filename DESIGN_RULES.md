# DESIGN_RULES

Owner: Sen (Design Lead). Tokens: `packages/ui/src/tokens.css`. Flows and exact labels: `docs/specs/design-flows.md`.
Each rule carries its reason. A rule without a reason is a defect; challenge it through a ticket.

**Who this is for.** The design target is the lightly trained, low-literacy officer who knows only what to click and when, on a shared office PC or an old phone, often in sunlight or a dim room, in Hindi or English. If that officer can finish the task, the average and senior officer can. The admin panel is denser but follows the same rules.

## 0. Banned (a screenshot showing any of these is blocked)
- Blue-to-purple gradients, and any decorative gradient. Reason: gradients carry no meaning and reduce text contrast unpredictably.
- Glassmorphism (blur, translucent panels) and neon glows. Reason: low and variable contrast; reads as consumer software, not a government tool.
- An unstyled component-library look (default Material, Bootstrap or Ant appearance). Reason: it signals nobody decided anything; components must use our tokens.
- The rounded-card-on-pastel-background landing look, hero sections, marketing copy, taglines, illustrations of people. Reason: this is a work tool opened to do one job; every pixel of persuasion delays it.
- Emoji as icons. Reason: they render differently per device, cannot be styled, and are unreadable at some sizes.
- Warm beige backgrounds with serif headings. Reason: decorative; serif Devanagari at small size breaks down; white gives the best contrast.
- A design-system dump: components or tokens with no written reason. Reason: unused variety increases inconsistency and review cost.
- Pill buttons, large radii, drop shadows for depth, animated entrances, auto-playing motion. Reason: a sober tool, and motion distracts and fails on low-end devices.

## 1. Palette
Restrained: neutrals, one action colour, and colours that carry meaning only. Contrast below is WCAG 2.x computed from the hex values in tokens.css.

| Token | Hex | Means | Contrast |
|---|---|---|---|
| `paper` | #FFFFFF | Page and panel background. White gives the highest contrast and is the least tiring in bright rooms. | base |
| `sunken` | #EEF1F5 | Area behind panels, table stripes. Cool grey so it does not tint text. | ink 15.3:1 |
| `ink` | #141B24 | Body text, titles. | 17.3:1 on paper (AAA) |
| `ink-2` | #3A4656 | Secondary text. Allowed everywhere. | 9.6:1 paper, 8.5:1 sunken (AAA) |
| `muted` | #566273 | Admin-only low-importance metadata. Never in the officer app. | 6.2:1 paper, 5.5:1 sunken (AA) |
| `line` | #7A8594 | Edges of buttons, inputs, tables. | 3.7:1 paper (AA non-text) |
| `action` | #0B3A6B | "Do this next": the single primary button, links, selected item. Deep blue, the usual colour of official forms, and not used for anything else. | 11.5:1 with white (AAA) |
| `strong` | text #14532D on #E3F2E8, edge #1E7B45 | Strong match, linked automatically. | 7.9:1 text; edge 5.3:1 |
| `check` | text #6B3F00 on #FFF1CC, edge #B45309 | Possible match, needs a person. Dark brown text on amber, never yellow text. | 8.0:1 text; edge 5.0:1 |
| `restricted` | text #2B2F55 on #E8E9F3 | Content in another jurisdiction. Distinct from every strength colour so that "restricted" is never mistaken for a strength. | 10.6:1 |
| `danger` | #9B1C1C (bg #FCE8E6) | Errors, reject, destructive actions. Used for nothing else. | 8.2:1 paper; 6.9:1 on bg |

Rules:
- Body text in the officer app must reach AAA (7:1). Admin body text and all non-text parts reach AA (4.5:1 text, 3:1 non-text). Reason: officers read in poor light on poor screens.
- Colour is never the only carrier of meaning (section 8). Reason: colour-blind officers (about 1 in 12 men) and monochrome printouts.
- Green means "strong" only, never "OK/success" on its own. Red means danger only. Reason: officers learn the colours as a fixed vocabulary.
- Dark theme is not provided in v1. Reason: doubles review surface; white is more legible in offices with glare.

## 2. Type
- Families: **Noto Sans** (Latin) and **Noto Sans Devanagari** (Hindi), **Noto Sans Mono** for case numbers, phone numbers, account numbers and vehicle numbers. All SIL Open Font Licence 1.1, free, self-hosted as WOFF2 from `packages/ui/fonts`; no CDN at runtime. Reason: one designed family with matching Latin and Devanagari weights and x-height, wide glyph coverage, and no fallback to an unknown system font that clips matras. Stack in `--font-sans`.
- Weights: 400 and 600 only for text, 700 for screen titles. Reason: fewer weights, faster load on slow links.
- Scale (rem so the user's browser font size is honoured): 14 / 16 / 20 / 24 / 30 / 36 px as `--text-xs..2xl`.
- Minimum sizes: **officer app body 20px, nothing below 16px anywhere**; **admin body 16px, nothing below 14px**, and 14px only for metadata. Reason: small text is the first thing a low-literacy reader gives up on.
- Hierarchy in the officer app, one level per job: screen title 30px/700; item title 24px/600; body 20px/400; secondary line 16px ink-2. A screen has exactly one title. Reason: the officer scans for "where am I" first.
- No all-caps, no italics, no letter-spacing tricks. Reason: caps and italics damage word shape in Latin and do not exist in Devanagari; mixed treatment looks inconsistent between languages.
- Numbers, IDs and phone numbers use mono with tabular figures and are never wrapped mid-number.
- Line length 60 characters maximum (`--measure`). Left-aligned, never justified. Reason: justified text creates uneven gaps that hinder weak readers.

## 3. Spacing, shape, tap targets
- Scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px (`--space-1..8`). Nothing outside the scale. Reason: predictable rhythm without per-screen decisions.
- **Tap/click target: officer app 56px minimum height and width, admin 44px.** Gap between adjacent targets at least 12px (officer) or 8px (admin). Reason: gloves, shaky hands, old touchscreens, mouse-unfamiliar users; WCAG 2.5.8 asks 24px, we ask for more.
- One radius, 4px. Borders 2px on controls and badges, 1px on dividers. No shadows; depth comes from borders and the `sunken` background. Reason: shadows blur on cheap screens and print as grey smears.
- Focus ring: 3px `action` outline with 2px offset, on dark surfaces white. Always visible, never removed. Reason: keyboard and switch users, and officers who navigate by Tab in forms.

## 4. Layout and navigation
**Officer app** (simplest):
- Single column, maximum width 720px, centred on desktop, full width on phone. No sidebar, no tabs, no dropdown menus, no modals except the confirm step for confirm/reject. Reason: every extra region is a choice the officer was not trained for.
- Fixed header 64px: back button on the left (icon + "Back"), screen title, language switch on the right (icon + "हिंदी" or "English"). Never hidden. Reason: "Back" is the one escape; the language switch must work from the first screen.
- Depth is at most four screens: My cases, Case, Item, Also appears in / Explanation. Breadcrumb line "My cases > Case 24/118" in plain text above the title. Reason: officers must always know how to get home.
- Lists are one item per row, full-width rows, 56px minimum, each row ends with a chevron icon and is one target. No tables, no pagination controls under 50 rows (use "Show more").
- Primary action sits at the bottom of the content, full width, not in a floating or sticky bar except on phone.

**Admin panel**:
- Left navigation (240px) with icon + label for each section: Upload, Matching, Review queue, Approvals, Users, Audit log, Settings, Network graph. Content area uses tables with 44px rows and sortable columns labelled in words.
- Header shows user, jurisdiction, language switch, sign out. Breadcrumbs for depth above two.
- Tables: header row sticky, number columns right aligned in mono, row actions in a single "Open" button, not icon clusters. Reason: reduces misclicks across many rows.
- Wide screens use width, up to the content maximum `--page-width-wide` (72rem, 1152px), centred inside the area right of the navigation; text blocks still obey the 60-character measure. Reason: a table or graph needs room, but rows wider than about 1150px make the eye lose its line.

## 5. One primary action
- Each screen has exactly one primary button: solid `action` fill, white text 24px/600 (officer), always bottom of content, verb + object ("Show where it appears").
- Secondary actions are outlined buttons with `ink` text. Destructive ones use `danger` and are never the primary except on the Reject confirm step.
- Confirm/Reject: on the explanation screen both are shown at equal size, side by side on desktop and stacked on phone with Confirm first. If the officer's role cannot decide this link, neither is shown; a line from the role table in section 7a appears. Reason: no disabled-looking buttons that provoke "why can't I?".
- Reason for the rule: an officer facing two equally loud buttons will hesitate or guess.

## 6. Icons
- Icon set: **Lucide** (ISC licence), bundled as inline SVG, 2px stroke, 24px (officer) or 20px (admin), `currentColor`.
- **Every icon has a visible text label beside it. Icons are never alone.** The only exception is the close "x" inside a toast, which also carries an accessible name. Reason: icon meaning is learned, and a low-literacy officer cannot learn 40 pictograms.
- Fixed vocabulary, one icon per meaning, defined in design-flows.md: Back = arrow-left; Case = folder; Person = user; Phone = phone; Bank account = landmark; Vehicle = car; Also appears in = link; Strong = check-circle; Possible = alert-triangle; Restricted = lock; Confirm = check; Reject = x; Help = circle-help; Language = languages.
- Decorative icons are `aria-hidden`; the label provides the name.

## 7. Plain language
Rules (apply to English and Hindi; Hindi uses everyday words, not Sanskritised or transliterated English where a common word exists):
- Sentences of 12 words or fewer. One idea per sentence. Active voice. Say who or what: "Same phone number in both cases".
- Buttons are verb + object. Titles name the thing on screen. No questions as buttons.
- Say what will happen before the officer clicks and what happened after.
- Use the same word for the same thing everywhere. Do not rename a thing between screens.
- Numbers show as counts ("2 other cases") never as percentages in the officer app.
- No abbreviations except those printed on police forms the officer already uses (FIR, PS).

Banned in the officer app (also avoid in admin labels where a plain word works):

| Never write | Write instead (English) | Hindi |
|---|---|---|
| entity | person / phone number / bank account / vehicle (by type) | व्यक्ति / फ़ोन नंबर / बैंक खाता / वाहन |
| SAME_AS, link edge, match | "also appears in", "same" | "इसके अलावा यहाँ भी है", "वही" |
| confidence, score, threshold, tier, band | "Strong match", "Possible match" (details under "More detail") | "पक्का मिलान", "संभावित मिलान" |
| resolve, merge, deduplicate | "Confirm they are the same" | "पुष्टि करें कि यह वही है" |
| provenance, evidence node | "Where this came from" | "यह कहाँ से आया" |
| jurisdiction (alone) | "another police area" | "दूसरा थाना क्षेत्र" |
| error 403, forbidden, null, undefined, invalid, exception | "You do not have access", "Something is missing" | "आपको पहुँच नहीं है", "कुछ कमी है" |
| query, ingest, parse, sync | "search", "upload", "read", "update" | "खोजें", "अपलोड", "पढ़ें", "अपडेट" |
| fuzzy, phonetic, Jaro-Winkler | "Names sound alike" | "नाम मिलते-जुलते हैं" |

Admin panel may use "link strength", "threshold", "matching run" because admins configure them; each is explained in one sentence next to its field. Never show raw enum values or IDs without a plain-language label.

## 7a. Roles in plain language
Raw role codes are never shown in the officer app; admin shows the plain label with the code in "More detail" only.

| Code | Label | What it can do | Line shown when a button is missing |
|---|---|---|---|
| JUNIOR | Officer | Look only | "You can look at this link but not decide it. Ask your investigating officer or supervisor." |
| INVESTIGATOR | Investigating officer | Confirm or reject a possible match when both cases are theirs. Cannot undo. | Other cases: "You do not have access to both cases." After deciding: no Undo shown. |
| SUPERVISOR | Supervisor | As above, plus "Undo this link" and, in the admin panel only, reopen a rejected link, inside own police area | Link across two areas: "This link joins two police areas. Only a senior officer can decide it." |
| SENIOR | Senior officer | All of the above; the only role that decides a link across two areas, and only when covering both | Not covering both: "You do not cover both police areas." |
| ADMIN | Administrator | Manages the system, no case access | Sees counts and status only, no case content |

A link made automatically (strong match) has no Reject button for anyone. Supervisor and above see "Undo this link"; others see no button.

Reason: officers recognise ranks and duties, not system codes, and must learn why a button is missing.

## 8. Link strength (not by colour alone)
Two strengths are ever shown (a low-band pair is not a link and is never stored, listed or drawn, in either app). Each is shown with **colour + icon + words + border style + a 3-step bar**, so any one channel failing leaves the others:

| Strength | Words (officer) | Icon | Border | Bar |
|---|---|---|---|---|
| High: linked automatically | "Strong match" | check-circle | solid 2px, `strong` | 3 of 3 filled |
| Medium: needs a person | "Possible match. Please check." | alert-triangle | dashed 2px, `check` | 2 of 3 filled |

- Words always appear; the badge is never a coloured dot. Reason: screen readers, monochrome prints, colour-blind users.
- Never show a percentage or decimal on the first view. Numbers and tier appear only after "More detail".
- Admin may add the numeric score beside the words in the review queue and graph. Nothing in either app implies a stored weak link: no "weak" badge, filter, colour or edge style.

## 9. Explanation panel
- Order: (1) strength badge, (2) "Why we think so" reasons, (3) "Why it may be wrong" reasons, (4) "Where this came from", (5) one "More detail" disclosure (closed by default), (6) the action buttons.
- Reasons are plain sentences, one per line, each with its evidence icon (check for support, alert for against) and its source line "Case 24/118, statement, page 2" in `ink-2` 16px.
- If there is no evidence against, show "Nothing found against this link." Never omit the section. Reason: officers must see that the system looked.
- "More detail" holds: numeric score, tier, matching rules fired, thresholds, raw values. Labels there may use admin terms, each explained.
- "More detail" is closed by default in the officer app (D69). In the admin link detail it is open by default (design-flows A3, A3d), because admins read the numbers.
- Wording patterns and examples are in design-flows.md.

## 10. Restricted (other-jurisdiction) content
- A restricted link is a **card with `restricted` background, dashed 2px `restricted` border, lock icon, and the words "Another police area"**. Contents shown: the officer's own item (its type and value), "also appears in a case in another police area", and the button "Ask for access".
- No case number, name, place, date, count of people, or strength. Reason: even those leak; the existence alone is what the officer may know.
- Never greyed-out or blurred to hint at hidden text; there is no hidden text in the page at all. Reason: access is enforced by the API; the UI must not pretend to hold data it was not sent.
- After the request: card shows "Request sent on 12 Mar. We will tell you when it is decided." and no button.
- Access request form: reason field only (single field, required, 10 to 500 characters), button "Send request".

## 11. Feedback, undo, errors
- Every action gets visible feedback within 1 second: a message in the page (not a vanishing toast) with icon and words, e.g. "Saved: you confirmed this link". Messages stay until dismissed or the next action. Reason: a slow reader needs time; vanishing text is missed.
- Decisions are recorded in the audit log. Only Supervisor and above are offered Undo (section 7a): after Confirm they see "You confirmed this link. [Undo]"; Investigating officers see the message without Undo. Reject requires a second step ("Reject this link? Yes, reject / No, go back") because wrongly rejecting loses a lead; Confirm does not. There is no Undo after Reject in the officer app: a rejected link is reopened only in the admin panel review queue (Rejected and Undone filters, Supervisor and above, with its own confirm step; D34). Reason: one place to reverse a rejection keeps the officer app simple, and a rejected link is not a connection, so the officer app has nothing to show for it.
- Admin status filter (Waiting / Rejected / Undone): a row of buttons; the chosen button is marked by border weight, bold text and a check icon, never by colour alone; every button shows its count. Reject, Undo and Reopen each ask for a required reason on their confirm step. A link the viewer cannot see shows the generic not-found state, never a role or access message (404, not 403).
- Admin tables at 375px: each row becomes a stacked block of label and value lines, with no sideways scroll. Reason: hidden columns would hide who rejected a link, when and why.
- Loading: a text line "Loading your cases..." with a spinner icon; no skeleton animation. Waiting over 10 seconds adds "This is taking long. Please wait or try again."
- Errors say what happened, whether data is safe, and what to do: "We could not save. Nothing was changed. [Try again]". Never codes, never blame ("you entered an invalid value"), never a dead end; always a button.
- Empty states say why and what next: "No cases yet. Ask your supervisor to add your cases."
- Session limit: the session lasts 8 hours and cannot be extended, so the notice 2 minutes before the end has no "Stay signed in" button. It says what will happen and that decisions are already saved: "You will be signed out in 2 minutes. Your decisions are already saved. Please sign in again after." Reason: a button that cannot do what it says would lie. If the API later allows a refresh, the button returns.
- Destructive admin actions state the effect in the button ("Delete this user") and need a second confirm. Every Administrator change to users, roles, areas, assignments or match settings is a proposal: after Save the page says "Sent for approval. Nothing changes until a senior officer approves it." and the item shows a tag with icon and words until a Senior officer decides (D35). Reason: the Administrator cannot change access alone, and the screen must not look as if the change already happened.

## 12. Graph view (admin only)
- Nodes are shapes with labels, never colour only: person = circle, phone = rounded square, bank account = diamond, vehicle = triangle, case = hexagon. Each label is visible text (min 14px), not hover-only.
- Edges: solid heavy = strong, dashed = possible, using the strength border styles. Restricted nodes are drawn as the `restricted` card shape with a lock and no label text beyond "Another police area".
- A legend is always visible, with icons + words. Selecting a node opens the same explanation panel as the officer app, with admin detail.
- Keyboard: Tab moves between nodes, Enter opens, and a "List view" toggle presents every node and edge as a table. Reason: graphs are inaccessible without a list alternative.
- Cap 150 nodes on screen with the message "Showing the 150 closest. Narrow the search to see others." Reason: unreadable above that, and slow on admin PCs.
- Layout is stable: moving the view never rearranges nodes. No physics bounce animation.
- Labels and words (TIR-94): a node label is cut at 20 characters with an ellipsis (full name in the node title, the spoken name and the list) and the layout keeps the label box inside the drawing, so nothing is clipped at 375 px. A link word ("Strong", "Possible") is placed clear of every label and shape, beside the line if needed, and is left out when no clear spot exists (line style, spoken name and list still carry it). From 30 nodes, labels that would sit on another label or shape are hidden (selected node and its neighbours first, then the best-connected) and a note says how many. Reason: 150 readable names do not fit in one picture; the list view is the readable route.
- Decision (P4.2): the network shows entities, not cases, so the hexagon is used for **organisation** (the graph's fifth entity type); a case is not a node. A "connected" relation (person and their phone, account or vehicle) is a thin dotted line with no strength, and a link to another police area is a dashed line to the restricted card. The layout is computed to the end before drawing (fixed seed, fixed steps), so nothing moves on screen and the same input always gives the same picture. Reason: the API has no case nodes, and a fixed layout lets a reviewer compare two screenshots.

## 13. Hindi and language rules
- The language switch is on the first screen and every screen header, label "हिंदी" in English mode and "English" in Hindi mode, written in the target language so it can be found by someone who cannot read the current one. Choice persists per device.
- **Never assume string length.** Hindi runs 20 to 40 percent longer. Buttons grow in height and wrap to two lines; never truncate with "...", never fixed-width labels, never clip. Reason: a truncated verb on a button is dangerous.
- Line-height 1.75 for Hindi, 1.5 for English (`--leading-hi`). Headline minimum 1.3 only for single lines. Reason: matras above and below the line collide at tighter spacing.
- No letter-spacing, no justified text, no uppercase transforms, no bold on conjuncts below 16px.
- Numerals: **Western digits (0-9) in both languages** for case numbers, phone numbers, dates and counts. Reason: these must match the source documents and FIR numbers the officer reads elsewhere, and copy-paste into other systems. Dates written "12 Mar 2026" / "12 मार्च 2026".
- All text comes from the i18n files in English and Hindi; a missing Hindi string fails CI and never falls back silently to English. Names of people are shown as stored, never translated; where a transliteration exists it is shown beneath, in `ink-2`.
- Review Hindi screens with the real longest string, not lorem ipsum.

## 14. Components (the complete list; add only with a written reason)
Button (primary, secondary, danger), TextField, SearchField, Select (admin only), Checkbox, FileDrop (admin), Tabs (admin only), TopBar, SideNav (admin), Breadcrumb, ListRow, Table (admin), Badge/StrengthBadge, ReasonList, EvidenceSource, MoreDetail (disclosure), RestrictedCard, Message (info/success/error, in-page), ConfirmStep, EmptyState, LanguageSwitch, GraphCanvas + GraphLegend (admin), Pager ("Show more").
Also built, with a written reason: **Loading** (the text line with a still spinner icon required by section 11, so every app draws it the same way and none uses a spinning or skeleton version) and **Icon** and **UiProvider** (not screens: the first holds the fixed icon vocabulary of section 6 so no app picks a second icon for one meaning; the second carries language and app variant so size, text size and line height switch from tokens in one place). Admin-only components (Select, FileDrop, Tabs, SideNav, Table) render nothing in the officer app. Reason: section 4 forbids dropdowns, tabs, tables and side navigation there, and a component that renders anyway lets the rule be broken silently.
Not in v1: toasts that vanish, tooltips (information hidden in hover is invisible on touch), carousels, modals other than ConfirmStep, drag and drop as the only way.

## 14a. Follow-up requirements (owner: Rao, Release Manager; not part of the design PR)
- Self-host the font files (Noto Sans, Noto Sans Devanagari, Noto Sans Mono, WOFF2) in `packages/ui`.
- Add Lucide as a pinned dependency of `packages/ui`.
- Add a CI check that fails on any key missing in the Hindi i18n file.

## 15. Review checklist (applied to rendered screenshots; any fail blocks the merge)
Screenshots required at 1280px wide desktop and 375px phone, in English and Hindi, with the longest real strings.
1. No item from section 0 is present.
2. Only tokens used; text sizes meet section 2 minimums; no text below 16px in officer app.
3. Exactly one primary action; its label is verb + object and fits on screen without scrolling to find it.
4. Every icon has a visible label beside it.
5. Every strength shown uses colour + icon + words + border + bar; no percentage on a first view in the officer app.
6. Restricted card shows no case-specific data; contains lock and "Another police area".
7. No jargon from section 7; no raw enum or ID shown without a plain label.
8. Targets measure 56px (officer) or 44px (admin) minimum with required gaps.
9. Hindi layout: nothing truncated or clipped, matras visible, line-height respected.
10. Contrast measured on the render for any new colour pair: body 7:1 officer, 4.5:1 admin, non-text 3:1.
11. Focus ring visible on every interactive element by keyboard.
12. Error, empty, loading and success states exist for the screen.
13. Back and language switch visible and working; the officer can reach home in one click.
14. Reject has a second step; Undo (after Confirm only) appears only for Supervisor and above; Reopen exists only in the admin Rejected and Undone filters, with a second step; strong (automatic) links show "Undo this link", never Reject.
15. Page usable at 200 percent zoom and in grayscale (strength still readable).
16. On the first real screens, also verify what the specimen could not: real Noto fonts loaded (no system fallback), layout at 375px width, and the longest real Hindi strings (no clipping, no truncation). **Ticked for the specimen** [x], from Edge headless renders of `docs/design/specimen.html` at true 375px and 1280px viewports (evidence in `docs/design/screenshots/`): Noto Sans 400/600/700, Noto Sans Devanagari 400/600/700 and Noto Sans Mono report status "loaded" and are the first family used; page scroll width equals viewport width (no horizontal scroll); no element extends past the right edge; every button and summary measures at least 56px (officer) or 44px (admin queue); long Hindi buttons wrap to two lines, none clipped. Fixed on the way: case numbers and the "खोलें" button wrapped mid-word in the narrow table (now no-wrap, wider admin container). Must be repeated on the real app screens.
