import { chromium, newCtx, login, go, settle, T, rx, step, shot, toggleLang, suffix, save, manifest, B, PW } from "./lib.mjs";

const vp = Number(process.env.VP ?? 1280);
const only = process.env.ONLY ?? "anon,hari,meena";
const browser = await chromium.launch();
const sx = suffix(vp);
const N = (id, name, lang) => `${id}-${name}-${lang}${sx}`;
const btn = (page, text) => page.getByRole("button", { name: rx(text) }).first();

async function filterBtn(page, lang, key) {
  const s = (await T(page, key, lang, { n: "" })).replace(/\s*\(\s*\)\s*/, "");
  await page.getByRole("button", { name: rx(s) }).first().click();
  await settle(page);
}

// ---------- anonymous: sign-in ----------
async function anon() {
  const page = await newCtx(browser, { width: vp });
  await page.goto(B + "/");
  await settle(page);
  for (const lang of ["en", "hi"]) {
    if (lang === "hi") await toggleLang(page);
    await shot(page, N("A0", "sign-in", lang), "Sign-in, empty", { role: "none" });
    await step("signin-missing-" + lang, async () => {
      await page.locator('form button[type="submit"]').click();
      await settle(page, 600);
      await shot(page, N("A0", "sign-in-missing", lang), "Submit with empty fields", { role: "none" });
    });
    await step("signin-wrong-" + lang, async () => {
      await page.getByRole("textbox").first().fill("nobody");
      await page.locator('input[type="password"]').fill("wrong-password");
      await page.locator('form button[type="submit"]').click();
      await settle(page, 2000);
      await shot(page, N("A0", "sign-in-wrong-password", lang), "Wrong password (real 401 from the API)", { role: "none" });
    });
  }
}

// ---------- hari (ADMIN) ----------
async function hariPages(page, lang) {
  const R = { role: "ADMIN (hari)" };
  await step("A1", async () => {
    await go(page, "/upload");
    await shot(page, N("A1", "upload", lang), "Form and the real upload list from the seed", R);
    await page.locator('main button[type="submit"], main form button').last().click().catch(() => {});
    await settle(page, 800);
    await shot(page, N("A1", "upload-nothing-chosen", lang), "Submit with no case and no file", R);
  });
  await step("A2", async () => {
    await go(page, "/matching");
    await shot(page, N("A2", "matching", lang), "Last run from the seed", R);
  });
  await step("A7", async () => {
    await go(page, "/thresholds");
    await shot(page, N("A7", "thresholds", lang), "Match settings (ADMIN proposes)", R);
    const inputs = page.locator("main input[type=number], main input");
    if ((await inputs.count()) >= 2) {
      await inputs.nth(0).fill("60");
      await btn(page, await T(page, "thresholds.save", lang)).click();
      await settle(page, 800);
      await shot(page, N("A7", "thresholds-invalid", lang), "Strong match set to 60, below the allowed 70", R);
    }
  });
  await step("A4-changes", async () => {
    await go(page, "/approvals");
    await shot(page, N("A4", "approvals-changes", lang), "Changes tab (ADMIN sees only this tab); 44 approved seed changes and 1 waiting", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A4", "approvals-change-detail", lang), "Change detail", R);
  });
  await step("A5", async () => {
    await go(page, "/users");
    await shot(page, N("A5", "users-list", lang), "User list (ADMIN, with Add user)", R);
    await btn(page, await T(page, "users.add", lang)).click();
    await settle(page);
    await shot(page, N("A5", "user-form-new", lang), "Add user form", R);
    await btn(page, await T(page, "users.save", lang)).click();
    await settle(page, 800);
    await shot(page, N("A5", "user-form-new-errors", lang), "Add user form, saved empty", R);
    await btn(page, await T(page, "state.backToList", lang)).click();
    await settle(page);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).nth(1).click();
    await settle(page);
    await shot(page, N("A5", "user-form-edit", lang), "Edit user form (second user)", R);
  });
  await step("A6", async () => {
    await go(page, "/audit");
    await shot(page, N("A6", "audit", lang), "Activity log as ADMIN", R);
  });
  await step("A8-admin", async () => {
    await go(page, "/graph");
    await shot(page, N("A8", "graph-not-available", lang), "ADMIN opens /graph: plain not-available state, no API call", R);
    await go(page, "/review");
    await shot(page, N("A3", "review-not-available", lang), "ADMIN opens /review (no menu item)", R);
  });
}

