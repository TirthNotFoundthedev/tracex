/* global setTimeout, history, window, PopStateEvent */
import { chromium, newCtx, login, go, settle, step, shot, toggleLang, save } from "./lib.mjs";

const browser = await chromium.launch();
const R = { role: "SENIOR (meena)" };

// loading and no-connection on the real stack (the network is slowed or cut for one request type)
for (const lang of ["en", "hi"]) {
  const page = await newCtx(browser, { width: 1280 });
  await login(page, "meena");
  if (lang === "hi") await toggleLang(page);
  await step("loading-" + lang, async () => {
    await go(page, "/audit");
    await page.route("**/api/review-queue**", async (route) => {
      await new Promise((r) => setTimeout(r, 6000));
      await route.continue();
    });
    await page.evaluate(() => {
      history.pushState({}, "", "/review");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await page.waitForTimeout(1200);
    await shot(
      page,
      `A3-review-loading-${lang}`,
      "Loading state: the real API answer was held back 6 seconds with a test proxy",
      R,
    );
    await page.waitForTimeout(6500);
    await page.unroute("**/api/review-queue**");
  });
  await step("noconn-" + lang, async () => {
    await page.route("**/api/review-queue**", (route) => route.abort("connectionrefused"));
    await go(page, "/audit");
    await go(page, "/review");
    await settle(page, 2500);
    await shot(
      page,
      `A3-review-no-connection-${lang}`,
      "No-connection state: the request was cut by the test browser, the stack was up",
      R,
    );
  });
  await page.context().close();
}
save("manifest-extras2.json");
await browser.close();
