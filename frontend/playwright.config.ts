import { defineConfig, devices } from "@playwright/test";
import fs from "fs";
import os from "os";
import path from "path";

/**
 * If the Playwright-managed headless shell is absent (e.g. disk space prevented
 * its download), fall back to the full Chromium binary that Playwright DID
 * install.  On other platforms, or when the shell is present, return undefined
 * so Playwright uses its default.
 */
function fallbackChromiumPath(): string | undefined {
  if (process.platform !== "win32") return undefined;
  const base = path.join(os.homedir(), "AppData", "Local", "ms-playwright");
  if (!fs.existsSync(base)) return undefined;
  const dirs = fs.readdirSync(base);
  const hasShell = dirs.some((d) => d.startsWith("chromium_headless_shell-"));
  if (hasShell) return undefined; // shell is present; let Playwright use it
  const fullDir = dirs.find((d) => d.startsWith("chromium-"));
  if (!fullDir) return undefined;
  const exe = path.join(base, fullDir, "chrome-win64", "chrome.exe");
  return fs.existsSync(exe) ? exe : undefined;
}

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          executablePath: fallbackChromiumPath(),
        },
      },
    },
  ],
});
