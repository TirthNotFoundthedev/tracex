/* global console */
import { chromium, newCtx, login, go, step } from "./lib.mjs";

const browser = await chromium.launch();
const longEn =
  "The two phone numbers differ by two digits and the names on the SIM records belong to different people. I read the source lines in both cases and found no other shared detail, so I do not think these are the same person.";
const longHi =
  "दोनों फ़ोन नंबर दो अंकों से अलग हैं और सिम रिकॉर्ड में नाम अलग-अलग लोगों के हैं। मैंने दोनों मामलों की स्रोत पंक्तियाँ पढ़ीं और कोई और साझा जानकारी नहीं मिली, इसलिए मुझे नहीं लगता कि ये एक ही व्यक्ति हैं।";

// meena: reject two possible links, undo one strong link
{
  const page = await newCtx(browser);
  await login(page, "meena");
  for (const reason of [longEn, longHi]) {
    await step("reject", async () => {
      await go(page, "/review");
      await page.getByRole("button", { name: "Open" }).nth(4).click();
      await page.waitForTimeout(2500);
      await page.getByRole("button", { name: "Reject this link" }).click();
      await page.waitForTimeout(800);
      await page.locator("textarea").fill(reason);
      await page.getByRole("button", { name: "Yes, reject" }).click();
      await page.waitForTimeout(2500);
      console.log("rejected one");
    });
  }
  await step("undo", async () => {
    await go(page, "/graph");
    await page.locator("input").first().fill("Irfan");
    await page.getByRole("button", { name: "Show network" }).click();
    await page.waitForTimeout(3000);
    await page.getByRole("button", { name: "Show this network" }).first().click();
    await page.waitForTimeout(3000);
    await page.getByRole("button", { name: "Show as list" }).click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: "Open" }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: "See why they are linked" }).click();
    await page.waitForTimeout(2500);
    await page.getByRole("button", { name: "Undo this link" }).first().click();
    await page.waitForTimeout(800);
    await page.locator("textarea").fill(longEn);
    await page.getByRole("button", { name: "Yes, undo" }).click();
    await page.waitForTimeout(2500);
    console.log("undone one");
  });
}

// hari: propose a role change
{
  const page = await newCtx(browser);
  await login(page, "hari");
  await step("propose", async () => {
    await go(page, "/users");
    await page.getByRole("button", { name: "Open" }).first().click();
    await page.waitForTimeout(1500);
    await page.locator("select").first().selectOption({ index: 3 });
    await page.getByRole("button", { name: "Save user" }).click();
    await page.waitForTimeout(2000);
    console.log((await page.locator("main").innerText()).slice(0, 800));
  });
}
await browser.close();
