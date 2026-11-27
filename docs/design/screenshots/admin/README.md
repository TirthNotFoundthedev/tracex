# Admin panel screenshots (P4.4, TIR-20)

Rendered screenshots of every admin screen on the real seeded stack, for the Design Lead review against DESIGN_RULES section 15. Nothing in the DOM is faked: all rows come from the API.

Naming follows `docs/design/screenshots/officer/`: `<screen id>-<name>-<en|hi>[-mobile|-zoom200|-grayscale].png`. Screen ids are from `docs/specs/design-flows.md` section 3 (A1 upload, A2 matching, A3 review queue, A3b link detail, A3c Rejected/Undone filters, A3d rejected or undone link, A4 approvals, A4a change to approve, A5 users and roles, A6 audit log, A7 thresholds, A8 network graph). `A0` is the admin sign-in page (it has no id in the flows file). Desktop files are 1280 wide, `-mobile` files are 375 wide; all are full-page captures.

## Checks done on every capture

- Fonts: after every capture the script read `document.fonts`. Noto Sans 400/600/700, Noto Sans Devanagari 400/600/700 and Noto Sans Mono 400 all reported status `loaded`. Every `-hi` file had Noto Sans Devanagari loaded. The app root and all controls use `"Noto Sans", "Noto Sans Devanagari", system-ui, ...` (the `body` element itself has no font set, see Known issues).
- Horizontal scroll at 375: `document.documentElement.scrollWidth` equals 375 on every `-mobile` file except the four Thresholds files (`A7-thresholds-*-mobile.png`: 469 wide in English, 410 in Hindi). The cause is `.admin-zone` (the three-zone bar), a real defect listed in the PR. The measured widths are in the last column below.
- All other 1280 files and all zoom200/grayscale files have scroll width equal to the viewport width.

## Files

Columns: file, role signed in as, what it shows, page scroll width / viewport width.

