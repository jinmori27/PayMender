import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const configDirectory = fileURLToPath(new URL(".", import.meta.url));
const python = process.env.PAYMENDER_PYTHON
  ?? (process.platform === "win32"
    ? fileURLToPath(new URL("../.venv/Scripts/python.exe", import.meta.url))
    : "python");
const systemChrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 120_000,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8011",
    trace: "retain-on-failure",
    launchOptions: process.platform === "win32" ? { executablePath: systemChrome } : {},
  },
  webServer: {
    command: `"${python}" -m uvicorn app.main:app --app-dir "${configDirectory}../backend" --host 127.0.0.1 --port 8011`,
    url: "http://127.0.0.1:8011/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      DEMO_MODE: "true",
      DATABASE_URL: "sqlite:///./paymender-e2e.sqlite3",
      OPERATOR_API_TOKEN: "test_operator_token_32_bytes_long",
      RAZORPAY_WEBHOOK_SECRET: "test_webhook_secret",
      RAZORPAY_KEY_ID: "",
      RAZORPAY_KEY_SECRET: "",
      GEMINI_API_KEY: "",
    },
  },
});