// ---------- meena (SENIOR) ----------
async function meenaPages(page, lang) {
  const R = { role: "SENIOR (meena)" };
  await step("A3-waiting", async () => {
    await go(page, "/review");
    await shot(page, N("A3", "review-waiting", lang), "Review queue, Waiting filter (28 real links)", R);
  });
  await step("A3-filter-empty", async () => {
    await go(page, "/review");
    await page.locator("select").first().selectOption({ index: 5 }).catch(() => {});
    await settle(page);
    await shot(page, N("A3", "review-filter-empty", lang), "Type filter with no match", R);
  });
  await step("A3-old", async () => {
    await go(page, "/review");
    await page.getByRole("checkbox").first().check().catch(async () => {
      await page.getByText(await T(page, "queue.filter.waitingLong", lang)).first().click();
    });
    await settle(page);
    await shot(page, N("A3", "review-waiting-over-7-days", lang), "Waiting more than 7 days (empty: all seed links are new)", R);
  });
  await step("A3-rejected", async () => {
    await go(page, "/review");
    await filterBtn(page, lang, "queue.filter.rejected");
    await shot(page, N("A3c", "review-rejected", lang), "Rejected filter (2 real rejections made in the app)", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A3d", "review-rejected-detail", lang), "Rejected link detail with history", R);
    const re = btn(page, await T(page, "queue.reopen.button", lang));
    await re.click();
    await settle(page, 800);
    await shot(page, N("A3d", "review-reopen-check", lang), "Reopen, second step (not confirmed)", R);
  });
  await step("A3-undone", async () => {
    await go(page, "/review");
    await filterBtn(page, lang, "queue.filter.undone");
    await shot(page, N("A3c", "review-undone", lang), "Undone filter (1 real undo made in the app)", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A3d", "review-undone-detail", lang), "Undone link detail with history", R);
  });
  await step("A3-detail", async () => {
    await go(page, "/review");
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).nth(0).click();
    await settle(page, 2500);
    await shot(page, N("A3b", "link-detail", lang), "Link detail, More detail open by default", R);
    await btn(page, await T(page, "queue.reject", lang)).click();
    await settle(page, 800);
    await shot(page, N("A3b", "reject-check", lang), "Reject, second step (not confirmed)", R);
  });
  await step("A4-access", async () => {
    await go(page, "/approvals");
    await shot(page, N("A4", "approvals-access", lang), "Access requests tab, 2 real waiting requests (one with a 330-character reason)", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A4", "approvals-access-detail", lang), "Access request detail", R);
    await btn(page, await T(page, "approvals.access.approve", lang)).click();
    await settle(page, 800);
    await shot(page, N("A4", "approvals-access-approve-check", lang), "Approve, second step (not confirmed)", R);
  });
  await step("A4-changes", async () => {
    await go(page, "/approvals");
    await page.getByRole("button", { name: rx((await T(page, "approvals.tab.changes", lang))) }).first().click();
    await settle(page);
    await shot(page, N("A4", "approvals-changes", lang), "Changes tab with 1 waiting change", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A4a", "approvals-change-detail", lang), "Change to approve, old and new value", R);
    await btn(page, await T(page, "approvals.approve.button", lang).catch(() => "Approve this change")).click().catch(() => {});
    await settle(page, 800);
    await shot(page, N("A4a", "approvals-change-approve-check", lang), "Approve this change, second step (not confirmed)", R);
  });
  await step("A5", async () => {
    await go(page, "/users");
    await shot(page, N("A5", "users-list", lang), "User list as SENIOR (read only)", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A5", "user-detail-readonly", lang), "User detail as SENIOR", R);
  });
  await step("A6", async () => {
    await go(page, "/audit");
    await shot(page, N("A6", "audit", lang), "Activity log, real chain written by the seed and this session", R);
  });
  await step("A7", async () => {
    await go(page, "/thresholds");
    await shot(page, N("A7", "thresholds", lang), "Match settings as SENIOR", R);
  });
  await step("A8", async () => {
    await go(page, "/graph");
    await shot(page, N("A8", "graph-search", lang), "Search form", R);
    await page.locator("input").first().fill("zzzzqq");
    await btn(page, await T(page, "graphPage.show", lang)).click();
    await settle(page, 2000);
    await shot(page, N("A8", "graph-nothing-found", lang), "Search with no result", R);
    await page.locator("input").first().fill("Irfan");
    await btn(page, await T(page, "graphPage.show", lang)).click();
    await settle(page, 2500);
    await shot(page, N("A8", "graph-matches", lang), "Search results (English and Hindi spellings of one name)", R);
    await page.locator("input").first().fill("90000 14471");
    await btn(page, await T(page, "graphPage.show", lang)).click();
    await settle(page, 2500);
    await page.getByRole("button", { name: await T(page, "graphPage.showRow", lang) }).first().click({ timeout: 2500 }).catch(() => {});
    await settle(page, 3500);
    await shot(page, N("A8", "graph-picture", lang), "Network picture: phone 90000 14471 (5 items, possible and restricted links)", R);
    await btn(page, await T(page, "graph.showList", lang)).click();
    await settle(page);
    await shot(page, N("A8", "graph-list", lang), "Same network as a list", R);
    await page.getByRole("button", { name: await T(page, "nav.openRow", lang) }).first().click();
    await settle(page);
    await shot(page, N("A8", "graph-list-selected", lang), "List view, one item selected", R);
    await btn(page, await T(page, "graphPage.seeWhy", lang)).click();
    await settle(page, 2500);
    await shot(page, N("A8", "graph-link-panel", lang), "Why linked panel opened from the graph", R);
  });
}

async function session(user, fn) {
  for (const lang of ["en", "hi"]) {
    const page = await newCtx(browser, { width: vp });
    await login(page, user);
    if (lang === "hi") await toggleLang(page);
    await fn(page, lang);
    await page.context().close();
  }
}

if (only.includes("hari")) await session("hari", hariPages);
if (only.includes("meena")) await session("meena", meenaPages);
if (only.includes("anon")) await anon();
save(`${process.env.SHOTS_JSON ?? "manifest"}-${vp}.json`);
await browser.close();
