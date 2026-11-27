import { execFileSync } from "node:child_process";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  metadata: {
    revision: execFileSync("git", ["rev-parse", "HEAD"], {
      encoding: "utf8",
    }).trim(),
  },
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    ["junit", { outputFile: "test-results/results.xml" }],
  ],
  globalTimeout: 120000,
  use: {
    baseURL: "http://127.0.0.1:4394",
    javaScriptEnabled: false,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "npm run build && npm run preview -- --host 127.0.0.1 --port 4394 --ignore-lock",
    url: "http://127.0.0.1:4394",
    reuseExistingServer: false,
  },
});
