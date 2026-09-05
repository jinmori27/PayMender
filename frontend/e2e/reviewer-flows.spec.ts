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
  await expect(page.getByText("Link ready · payment unconfirmed", { exact: true })).toBeVisible();
  await expect(page.getByText("Payment confirmed", { exact: true })).toHaveCount(0);
  await page.route("**/api/cases/*", async (route) => {
    const response = await route.fetch();
    const detail = await response.json();
    await route.fulfill({ json: { ...detail, recovered_amount_paise: detail.amount_paise, status: "charged" } });
  });
  await page.getByRole("button", { name: "Refresh portfolio" }).click();
  await expect(page.getByText("Payment confirmed", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open test link" })).toHaveCount(0);
});

test("contact-capped case exposes no approval action", async ({ page }) => {
  await page.getByRole("button", { name: /Neil Verma/ }).click();
  await expect(page.getByRole("heading", { name: "Stop contact" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve action" })).toHaveCount(0);
  await expect(page.getByText("Contact stopped", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Message previews", exact: true }).click();
  await expect(page.getByText("Contact is stopped for this case. No outreach preview is actionable.")).toBeVisible();
  await expect(page.getByText("English preview", { exact: true })).toHaveCount(0);
});

test("evaluation discloses mean and deviation for every metric", async ({ page }, testInfo) => {
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
  await page.screenshot({ path: testInfo.outputPath("evaluation.png"), fullPage: true });
});

test("queue search, filters and sorting preserve the reviewed case", async ({ page, request }) => {
  const cases = await (await request.get("/api/cases", { headers: operatorHeaders })).json();
  const queue = page.getByRole("region", { name: "Recovery queue" });
  const snapshot = page.getByRole("region", { name: "Portfolio snapshot" });
  await expect(snapshot).toContainText(`${cases.length} cases in this run`);
  await expect(snapshot).toContainText("Current case statuses, not a recovery-rate forecast.");
  const statuses = [...new Set(cases.map((item: { status: string }) => item.status))];
  for (const status of statuses) {
    const count = cases.filter((item: { status: string }) => item.status === status).length;
    await expect(snapshot.locator(`[data-status="${status}"]`)).toContainText(`${count}`);
  }
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
  await page.route("**/api/cases", (route) => route.fulfill({ json: [] }));
  await page.getByRole("button", { name: "Refresh portfolio" }).click();
  await expect(snapshot).toContainText("0 cases in this run");
  await expect(snapshot).toContainText("No cases yet.");
  await expect(snapshot.locator(".snapshot-track")).toHaveCount(0);
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
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 1280, height: 720 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByLabel("Search recovery cases")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`command-${viewport.width}.png`), fullPage: true });
  }
  await page.getByRole("button", { name: "Lock command center" }).click();
  await expect(page.getByLabel("Operator token")).toHaveValue("");
  const placeholder = await page.getByLabel("Operator token").evaluate((input) => {
    const style = getComputedStyle(input, "::placeholder");
    return { color: style.color, opacity: style.opacity };
  });
  expect(placeholder).toEqual({ color: "rgb(98, 107, 126)", opacity: "1" });
  await page.screenshot({ path: testInfo.outputPath("unlock-390.png"), fullPage: true });
});

test("workflow guide and case views explain the recovery boundaries", async ({ page }, testInfo) => {
  await page.getByRole("button", { name: /Aarav Mehta/ }).click();
  await page.getByRole("button", { name: "Model evidence", exact: true }).click();
  await expect(page.getByRole("region", { name: "Model evidence" })).toContainText("Simulator-trained estimates, not guaranteed recovery.");
  await page.getByRole("button", { name: "Message previews", exact: true }).click();
  await expect(page.getByRole("region", { name: "Customer message previews" })).toContainText("Approval does not send these drafts.");
  await page.getByRole("button", { name: /Neil Verma/ }).click();
  await expect(page.getByRole("button", { name: "Decision", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "How it works", exact: true }).click();
  await expect(page.getByRole("heading", { name: "How recovery works" })).toBeVisible();
  const stages = page.getByRole("navigation", { name: "Recovery workflow stages" });
  for (const stage of ["Detect the failed payment", "Compare recovery options", "Apply the safety rules", "Review and approve", "Confirm what recovered"]) {
    await stages.getByRole("button", { name: stage }).click();
    await expect(page.getByRole("heading", { name: stage, exact: true })).toBeVisible();
  }
  await expect(page.getByText("Creating a link does not mean the customer paid.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "You’re in synthetic demo mode" })).toBeVisible();
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`workflow-${viewport.width}.png`), fullPage: true });
  }
  await page.getByRole("button", { name: "Review a case", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Neil Verma" })).toBeVisible();
});

test("all Reliability Lab controls return traceable contained evidence", async ({ page }, testInfo) => {
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
  await page.screenshot({ path: testInfo.outputPath("reliability.png"), fullPage: true });
});