| File | Role | Screen and notes | Scroll |
|---|---|---|---|
| A0-sign-in-en-mobile.png | none | Sign-in, empty | 375/375 |
| A0-sign-in-en.png | none | Sign-in, empty | 1280/1280 |
| A0-sign-in-hi-mobile.png | none | Sign-in, empty | 375/375 |
| A0-sign-in-hi.png | none | Sign-in, empty | 1280/1280 |
| A0-sign-in-missing-en-mobile.png | none | Submit with empty fields | 375/375 |
| A0-sign-in-missing-en.png | none | Submit with empty fields | 1280/1280 |
| A0-sign-in-missing-hi-mobile.png | none | Submit with empty fields | 375/375 |
| A0-sign-in-missing-hi.png | none | Submit with empty fields | 1280/1280 |
| A0-sign-in-wrong-password-en-mobile.png | none | Wrong password (real 401 from the API) | 375/375 |
| A0-sign-in-wrong-password-en.png | none | Wrong password (real 401 from the API) | 1280/1280 |
| A0-sign-in-wrong-password-hi-mobile.png | none | Wrong password (real 401 from the API) | 375/375 |
| A0-sign-in-wrong-password-hi.png | none | Wrong password (real 401 from the API) | 1280/1280 |
| A1-upload-en-mobile.png | ADMIN (hari) | Form and the real upload list from the seed | 375/375 |
| A1-upload-en.png | ADMIN (hari) | Form and the real upload list from the seed | 1280/1280 |
| A1-upload-hi-mobile.png | ADMIN (hari) | Form and the real upload list from the seed | 375/375 |
| A1-upload-hi.png | ADMIN (hari) | Form and the real upload list from the seed | 1280/1280 |
| A1-upload-nothing-chosen-en-mobile.png | ADMIN (hari) | Submit with no case and no file | 375/375 |
| A1-upload-nothing-chosen-en.png | ADMIN (hari) | Submit with no case and no file | 1280/1280 |
| A1-upload-nothing-chosen-hi-mobile.png | ADMIN (hari) | Submit with no case and no file | 375/375 |
| A1-upload-nothing-chosen-hi.png | ADMIN (hari) | Submit with no case and no file | 1280/1280 |
| A2-matching-en-mobile.png | ADMIN (hari) | Last run from the seed | 375/375 |
| A2-matching-en.png | ADMIN (hari) | Last run from the seed | 1280/1280 |
| A2-matching-hi-mobile.png | ADMIN (hari) | Last run from the seed | 375/375 |
| A2-matching-hi.png | ADMIN (hari) | Last run from the seed | 1280/1280 |
| A3-review-filter-empty-en-mobile.png | SENIOR (meena) | Type filter with no match | 375/375 |
| A3-review-filter-empty-en.png | SENIOR (meena) | Type filter with no match | 1280/1280 |
| A3-review-filter-empty-hi-mobile.png | SENIOR (meena) | Type filter with no match | 375/375 |
| A3-review-filter-empty-hi.png | SENIOR (meena) | Type filter with no match | 1280/1280 |
| A3-review-loading-en.png | SENIOR (meena) | Loading state: the real API answer was held back 6 seconds with a test proxy | 1280/1280 |
| A3-review-loading-hi.png | SENIOR (meena) | Loading state: the real API answer was held back 6 seconds with a test proxy | 1280/1280 |
| A3-review-no-connection-en.png | SENIOR (meena) | No-connection state: the request was cut by the test browser, the stack was up | 1280/1280 |
| A3-review-no-connection-hi.png | SENIOR (meena) | No-connection state: the request was cut by the test browser, the stack was up | 1280/1280 |
| A3-review-not-available-en-mobile.png | ADMIN (hari) | ADMIN opens /review (no menu item) | 375/375 |
| A3-review-not-available-en.png | ADMIN (hari) | ADMIN opens /review (no menu item) | 1280/1280 |
| A3-review-not-available-hi-mobile.png | ADMIN (hari) | ADMIN opens /review (no menu item) | 375/375 |
| A3-review-not-available-hi.png | ADMIN (hari) | ADMIN opens /review (no menu item) | 1280/1280 |
| A3-review-waiting-en-grayscale.png | SENIOR (meena) (grayscale) | Grayscale filter on the whole page | 1280/1280 |
| A3-review-waiting-en-mobile.png | SENIOR (meena) | Review queue, Waiting filter (28 real links) | 375/375 |
| A3-review-waiting-en-zoom200.png | SENIOR (meena) (zoom200) | 200 percent zoom: 640 CSS px wide, device scale 2 (same layout as browser zoom 200% at 1280) | 640/640 |
| A3-review-waiting-en.png | SENIOR (meena) | Review queue, Waiting filter (28 real links) | 1280/1280 |
| A3-review-waiting-hi-grayscale.png | SENIOR (meena) (grayscale) | Grayscale filter on the whole page | 1280/1280 |
| A3-review-waiting-hi-mobile.png | SENIOR (meena) | Review queue, Waiting filter (28 real links) | 375/375 |
| A3-review-waiting-hi-zoom200.png | SENIOR (meena) (zoom200) | 200 percent zoom: 640 CSS px wide, device scale 2 (same layout as browser zoom 200% at 1280) | 640/640 |
| A3-review-waiting-hi.png | SENIOR (meena) | Review queue, Waiting filter (28 real links) | 1280/1280 |
| A3-review-waiting-over-7-days-en-mobile.png | SENIOR (meena) | Waiting more than 7 days (empty: all seed links are new) | 375/375 |
| A3-review-waiting-over-7-days-en.png | SENIOR (meena) | Waiting more than 7 days (empty: all seed links are new) | 1280/1280 |
| A3-review-waiting-over-7-days-hi-mobile.png | SENIOR (meena) | Waiting more than 7 days (empty: all seed links are new) | 375/375 |
| A3-review-waiting-over-7-days-hi.png | SENIOR (meena) | Waiting more than 7 days (empty: all seed links are new) | 1280/1280 |
| A3b-link-detail-en-mobile.png | SENIOR (meena) | Link detail, More detail open by default | 375/375 |
| A3b-link-detail-en.png | SENIOR (meena) | Link detail, More detail open by default | 1280/1280 |
| A3b-link-detail-hi-mobile.png | SENIOR (meena) | Link detail, More detail open by default | 375/375 |
| A3b-link-detail-hi.png | SENIOR (meena) | Link detail, More detail open by default | 1280/1280 |
| A3b-reject-check-en-mobile.png | SENIOR (meena) | Reject, second step (not confirmed) | 375/375 |
| A3b-reject-check-en.png | SENIOR (meena) | Reject, second step (not confirmed) | 1280/1280 |
| A3b-reject-check-hi-mobile.png | SENIOR (meena) | Reject, second step (not confirmed) | 375/375 |
| A3b-reject-check-hi.png | SENIOR (meena) | Reject, second step (not confirmed) | 1280/1280 |
| A3c-review-rejected-en-mobile.png | SENIOR (meena) | Rejected filter (2 real rejections made in the app) | 375/375 |
| A3c-review-rejected-en.png | SENIOR (meena) | Rejected filter (2 real rejections made in the app) | 1280/1280 |
| A3c-review-rejected-hi-mobile.png | SENIOR (meena) | Rejected filter (2 real rejections made in the app) | 375/375 |
| A3c-review-rejected-hi.png | SENIOR (meena) | Rejected filter (2 real rejections made in the app) | 1280/1280 |
| A3c-review-undone-en-mobile.png | SENIOR (meena) | Undone filter (1 real undo made in the app) | 375/375 |
| A3c-review-undone-en.png | SENIOR (meena) | Undone filter (1 real undo made in the app) | 1280/1280 |
| A3c-review-undone-hi-mobile.png | SENIOR (meena) | Undone filter (1 real undo made in the app) | 375/375 |
| A3c-review-undone-hi.png | SENIOR (meena) | Undone filter (1 real undo made in the app) | 1280/1280 |
| A3d-review-rejected-detail-en-mobile.png | SENIOR (meena) | Rejected link detail with history | 375/375 |
| A3d-review-rejected-detail-en.png | SENIOR (meena) | Rejected link detail with history | 1280/1280 |
| A3d-review-rejected-detail-hi-mobile.png | SENIOR (meena) | Rejected link detail with history | 375/375 |
| A3d-review-rejected-detail-hi.png | SENIOR (meena) | Rejected link detail with history | 1280/1280 |
| A3d-review-reopen-check-en-mobile.png | SENIOR (meena) | Reopen, second step (not confirmed) | 375/375 |
| A3d-review-reopen-check-en.png | SENIOR (meena) | Reopen, second step (not confirmed) | 1280/1280 |
| A3d-review-reopen-check-hi-mobile.png | SENIOR (meena) | Reopen, second step (not confirmed) | 375/375 |
| A3d-review-reopen-check-hi.png | SENIOR (meena) | Reopen, second step (not confirmed) | 1280/1280 |
| A3d-review-undone-detail-en-mobile.png | SENIOR (meena) | Undone link detail with history | 375/375 |
| A3d-review-undone-detail-en.png | SENIOR (meena) | Undone link detail with history | 1280/1280 |
| A3d-review-undone-detail-hi-mobile.png | SENIOR (meena) | Undone link detail with history | 375/375 |
| A3d-review-undone-detail-hi.png | SENIOR (meena) | Undone link detail with history | 1280/1280 |
| A4-approvals-access-approve-check-en-mobile.png | SENIOR (meena) | Approve, second step (not confirmed) | 375/375 |
| A4-approvals-access-approve-check-en.png | SENIOR (meena) | Approve, second step (not confirmed) | 1280/1280 |
| A4-approvals-access-approve-check-hi-mobile.png | SENIOR (meena) | Approve, second step (not confirmed) | 375/375 |
| A4-approvals-access-approve-check-hi.png | SENIOR (meena) | Approve, second step (not confirmed) | 1280/1280 |
| A4-approvals-access-detail-en-mobile.png | SENIOR (meena) | Access request detail | 375/375 |
| A4-approvals-access-detail-en.png | SENIOR (meena) | Access request detail | 1280/1280 |
| A4-approvals-access-detail-hi-mobile.png | SENIOR (meena) | Access request detail | 375/375 |
| A4-approvals-access-detail-hi.png | SENIOR (meena) | Access request detail | 1280/1280 |
| A4-approvals-access-en-mobile.png | SENIOR (meena) | Access requests tab, 2 real waiting requests (one with a 330-character reason) | 375/375 |
| A4-approvals-access-en.png | SENIOR (meena) | Access requests tab, 2 real waiting requests (one with a 330-character reason) | 1280/1280 |
| A4-approvals-access-hi-mobile.png | SENIOR (meena) | Access requests tab, 2 real waiting requests (one with a 330-character reason) | 375/375 |
| A4-approvals-access-hi.png | SENIOR (meena) | Access requests tab, 2 real waiting requests (one with a 330-character reason) | 1280/1280 |
| A4-approvals-change-detail-en-mobile.png | ADMIN (hari) | Change detail | 375/375 |
| A4-approvals-change-detail-en.png | ADMIN (hari) | Change detail | 1280/1280 |
| A4-approvals-change-detail-hi-mobile.png | ADMIN (hari) | Change detail | 375/375 |
| A4-approvals-change-detail-hi.png | ADMIN (hari) | Change detail | 1280/1280 |
| A4-approvals-changes-en-mobile.png | SENIOR (meena) | Changes tab with 1 waiting change | 375/375 |
| A4-approvals-changes-en.png | SENIOR (meena) | Changes tab with 1 waiting change | 1280/1280 |
| A4-approvals-changes-hi-mobile.png | SENIOR (meena) | Changes tab with 1 waiting change | 375/375 |
| A4-approvals-changes-hi.png | SENIOR (meena) | Changes tab with 1 waiting change | 1280/1280 |
| A4a-approvals-change-approve-check-en-mobile.png | SENIOR (meena) | Approve this change, second step (not confirmed) | 375/375 |
| A4a-approvals-change-approve-check-en.png | SENIOR (meena) | Approve this change, second step (not confirmed) | 1280/1280 |
| A4a-approvals-change-approve-check-hi-mobile.png | SENIOR (meena) | Approve this change, second step (not confirmed) | 375/375 |
| A4a-approvals-change-approve-check-hi.png | SENIOR (meena) | Approve this change, second step (not confirmed) | 1280/1280 |
| A4a-approvals-change-detail-en-mobile.png | SENIOR (meena) | Change to approve, old and new value | 375/375 |
| A4a-approvals-change-detail-en.png | SENIOR (meena) | Change to approve, old and new value | 1280/1280 |
| A4a-approvals-change-detail-hi-mobile.png | SENIOR (meena) | Change to approve, old and new value | 375/375 |
| A4a-approvals-change-detail-hi.png | SENIOR (meena) | Change to approve, old and new value | 1280/1280 |
| A5-user-detail-readonly-en-mobile.png | SENIOR (meena) | User detail as SENIOR | 375/375 |
| A5-user-detail-readonly-en.png | SENIOR (meena) | User detail as SENIOR | 1280/1280 |
| A5-user-detail-readonly-hi-mobile.png | SENIOR (meena) | User detail as SENIOR | 375/375 |
| A5-user-detail-readonly-hi.png | SENIOR (meena) | User detail as SENIOR | 1280/1280 |
| A5-user-form-edit-en-mobile.png | ADMIN (hari) | Edit user form (second user) | 375/375 |
| A5-user-form-edit-en.png | ADMIN (hari) | Edit user form (second user) | 1280/1280 |
| A5-user-form-edit-hi-mobile.png | ADMIN (hari) | Edit user form (second user) | 375/375 |
| A5-user-form-edit-hi.png | ADMIN (hari) | Edit user form (second user) | 1280/1280 |
| A5-user-form-new-en-mobile.png | ADMIN (hari) | Add user form | 375/375 |
| A5-user-form-new-en.png | ADMIN (hari) | Add user form | 1280/1280 |
| A5-user-form-new-errors-en-mobile.png | ADMIN (hari) | Add user form, saved empty | 375/375 |
| A5-user-form-new-errors-en.png | ADMIN (hari) | Add user form, saved empty | 1280/1280 |
| A5-user-form-new-errors-hi-mobile.png | ADMIN (hari) | Add user form, saved empty | 375/375 |
| A5-user-form-new-errors-hi.png | ADMIN (hari) | Add user form, saved empty | 1280/1280 |
| A5-user-form-new-hi-mobile.png | ADMIN (hari) | Add user form | 375/375 |
| A5-user-form-new-hi.png | ADMIN (hari) | Add user form | 1280/1280 |
| A5-users-list-en-mobile.png | SENIOR (meena) | User list as SENIOR (read only) | 375/375 |
| A5-users-list-en.png | SENIOR (meena) | User list as SENIOR (read only) | 1280/1280 |
| A5-users-list-hi-mobile.png | SENIOR (meena) | User list as SENIOR (read only) | 375/375 |
| A5-users-list-hi.png | SENIOR (meena) | User list as SENIOR (read only) | 1280/1280 |
| A6-audit-en-mobile.png | SENIOR (meena) | Activity log, real chain written by the seed and this session | 375/375 |
| A6-audit-en.png | SENIOR (meena) | Activity log, real chain written by the seed and this session | 1280/1280 |
| A6-audit-hi-mobile.png | SENIOR (meena) | Activity log, real chain written by the seed and this session | 375/375 |
| A6-audit-hi.png | SENIOR (meena) | Activity log, real chain written by the seed and this session | 1280/1280 |
| A7-thresholds-en-mobile.png | SENIOR (meena) | Match settings as SENIOR | 469/375 |
| A7-thresholds-en.png | SENIOR (meena) | Match settings as SENIOR | 1280/1280 |
| A7-thresholds-hi-mobile.png | SENIOR (meena) | Match settings as SENIOR | 410/375 |
| A7-thresholds-hi.png | SENIOR (meena) | Match settings as SENIOR | 1280/1280 |
| A7-thresholds-invalid-en-mobile.png | ADMIN (hari) | Strong match set to 60, below the allowed 70 | 469/375 |
| A7-thresholds-invalid-en.png | ADMIN (hari) | Strong match set to 60, below the allowed 70 | 1280/1280 |
| A7-thresholds-invalid-hi-mobile.png | ADMIN (hari) | Strong match set to 60, below the allowed 70 | 410/375 |
| A7-thresholds-invalid-hi.png | ADMIN (hari) | Strong match set to 60, below the allowed 70 | 1280/1280 |
| A8-graph-link-panel-en-mobile.png | SENIOR (meena) | Why linked panel opened from the graph | 375/375 |
| A8-graph-link-panel-en.png | SENIOR (meena) | Why linked panel opened from the graph | 1280/1280 |
| A8-graph-link-panel-hi-mobile.png | SENIOR (meena) | Why linked panel opened from the graph | 375/375 |
| A8-graph-link-panel-hi.png | SENIOR (meena) | Why linked panel opened from the graph | 1280/1280 |
| A8-graph-list-en-mobile.png | SENIOR (meena) | Same network as a list | 375/375 |
| A8-graph-list-en.png | SENIOR (meena) | Same network as a list | 1280/1280 |
| A8-graph-list-hi-mobile.png | SENIOR (meena) | Same network as a list | 375/375 |
| A8-graph-list-hi.png | SENIOR (meena) | Same network as a list | 1280/1280 |
| A8-graph-list-selected-en-mobile.png | SENIOR (meena) | List view, one item selected | 375/375 |
| A8-graph-list-selected-en.png | SENIOR (meena) | List view, one item selected | 1280/1280 |
| A8-graph-list-selected-hi-mobile.png | SENIOR (meena) | List view, one item selected | 375/375 |
| A8-graph-list-selected-hi.png | SENIOR (meena) | List view, one item selected | 1280/1280 |
| A8-graph-matches-en-mobile.png | SENIOR (meena) | Search results (English and Hindi spellings of one name) | 375/375 |
| A8-graph-matches-en.png | SENIOR (meena) | Search results (English and Hindi spellings of one name) | 1280/1280 |
| A8-graph-matches-hi-mobile.png | SENIOR (meena) | Search results (English and Hindi spellings of one name) | 375/375 |
| A8-graph-matches-hi.png | SENIOR (meena) | Search results (English and Hindi spellings of one name) | 1280/1280 |
| A8-graph-not-available-en-mobile.png | ADMIN (hari) | ADMIN opens /graph: plain not-available state, no API call | 375/375 |
| A8-graph-not-available-en.png | ADMIN (hari) | ADMIN opens /graph: plain not-available state, no API call | 1280/1280 |
| A8-graph-not-available-hi-mobile.png | ADMIN (hari) | ADMIN opens /graph: plain not-available state, no API call | 375/375 |
| A8-graph-not-available-hi.png | ADMIN (hari) | ADMIN opens /graph: plain not-available state, no API call | 1280/1280 |
| A8-graph-nothing-found-en-mobile.png | SENIOR (meena) | Search with no result | 375/375 |
| A8-graph-nothing-found-en.png | SENIOR (meena) | Search with no result | 1280/1280 |
| A8-graph-nothing-found-hi-mobile.png | SENIOR (meena) | Search with no result | 375/375 |
| A8-graph-nothing-found-hi.png | SENIOR (meena) | Search with no result | 1280/1280 |
| A8-graph-picture-en-grayscale.png | SENIOR (meena) (grayscale) | Grayscale filter on the whole page | 1280/1280 |
| A8-graph-picture-en-mobile.png | SENIOR (meena) | Network picture: phone 90000 14471 (5 items, possible and restricted links) | 375/375 |
| A8-graph-picture-en-zoom200.png | SENIOR (meena) (zoom200) | 200 percent zoom: 640 CSS px wide, device scale 2 (same layout as browser zoom 200% at 1280) | 640/640 |
| A8-graph-picture-en.png | SENIOR (meena) | Network picture: phone 90000 14471 (5 items, possible and restricted links) | 1280/1280 |
| A8-graph-picture-hi-grayscale.png | SENIOR (meena) (grayscale) | Grayscale filter on the whole page | 1280/1280 |
| A8-graph-picture-hi-mobile.png | SENIOR (meena) | Network picture: phone 90000 14471 (5 items, possible and restricted links) | 375/375 |
| A8-graph-picture-hi-zoom200.png | SENIOR (meena) (zoom200) | 200 percent zoom: 640 CSS px wide, device scale 2 (same layout as browser zoom 200% at 1280) | 640/640 |
| A8-graph-picture-hi.png | SENIOR (meena) | Network picture: phone 90000 14471 (5 items, possible and restricted links) | 1280/1280 |
| A8-graph-search-en-mobile.png | SENIOR (meena) | Search form | 375/375 |
| A8-graph-search-en.png | SENIOR (meena) | Search form | 1280/1280 |
| A8-graph-search-hi-mobile.png | SENIOR (meena) | Search form | 375/375 |
| A8-graph-search-hi.png | SENIOR (meena) | Search form | 1280/1280 |

