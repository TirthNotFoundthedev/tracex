import {
  chromium,
  newCtx,
  login,
  go,
  settle,
  T,
  rx,
  step,
  shot,
  toggleLang,
  save,
} from "./lib.mjs";

const browser = await chromium.launch();
const R = { role: "SENIOR (meena)" };
const btn = (page, text) => page.getByRole("button", { name: rx(text) }).first();

async function graph(page, lang) {
  await go(page, "/graph");
  await page.locator("input").first().fill("90000 14471");
  await btn(page, await T(page, "graphPage.show", lang)).click();
  await settle(page, 3500);
}

for (const mode of ["zoom200", "grayscale"]) {
  for (const lang of ["en", "hi"]) {
    const page = await newCtx(
      browser,
      mode === "zoom200" ? { width: 640, height: 800, dpr: 2 } : { width: 1280 },
    );
    await login(page, "meena");
    if (lang === "hi") await toggleLang(page);
    if (mode === "grayscale") await page.addStyleTag({ content: "html{filter:grayscale(1)}" });
    const meta = { ...R, mode };
    const note =
      mode === "zoom200"
        ? "200 percent zoom: 640 CSS px wide, device scale 2 (same layout as browser zoom 200% at 1280)"
        : "Grayscale filter on the whole page";
    await step("review-" + mode + lang, async () => {
      await go(page, "/review");
      await shot(page, `A3-review-waiting-${lang}-${mode}`, note, meta);
    });
    await step("graph-" + mode + lang, async () => {
      await graph(page, lang);
      await shot(page, `A8-graph-picture-${lang}-${mode}`, note, meta);
    });
    await page.context().close();
  }
}

save("manifest-extras.json");
await browser.close();
