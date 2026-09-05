import { expect, test, type Page } from "@playwright/test";

const token = "test_operator_token_32_bytes_long";
const headers = { "X-Operator-Token": token };
const viewports = [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
];

async function unlock(page: Page) {
  await page.goto("/");
  await page.getByLabel("Operator token").fill(token);
  await page.getByRole("button", { name: "Unlock command center" }).click();
  await expect(page.getByRole("button", { name: "Refresh portfolio" })).toBeEnabled();
}

async function checkLayout(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  const clipped = await page.locator("h1, h2, h3, .reasoning, .case-identity, .proposal-banner, .kpi-card, .failure-card").evaluateAll(
    (elements) => elements.filter((element) => element.scrollWidth > element.clientWidth + 1).map((element) => element.className || element.tagName),
  );
  expect(clipped).toEqual([]);
}

test("all product screens fit mobile tablet laptop and desktop without console errors", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await request.post("/api/demo/reset", { headers });
  await unlock(page);
  await page.getByRole("button", { name: "Evaluation", exact: true }).click();
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "Dismiss notification" }).click();

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.getByRole("button", { name: "Command center", exact: true }).click();
    await page.getByRole("button", { name: /Aarav Mehta/ }).click();
    await expect(page.getByRole("button", { name: "Approve action" })).toBeEnabled();
    await checkLayout(page);
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`command-${viewport.width}.png`), fullPage: true });
    await page.locator(".inspector").screenshot({ path: testInfo.outputPath(`inspector-${viewport.width}.png`) });
    for (const [label, slug] of [["Evaluation", "evaluation"], ["Reliability lab", "lab"], ["How it works", "guide"]]) {
      await page.getByRole("button", { name: label, exact: true }).click();
      await expect(page.locator("#main-content")).toBeFocused();
      await checkLayout(page);
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath(`${slug}-${viewport.width}.png`), fullPage: true });
    }
  }
  await page.getByRole("button", { name: "Evaluation", exact: true }).click();
  await page.setViewportSize(viewports[0]);
  const tableRegion = page.getByRole("region", { name: "Evaluation metric comparison" });
  await tableRegion.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => tableRegion.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Lock command center" }).click();
  await page.screenshot({ path: testInfo.outputPath("unlock-375.png"), fullPage: true });
  expect(errors).toEqual([]);
});

test("loading and failure feedback remain truthful and keyboard accessible", async ({ page, request }) => {
  await request.post("/api/demo/reset", { headers });
  await page.goto("/");
  await page.route("**/api/operator/session", (route) => route.fulfill({ status: 401, json: { detail: "Operator token was not accepted." } }));
  await page.getByLabel("Operator token").fill("invalid_token_long_enough_for_form");
  await page.getByRole("button", { name: "Unlock command center" }).click();
  await expect(page.getByRole("alert")).toContainText("Operator token was not accepted.");
  await expect(page.getByLabel("Operator token")).toHaveAttribute("aria-invalid", "true");
  await page.unroute("**/api/operator/session");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/metrics", async (route) => { await gate; await route.continue(); });
  await page.getByLabel("Operator token").fill(token);
  await page.getByRole("button", { name: "Unlock command center" }).click();
  await expect(page.locator(".kpi-card[aria-busy=true]")).toHaveCount(4);
  await expect(page.locator(".kpi-grid")).not.toContainText("₹0");
  release();
  await expect(page.getByRole("button", { name: "Refresh portfolio" })).toBeEnabled();
  await page.getByRole("link", { name: "Skip to workspace" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page.getByRole("button", { name: /Aarav Mehta/ }).click();
  await page.route("**/api/cases/*/approve", (route) => route.fulfill({ status: 503, json: { detail: "Provider unavailable. Please retry." } }));
  await page.getByRole("button", { name: "Approve action" }).click();
  await expect(page.locator(".toast.error")).toContainText("Provider unavailable.");
  await expect(page.locator(".toast.error")).toHaveAttribute("role", "alert");
  await page.getByRole("button", { name: "Dismiss notification" }).click();
  await expect(page.locator(".toast")).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByRole("button", { name: "Approve action" })).toBeEnabled();
});