## How the data was made

Data comes from the demo seed (`small` tier: 122 cases, 138 strong and 28 possible links, 44 case assignments). Because the seed leaves some lists empty, I added real data through the app and the API on the throw-away stack. This changes nothing in the repo:

- `setup.mjs`: as `meena` rejected two possible links in the review queue (one reason in English, one in Hindi) and undid one strong link (Irfan network) from the graph panel. So the Rejected (2) and Undone (1) filters hold real rows; the Waiting count drops from 28 to 26. As `hari` proposed a role change for `asha`, so Approvals / Changes has one waiting change.
- `make-access-requests.mjs`: as `asha` sent two access requests through the API (`POST /access-requests`, one with a 330-character reason), so Approvals / Access requests has two waiting rows.
- Second steps (Reject, Reopen, Approve) are captured open but never confirmed.

## What was not captured, and why

- Server problem, safety pause, session ending and too-many-tries states: the stack cannot reach them without faking a response. Not captured.
- Loading and no-connection (`A3-review-loading-*`, `A3-review-no-connection-*`) are real UI on the real stack, but made with a test browser route: the `/review-queue` answer was held back 6 seconds (loading) or the request was cut (no connection). The counts show (0) while the list fails to load.
- Matching "running" state: not captured, to avoid starting a second run on the seeded data.
- Zoom 200 percent is a 640 CSS px wide viewport at device scale 2 (same layout as browser zoom 200 percent on a 1280 screen). Grayscale is `filter: grayscale(1)` on `html`. Both are for the review queue and the graph, EN and HI.
- Keyboard focus rings (section 15 item 11) were not captured; this PR does not cover that item.
- ADMIN has no review queue or graph (nav.ts). Those two are shown as the plain not-available state (`A8-graph-not-available-*`, `A3-review-not-available-*`).
- Users form: the edit form is shown for `hari` (second user in the list); the `meena` view is the read-only detail.

