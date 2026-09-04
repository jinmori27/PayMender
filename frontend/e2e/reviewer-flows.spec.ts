import { expect, test } from "@playwright/test";

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
