/* global document, getComputedStyle, console */
import {
  chromium,
  newCtx,
  login,
  go,
  settle,
  T,
  rx,
  step,
  toggleLang,
  save,
  manifest,
  B,
  OUT,
} from "./lib.mjs";

const browser = await chromium.launch();

function lum(c) {
  const v = c.map((x) => {
    const s = x / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
}
const ratio = (a, b) => {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};

/** Press Tab until the focused element passes `test` (run in the page); returns false when never reached. */
async function tabTo(page, test, arg) {
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.mouse.click(1, 1).catch(() => {});
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press("Tab");
    const hit = await page.evaluate(
      ([src, a]) =>
        new Function("el", "a", "return (" + src + ")(el, a)")(document.activeElement, a),
      [test, arg],
    );
    if (hit) return true;
  }
  return false;
}

async function ringInfo(page) {
  return page.evaluate(() => {
    const el = document.activeElement;
    const cs = getComputedStyle(el);
    const rgb = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const bgOf = (e) => {
      for (let n = e; n; n = n.parentElement) {
        const m = getComputedStyle(n).backgroundColor.match(/[\d.]+/g) || [];
        if (m.length >= 3 && !(m.length === 4 && Number(m[3]) === 0))
          return m.slice(0, 3).map(Number);
      }
      return [255, 255, 255];
    };
    return {
      outlineStyle: cs.outlineStyle,
      outlineWidth: cs.outlineWidth,
      offset: cs.outlineOffset,
      outlineColor: rgb(cs.outlineColor),
      inside: bgOf(el),
      outside: bgOf(el.parentElement),
    };
  });
}

async function capture(page, name, note, meta) {
  await settle(page, 500);
  const r = await ringInfo(page);
  const visible = r.outlineStyle !== "none" && parseFloat(r.outlineWidth) > 0;
  const c1 = ratio(r.outlineColor, r.inside);
  const c2 = ratio(r.outlineColor, r.outside);
  const file = name + ".png";
  await page.screenshot({ path: `${OUT}/${file}` });
  const info = `ring ${r.outlineWidth} ${r.outlineStyle}, offset ${r.offset}; contrast ring/inside ${c1.toFixed(1)}:1, ring/outside ${c2.toFixed(1)}:1`;
  manifest.push({
    file,
    note: note + " (" + info + ")",
    ...meta,
    scrollWidth: 0,
    innerWidth: 0,
    hscroll: false,
    overflowEl: "",
    fonts: "",
    bodyFont: "",
    focus: true,
    ringVisible: visible,
  });
  console.log("FOCUS", file, info, visible ? "" : "NO RING");
}

const isSubmit = `(el) => el.tagName === "BUTTON" && el.type === "submit"`;
const hasText = `(el, a) => el.tagName === "BUTTON" && new RegExp(a).test(el.textContent)`;
const sel = `(el, a) => el.matches(a)`;

for (const lang of ["en", "hi"]) {
  // sign-in button
  await step("f-signin-" + lang, async () => {
    const page = await newCtx(browser, { width: 1280 });
    await page.goto(B + "/");
    await settle(page);
    if (lang === "hi") await toggleLang(page);
    if (!(await tabTo(page, isSubmit))) throw new Error("no submit");
    await capture(page, `F-sign-in-button-${lang}`, "Keyboard focus on the sign-in button", {
      role: "none",
    });
    await page.context().close();
  });

  // desktop, meena
  const page = await newCtx(browser, { width: 1280 });
  await login(page, "meena");
  if (lang === "hi") await toggleLang(page);
  const R = { role: "SENIOR (meena)" };
  const open = await T(page, "nav.openRow", lang);
  await step("f-menu-item-" + lang, async () => {
    if (!(await tabTo(page, sel, ".tx-sidenav__item"))) throw new Error("none");
    await capture(page, `F-menu-item-${lang}`, "Keyboard focus on a menu item", R);
  });
  await step("f-filter-" + lang, async () => {
    await go(page, "/review");
    if (
      !(await tabTo(
        page,
        `(el)=> el.tagName==="BUTTON" && el.getAttribute("aria-pressed")==="true"`,
      ))
    )
      throw new Error("none");
    await page.keyboard.press("Tab");
    await capture(
      page,
      `F-filter-button-${lang}`,
      "Keyboard focus on a status filter button (Rejected)",
      R,
    );
  });
  await step("f-open-" + lang, async () => {
    if (!(await tabTo(page, hasText, "^\\s*" + open + "\\s*$"))) throw new Error("none");
    await capture(page, `F-queue-row-open-${lang}`, "Keyboard focus on a queue row Open button", R);
  });
  await step("f-reject-" + lang, async () => {
    await page
      .getByRole("button", { name: await T(page, "nav.openRow", lang) })
      .first()
      .click();
    await settle(page, 2000);
    await page
      .getByRole("button", { name: rx(await T(page, "queue.reject", lang)) })
      .first()
      .click();
    await settle(page, 800);
    if (!(await tabTo(page, `(el)=> el.tagName==="TEXTAREA"`))) throw new Error("no textarea");
    await capture(
      page,
      `F-reject-step-field-${lang}`,
      "Reject second step: focus on the reason field",
      R,
    );
    await page.keyboard.type("x");
    if (!(await tabTo(page, hasText, rx0(await T(page, "queue.reject.yes", lang)))))
      throw new Error("no yes");
    await capture(
      page,
      `F-reject-step-button-${lang}`,
      "Reject second step: focus on the primary button",
      R,
    );
  });
  await step("f-graph-" + lang, async () => {
    await go(page, "/graph");
    await page.locator("input").first().fill("90000 14471");
    await page
      .getByRole("button", { name: rx(await T(page, "graphPage.show", lang)) })
      .first()
      .click();
    await settle(page, 3500);
    const ok = await tabTo(page, `(el)=> !!el.closest("svg") && el.tagName!=="svg"`);
    if (!ok) throw new Error("no graph node focusable");
    await capture(page, `F-graph-node-${lang}`, "Keyboard focus on a graph node", R);
  });
  await step("f-field-" + lang, async () => {
    await page.context().close();
    const p2 = await newCtx(browser, { width: 1280 });
    await login(p2, "hari");
    if (lang === "hi") await toggleLang(p2);
    await go(p2, "/users");
    await p2
      .getByRole("button", { name: await T(p2, "users.add", lang) })
      .first()
      .click();
    await settle(p2);
    if (!(await tabTo(p2, `(el)=> el.tagName==="INPUT"`))) throw new Error("no input");
    await capture(p2, `F-form-field-${lang}`, "Add user form: focus on the first field", {
      role: "ADMIN (hari)",
    });
    if (
      !(await tabTo(
        p2,
        `(el)=> el.tagName==="BUTTON" && el.getAttribute("data-variant")==="primary"`,
      ))
    )
      throw new Error("no primary");
    await capture(p2, `F-primary-button-${lang}`, "Add user form: focus on the primary button", {
      role: "ADMIN (hari)",
    });
    await p2.context().close();
  });

  // mobile menu button
  await step("f-menu-mobile-" + lang, async () => {
    const m = await newCtx(browser, { width: 375, height: 812 });
    await login(m, "meena");
    if (lang === "hi") await toggleLang(m);
    const label = await T(m, "shell.menu", lang);
    if (!(await tabTo(m, hasText, "^\\s*" + label + "\\s*$"))) throw new Error("no menu button");
    await capture(
      m,
      `F-menu-button-${lang}-mobile`,
      "375 wide: keyboard focus on the Menu button",
      { role: "SENIOR (meena)" },
    );
    await m.keyboard.press("Enter");
    await settle(m, 500);
    await m.screenshot({ path: `${OUT}/F-menu-open-${lang}-mobile.png` });
    manifest.push({
      file: `F-menu-open-${lang}-mobile.png`,
      note: "375 wide: menu opened with Enter",
      role: "SENIOR (meena)",
      scrollWidth: 0,
      innerWidth: 0,
      hscroll: false,
      overflowEl: "",
      fonts: "",
      bodyFont: "",
      focus: true,
    });
    await m.context().close();
  });
}
function rx0(s) {
  return "^\\s*" + s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*$";
}
save("manifest-focus.json");
await browser.close();