## How they were made

```
cp .env.example .env     # then in .env: API_PORT=18000 POSTGRES_PORT=15432 NEO4J_HTTP_PORT=17474 NEO4J_BOLT_PORT=17687
docker compose -p tracex-shots up -d --wait api
docker compose -p tracex-shots run --rm seed
npm ci
# admin app: Vite dev server on 19173, API reached through /api proxy (no CORS on the API)
ADMIN_ROOT=$PWD/apps/admin npx vite --config docs/design/screenshots/admin/capture/vite.shots.mjs
# in a scratch folder with `playwright` installed (npx playwright install chromium):
node make-access-requests.mjs
node setup.mjs
SHOTS_OUT=<dir> VP=1280 node main.mjs
SHOTS_OUT=<dir> VP=375  node main.mjs
SHOTS_OUT=<dir> node zoom-gray.mjs
SHOTS_OUT=<dir> node states.mjs
docker compose -p tracex-shots down -v
```

The scripts in `capture/` import `playwright` and `lib.mjs` from their own folder; copy them to a scratch folder and run `npm i playwright` there. `vite.shots.mjs` leaves the app code untouched and defines `VITE_API_URL=/api` itself. Playwright was Chromium (headless), `device scale 1` except zoom200. Seed passwords are the dev defaults in `.env.example`.
