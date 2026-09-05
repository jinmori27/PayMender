import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const operatorToken = "test_operator_token_32_bytes_long";
const operatorHeaders = { "X-Operator-Token": operatorToken };

test.beforeEach(async ({ page, request }) => {
  const reset = await request.post("/api/demo/reset", { headers: operatorHeaders });
  expect(reset.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByLabel("Operator token").fill(operatorToken);
  await page.getByRole("button", { name: "Unlock command center" }).click();
  await expect(page.getByRole("heading", { name: "Recover failed subscriptions safely." })).toBeVisible();
});

test("operator can approve one gated recovery link", async ({ page }) => {
  await page.getByRole("button", { name: /Aarav Mehta/ }).click();
  await expect(page.getByRole("heading", { name: "Aarav Mehta" })).toBeVisible();
  await page.getByRole("button", { name: "Approve action" }).click();
  await expect(page.getByText("Recovery link ready")).toBeVisible();
  await expect(page.getByText("No notification sent.", { exact: false })).toBeVisible();
});

test("contact-capped case exposes no approval action", async ({ page }) => {
  await page.getByRole("button", { name: /Neil Verma/ }).click();
  await expect(page.getByRole("heading", { name: "Stop contact" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve action" })).toHaveCount(0);
});

test("evaluation discloses mean and deviation for every metric", async ({ page }) => {
  await page.getByRole("button", { name: "Evaluation" }).click();
  await page.getByRole("button", { name: "Run evaluation" }).click();
  const table = page.getByRole("table");
  await expect(table).toBeVisible({ timeout: 60_000 });
  await expect(table.getByRole("columnheader", { name: "Unsafe blocked" })).toBeVisible();
  await expect(table.getByRole("row", { name: /PayMender/ })).toContainText("±");
  for (const card of await page.locator(".eval-kpis .kpi-card").all()) {
    await expect(card).toContainText("±");
  }
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export evaluation" }).click();
  const download = await downloadPromise;
  const exported = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(exported.evidence_source).toBe("synthetic");
  expect(exported.evaluation.policies).toHaveLength(4);
  expect(exported.evaluation.policies[0]).toHaveProperty("recovery_rate_std");
});

test("queue search, filters and sorting preserve the reviewed case", async ({ page, request }) => {
  const cases = await (await request.get("/api/cases", { headers: operatorHeaders })).json();
  const queue = page.getByRole("region", { name: "Recovery queue" });
  await page.getByLabel("Search recovery cases").fill("  aarav  ");
  await expect(queue.locator(".case-card")).toHaveCount(1);
  await queue.getByRole("button", { name: /Aarav Mehta/ }).click();
  await expect(page.getByRole("heading", { name: "Aarav Mehta" })).toBeVisible();
  await page.getByLabel("Search recovery cases").fill("no-such-subscription");
  await expect(page.getByText("No matching cases")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(queue.locator(".case-card")).toHaveCount(cases.length);
  await page.getByLabel("Status", { exact: true }).selectOption("halted");
  await expect(queue.locator(".case-card")).toHaveCount(cases.filter((item: { status: string }) => item.status === "halted").length);
  await page.getByLabel("Status", { exact: true }).selectOption("all");
  await page.getByLabel("Sort by").selectOption("amount");
  const highest = cases.sort((a: { amount_paise: number }, b: { amount_paise: number }) => b.amount_paise - a.amount_paise)[0];
  await expect(queue.locator(".case-card").first()).toContainText(highest.customer_name);
  await page.getByLabel("Audit scope").selectOption("case");
  await expect(page.locator(".audit-context").first()).toContainText(cases.find((item: { customer_name: string }) => item.customer_name === "Aarav Mehta").subscription_id);
});

test("slow case responses cannot restore stale approval controls", async ({ page, request }) => {
  const cases = await (await request.get("/api/cases", { headers: operatorHeaders })).json();
  const aarav = cases.find((item: { customer_name: string }) => item.customer_name === "Aarav Mehta");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/api/cases/${aarav.id}`, async (route) => {
    await gate;
    await route.continue();
  });
  await page.getByRole("button", { name: /Aarav Mehta/ }).click();
  await expect(page.getByRole("heading", { name: "Loading case details" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve action" })).toHaveCount(0);
  await page.getByRole("button", { name: /Neil Verma/ }).click();
  await expect(page.getByRole("heading", { name: "Neil Verma" })).toBeVisible();
  const delayedResponse = page.waitForResponse(`**/api/cases/${aarav.id}`);
  release();
  await delayedResponse;
  await expect(page.getByRole("heading", { name: "Neil Verma" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve action" })).toHaveCount(0);
});

test("failed refresh blocks approval and recovers without resetting the run", async ({ page }) => {
  await page.getByRole("button", { name: /Aarav Mehta/ }).click();
  await expect(page.getByRole("button", { name: "Approve action" })).toBeEnabled();
  await page.route("**/api/metrics", (route) => route.fulfill({ status: 503, json: { detail: "Temporary connection failure" } }));
  await page.getByRole("button", { name: "Refresh portfolio" }).click();
  await expect(page.getByText("Portfolio could not be refreshed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve action" })).toBeDisabled();
  await page.unroute("**/api/metrics");
  await page.getByRole("button", { name: "Try refresh again" }).click();
  await expect(page.getByRole("button", { name: "Approve action" })).toBeEnabled();
  await expect(page.getByText("Portfolio could not be refreshed")).toHaveCount(0);
});

test("reset requires confirmation before clearing current approvals", async ({ page }) => {
  await page.getByRole("button", { name: /Aarav Mehta/ }).click();
  await page.getByRole("button", { name: "Approve action" }).click();
  await expect(page.getByText("Recovery link ready")).toBeVisible();
  await page.getByRole("button", { name: "Reset demo data" }).click();
  await page.getByRole("button", { name: "Keep current run" }).click();
  await expect(page.getByText("Recovery link ready")).toBeVisible();
  await page.getByRole("button", { name: "Reset demo data" }).click();
  await page.getByRole("button", { name: "Start new run" }).click();
  await expect(page.getByText("Demo data restored. A new evidence run has started.")).toBeVisible();
  await expect(page.getByText("Recovery link ready")).toHaveCount(0);
});

test("reviewer interface fits desktop and mobile", async ({ page }, testInfo) => {
  await expect(page.getByRole("button", { name: "Refresh portfolio" })).toBeEnabled();
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByLabel("Search recovery cases")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`command-${viewport.width}.png`), fullPage: true });
  }
});

test("all Reliability Lab controls return traceable contained evidence", async ({ page }) => {
  await page.getByRole("button", { name: "Reliability lab" }).click();
  const scenarios = [
    ["Concurrent duplicate", /duplicate contained/i],
    ["Gemini quota exhausted", /gemini-quota contained/i],
    ["Razorpay returns 5xx", /razorpay-500 contained/i],
    ["Worker crashes mid-job", /worker-crash contained/i],
  ];
  for (const [buttonName, resultName] of scenarios) {
    await page.getByRole("button", { name: new RegExp(String(buttonName)) }).click();
    await expect(page.getByText(resultName)).toBeVisible();
    await expect(page.getByText("Evidence:", { exact: false })).toBeVisible();
  }
});
