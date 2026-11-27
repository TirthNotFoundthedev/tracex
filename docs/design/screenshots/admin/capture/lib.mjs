/* global process, console, history, window, PopStateEvent, document, getComputedStyle */
import { chromium } from "playwright";
import fs from "node:fs";

export const B = process.env.SHOTS_BASE ?? "http://localhost:19173";
export const OUT = process.env.SHOTS_OUT;
export const PW = (u) => "dev-only-seed-" + u;
export const manifest = [];
export const failures = [];

export async function newCtx(browser, { width = 1280, height = 900, dpr = 1 } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dpr });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERR", e.message));
  return page;
}

export async function T(page, key, lang, params) {
  return page.evaluate(
    ([k, l, p]) => import("/src/i18n/index.ts").then((m) => m.t(k, l, p)),
    [key, lang, params],
  );
}

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
export const rx = (s) => new RegExp(esc(s));

export async function login(page, user) {
  await page.goto(B + "/");
  await page.getByRole("textbox").first().fill(user);
  await page.locator('input[type="password"]').fill(PW(user));
  await page.locator('form button[type="submit"]').click();
  await page.waitForSelector("main[data-page], main.admin-main", { timeout: 15000 });
  await settle(page);
}

export async function go(page, p) {
  await page.evaluate((p) => {
    history.pushState({}, "", p);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, p);
  await settle(page);
}

export async function settle(page, ms = 1500) {
  await page.waitForTimeout(ms);
  for (let i = 0; i < 20; i++) {
    const busy = await page.locator('[role="status"], [aria-busy="true"]').count();
    if (!busy) break;
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(300);
}

export async function toggleLang(page) {
  await page
    .locator("header button")
    .filter({ hasText: /हिन्दी|English/ })
    .first()
    .click();
  await settle(page, 800);
}

export async function checks(page) {
  return page.evaluate(async () => {
    await document.fonts.ready;
    const fonts = [...document.fonts]
      .filter((f) => f.status !== "unloaded")
      .map((f) => `${f.family} ${f.weight} ${f.status}`);
    const loaded = [...document.fonts]
      .filter((f) => f.status === "loaded")
      .map((f) => `${f.family} ${f.weight}`);
    const de = document.documentElement;
    const vw = window.innerWidth;
    let overflowEl = "";
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > vw + 1 && getComputedStyle(el).position !== "fixed") {
        // inside a horizontally scrollable wrapper does not count as page overflow
        let p = el.parentElement,
          scroller = false;
        while (p && p !== document.body) {
          const o = getComputedStyle(p).overflowX;
          if (o === "auto" || o === "scroll" || o === "hidden") {
            scroller = true;
            break;
          }
          p = p.parentElement;
        }
        if (!scroller) {
          overflowEl = el.tagName + "." + (el.className || "").toString().slice(0, 40);
          break;
        }
      }
    }
    const fam = getComputedStyle(document.body).fontFamily;
    return {
      scrollWidth: de.scrollWidth,
      innerWidth: vw,
      loaded,
      fonts,
      overflowEl,
      bodyFont: fam.slice(0, 80),
    };
  });
}

export async function shot(page, name, note = "", meta = {}) {
  const file = name + ".png";
  const c = await checks(page);
  await page.screenshot({ path: `${OUT}/${file}`, fullPage: true });
  manifest.push({
    file,
    note,
    ...meta,
    scrollWidth: c.scrollWidth,
    innerWidth: c.innerWidth,
    hscroll: c.scrollWidth > c.innerWidth,
    overflowEl: c.overflowEl,
    fonts: c.loaded.join("; "),
    bodyFont: c.bodyFont,
  });
  console.log("SHOT", file, c.scrollWidth + "/" + c.innerWidth, c.overflowEl);
}

export async function step(name, fn) {
  try {
    await fn();
  } catch (e) {
    failures.push(name + ": " + String(e.message).split("\n")[0]);
    console.log("FAIL", name, String(e.message).split("\n")[0]);
  }
}

export function suffix(vp) {
  return vp === 375 ? "-mobile" : "";
}

export function save(file) {
  fs.writeFileSync(file, JSON.stringify({ manifest, failures }, null, 1));
}

export { chromium };
